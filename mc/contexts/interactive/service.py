"""Provider-agnostic interactive session orchestration."""

from __future__ import annotations

from typing import Callable

from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.contexts.interactive.registry import InteractiveSessionRegistry
from mc.contexts.interactive.types import InteractiveAttachment
from mc.infrastructure.interactive import AttachedTerminal, TerminalSize, TmuxSessionManager
from mc.infrastructure.interactive.pty import spawn_tmux_attach_pty


class InteractiveSessionService:
    """Own the create, attach, list, and terminate lifecycle for interactive sessions."""

    def __init__(
        self,
        *,
        registry: InteractiveSessionRegistry,
        tmux: TmuxSessionManager,
        attach_factory: Callable[..., AttachedTerminal] = spawn_tmux_attach_pty,
    ) -> None:
        self._registry = registry
        self._tmux = tmux
        self._attach_factory = attach_factory

    def create_session(
        self,
        identity: InteractiveSessionIdentity,
        *,
        cwd: str | None,
        command: list[str] | None,
        capabilities: list[str],
        timestamp: str,
    ) -> dict[str, object]:
        self._tmux.ensure_session(identity.tmux_session_name, cwd=cwd, command=command)
        return self._registry.register(
            identity,
            status="ready",
            capabilities=capabilities,
            timestamp=timestamp,
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
            raise ValueError(f"Interactive session metadata not found for {session_id}")
        if attach_token != metadata.get("attach_token"):
            raise ValueError(f"Interactive session attach is not authorized for {session_id}")
        if not self._tmux.has_session(metadata["tmux_session"]):
            self._registry.end_session(session_id, timestamp=timestamp, outcome="crashed")
            raise ValueError(f"Interactive session metadata not found for {session_id}")

        tmux_session = metadata["tmux_session"]
        terminal = self._attach_factory(tmux_session, size=size)
        attached_metadata = self._registry.mark_attached(session_id, timestamp=timestamp)
        return InteractiveAttachment(terminal=terminal, metadata=attached_metadata)

    def detach_session(self, session_id: str, *, timestamp: str) -> dict[str, object]:
        return self._registry.mark_detached(session_id, timestamp=timestamp)

    def mark_session_crashed(self, session_id: str, *, timestamp: str) -> dict[str, object]:
        return self._registry.end_session(session_id, timestamp=timestamp, outcome="crashed")

    def list_sessions(self, *, agent_name: str | None = None) -> list[dict[str, object]]:
        return self._registry.list_sessions(agent_name=agent_name)

    def terminate_session(
        self,
        identity: InteractiveSessionIdentity,
        *,
        timestamp: str,
    ) -> dict[str, object]:
        metadata = self._registry.terminate(identity, timestamp=timestamp)
        self._tmux.terminate_session(identity.tmux_session_name)
        return metadata
