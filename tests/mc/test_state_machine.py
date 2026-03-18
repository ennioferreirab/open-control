"""Tests for the task state machine module."""

import pytest

from mc.domain.workflow.state_machine import (
    get_event_type,
    is_valid_transition,
    validate_transition,
)
from mc.types import ActivityEventType, TaskStatus

# --- is_valid_transition tests ---


class TestIsValidTransition:
    """Test all valid forward transitions."""

    def test_inbox_to_assigned(self) -> None:
        assert is_valid_transition(TaskStatus.INBOX, TaskStatus.ASSIGNED) is True

    def test_assigned_to_in_progress(self) -> None:
        assert is_valid_transition(TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS) is True

    def test_in_progress_to_review(self) -> None:
        assert is_valid_transition(TaskStatus.IN_PROGRESS, TaskStatus.REVIEW) is True

    def test_in_progress_to_done(self) -> None:
        assert is_valid_transition(TaskStatus.IN_PROGRESS, TaskStatus.DONE) is True

    def test_review_to_done(self) -> None:
        assert is_valid_transition(TaskStatus.REVIEW, TaskStatus.DONE) is True

    def test_crashed_to_inbox(self) -> None:
        assert is_valid_transition(TaskStatus.CRASHED, TaskStatus.INBOX) is True

    def test_review_to_inbox(self) -> None:
        assert is_valid_transition(TaskStatus.REVIEW, TaskStatus.INBOX) is True


class TestUniversalTransitions:
    """Test universal transitions (retrying/crashed from any state)."""

    @pytest.mark.parametrize(
        "source",
        [
            TaskStatus.INBOX,
            TaskStatus.ASSIGNED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.REVIEW,
            TaskStatus.DONE,
            TaskStatus.RETRYING,
            TaskStatus.CRASHED,
        ],
    )
    def test_any_to_retrying(self, source: str) -> None:
        assert is_valid_transition(source, TaskStatus.RETRYING) is True

    @pytest.mark.parametrize(
        "source",
        [
            TaskStatus.INBOX,
            TaskStatus.ASSIGNED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.REVIEW,
            TaskStatus.DONE,
            TaskStatus.RETRYING,
            TaskStatus.CRASHED,
        ],
    )
    def test_any_to_crashed(self, source: str) -> None:
        assert is_valid_transition(source, TaskStatus.CRASHED) is True


class TestInvalidTransitions:
    """Test that backward and illegal transitions are rejected."""

    def test_inbox_to_in_progress_is_valid(self) -> None:
        assert is_valid_transition(TaskStatus.INBOX, TaskStatus.IN_PROGRESS) is True

    def test_inbox_to_done(self) -> None:
        assert is_valid_transition(TaskStatus.INBOX, TaskStatus.DONE) is False

    def test_assigned_to_inbox(self) -> None:
        assert is_valid_transition(TaskStatus.ASSIGNED, TaskStatus.INBOX) is False

    def test_assigned_to_review(self) -> None:
        assert is_valid_transition(TaskStatus.ASSIGNED, TaskStatus.REVIEW) is False

    def test_in_progress_to_inbox(self) -> None:
        assert is_valid_transition(TaskStatus.IN_PROGRESS, TaskStatus.INBOX) is False

    def test_in_progress_to_assigned(self) -> None:
        # in_progress -> assigned is valid (Convex authoritative, Story 15.1 reconciliation)
        assert is_valid_transition(TaskStatus.IN_PROGRESS, TaskStatus.ASSIGNED) is True

    def test_review_to_in_progress(self) -> None:
        assert is_valid_transition(TaskStatus.REVIEW, TaskStatus.IN_PROGRESS) is True

    def test_done_to_inbox(self) -> None:
        assert is_valid_transition(TaskStatus.DONE, TaskStatus.INBOX) is False

    def test_done_to_assigned(self) -> None:
        # done -> assigned is valid (Convex authoritative, Story 15.1 reconciliation)
        assert is_valid_transition(TaskStatus.DONE, TaskStatus.ASSIGNED) is True

    def test_done_to_in_progress(self) -> None:
        assert is_valid_transition(TaskStatus.DONE, TaskStatus.IN_PROGRESS) is False

    def test_done_to_review(self) -> None:
        assert is_valid_transition(TaskStatus.DONE, TaskStatus.REVIEW) is False


# --- validate_transition tests ---


class TestValidateTransition:
    """Test that validate_transition raises on invalid and passes on valid."""

    def test_valid_transition_does_not_raise(self) -> None:
        validate_transition(TaskStatus.INBOX, TaskStatus.ASSIGNED)

    def test_invalid_transition_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Cannot transition from 'done' to 'inbox'"):
            validate_transition(TaskStatus.DONE, TaskStatus.INBOX)

    def test_universal_target_does_not_raise(self) -> None:
        validate_transition(TaskStatus.DONE, TaskStatus.CRASHED)

    def test_error_message_format(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            validate_transition(TaskStatus.DONE, TaskStatus.IN_PROGRESS)
        assert "Cannot transition from 'done' to 'in_progress'" in str(exc_info.value)


# --- get_event_type tests ---


class TestGetEventType:
    """Test activity event type mapping for transitions."""

    def test_inbox_to_assigned(self) -> None:
        assert (
            get_event_type(TaskStatus.INBOX, TaskStatus.ASSIGNED) == ActivityEventType.TASK_ASSIGNED
        )

    def test_assigned_to_in_progress(self) -> None:
        assert (
            get_event_type(TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS)
            == ActivityEventType.TASK_STARTED
        )

    def test_in_progress_to_review(self) -> None:
        assert (
            get_event_type(TaskStatus.IN_PROGRESS, TaskStatus.REVIEW)
            == ActivityEventType.REVIEW_REQUESTED
        )

    def test_in_progress_to_done(self) -> None:
        assert (
            get_event_type(TaskStatus.IN_PROGRESS, TaskStatus.DONE)
            == ActivityEventType.TASK_COMPLETED
        )

    def test_review_to_done(self) -> None:
        assert (
            get_event_type(TaskStatus.REVIEW, TaskStatus.DONE) == ActivityEventType.TASK_COMPLETED
        )

    def test_crashed_to_inbox(self) -> None:
        assert (
            get_event_type(TaskStatus.CRASHED, TaskStatus.INBOX) == ActivityEventType.TASK_RETRYING
        )

    def test_any_to_retrying(self) -> None:
        assert (
            get_event_type(TaskStatus.IN_PROGRESS, TaskStatus.RETRYING)
            == ActivityEventType.TASK_RETRYING
        )

    def test_any_to_crashed(self) -> None:
        assert (
            get_event_type(TaskStatus.ASSIGNED, TaskStatus.CRASHED)
            == ActivityEventType.TASK_CRASHED
        )

    def test_unmapped_transition_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="No event type mapping"):
            get_event_type(TaskStatus.DONE, TaskStatus.INBOX)
