"""Codex adapter for the interactive session runtime."""

from __future__ import annotations

import shutil
from inspect import isawaitable
from pathlib import Path
from typing import Awaitable, Callable, ClassVar

from mc.contexts.interactive.adapters.codex_app_server import (
    CodexAppServerSession,
    start_codex_app_server_session,
    stop_codex_app_server_session,
)
from mc.contexts.interactive.errors import (
    InteractiveSessionBinaryMissingError,
    InteractiveSessionBootstrapError,
)
from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.contexts.interactive.types import InteractiveLaunchSpec, InteractiveSupervisionSink
from mc.infrastructure.config import AGENTS_DIR
from mc.types import AgentData


def _strip_codex_model_prefix(model: str | None) -> str | None:
    if not model:
        return None
    for prefix in (
        "codex/",
        "openai-codex/",
        "openai_codex/",
        "github-copilot/",
        "github_copilot/",
    ):
        if model.startswith(prefix):
            return model[len(prefix) :]
    return model


class CodexInteractiveAdapter:
    """Prepare and clean up Codex interactive sessions."""

    provider_name = "codex"
    capabilities: ClassVar[list[str]] = [
        "tui",
        "autocomplete",
        "interactive-prompts",
        "commands",
    ]

    def __init__(
        self,
        *,
        cli_path: str = "codex",
        which: Callable[[str], str | None] = shutil.which,
        agents_dir: Path = AGENTS_DIR,
        supervision_sink: InteractiveSupervisionSink | None = None,
        supervision_starter: Callable[
            ..., Awaitable[CodexAppServerSession] | CodexAppServerSession
        ] = start_codex_app_server_session,
    ) -> None:
        self._cli_path = cli_path
        self._which = which
        self._agents_dir = agents_dir
        self._supervision_sink = supervision_sink
        self._supervision_starter = supervision_starter
        self._supervision_sessions: dict[str, CodexAppServerSession] = {}

    async def healthcheck(self, *, agent: AgentData) -> None:
        del agent
        if self._which(self._cli_path) is None:
            raise InteractiveSessionBinaryMissingError(
                f"Codex binary '{self._cli_path}' is not available on PATH."
            )

    async def prepare_launch(
        self,
        *,
        identity: InteractiveSessionIdentity,
        agent: AgentData,
        task_id: str | None = None,
        orientation: str | None = None,
        task_prompt: str | None = None,
        board_name: str | None = None,
        memory_mode: str = "clean",
        memory_workspace: Path | None = None,
        resume_session_id: str | None = None,
    ) -> InteractiveLaunchSpec:
        del board_name, memory_mode, resume_session_id
        await self.healthcheck(agent=agent)

        try:
            cwd = self._agents_dir / agent.name
            cwd.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise InteractiveSessionBootstrapError(
                f"Codex workspace bootstrap failed: {exc}"
            ) from exc

        if self._supervision_sink is not None:
            session = self._supervision_starter(
                session_id=identity.session_key,
                task_id=task_id,
                step_id=None,
                agent_name=agent.name,
                cwd=cwd,
                sink=self._supervision_sink,
                cli_path=self._cli_path,
            )
            if isawaitable(session):
                session = await session
            self._supervision_sessions[identity.session_key] = session

        return InteractiveLaunchSpec(
            cwd=cwd,
            command=self._build_command(agent),
            capabilities=list(self.capabilities),
            environment={"MEMORY_WORKSPACE": str(memory_workspace or cwd)},
            bootstrap_input=_build_bootstrap_prompt(
                orientation=orientation,
                task_prompt=task_prompt,
            ),
        )

    async def stop_session(self, session_key: str) -> None:
        session = self._supervision_sessions.pop(session_key, None)
        if session is not None:
            await stop_codex_app_server_session(session)

    def _build_command(self, agent: AgentData) -> list[str]:
        command = [
            self._cli_path,
            "--sandbox",
            "workspace-write",
            "--ask-for-approval",
            "on-request",
        ]
        model = _strip_codex_model_prefix(agent.model)
        if model:
            command.extend(["--model", model])
        return command


def _build_bootstrap_prompt(*, orientation: str | None, task_prompt: str | None) -> str | None:
    parts = [part.strip() for part in (orientation, task_prompt) if part and part.strip()]
    if not parts:
        return None
    return "\n\n".join(parts)
