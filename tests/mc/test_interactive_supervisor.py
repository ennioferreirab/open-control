from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from mc.contexts.interactive.supervision_types import InteractiveSupervisionEvent
from mc.contexts.interactive.supervisor import (
    InteractiveExecutionSupervisor,
    _extract_file_path,
    _stringify_input,
)
from mc.types import ActivityEventType


def test_supervisor_marks_task_and_step_running_on_turn_started() -> None:
    bridge = MagicMock()
    bridge.get_task.return_value = {"id": "task-1", "status": "review", "state_version": 1}
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
    bridge.get_task.assert_called_once_with("task-1")
    bridge.transition_task_from_snapshot.assert_called_once()
    transition_call = bridge.transition_task_from_snapshot.call_args
    assert transition_call.args[0]["id"] == "task-1"
    assert transition_call.args[1] == "in_progress"
    assert transition_call.kwargs["agent_name"] == "claude-pair"
    assert transition_call.kwargs["reason"] == "Interactive turn started for step step-1"
    bridge.update_step_status.assert_called_once_with("step-1", "running")
    bridge.create_activity.assert_called_once_with(
        ActivityEventType.STEP_STARTED,
        "Interactive step started for @claude-pair.",
        task_id="task-1",
        agent_name="claude-pair",
    )


def test_supervisor_marks_task_review_and_step_waiting_human_when_paused() -> None:
    bridge = MagicMock()
    bridge.get_task.return_value = {"id": "task-1", "status": "in_progress", "state_version": 1}
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

    bridge.get_task.assert_called_once_with("task-1")
    bridge.transition_task_from_snapshot.assert_called_once()
    transition_call = bridge.transition_task_from_snapshot.call_args
    assert transition_call.args[1] == "review"
    assert transition_call.kwargs["agent_name"] == "claude-pair"
    assert transition_call.kwargs["reason"] == "Need user confirmation before continuing."
    assert transition_call.kwargs["awaiting_kickoff"] is False
    assert transition_call.kwargs["review_phase"] == "execution_pause"
    bridge.update_step_status.assert_called_once_with("step-1", "waiting_human")
    bridge.create_activity.assert_called_once_with(
        ActivityEventType.REVIEW_REQUESTED,
        "Interactive session paused for review for @claude-pair.",
        task_id="task-1",
        agent_name="claude-pair",
    )


def test_supervisor_does_not_project_approval_requested_as_workflow_review() -> None:
    bridge = MagicMock()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:codex",
        "agent_name": "codex-reviewer",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="approval_requested",
            provider="codex",
            session_id="interactive_session:codex",
            summary="Approve the shell command?",
        )
    )

    bridge.update_task_status.assert_not_called()
    bridge.update_step_status.assert_not_called()
    bridge.create_activity.assert_called_once_with(
        ActivityEventType.HITL_REQUESTED,
        "Interactive session requested approval for @codex-reviewer.",
        task_id="task-1",
        agent_name="codex-reviewer",
    )


def test_supervisor_marks_task_and_step_crashed_on_session_failure() -> None:
    bridge = MagicMock()
    bridge.get_task.return_value = {"id": "task-1", "status": "in_progress", "state_version": 1}
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

    bridge.get_task.assert_called_once_with("task-1")
    bridge.transition_task_from_snapshot.assert_called_once()
    transition_call = bridge.transition_task_from_snapshot.call_args
    assert transition_call.args[1] == "crashed"
    assert transition_call.kwargs["agent_name"] == "claude-pair"
    assert transition_call.kwargs["reason"] == "Provider process exited unexpectedly"
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


# ---------------------------------------------------------------------------
# Activity log write tests
# ---------------------------------------------------------------------------


def _make_supervisor() -> tuple[MagicMock, MagicMock, InteractiveExecutionSupervisor]:
    bridge = MagicMock()
    bridge.get_task.return_value = {"id": "task-1", "status": "review", "state_version": 1}
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    registry.record_supervision.return_value = {}
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)
    return bridge, registry, supervisor


def test_activity_log_append_called_after_record_supervision_on_item_started() -> None:
    bridge, registry, supervisor = _make_supervisor()

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="item_started",
            session_id="interactive_session:claude",
            provider="claude-code",
            agent_name="claude-pair",
            turn_id="turn-1",
            item_id="item-1",
            step_id="step-1",
            metadata={"tool_name": "str_replace_editor", "input": {"file_path": "/tmp/foo.py"}},
        )
    )

    registry.record_supervision.assert_called_once()
    bridge.mutation.assert_called_once()
    name, payload = bridge.mutation.call_args[0]
    assert name == "sessionActivityLog:append"
    assert payload["session_id"] == "interactive_session:claude"
    assert payload["kind"] == "item_started"
    assert payload["tool_name"] == "str_replace_editor"
    assert payload["tool_input"] == json.dumps({"file_path": "/tmp/foo.py"})
    assert payload["file_path"] == "/tmp/foo.py"
    assert payload["requires_action"] is False


def test_activity_log_payload_for_turn_completed_with_summary() -> None:
    bridge, registry, supervisor = _make_supervisor()

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="turn_completed",
            session_id="interactive_session:claude",
            provider="claude-code",
            agent_name="claude-pair",
            turn_id="turn-2",
            summary="Turn finished successfully.",
        )
    )

    bridge.mutation.assert_called_once()
    _, payload = bridge.mutation.call_args[0]
    assert payload["kind"] == "turn_completed"
    assert payload["summary"] == "Turn finished successfully."
    assert payload["turn_id"] == "turn-2"
    assert payload["requires_action"] is False


def test_activity_log_missing_metadata_fields_result_in_none() -> None:
    bridge, registry, supervisor = _make_supervisor()

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="session_ready",
            session_id="interactive_session:claude",
            provider="claude-code",
            agent_name="claude-pair",
        )
    )

    bridge.mutation.assert_called_once()
    _, payload = bridge.mutation.call_args[0]
    # With _set_if, absent optional fields are omitted (not sent as None)
    assert "tool_name" not in payload
    assert "tool_input" not in payload
    assert "file_path" not in payload


def test_activity_log_requires_action_true_for_approval_requested() -> None:
    bridge, registry, supervisor = _make_supervisor()

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="approval_requested",
            session_id="interactive_session:claude",
            provider="claude-code",
            agent_name="claude-pair",
            summary="Approve the shell command?",
        )
    )

    bridge.mutation.assert_called_once()
    _, payload = bridge.mutation.call_args[0]
    assert payload["requires_action"] is True
    assert payload["summary"] == "Approve the shell command?"


def test_activity_log_requires_action_true_for_user_input_requested() -> None:
    bridge, registry, supervisor = _make_supervisor()

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="user_input_requested",
            session_id="interactive_session:claude",
            provider="claude-code",
            agent_name="claude-pair",
        )
    )

    _, payload = bridge.mutation.call_args[0]
    assert payload["requires_action"] is True


def test_activity_log_write_failure_does_not_break_supervision_flow() -> None:
    bridge, registry, supervisor = _make_supervisor()
    bridge.mutation.side_effect = RuntimeError("Convex is down")

    # Should not raise; supervision continues normally
    result = supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="turn_started",
            session_id="interactive_session:claude",
            provider="claude-code",
            agent_name="claude-pair",
            task_id="task-1",
            step_id="step-1",
        )
    )

    # record_supervision still called
    registry.record_supervision.assert_called_once()
    # lifecycle side-effects still applied
    bridge.transition_task_from_snapshot.assert_called_once()
    bridge.update_step_status.assert_called_once()
    assert result == {}


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


def test_stringify_input_none_returns_none() -> None:
    assert _stringify_input(None) is None


def test_stringify_input_dict_serialises_to_json() -> None:
    result = _stringify_input({"key": "value"})
    assert result == '{"key": "value"}'


def test_stringify_input_truncates_long_strings() -> None:
    long_str = "x" * 3000
    result = _stringify_input(long_str, max_len=2000)
    assert result is not None
    assert len(result) == 2000


def test_extract_file_path_from_file_path_key() -> None:
    assert _extract_file_path({"input": {"file_path": "/src/foo.py"}}) == "/src/foo.py"


def test_extract_file_path_from_path_key() -> None:
    assert _extract_file_path({"input": {"path": "/src/bar.py"}}) == "/src/bar.py"


def test_extract_file_path_returns_none_when_absent() -> None:
    assert _extract_file_path({"input": {}}) is None
    assert _extract_file_path({}) is None


# ── Story 28-0b: session activity payload serialization ───────────────


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
        )
    )

    call_kwargs = registry.record_supervision.call_args
    event_payload = call_kwargs[1]["event"]

    assert "kind" in event_payload
    assert event_payload["kind"] == "turn_started"

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


# ── Story 28-0b: idempotent supervision status projection ────────────


def test_supervisor_turn_started_is_idempotent_when_task_already_in_progress() -> None:
    """Repeated turn_started must not fail when task is already in_progress."""
    bridge = MagicMock()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    registry.record_supervision.return_value = {}
    bridge.get_task.return_value = {"id": "task-1", "status": "in_progress", "state_version": 3}
    bridge.transition_task_from_snapshot.return_value = {
        "kind": "noop",
        "reason": "already_applied",
    }
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

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

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="item_started",
            session_id="interactive_session:claude",
            provider="claude-code",
        )
    )


def test_supervisor_paused_for_review_is_idempotent_when_task_and_step_already_waiting() -> None:
    """Repeated pause events must not fail when ask_user already moved workflow to review."""
    bridge = MagicMock()

    def _update_step_status(*args: object, **kwargs: object) -> None:
        raise Exception("Cannot transition waiting_human -> waiting_human")

    bridge.update_step_status.side_effect = _update_step_status
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    registry.record_supervision.return_value = {}
    bridge.get_task.return_value = {"id": "task-1", "status": "review", "state_version": 5}
    bridge.transition_task_from_snapshot.return_value = {
        "kind": "noop",
        "reason": "already_applied",
    }
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="ask_user_requested",
            session_id="interactive_session:claude",
            provider="claude-code",
            summary="Need user input before continuing.",
        )
    )

    bridge.create_activity.assert_called_once_with(
        ActivityEventType.REVIEW_REQUESTED,
        "Interactive session paused for review for @claude-pair.",
        task_id="task-1",
        agent_name="claude-pair",
    )


def test_supervisor_skips_step_and_activity_projection_when_task_snapshot_is_missing() -> None:
    bridge = MagicMock()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    registry.record_supervision.return_value = {}
    bridge.get_task.return_value = None
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="turn_started",
            session_id="interactive_session:claude",
            provider="claude-code",
        )
    )

    bridge.transition_task_from_snapshot.assert_not_called()
    bridge.update_step_status.assert_not_called()
    bridge.create_activity.assert_not_called()


def test_supervisor_skips_step_and_activity_projection_on_task_transition_conflict() -> None:
    bridge = MagicMock()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    registry.record_supervision.return_value = {}
    bridge.get_task.return_value = {"id": "task-1", "status": "review", "state_version": 4}
    bridge.transition_task_from_snapshot.return_value = {
        "kind": "conflict",
        "reason": "stale_state",
    }
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="turn_started",
            session_id="interactive_session:claude",
            provider="claude-code",
        )
    )

    bridge.update_step_status.assert_not_called()
    bridge.create_activity.assert_not_called()


def test_supervisor_genuine_transition_failure_still_surfaces() -> None:
    """Unexpected transition failures must not be silently swallowed."""
    bridge = MagicMock()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    registry.record_supervision.return_value = {}
    bridge.get_task.return_value = {"id": "task-1", "status": "review", "state_version": 4}
    bridge.transition_task_from_snapshot.side_effect = Exception(
        "Network timeout connecting to Convex"
    )
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    with pytest.raises(Exception, match="Network timeout"):
        supervisor.handle_event(
            InteractiveSupervisionEvent(
                kind="turn_started",
                session_id="interactive_session:claude",
                provider="claude-code",
            )
        )
