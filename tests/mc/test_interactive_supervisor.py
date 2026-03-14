from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mc.contexts.interactive.supervision_types import InteractiveSupervisionEvent
from mc.contexts.interactive.supervisor import InteractiveExecutionSupervisor
from mc.types import ActivityEventType


def test_supervisor_marks_task_and_step_running_on_turn_started() -> None:
    bridge = MagicMock()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="turn_started",
            provider="claude-code",
            session_id="interactive_session:claude",
        )
    )

    registry.record_supervision.assert_called_once()
    bridge.update_task_status.assert_called_once_with(
        "task-1",
        "in_progress",
        agent_name="claude-pair",
        description="Interactive turn started for step step-1",
    )
    bridge.update_step_status.assert_called_once_with("step-1", "running")
    bridge.create_activity.assert_called_once_with(
        ActivityEventType.STEP_STARTED,
        "Interactive step started for @claude-pair.",
        task_id="task-1",
        agent_name="claude-pair",
    )


def test_supervisor_marks_task_review_and_step_review_when_paused() -> None:
    bridge = MagicMock()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="paused_for_review",
            provider="claude-code",
            session_id="interactive_session:claude",
            summary="Need user confirmation before continuing.",
        )
    )

    bridge.update_task_status.assert_called_once_with(
        "task-1",
        "review",
        agent_name="claude-pair",
        description="Need user confirmation before continuing.",
    )
    bridge.update_step_status.assert_called_once_with("step-1", "review")
    bridge.create_activity.assert_called_once_with(
        ActivityEventType.REVIEW_REQUESTED,
        "Interactive session paused for review for @claude-pair.",
        task_id="task-1",
        agent_name="claude-pair",
    )


def test_supervisor_marks_task_and_step_crashed_on_session_failure() -> None:
    bridge = MagicMock()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="session_failed",
            provider="claude-code",
            session_id="interactive_session:claude",
            error="Provider process exited unexpectedly",
        )
    )

    bridge.update_task_status.assert_called_once_with(
        "task-1",
        "crashed",
        agent_name="claude-pair",
        description="Provider process exited unexpectedly",
    )
    bridge.update_step_status.assert_called_once_with(
        "step-1",
        "crashed",
        "Provider process exited unexpectedly",
    )
    bridge.create_activity.assert_called_once_with(
        ActivityEventType.AGENT_CRASHED,
        "Interactive session failed for @claude-pair.",
        task_id="task-1",
        agent_name="claude-pair",
    )


def test_supervisor_emits_activity_when_supervision_becomes_ready() -> None:
    bridge = MagicMock()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="session_ready",
            provider="claude-code",
            session_id="interactive_session:claude",
        )
    )

    bridge.create_activity.assert_called_once_with(
        ActivityEventType.AGENT_CONNECTED,
        "Interactive supervision ready for @claude-pair.",
        task_id="task-1",
        agent_name="claude-pair",
    )


def test_supervisor_records_final_result_without_posting_completion_side_effects() -> None:
    bridge = MagicMock()
    registry = MagicMock()
    registry.record_final_result.return_value = {"session_id": "interactive_session:claude"}
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    result = supervisor.record_final_result(
        session_id="interactive_session:claude",
        content="Step finished successfully with the requested code changes.",
        source="claude-mcp",
    )

    registry.record_final_result.assert_called_once_with(
        "interactive_session:claude",
        content="Step finished successfully with the requested code changes.",
        source="claude-mcp",
        timestamp=result["recorded_at"],
    )
    bridge.update_task_status.assert_not_called()
    bridge.update_step_status.assert_not_called()


def test_supervisor_suppresses_lifecycle_side_effects_during_human_takeover() -> None:
    bridge = MagicMock()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
        "control_mode": "human",
    }
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="session_failed",
            provider="claude-code",
            session_id="interactive_session:claude",
            error="Provider exited while the human was taking over.",
        )
    )

    registry.record_supervision.assert_called_once()
    bridge.update_task_status.assert_not_called()
    bridge.update_step_status.assert_not_called()
    bridge.create_activity.assert_not_called()


# ── Task 1: session activity payload serialization ────────────────────


def test_supervisor_record_supervision_omits_none_optional_fields() -> None:
    """Optional string fields must not be sent as None to record_supervision."""
    bridge = MagicMock()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    registry.record_supervision.return_value = {}
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="turn_started",
            session_id="interactive_session:claude",
            provider="claude-code",
            # No turn_id, item_id, summary, final_output, error, status, agent_name
        )
    )

    call_kwargs = registry.record_supervision.call_args
    event_payload = call_kwargs[1]["event"]  # keyword arg "event"

    # Required fields must be present
    assert "kind" in event_payload
    assert event_payload["kind"] == "turn_started"

    # Optional fields that are None must be omitted, not sent as None
    for optional_field in ("turn_id", "item_id", "summary", "final_output", "error", "status"):
        assert (
            event_payload.get(optional_field) is not None or optional_field not in event_payload
        ), f"Optional field '{optional_field}' must be omitted when None, not sent as None"


def test_supervisor_record_supervision_includes_present_optional_fields() -> None:
    """Optional fields with values must still be included in the payload."""
    bridge = MagicMock()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    registry.record_supervision.return_value = {}
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="turn_started",
            session_id="interactive_session:claude",
            provider="claude-code",
            turn_id="turn-99",
            summary="Working on it",
        )
    )

    call_kwargs = registry.record_supervision.call_args
    event_payload = call_kwargs[1]["event"]

    assert event_payload["turn_id"] == "turn-99"
    assert event_payload["summary"] == "Working on it"


def test_supervisor_record_supervision_no_null_values_in_payload() -> None:
    """The event payload passed to record_supervision must not contain any None values."""
    bridge = MagicMock()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    registry.record_supervision.return_value = {}
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="session_ready",
            session_id="interactive_session:claude",
            provider="claude-code",
        )
    )

    call_kwargs = registry.record_supervision.call_args
    event_payload = call_kwargs[1]["event"]

    null_fields = [k for k, v in event_payload.items() if v is None]
    assert null_fields == [], f"Payload must not contain null values, found: {null_fields}"


# ── Task 2: idempotent supervision status projection ─────────────────


def test_supervisor_turn_started_is_idempotent_when_task_already_in_progress() -> None:
    """Repeated turn_started must not fail when task is already in_progress."""
    bridge = MagicMock()
    # Simulate update_task_status raising the same-status transition error
    bridge.update_task_status.side_effect = Exception(
        "Cannot transition in_progress -> in_progress"
    )
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    registry.record_supervision.return_value = {}
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    # Should not raise even though update_task_status raises a same-status error
    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="turn_started",
            session_id="interactive_session:claude",
            provider="claude-code",
        )
    )


def test_supervisor_item_started_is_idempotent_when_step_already_running() -> None:
    """Repeated item_started must not fail when step is already running."""
    bridge = MagicMock()
    bridge.update_step_status.side_effect = Exception("Cannot transition running -> running")
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    registry.record_supervision.return_value = {}
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    # Should not raise even though update_step_status raises a same-status error
    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="item_started",
            session_id="interactive_session:claude",
            provider="claude-code",
        )
    )


def test_supervisor_genuine_transition_failure_still_surfaces() -> None:
    """Unexpected transition failures must not be silently swallowed."""
    bridge = MagicMock()
    bridge.update_task_status.side_effect = Exception("Network timeout connecting to Convex")
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    registry.record_supervision.return_value = {}
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    with pytest.raises(Exception, match="Network timeout"):
        supervisor.handle_event(
            InteractiveSupervisionEvent(
                kind="turn_started",
                session_id="interactive_session:claude",
                provider="claude-code",
            )
        )
