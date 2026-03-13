"""Canonical supervision event types for provider-backed interactive sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

INTERACTIVE_SUPERVISION_EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "session_started",
        "session_ready",
        "turn_started",
        "turn_updated",
        "turn_completed",
        "item_started",
        "item_completed",
        "approval_requested",
        "user_input_requested",
        "ask_user_requested",
        "paused_for_review",
        "session_failed",
        "session_stopped",
    }
)


@dataclass(frozen=True)
class InteractiveSupervisionEvent:
    """Provider-agnostic lifecycle event emitted above the interactive PTY runtime."""

    kind: str
    session_id: str | None = None
    provider: str | None = None
    task_id: str | None = None
    step_id: str | None = None
    turn_id: str | None = None
    item_id: str | None = None
    status: str | None = None
    summary: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    occurred_at: str | None = None
    agent_name: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in INTERACTIVE_SUPERVISION_EVENT_KINDS:
            raise ValueError(f"Unknown interactive supervision event kind: {self.kind}")
