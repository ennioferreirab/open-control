"""Integration test: full review workflow driven by real workers against Convex.

Flow tested (workers drive every transition after initial setup):
  1. TaskExecutor picks up assigned task → in_progress → executes → review
  2. ReviewWorker runs reviewer → rejection → assigned (back to original agent)
  3. TaskExecutor picks up re-assigned task → in_progress → re-executes → review
  4. ReviewWorker runs reviewer → approval → done

Only LLM execution is mocked (ExecutionEngine strategy + reviewer agent).
All state transitions, messages, activities, and runtime claims go through real Convex.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from mc.application.execution.request import ExecutionResult, RunnerType
from mc.application.execution.strategies.base import RunnerStrategy
from mc.contexts.execution.executor import TaskExecutor
from mc.domain.workflow.review_result import ReviewResult
from mc.infrastructure.runtime_context import RuntimeContext
from mc.runtime.workers.review import ReviewWorker
from mc.types import (
    ActivityEventType,
    MessageType,
    TaskStatus,
    TrustLevel,
)
from tests.mc.integration.conftest import requires_convex

logger = logging.getLogger(__name__)


def _save_fixture(
    output_dir: Path, label: str, task: dict, messages: list, activities: list
) -> None:
    """Save a checkpoint fixture to disk."""
    fixture = {
        "label": label,
        "task": task,
        "messages": messages,
        "activities": activities,
    }
    path = output_dir / f"review_workflow_{label}.json"
    path.write_text(json.dumps(fixture, indent=2, default=str))
    logger.info("Saved fixture: %s", path)


def _get_task_activities(bridge: Any, task_id: str) -> list[dict]:
    """Fetch recent activities filtered to a specific task."""
    all_activities = bridge.query("activities:listRecent", {}) or []
    return [a for a in all_activities if a.get("task_id") == task_id]


class _FakeStrategy(RunnerStrategy):
    """Strategy that returns a canned success result without calling any LLM."""

    def __init__(self, output: str = "Work completed.") -> None:
        self._output = output

    async def execute(self, request: Any) -> ExecutionResult:
        return ExecutionResult(success=True, output=self._output)


@pytest.mark.integration
@requires_convex
class TestReviewWorkflowIntegration:
    """End-to-end review workflow: execution → rejection → re-execution → approval.

    Workers drive every transition after initial setup. Only LLM execution is mocked.
    """

    @pytest.fixture(autouse=True)
    def _setup_output(self, fixture_output_dir: Path) -> None:
        self._fixture_dir = fixture_output_dir

    @pytest.mark.timeout(45)
    async def test_full_review_cycle(self, real_bridge: Any, default_board_id: str) -> None:
        """Full worker-driven cycle: assigned → review → rejected → assigned → review → done."""
        bridge = real_bridge
        task_id: str | None = None

        try:
            # ── SETUP: Create task in assigned status ─────────────────────
            task_id = bridge.mutation(
                "tasks:create",
                {
                    "title": "[TEST] Review workflow integration",
                    "description": "Integration test for review workflow",
                    "assigned_agent": "test-writer",
                    "trust_level": TrustLevel.AUTONOMOUS,
                    "reviewers": ["test-reviewer"],
                    "board_id": default_board_id,
                },
            )
            assert task_id, "Task creation must return an ID"
            logger.info("Created test task: %s", task_id)

            # Move to assigned (inbox → assigned is done by InboxWorker which
            # requires LLM for auto-titling/routing — skip that for setup)
            bridge.update_task_status(task_id, TaskStatus.ASSIGNED, "test-writer")

            # ── PHASE 1: TaskExecutor picks up → in_progress → review ────
            executor = TaskExecutor(bridge)
            # Mock only the execution engine strategy — everything else is real
            fake_engine_strategies = {RunnerType.NANOBOT: _FakeStrategy("Work completed.")}
            executor._build_execution_engine = lambda: __import__(  # type: ignore[assignment]
                "mc.application.execution.engine", fromlist=["ExecutionEngine"]
            ).ExecutionEngine(strategies=fake_engine_strategies, post_execution_hooks=[])

            assigned_snapshot = bridge.query("tasks:getById", {"task_id": task_id})
            assert assigned_snapshot is not None
            await executor._pickup_task(assigned_snapshot)

            # Verify: task should be in review now
            task_after_exec = bridge.query("tasks:getById", {"task_id": task_id})
            assert task_after_exec is not None
            assert task_after_exec["status"] == TaskStatus.REVIEW, (
                f"Expected 'review' after execution, got '{task_after_exec['status']}'"
            )
            assert task_after_exec.get("review_phase") == "final_approval"

            # Verify executor posted system event + work message
            messages_after_exec = bridge.get_task_messages(task_id)
            system_events = [
                m for m in messages_after_exec if m.get("message_type") == MessageType.SYSTEM_EVENT
            ]
            assert any("started work" in m["content"] for m in system_events), (
                "Expected 'started work' system event from executor pickup"
            )
            work_msgs = [
                m for m in messages_after_exec if m.get("message_type") == MessageType.WORK
            ]
            assert len(work_msgs) >= 1, "Expected work message from executor"

            _save_fixture(
                self._fixture_dir,
                "01_after_first_execution",
                task_after_exec,
                messages_after_exec,
                _get_task_activities(bridge, task_id),
            )

            # ── PHASE 2: ReviewWorker picks up → rejection → assigned ────
            ctx = RuntimeContext(bridge=bridge, agents_dir=Path("/tmp/test-agents"))
            worker = ReviewWorker(ctx)

            rejected_result = ReviewResult(
                verdict="rejected",
                issues=["Variable naming is inconsistent", "Missing error handling in parser"],
                strengths=["Good test coverage"],
                scores={"readability": 0.4, "correctness": 0.6},
                vetoes_triggered=["naming_convention"],
                recommended_return_step=None,
            )
            worker._run_reviewer_agent = AsyncMock(return_value=rejected_result)

            review_snapshot = bridge.query("tasks:getById", {"task_id": task_id})
            assert review_snapshot is not None
            await worker.process_batch([review_snapshot])

            # Verify: task returned to assigned with original agent preserved
            task_after_reject = bridge.query("tasks:getById", {"task_id": task_id})
            assert task_after_reject is not None
            assert task_after_reject["status"] == TaskStatus.ASSIGNED, (
                f"Expected 'assigned' after rejection, got '{task_after_reject['status']}'"
            )
            assert task_after_reject.get("assigned_agent") == "test-writer", (
                "assigned_agent must be preserved after rejection"
            )

            # Verify review messages
            messages_after_reject = bridge.get_task_messages(task_id)
            feedback_msgs = [
                m
                for m in messages_after_reject
                if m.get("message_type") == MessageType.REVIEW_FEEDBACK
            ]
            assert len(feedback_msgs) >= 1, "Expected review_feedback message"
            assert "Variable naming is inconsistent" in feedback_msgs[0]["content"]
            assert "Missing error handling in parser" in feedback_msgs[0]["content"]

            review_system_msgs = [
                m
                for m in messages_after_reject
                if m.get("message_type") == MessageType.SYSTEM_EVENT
                and "test-reviewer" in m.get("content", "")
            ]
            assert len(review_system_msgs) >= 1, "Expected system_event about review request"

            _save_fixture(
                self._fixture_dir,
                "02_after_rejection",
                task_after_reject,
                messages_after_reject,
                _get_task_activities(bridge, task_id),
            )

            # ── PHASE 3: TaskExecutor picks up re-assigned task ──────────
            # Worker drives: assigned → in_progress → review (again)
            executor._known_assigned_ids.clear()
            fake_engine_strategies[RunnerType.NANOBOT] = _FakeStrategy(
                "Revision completed: addressed naming and error handling issues."
            )

            assigned_snapshot_2 = bridge.query("tasks:getById", {"task_id": task_id})
            assert assigned_snapshot_2 is not None
            assert assigned_snapshot_2["status"] == TaskStatus.ASSIGNED
            await executor._pickup_task(assigned_snapshot_2)

            # Verify: task is back in review
            task_after_reexec = bridge.query("tasks:getById", {"task_id": task_id})
            assert task_after_reexec is not None
            assert task_after_reexec["status"] == TaskStatus.REVIEW, (
                f"Expected 'review' after re-execution, got '{task_after_reexec['status']}'"
            )

            # Verify second execution posted new work message
            messages_after_reexec = bridge.get_task_messages(task_id)
            work_msgs_2 = [
                m for m in messages_after_reexec if m.get("message_type") == MessageType.WORK
            ]
            assert len(work_msgs_2) >= 2, "Expected at least 2 work messages (initial + revision)"
            assert any("Revision completed" in m["content"] for m in work_msgs_2)

            _save_fixture(
                self._fixture_dir,
                "03_after_re_execution",
                task_after_reexec,
                messages_after_reexec,
                _get_task_activities(bridge, task_id),
            )

            # ── PHASE 4: ReviewWorker picks up → approval → done ─────────
            worker._known_review_task_ids.clear()

            approved_result = ReviewResult(
                verdict="approved",
                issues=[],
                strengths=["All issues addressed", "Clean implementation"],
                scores={"readability": 0.9, "correctness": 0.95},
                vetoes_triggered=[],
                recommended_return_step=None,
            )
            worker._run_reviewer_agent = AsyncMock(return_value=approved_result)

            review_snapshot_2 = bridge.query("tasks:getById", {"task_id": task_id})
            assert review_snapshot_2 is not None
            await worker.process_batch([review_snapshot_2])

            # Verify: task is done
            task_after_approve = bridge.query("tasks:getById", {"task_id": task_id})
            assert task_after_approve is not None
            assert task_after_approve["status"] == TaskStatus.DONE, (
                f"Expected 'done' after approval, got '{task_after_approve['status']}'"
            )

            # Verify approval message
            messages_final = bridge.get_task_messages(task_id)
            approval_msgs = [
                m for m in messages_final if m.get("message_type") == MessageType.APPROVAL
            ]
            assert len(approval_msgs) >= 1, "Expected approval message"
            assert any("test-reviewer" in m["content"] for m in approval_msgs)

            # Verify complete message type sequence across full cycle
            msg_types = [m.get("message_type") for m in messages_final]
            assert MessageType.SYSTEM_EVENT in msg_types
            assert MessageType.WORK in msg_types
            assert MessageType.REVIEW_FEEDBACK in msg_types
            assert MessageType.APPROVAL in msg_types

            # Verify activity trail covers full lifecycle
            final_activities = _get_task_activities(bridge, task_id)
            activity_types = {a.get("event_type") for a in final_activities}
            assert ActivityEventType.REVIEW_REQUESTED in activity_types, (
                f"Missing review_requested. Got: {activity_types}"
            )
            assert ActivityEventType.REVIEW_APPROVED in activity_types, (
                f"Missing review_approved. Got: {activity_types}"
            )
            assert ActivityEventType.REVIEW_FEEDBACK in activity_types, (
                f"Missing review_feedback. Got: {activity_types}"
            )

            _save_fixture(
                self._fixture_dir,
                "04_after_approval",
                task_after_approve,
                messages_final,
                final_activities,
            )

        finally:
            # ── CLEANUP ────────────────────────────────────────────────────
            if task_id:
                try:
                    bridge.mutation("tasks:softDelete", {"task_id": task_id})
                    logger.info("Cleaned up test task: %s", task_id)
                except Exception as exc:
                    logger.warning("Failed to clean up test task %s: %s", task_id, exc)
