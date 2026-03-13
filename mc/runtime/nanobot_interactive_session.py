"""Nanobot-backed interactive runtime wrapper for backend-owned Live sessions."""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from mc.application.execution.runtime import run_nanobot_task
from mc.cli import _get_bridge
from mc.contexts.interactive.registry import InteractiveSessionRegistry
from mc.contexts.interactive.supervision_types import InteractiveSupervisionEvent
from mc.contexts.interactive.supervisor import InteractiveExecutionSupervisor

EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit", ":q"}


@dataclass(frozen=True)
class NanobotInteractiveSessionConfig:
    """Environment-backed runtime config for a Nanobot Live session."""

    session_id: str
    task_id: str
    agent_name: str
    agent_prompt: str | None = None
    agent_model: str | None = None
    task_prompt: str | None = None
    board_name: str | None = None
    memory_workspace: Path | None = None

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "NanobotInteractiveSessionConfig":
        source = env or os.environ
        session_id = _require_env(source, "MC_INTERACTIVE_SESSION_ID")
        task_id = _require_env(source, "MC_INTERACTIVE_TASK_ID")
        agent_name = _require_env(source, "MC_INTERACTIVE_AGENT_NAME")
        memory_workspace = source.get("MC_INTERACTIVE_MEMORY_WORKSPACE")
        return cls(
            session_id=session_id,
            task_id=task_id,
            agent_name=agent_name,
            agent_prompt=_strip_or_none(source.get("MC_INTERACTIVE_AGENT_PROMPT")),
            agent_model=_strip_or_none(source.get("MC_INTERACTIVE_AGENT_MODEL")),
            task_prompt=_strip_or_none(source.get("MC_INTERACTIVE_TASK_PROMPT")),
            board_name=_strip_or_none(source.get("MC_INTERACTIVE_BOARD_NAME")),
            memory_workspace=Path(memory_workspace) if memory_workspace else None,
        )

    @property
    def initial_task_title(self) -> str:
        title, _description = _split_task_prompt(self.task_prompt)
        return title or f"Interactive step for {self.agent_name}"

    @property
    def initial_task_description(self) -> str | None:
        _title, description = _split_task_prompt(self.task_prompt)
        return description


class NanobotInteractiveSessionRunner:
    """Run a step-owned Nanobot session and keep a simple REPL alive for Live."""

    def __init__(
        self,
        *,
        config: NanobotInteractiveSessionConfig,
        bridge: Any,
        supervisor: InteractiveExecutionSupervisor,
        run_initial_turn: Any = run_nanobot_task,
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
        registration_poll_interval: float = 0.1,
        registration_timeout_seconds: float = 5.0,
        repl_idle_poll_seconds: float = 0.5,
    ) -> None:
        self._config = config
        self._bridge = bridge
        self._supervisor = supervisor
        self._run_initial_turn = run_initial_turn
        self._stdin = stdin or sys.stdin
        self._stdout = stdout or sys.stdout
        self._registration_poll_interval = registration_poll_interval
        self._registration_timeout_seconds = registration_timeout_seconds
        self._repl_idle_poll_seconds = repl_idle_poll_seconds
        self._session_key: str | None = None
        self._loop: Any | None = None

    async def run(self) -> int:
        try:
            await self._wait_for_session_registration()
            self._emit_event("session_ready", summary="Nanobot interactive runtime attached.")
            result, session_key, loop = await self._run_initial_turn(
                agent_name=self._config.agent_name,
                agent_prompt=self._config.agent_prompt,
                agent_model=self._config.agent_model,
                task_title=self._config.initial_task_title,
                task_description=self._config.initial_task_description,
                board_name=self._config.board_name,
                memory_workspace=self._config.memory_workspace,
                task_id=self._config.task_id,
                bridge=self._bridge,
                on_progress=self._on_progress,
            )
            self._session_key = session_key
            self._loop = loop
            self._record_result(
                content=_coerce_content(result),
                summary="Nanobot completed the interactive step.",
            )
            await self._run_repl()
            self._emit_event("session_stopped", summary="Nanobot Live session ended.")
            return 0
        except Exception as exc:
            self._write_line(f"[nanobot-live] {type(exc).__name__}: {exc}")
            self._emit_event("session_failed", error=str(exc), summary="Nanobot Live failed.")
            return 1

    async def _run_repl(self) -> None:
        if self._loop is None or self._session_key is None:
            return
        self._write_line("")
        self._write_line("[nanobot-live] Session ready. Type /exit to close Live.")
        while True:
            line = await asyncio.to_thread(self._stdin.readline)
            if line == "":
                await asyncio.sleep(self._repl_idle_poll_seconds)
                continue
            message = line.strip()
            if not message:
                continue
            if message.lower() in EXIT_COMMANDS:
                return
            self._emit_event("turn_started", summary="Nanobot interactive turn started.")
            result = await self._loop.process_direct(
                message,
                self._session_key,
                channel="mc",
                chat_id=self._config.agent_name,
                task_id=self._config.task_id,
                on_progress=self._on_progress,
            )
            self._record_result(
                content=_coerce_content(result),
                summary="Nanobot interactive turn completed.",
            )

    async def _wait_for_session_registration(self) -> None:
        deadline = asyncio.get_running_loop().time() + self._registration_timeout_seconds
        while True:
            metadata = self._bridge.query(
                "interactiveSessions:getForRuntime",
                {"session_id": self._config.session_id},
            )
            if isinstance(metadata, dict):
                return
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError(
                    f"Interactive session metadata not found for {self._config.session_id}"
                )
            await asyncio.sleep(self._registration_poll_interval)

    async def _on_progress(self, content: str, *, tool_hint: bool = False) -> None:
        prefix = "[tool]" if tool_hint else "[progress]"
        self._write_line(f"{prefix} {content}")

    def _record_result(self, *, content: str, summary: str) -> None:
        if content.strip():
            self._write_line(content)
            self._supervisor.record_final_result(
                session_id=self._config.session_id,
                content=content,
                source="mc-runtime",
            )
        self._emit_event(
            "turn_completed",
            summary=summary,
            final_output=content.strip() or None,
        )

    def _emit_event(
        self,
        kind: str,
        *,
        summary: str | None = None,
        final_output: str | None = None,
        error: str | None = None,
    ) -> None:
        self._supervisor.handle_event(
            InteractiveSupervisionEvent(
                kind=kind,
                session_id=self._config.session_id,
                provider="mc",
                task_id=self._config.task_id,
                summary=summary,
                final_output=final_output,
                error=error,
                agent_name=self._config.agent_name,
            )
        )

    def _write_line(self, content: str) -> None:
        self._stdout.write(content + "\n")
        self._stdout.flush()


def main() -> int:
    config = NanobotInteractiveSessionConfig.from_env()
    bridge = _get_bridge()
    registry = InteractiveSessionRegistry(bridge)
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)
    runner = NanobotInteractiveSessionRunner(
        config=config,
        bridge=bridge,
        supervisor=supervisor,
    )
    try:
        return asyncio.run(runner.run())
    finally:
        bridge.close()


def _require_env(env: dict[str, str], key: str) -> str:
    value = env.get(key, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _split_task_prompt(task_prompt: str | None) -> tuple[str | None, str | None]:
    if not task_prompt:
        return None, None
    text = task_prompt.strip()
    if not text:
        return None, None
    parts = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not parts:
        return None, None
    title = parts[0]
    if title.lower().startswith("step:"):
        title = title.split(":", 1)[1].strip() or title
    description = "\n\n".join(parts[1:]).strip() or None
    return title, description


def _coerce_content(result: Any) -> str:
    if isinstance(result, str):
        return result
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content
    return str(result or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
