"""Shared types for interactive provider adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.contexts.interactive.supervision_types import InteractiveSupervisionEvent
from mc.infrastructure.interactive import AttachedTerminal
from mc.types import AgentData


@dataclass(frozen=True)
class InteractiveLaunchSpec:
    """Launch details for an interactive provider session."""

    cwd: Path
    command: list[str]
    capabilities: list[str]
    environment: dict[str, str] | None = None


@dataclass(frozen=True)
class InteractiveAttachment:
    """Attached PTY plus the runtime metadata used to authorize reconnects."""

    terminal: AttachedTerminal
    metadata: dict[str, object]


class InteractiveProviderAdapter(Protocol):
    """Contract for provider-backed interactive TUI adapters."""

    provider_name: str
    capabilities: list[str]

    async def healthcheck(self, *, agent: AgentData) -> None:
        """Raise when the provider cannot start an interactive session."""

    async def prepare_launch(
        self,
        *,
        identity: InteractiveSessionIdentity,
        agent: AgentData,
        task_id: str,
        orientation: str | None = None,
        task_prompt: str | None = None,
        board_name: str | None = None,
        memory_mode: str = "clean",
        resume_session_id: str | None = None,
    ) -> InteractiveLaunchSpec:
        """Prepare launch metadata for a provider-backed interactive session."""

    async def stop_session(self, session_key: str) -> None:
        """Tear down provider-specific runtime state for a session."""


class InteractiveSupervisionSink(Protocol):
    """Consumer for normalized interactive supervision events."""

    def handle_event(self, event: InteractiveSupervisionEvent) -> dict[str, object]:
        """Consume a provider-agnostic lifecycle event."""
