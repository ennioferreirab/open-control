"""Provider-aware orchestration for interactive sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from mc.contexts.interactive.errors import (
    InteractiveSessionAttachError,
    InteractiveSessionStartupError,
)
from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.contexts.interactive.registry import InteractiveSessionRegistry
from mc.contexts.interactive.types import InteractiveAttachment, InteractiveProviderAdapter
from mc.infrastructure.interactive import AttachedTerminal, TerminalSize, TmuxSessionManager
from mc.infrastructure.interactive.pty import spawn_tmux_attach_pty
from mc.types import AgentData


class InteractiveSessionCoordinator:
    """Create, reuse, attach, and terminate provider-backed interactive sessions."""

    def __init__(
        self,
        *,
        registry: InteractiveSessionRegistry,
        tmux: TmuxSessionManager,
        adapters: dict[str, InteractiveProviderAdapter],
        attach_factory: Callable[..., AttachedTerminal] = spawn_tmux_attach_pty,
        idle_timeout_seconds: int = 900,
    ) -> None:
        self._registry = registry
        self._tmux = tmux
        self._adapters = adapters
        self._attach_factory = attach_factory
        self._idle_timeout_seconds = idle_timeout_seconds

    async def create_or_attach(
        self,
        *,
        identity: InteractiveSessionIdentity,
        agent: AgentData,
        task_id: str,
        step_id: str | None = None,
        timestamp: str,
        orientation: str | None = None,
        task_prompt: str | None = None,
        board_name: str | None = None,
        memory_mode: str = "clean",
        memory_workspace: Path | None = None,
        resume_session_id: str | None = None,
    ) -> dict[str, Any]:
        existing = self._registry.get(identity.session_key)
        if existing:
            if self._tmux.has_session(existing["tmux_session"]):
                if self._is_idle_detached(existing, timestamp):
                    await self._stop_existing_session(
                        existing, timestamp=timestamp, outcome="terminated"
                    )
                else:
                    return existing
            else:
                await self._stop_existing_session(existing, timestamp=timestamp, outcome="crashed")

        adapter = self._adapters[identity.provider]
        await adapter.healthcheck(agent=agent)
        launch = await adapter.prepare_launch(
            identity=identity,
            agent=agent,
            task_id=task_id,
            orientation=orientation,
            task_prompt=task_prompt,
            board_name=board_name,
            memory_mode=memory_mode,
            memory_workspace=memory_workspace,
            resume_session_id=resume_session_id,
        )

        try:
            self._tmux.ensure_session(
                identity.tmux_session_name,
                cwd=str(launch.cwd),
                command=launch.command,
                env=launch.environment,
            )
            if launch.bootstrap_input:
                self._tmux.send_keys(identity.tmux_session_name, launch.bootstrap_input)
        except Exception as exc:
            await adapter.stop_session(identity.session_key)
            raise InteractiveSessionStartupError(
                f"Interactive session startup failed: {exc}"
            ) from exc

        return self._registry.register(
            identity,
            status="ready",
            capabilities=launch.capabilities,
            timestamp=timestamp,
            task_id=task_id,
            step_id=step_id,
            rotate_attach_token=True,
        )

    def attach_session(
        self,
        session_id: str,
        *,
        size: TerminalSize,
        attach_token: str | None,
        timestamp: str,
    ) -> InteractiveAttachment:
        metadata = self._registry.get(session_id)
        if metadata is None:
            raise InteractiveSessionAttachError(
                f"Interactive session metadata not found for {session_id}"
            )
        if attach_token != metadata.get("attach_token"):
            raise InteractiveSessionAttachError(
                f"Interactive session attach is not authorized for {session_id}"
            )
        if not self._tmux.has_session(metadata["tmux_session"]):
            self._registry.end_session(session_id, timestamp=timestamp, outcome="crashed")
            raise InteractiveSessionAttachError(
                f"Interactive session is no longer available for {session_id}"
            )

        try:
            terminal = self._attach_factory(metadata["tmux_session"], size=size)
            attached_metadata = self._registry.mark_attached(session_id, timestamp=timestamp)
            return InteractiveAttachment(terminal=terminal, metadata=attached_metadata)
        except Exception as exc:
            raise InteractiveSessionAttachError(f"Interactive attach failed: {exc}") from exc

    def detach_session(self, session_id: str, *, timestamp: str) -> dict[str, Any]:
        return self._registry.mark_detached(session_id, timestamp=timestamp)

    def mark_session_crashed(self, session_id: str, *, timestamp: str) -> dict[str, Any]:
        return self._registry.end_session(session_id, timestamp=timestamp, outcome="crashed")

    async def terminate_session(
        self,
        identity: InteractiveSessionIdentity,
        *,
        timestamp: str,
    ) -> dict[str, Any]:
        adapter = self._adapters.get(identity.provider)
        if adapter is not None:
            await adapter.stop_session(identity.session_key)

        self._tmux.terminate_session(identity.tmux_session_name)
        return self._registry.terminate(identity, timestamp=timestamp)

    async def cleanup_idle_sessions(self, *, timestamp: str) -> list[str]:
        cleaned: list[str] = []
        for metadata in self._registry.list_sessions():
            if not self._is_idle_detached(metadata, timestamp):
                continue
            await self._stop_existing_session(metadata, timestamp=timestamp, outcome="terminated")
            cleaned.append(metadata["session_id"])
        return cleaned

    async def _stop_existing_session(
        self,
        metadata: dict[str, Any],
        *,
        timestamp: str,
        outcome: str,
    ) -> None:
        adapter = self._adapters.get(metadata["provider"])
        if adapter is not None:
            await adapter.stop_session(metadata["session_id"])
        if self._tmux.has_session(metadata["tmux_session"]):
            self._tmux.terminate_session(metadata["tmux_session"])
        self._registry.end_session(metadata["session_id"], timestamp=timestamp, outcome=outcome)

    def _is_idle_detached(self, metadata: dict[str, Any], timestamp: str) -> bool:
        if metadata.get("status") != "detached":
            return False
        last_active_at = metadata.get("last_active_at")
        if not isinstance(last_active_at, str):
            return False
        last_active = _parse_timestamp(last_active_at)
        now = _parse_timestamp(timestamp)
        return (now - last_active).total_seconds() >= self._idle_timeout_seconds


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
