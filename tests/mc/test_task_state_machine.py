"""Unit tests for task-level state machine transitions (Story 4.6)."""

from __future__ import annotations

from mc.domain.workflow.state_machine import (
    TRANSITION_EVENT_MAP,
    is_valid_transition,
)
from mc.types import ActivityEventType, TaskStatus


class TestReviewTransitions:
    """State machine transitions involving the review status."""

    def test_review_to_in_progress_is_valid(self) -> None:
        """User kick-off: review -> in_progress must be valid."""
        assert is_valid_transition(TaskStatus.REVIEW, TaskStatus.IN_PROGRESS) is True

    def test_review_to_in_progress_event_is_task_started(self) -> None:
        """The kick-off event type must be TASK_STARTED."""
        event = TRANSITION_EVENT_MAP.get((TaskStatus.REVIEW, TaskStatus.IN_PROGRESS))
        assert event == ActivityEventType.TASK_STARTED

    def test_review_to_done_is_valid(self) -> None:
        """HITL approval: review -> done must be valid."""
        assert is_valid_transition(TaskStatus.REVIEW, TaskStatus.DONE) is True

    def test_review_to_inbox_is_valid(self) -> None:
        """Return to lead agent: review -> inbox must be valid."""
        assert is_valid_transition(TaskStatus.REVIEW, TaskStatus.INBOX) is True


# Import UNIVERSAL_TARGETS for reachability check
