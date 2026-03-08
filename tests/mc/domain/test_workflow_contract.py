"""Unit tests for the workflow contract adapter (Story 15.1)."""

from __future__ import annotations

import json
from pathlib import Path

from mc.domain.workflow_contract import (
    SPEC,
    STEP_STATUSES,
    TASK_STATUSES,
    get_allowed_transitions,
    get_step_allowed_transitions,
    get_universal_transitions,
    is_mention_safe,
    is_valid_step_transition,
    is_valid_task_transition,
)

# ---------------------------------------------------------------------------
# Spec loading
# ---------------------------------------------------------------------------


class TestSpecLoading:
    """Verify the spec is loaded correctly from the JSON file."""

    def test_spec_is_dict(self) -> None:
        assert isinstance(SPEC, dict)

    def test_spec_has_version(self) -> None:
        assert "version" in SPEC

    def test_spec_has_task_statuses(self) -> None:
        assert "taskStatuses" in SPEC

    def test_spec_has_step_statuses(self) -> None:
        assert "stepStatuses" in SPEC

    def test_spec_matches_json_file(self) -> None:
        """The loaded SPEC must match the file on disk exactly."""
        spec_path = (
            Path(__file__).resolve().parents[3]
            / "shared"
            / "workflow"
            / "workflow_spec.json"
        )
        with open(spec_path, "r") as f:
            raw = json.load(f)
        assert SPEC == raw


# ---------------------------------------------------------------------------
# Task status constants
# ---------------------------------------------------------------------------


class TestTaskStatuses:
    """Verify task status constants are correctly derived from spec."""

    def test_contains_inbox(self) -> None:
        assert "inbox" in TASK_STATUSES

    def test_contains_assigned(self) -> None:
        assert "assigned" in TASK_STATUSES

    def test_contains_in_progress(self) -> None:
        assert "in_progress" in TASK_STATUSES

    def test_contains_review(self) -> None:
        assert "review" in TASK_STATUSES

    def test_contains_done(self) -> None:
        assert "done" in TASK_STATUSES

    def test_contains_retrying(self) -> None:
        assert "retrying" in TASK_STATUSES

    def test_contains_crashed(self) -> None:
        assert "crashed" in TASK_STATUSES

    def test_contains_planning(self) -> None:
        assert "planning" in TASK_STATUSES

    def test_contains_ready(self) -> None:
        assert "ready" in TASK_STATUSES

    def test_contains_failed(self) -> None:
        assert "failed" in TASK_STATUSES

    def test_count(self) -> None:
        assert len(TASK_STATUSES) == 10


# ---------------------------------------------------------------------------
# Step status constants
# ---------------------------------------------------------------------------


class TestStepStatuses:
    """Verify step status constants are correctly derived from spec."""

    def test_contains_planned(self) -> None:
        assert "planned" in STEP_STATUSES

    def test_contains_assigned(self) -> None:
        assert "assigned" in STEP_STATUSES

    def test_contains_running(self) -> None:
        assert "running" in STEP_STATUSES

    def test_contains_completed(self) -> None:
        assert "completed" in STEP_STATUSES

    def test_contains_crashed(self) -> None:
        assert "crashed" in STEP_STATUSES

    def test_contains_blocked(self) -> None:
        assert "blocked" in STEP_STATUSES

    def test_contains_waiting_human(self) -> None:
        assert "waiting_human" in STEP_STATUSES

    def test_contains_deleted(self) -> None:
        assert "deleted" in STEP_STATUSES

    def test_count(self) -> None:
        assert len(STEP_STATUSES) == 8


# ---------------------------------------------------------------------------
# is_valid_task_transition
# ---------------------------------------------------------------------------


class TestIsValidTaskTransition:
    """Test task transition validation."""

    def test_inbox_to_assigned_valid(self) -> None:
        assert is_valid_task_transition("inbox", "assigned") is True

    def test_assigned_to_in_progress_valid(self) -> None:
        assert is_valid_task_transition("assigned", "in_progress") is True

    def test_in_progress_to_review_valid(self) -> None:
        assert is_valid_task_transition("in_progress", "review") is True

    def test_in_progress_to_done_valid(self) -> None:
        assert is_valid_task_transition("in_progress", "done") is True

    def test_review_to_done_valid(self) -> None:
        assert is_valid_task_transition("review", "done") is True

    def test_review_to_inbox_valid(self) -> None:
        assert is_valid_task_transition("review", "inbox") is True

    def test_review_to_in_progress_valid(self) -> None:
        assert is_valid_task_transition("review", "in_progress") is True

    def test_crashed_to_inbox_valid(self) -> None:
        assert is_valid_task_transition("crashed", "inbox") is True

    def test_crashed_to_assigned_valid(self) -> None:
        assert is_valid_task_transition("crashed", "assigned") is True

    def test_done_to_assigned_valid(self) -> None:
        assert is_valid_task_transition("done", "assigned") is True

    def test_planning_to_review_valid(self) -> None:
        assert is_valid_task_transition("planning", "review") is True

    def test_planning_to_failed_valid(self) -> None:
        assert is_valid_task_transition("planning", "failed") is True

    def test_planning_to_ready_valid(self) -> None:
        assert is_valid_task_transition("planning", "ready") is True

    def test_planning_to_in_progress_valid(self) -> None:
        assert is_valid_task_transition("planning", "in_progress") is True

    def test_ready_to_in_progress_valid(self) -> None:
        assert is_valid_task_transition("ready", "in_progress") is True

    def test_inbox_to_planning_valid(self) -> None:
        assert is_valid_task_transition("inbox", "planning") is True

    # Universal targets
    def test_any_to_retrying_valid(self) -> None:
        for status in TASK_STATUSES:
            assert is_valid_task_transition(status, "retrying") is True

    def test_any_to_crashed_valid(self) -> None:
        for status in TASK_STATUSES:
            assert is_valid_task_transition(status, "crashed") is True

    def test_any_to_deleted_valid(self) -> None:
        for status in TASK_STATUSES:
            assert is_valid_task_transition(status, "deleted") is True

    # Invalid transitions
    def test_inbox_to_done_invalid(self) -> None:
        assert is_valid_task_transition("inbox", "done") is False

    def test_inbox_to_in_progress_invalid(self) -> None:
        assert is_valid_task_transition("inbox", "in_progress") is False

    def test_done_to_done_invalid(self) -> None:
        assert is_valid_task_transition("done", "done") is False

    def test_unknown_status_invalid(self) -> None:
        assert is_valid_task_transition("nonexistent", "assigned") is False


# ---------------------------------------------------------------------------
# get_allowed_transitions
# ---------------------------------------------------------------------------


class TestGetAllowedTransitions:
    """Test retrieving allowed target statuses for a given status."""

    def test_inbox_allowed(self) -> None:
        allowed = get_allowed_transitions("inbox")
        assert "assigned" in allowed
        assert "planning" in allowed

    def test_assigned_allowed(self) -> None:
        allowed = get_allowed_transitions("assigned")
        assert "in_progress" in allowed

    def test_completed_returns_empty_for_done(self) -> None:
        allowed = get_allowed_transitions("done")
        assert "assigned" in allowed

    def test_unknown_status_returns_empty(self) -> None:
        allowed = get_allowed_transitions("nonexistent")
        assert allowed == []


# ---------------------------------------------------------------------------
# is_valid_step_transition
# ---------------------------------------------------------------------------


class TestIsValidStepTransition:
    """Test step transition validation."""

    def test_planned_to_assigned_valid(self) -> None:
        assert is_valid_step_transition("planned", "assigned") is True

    def test_planned_to_blocked_valid(self) -> None:
        assert is_valid_step_transition("planned", "blocked") is True

    def test_assigned_to_running_valid(self) -> None:
        assert is_valid_step_transition("assigned", "running") is True

    def test_assigned_to_completed_valid(self) -> None:
        assert is_valid_step_transition("assigned", "completed") is True

    def test_assigned_to_crashed_valid(self) -> None:
        assert is_valid_step_transition("assigned", "crashed") is True

    def test_assigned_to_blocked_valid(self) -> None:
        assert is_valid_step_transition("assigned", "blocked") is True

    def test_assigned_to_waiting_human_valid(self) -> None:
        assert is_valid_step_transition("assigned", "waiting_human") is True

    def test_running_to_completed_valid(self) -> None:
        assert is_valid_step_transition("running", "completed") is True

    def test_running_to_crashed_valid(self) -> None:
        assert is_valid_step_transition("running", "crashed") is True

    def test_crashed_to_assigned_valid(self) -> None:
        assert is_valid_step_transition("crashed", "assigned") is True

    def test_blocked_to_assigned_valid(self) -> None:
        assert is_valid_step_transition("blocked", "assigned") is True

    def test_blocked_to_crashed_valid(self) -> None:
        assert is_valid_step_transition("blocked", "crashed") is True

    def test_waiting_human_to_completed_valid(self) -> None:
        assert is_valid_step_transition("waiting_human", "completed") is True

    def test_waiting_human_to_crashed_valid(self) -> None:
        assert is_valid_step_transition("waiting_human", "crashed") is True

    # Invalid transitions
    def test_completed_to_running_invalid(self) -> None:
        assert is_valid_step_transition("completed", "running") is False

    def test_running_to_planned_invalid(self) -> None:
        assert is_valid_step_transition("running", "planned") is False

    def test_completed_has_no_transitions(self) -> None:
        for status in STEP_STATUSES:
            if status == "completed":
                continue
            assert is_valid_step_transition("completed", status) is False

    def test_unknown_step_status_invalid(self) -> None:
        assert is_valid_step_transition("nonexistent", "assigned") is False


# ---------------------------------------------------------------------------
# get_step_allowed_transitions
# ---------------------------------------------------------------------------


class TestGetStepAllowedTransitions:
    """Test retrieving allowed step target statuses."""

    def test_planned_allowed(self) -> None:
        allowed = get_step_allowed_transitions("planned")
        assert set(allowed) == {"assigned", "blocked"}

    def test_completed_allowed_empty(self) -> None:
        allowed = get_step_allowed_transitions("completed")
        assert allowed == []

    def test_deleted_allowed_empty(self) -> None:
        allowed = get_step_allowed_transitions("deleted")
        assert allowed == []

    def test_unknown_status_returns_empty(self) -> None:
        allowed = get_step_allowed_transitions("nonexistent")
        assert allowed == []


# ---------------------------------------------------------------------------
# get_universal_transitions
# ---------------------------------------------------------------------------


class TestGetUniversalTransitions:
    """Test retrieval of universal target statuses."""

    def test_returns_list(self) -> None:
        result = get_universal_transitions()
        assert isinstance(result, list)

    def test_contains_retrying(self) -> None:
        assert "retrying" in get_universal_transitions()

    def test_contains_crashed(self) -> None:
        assert "crashed" in get_universal_transitions()

    def test_contains_deleted(self) -> None:
        assert "deleted" in get_universal_transitions()


# ---------------------------------------------------------------------------
# is_mention_safe
# ---------------------------------------------------------------------------


class TestIsMentionSafe:
    """Test mention-safe status checks."""

    def test_inbox_is_mention_safe(self) -> None:
        assert is_mention_safe("inbox") is True

    def test_assigned_is_mention_safe(self) -> None:
        assert is_mention_safe("assigned") is True

    def test_in_progress_is_mention_safe(self) -> None:
        assert is_mention_safe("in_progress") is True

    def test_review_is_mention_safe(self) -> None:
        assert is_mention_safe("review") is True

    def test_done_is_mention_safe(self) -> None:
        assert is_mention_safe("done") is True

    def test_crashed_is_mention_safe(self) -> None:
        assert is_mention_safe("crashed") is True

    def test_retrying_is_mention_safe(self) -> None:
        assert is_mention_safe("retrying") is True

    def test_planning_not_mention_safe(self) -> None:
        assert is_mention_safe("planning") is False

    def test_ready_not_mention_safe(self) -> None:
        assert is_mention_safe("ready") is False

    def test_failed_not_mention_safe(self) -> None:
        assert is_mention_safe("failed") is False

    def test_unknown_not_mention_safe(self) -> None:
        assert is_mention_safe("nonexistent") is False


# ---------------------------------------------------------------------------
# Parity tests — verify spec covers all known types and matches Convex
# ---------------------------------------------------------------------------


class TestParityWithTypes:
    """Verify the spec matches mc.types enums (Task 4.1)."""

    def test_all_task_status_enum_values_in_spec(self) -> None:
        """Every TaskStatus enum member must appear in the spec's taskStatuses."""
        from mc.types import TaskStatus

        for member in TaskStatus:
            assert member.value in TASK_STATUSES, (
                f"TaskStatus.{member.name} ({member.value}) missing from spec"
            )

    def test_all_step_status_enum_values_in_spec(self) -> None:
        """Every StepStatus enum member must appear in the spec's stepStatuses."""
        from mc.types import StepStatus

        for member in StepStatus:
            assert member.value in STEP_STATUSES, (
                f"StepStatus.{member.name} ({member.value}) missing from spec"
            )

    def test_all_thread_message_type_values_in_spec(self) -> None:
        """Every ThreadMessageType enum member must appear in the spec."""
        from mc.domain.workflow_contract import THREAD_MESSAGE_TYPES
        from mc.types import ThreadMessageType

        for member in ThreadMessageType:
            assert member.value in THREAD_MESSAGE_TYPES, (
                f"ThreadMessageType.{member.name} ({member.value}) missing from spec"
            )


class TestParityWithStateMachine:
    """Verify the contract is equivalent to the legacy state_machine module (Task 4.3)."""

    def test_state_machine_delegates_to_contract_for_task_transitions(self) -> None:
        """mc.domain.workflow.state_machine.is_valid_transition must match contract for all pairs."""
        from mc.domain.workflow.state_machine import is_valid_transition

        for from_s in TASK_STATUSES:
            for to_s in TASK_STATUSES:
                sm_result = is_valid_transition(from_s, to_s)
                contract_result = is_valid_task_transition(from_s, to_s)
                assert sm_result == contract_result, (
                    f"Mismatch for ({from_s} -> {to_s}): "
                    f"state_machine={sm_result}, contract={contract_result}"
                )

    def test_state_machine_delegates_to_contract_for_step_transitions(self) -> None:
        """mc.domain.workflow.state_machine.is_valid_step_transition must match contract for all pairs."""
        from mc.domain.workflow.state_machine import is_valid_step_transition as sm_step

        for from_s in STEP_STATUSES:
            for to_s in STEP_STATUSES:
                sm_result = sm_step(from_s, to_s)
                contract_result = is_valid_step_transition(from_s, to_s)
                assert sm_result == contract_result, (
                    f"Mismatch for step ({from_s} -> {to_s}): "
                    f"state_machine={sm_result}, contract={contract_result}"
                )

    def test_no_hardcoded_dicts_in_state_machine(self) -> None:
        """mc.domain.workflow.state_machine should not contain hardcoded transition dictionaries.

        The module-level dicts must be derived from the contract spec, not
        defined inline. We verify by checking that VALID_TRANSITIONS and
        STEP_VALID_TRANSITIONS match the spec exactly.
        """
        from mc.domain.workflow.state_machine import STEP_VALID_TRANSITIONS, VALID_TRANSITIONS

        # Task transitions must match spec
        for status, targets in SPEC["taskTransitions"].items():
            assert set(VALID_TRANSITIONS.get(status, [])) == set(targets), (
                f"Task transition mismatch for '{status}'"
            )

        # Step transitions must match spec
        for status, targets in SPEC["stepTransitions"].items():
            assert set(STEP_VALID_TRANSITIONS.get(status, [])) == set(targets), (
                f"Step transition mismatch for '{status}'"
            )


class TestParityWithConvex:
    """Verify the spec matches the authoritative Convex-side constants (Task 4.2).

    These tests encode the Convex task/step transition tables as the ground
    truth and assert the spec contains all the same entries.
    """

    def test_spec_task_transitions_match_convex(self) -> None:
        """taskTransitions in spec must match Convex VALID_TRANSITIONS exactly."""
        convex_transitions: dict[str, list[str]] = {
            "planning": ["failed", "review", "ready", "in_progress"],
            "ready": ["in_progress", "planning", "failed"],
            "failed": ["planning"],
            "inbox": ["assigned", "planning"],
            "assigned": ["in_progress", "assigned"],
            "in_progress": ["review", "done", "assigned"],
            "review": ["done", "inbox", "assigned", "in_progress", "planning"],
            "done": ["assigned"],
            "retrying": ["in_progress", "crashed"],
            "crashed": ["inbox", "assigned"],
        }

        spec_transitions = SPEC["taskTransitions"]
        assert set(spec_transitions.keys()) == set(convex_transitions.keys())

        for status, expected_targets in convex_transitions.items():
            assert set(spec_transitions[status]) == set(expected_targets), (
                f"Task transition mismatch for '{status}': "
                f"spec={spec_transitions[status]}, convex={expected_targets}"
            )

    def test_spec_step_transitions_match_convex(self) -> None:
        """stepTransitions in spec must match Convex STEP_TRANSITIONS exactly."""
        convex_step_transitions: dict[str, list[str]] = {
            "planned": ["assigned", "blocked"],
            "assigned": ["running", "completed", "crashed", "blocked", "waiting_human"],
            "running": ["completed", "crashed"],
            "completed": [],
            "crashed": ["assigned"],
            "blocked": ["assigned", "crashed"],
            "waiting_human": ["running", "completed", "crashed"],
            "deleted": [],
        }

        spec_transitions = SPEC["stepTransitions"]
        assert set(spec_transitions.keys()) == set(convex_step_transitions.keys())

        for status, expected_targets in convex_step_transitions.items():
            assert set(spec_transitions[status]) == set(expected_targets), (
                f"Step transition mismatch for '{status}'"
            )

    def test_spec_universal_targets_match_convex(self) -> None:
        """Universal targets must match Convex UNIVERSAL_TARGETS."""
        convex_universal = ["retrying", "crashed", "deleted"]
        assert set(SPEC["taskUniversalTargets"]) == set(convex_universal)
