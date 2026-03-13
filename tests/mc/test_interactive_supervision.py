from __future__ import annotations

import pytest

from mc.contexts.interactive.supervision import normalize_provider_event
from mc.contexts.interactive.supervision_types import InteractiveSupervisionEvent


def test_normalize_claude_permission_request_into_supervision_event() -> None:
    event = normalize_provider_event(
        provider="claude-code",
        raw_event={
            "eventName": "PermissionRequest",
            "session_id": "interactive_session:claude",
            "task_id": "task-1",
            "step_id": "step-1",
            "metadata": {"tool_name": "Bash"},
        },
    )

    assert event == InteractiveSupervisionEvent(
        kind="approval_requested",
        session_id="interactive_session:claude",
        provider="claude-code",
        task_id="task-1",
        step_id="step-1",
        metadata={"tool_name": "Bash"},
    )


def test_normalize_codex_turn_completed_into_supervision_event() -> None:
    event = normalize_provider_event(
        provider="codex",
        raw_event={
            "event": "turn/completed",
            "session_id": "interactive_session:codex",
            "task_id": "task-2",
            "step_id": "step-2",
            "turn_id": "turn-9",
            "summary": "Finished implementing the step.",
        },
    )

    assert event.kind == "turn_completed"
    assert event.session_id == "interactive_session:codex"
    assert event.provider == "codex"
    assert event.task_id == "task-2"
    assert event.step_id == "step-2"
    assert event.turn_id == "turn-9"
    assert event.summary == "Finished implementing the step."


def test_interactive_supervision_event_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unknown interactive supervision event kind"):
        InteractiveSupervisionEvent(kind="mystery_event")
