"""Unit tests for the step-level state machine in mc.domain.workflow.state_machine."""

from __future__ import annotations

import pytest

from mc.domain.workflow.state_machine import (
    STEP_TRANSITION_EVENT_MAP,
    STEP_VALID_TRANSITIONS,
    get_step_event_type,
    is_valid_step_transition,
    validate_step_transition,
)
from mc.types import ActivityEventType, StepStatus


# ---------------------------------------------------------------------------
# is_valid_step_transition — valid transitions
# ---------------------------------------------------------------------------

class TestIsValidStepTransitionValid:
    """All valid step transitions return True."""

    def test_planned_to_assigned(self) -> None:
        assert is_valid_step_transition(StepStatus.PLANNED, StepStatus.ASSIGNED) is True

    def test_planned_to_blocked(self) -> None:
        assert is_valid_step_transition(StepStatus.PLANNED, StepStatus.BLOCKED) is True

    def test_assigned_to_running(self) -> None:
        assert is_valid_step_transition(StepStatus.ASSIGNED, StepStatus.RUNNING) is True

    def test_assigned_to_completed(self) -> None:
        assert is_valid_step_transition(StepStatus.ASSIGNED, StepStatus.COMPLETED) is True

    def test_assigned_to_crashed(self) -> None:
        assert is_valid_step_transition(StepStatus.ASSIGNED, StepStatus.CRASHED) is True

    def test_assigned_to_blocked(self) -> None:
        assert is_valid_step_transition(StepStatus.ASSIGNED, StepStatus.BLOCKED) is True

    def test_running_to_completed(self) -> None:
        assert is_valid_step_transition(StepStatus.RUNNING, StepStatus.COMPLETED) is True

    def test_running_to_crashed(self) -> None:
        assert is_valid_step_transition(StepStatus.RUNNING, StepStatus.CRASHED) is True

    def test_crashed_to_assigned(self) -> None:
        assert is_valid_step_transition(StepStatus.CRASHED, StepStatus.ASSIGNED) is True

    def test_blocked_to_assigned(self) -> None:
        assert is_valid_step_transition(StepStatus.BLOCKED, StepStatus.ASSIGNED) is True

    def test_blocked_to_crashed(self) -> None:
        assert is_valid_step_transition(StepStatus.BLOCKED, StepStatus.CRASHED) is True

    # Story 7.2: waiting_human transitions
    def test_assigned_to_waiting_human(self) -> None:
        assert is_valid_step_transition(StepStatus.ASSIGNED, StepStatus.WAITING_HUMAN) is True

    def test_waiting_human_to_running(self) -> None:
        assert is_valid_step_transition(StepStatus.WAITING_HUMAN, StepStatus.RUNNING) is True

    def test_waiting_human_to_completed(self) -> None:
        assert is_valid_step_transition(StepStatus.WAITING_HUMAN, StepStatus.COMPLETED) is True

    def test_waiting_human_to_crashed(self) -> None:
        assert is_valid_step_transition(StepStatus.WAITING_HUMAN, StepStatus.CRASHED) is True


# ---------------------------------------------------------------------------
# is_valid_step_transition — invalid transitions
# ---------------------------------------------------------------------------

class TestIsValidStepTransitionInvalid:
    """Invalid step transitions return False."""

    def test_completed_to_running(self) -> None:
        assert is_valid_step_transition(StepStatus.COMPLETED, StepStatus.RUNNING) is False

    def test_completed_to_assigned(self) -> None:
        assert is_valid_step_transition(StepStatus.COMPLETED, StepStatus.ASSIGNED) is False

    def test_completed_to_crashed(self) -> None:
        assert is_valid_step_transition(StepStatus.COMPLETED, StepStatus.CRASHED) is False

    def test_running_to_planned(self) -> None:
        assert is_valid_step_transition(StepStatus.RUNNING, StepStatus.PLANNED) is False

    def test_running_to_blocked(self) -> None:
        assert is_valid_step_transition(StepStatus.RUNNING, StepStatus.BLOCKED) is False

    def test_running_to_assigned(self) -> None:
        assert is_valid_step_transition(StepStatus.RUNNING, StepStatus.ASSIGNED) is False

    def test_crashed_to_running(self) -> None:
        assert is_valid_step_transition(StepStatus.CRASHED, StepStatus.RUNNING) is False

    def test_crashed_to_completed(self) -> None:
        assert is_valid_step_transition(StepStatus.CRASHED, StepStatus.COMPLETED) is False

    def test_assigned_to_planned(self) -> None:
        assert is_valid_step_transition(StepStatus.ASSIGNED, StepStatus.PLANNED) is False

    def test_unknown_status_returns_false(self) -> None:
        assert is_valid_step_transition("nonexistent", StepStatus.ASSIGNED) is False

    def test_planned_to_running(self) -> None:
        assert is_valid_step_transition(StepStatus.PLANNED, StepStatus.RUNNING) is False

    # Story 7.2: waiting_human invalid transitions
    def test_waiting_human_to_assigned(self) -> None:
        assert is_valid_step_transition(StepStatus.WAITING_HUMAN, StepStatus.ASSIGNED) is False

    def test_waiting_human_to_blocked(self) -> None:
        assert is_valid_step_transition(StepStatus.WAITING_HUMAN, StepStatus.BLOCKED) is False


# ---------------------------------------------------------------------------
# validate_step_transition
# ---------------------------------------------------------------------------

class TestValidateStepTransition:
    """validate_step_transition raises ValueError on invalid transitions."""

    def test_valid_transition_does_not_raise(self) -> None:
        validate_step_transition(StepStatus.ASSIGNED, StepStatus.RUNNING)  # no exception

    def test_invalid_transition_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Cannot transition step from 'completed' to 'running'"):
            validate_step_transition(StepStatus.COMPLETED, StepStatus.RUNNING)

    def test_error_message_includes_from_and_to_status(self) -> None:
        with pytest.raises(ValueError, match="Cannot transition step from 'running' to 'planned'"):
            validate_step_transition(StepStatus.RUNNING, StepStatus.PLANNED)

    def test_crashed_to_running_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_step_transition(StepStatus.CRASHED, StepStatus.RUNNING)


# ---------------------------------------------------------------------------
# get_step_event_type — correct mappings
# ---------------------------------------------------------------------------

class TestGetStepEventType:
    """get_step_event_type returns the correct ActivityEventType for each mapping."""

    def test_planned_to_assigned_returns_step_dispatched(self) -> None:
        result = get_step_event_type(StepStatus.PLANNED, StepStatus.ASSIGNED)
        assert result == ActivityEventType.STEP_DISPATCHED

    def test_blocked_to_assigned_returns_step_dispatched(self) -> None:
        result = get_step_event_type(StepStatus.BLOCKED, StepStatus.ASSIGNED)
        assert result == ActivityEventType.STEP_DISPATCHED

    def test_crashed_to_assigned_returns_step_dispatched(self) -> None:
        result = get_step_event_type(StepStatus.CRASHED, StepStatus.ASSIGNED)
        assert result == ActivityEventType.STEP_DISPATCHED

    def test_assigned_to_running_returns_step_started(self) -> None:
        result = get_step_event_type(StepStatus.ASSIGNED, StepStatus.RUNNING)
        assert result == ActivityEventType.STEP_STARTED

    def test_running_to_completed_returns_step_completed(self) -> None:
        result = get_step_event_type(StepStatus.RUNNING, StepStatus.COMPLETED)
        assert result == ActivityEventType.STEP_COMPLETED

    def test_running_to_crashed_returns_system_error(self) -> None:
        result = get_step_event_type(StepStatus.RUNNING, StepStatus.CRASHED)
        assert result == ActivityEventType.SYSTEM_ERROR

    def test_assigned_to_crashed_returns_system_error(self) -> None:
        result = get_step_event_type(StepStatus.ASSIGNED, StepStatus.CRASHED)
        assert result == ActivityEventType.SYSTEM_ERROR

    # Story 7.2: waiting_human event types
    def test_assigned_to_waiting_human_returns_step_dispatched(self) -> None:
        result = get_step_event_type(StepStatus.ASSIGNED, StepStatus.WAITING_HUMAN)
        assert result == ActivityEventType.STEP_DISPATCHED

    def test_waiting_human_to_running_returns_step_started(self) -> None:
        result = get_step_event_type(StepStatus.WAITING_HUMAN, StepStatus.RUNNING)
        assert result == ActivityEventType.STEP_STARTED

    def test_waiting_human_to_completed_returns_step_completed(self) -> None:
        result = get_step_event_type(StepStatus.WAITING_HUMAN, StepStatus.COMPLETED)
        assert result == ActivityEventType.STEP_COMPLETED

    def test_waiting_human_to_crashed_returns_system_error(self) -> None:
        result = get_step_event_type(StepStatus.WAITING_HUMAN, StepStatus.CRASHED)
        assert result == ActivityEventType.SYSTEM_ERROR


# ---------------------------------------------------------------------------
# get_step_event_type — unmapped transitions raise ValueError
# ---------------------------------------------------------------------------

class TestGetStepEventTypeUnmapped:
    """get_step_event_type raises ValueError for transitions without an event mapping."""

    def test_completed_to_running_raises(self) -> None:
        with pytest.raises(ValueError, match="No event type mapping"):
            get_step_event_type(StepStatus.COMPLETED, StepStatus.RUNNING)

    def test_planned_to_blocked_raises(self) -> None:
        # planned->blocked is a valid transition but has no event type mapping
        with pytest.raises(ValueError, match="No event type mapping"):
            get_step_event_type(StepStatus.PLANNED, StepStatus.BLOCKED)

    def test_assigned_to_blocked_raises(self) -> None:
        with pytest.raises(ValueError, match="No event type mapping"):
            get_step_event_type(StepStatus.ASSIGNED, StepStatus.BLOCKED)

    def test_assigned_to_completed_raises(self) -> None:
        # assigned->completed is a valid transition (skip-running shortcut) but has
        # no dedicated event type mapping — callers must not assume all valid
        # transitions have a corresponding event type.
        with pytest.raises(ValueError, match="No event type mapping"):
            get_step_event_type(StepStatus.ASSIGNED, StepStatus.COMPLETED)

    def test_blocked_to_crashed_raises(self) -> None:
        # blocked->crashed is a valid transition but has no event type mapping
        with pytest.raises(ValueError, match="No event type mapping"):
            get_step_event_type(StepStatus.BLOCKED, StepStatus.CRASHED)


# ---------------------------------------------------------------------------
# Parity test: Python STEP_VALID_TRANSITIONS must mirror the Convex spec
# ---------------------------------------------------------------------------

def test_step_valid_transitions_match_convex_spec() -> None:
    """Guard against Python/Convex state machine drift.

    The expected values below are the authoritative Convex STEP_TRANSITIONS table
    from dashboard/convex/steps.ts. This test will fail if either side diverges.
    Updated in Story 7.2 to include waiting_human transitions.
    """
    expected: dict[str, list[str]] = {
        "planned": ["assigned", "blocked"],
        "assigned": ["running", "completed", "crashed", "blocked", "waiting_human"],
        "running": ["completed", "crashed"],
        "completed": [],
        "crashed": ["assigned"],
        "blocked": ["assigned", "crashed"],
        "waiting_human": ["running", "completed", "crashed"],
    }
    # Check all expected states are present in Python dict
    assert set(STEP_VALID_TRANSITIONS.keys()) == set(expected.keys()), (
        f"Key mismatch: Python has {set(STEP_VALID_TRANSITIONS.keys())}, "
        f"expected {set(expected.keys())}"
    )
    # Compare as sets to ignore list ordering
    for state, allowed in expected.items():
        python_allowed = set(STEP_VALID_TRANSITIONS[state])
        expected_allowed = set(allowed)
        assert python_allowed == expected_allowed, (
            f"Mismatch for state '{state}': "
            f"expected {expected_allowed}, got {python_allowed}"
        )
