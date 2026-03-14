"""Shared dataclasses and enums for the provider CLI session domain."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Literal


class SessionStatus(enum.Enum):
    """Lifecycle states for a provider CLI session."""

    STARTING = "starting"
    RUNNING = "running"
    WAITING_FOR_INPUT = "waiting_for_input"
    INTERRUPTING = "interrupting"
    HUMAN_INTERVENING = "human_intervening"
    RESUMING = "resuming"
    COMPLETED = "completed"
    STOPPED = "stopped"
    CRASHED = "crashed"


@dataclass
class ProviderProcessHandle:
    """OS-level handle for a launched provider CLI process."""

    mc_session_id: str
    provider: str
    pid: int
    pgid: int | None
    cwd: str
    command: list[str]
    started_at: str


@dataclass
class ProviderSessionSnapshot:
    """Normalized snapshot of a provider session's identity and capabilities."""

    mc_session_id: str
    provider_session_id: str | None
    mode: Literal["provider-native", "runtime-owned"]
    supports_resume: bool
    supports_interrupt: bool
    supports_stop: bool


@dataclass
class ParsedCliEvent:
    """A single parsed event from a provider CLI output stream."""

    kind: str  # "output", "session_discovered", "turn_started", "turn_completed",
    #              "subagent_spawned", "approval_requested", "error"
    text: str | None = None
    provider_session_id: str | None = None
    pid: int | None = None
    metadata: dict[str, Any] | None = None
