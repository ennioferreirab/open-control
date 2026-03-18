"""Tests for ReviewWorker — review routing, completion detection, post-review transitions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.infrastructure.runtime_context import RuntimeContext
from mc.domain.workflow.review_result import ReviewResult
from mc.runtime.workers.review import ReviewWorker
from mc.types import (
    ActivityEventType,
    AuthorType,
    MessageType,
    ReviewPhase,
    TaskStatus,
    TrustLevel,
)


async def _sync_to_thread(func, *args, **kwargs):
    """Run to_thread payloads synchronously in tests."""
    return func(*args, **kwargs)


def _make_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.update_task_status.return_value = None
    bridge.transition_task_from_snapshot.return_value = {"kind": "applied"}
    bridge.create_activity.return_value = None
    bridge.send_message.return_value = None
    bridge.get_steps_by_task.return_value = []

    def _mutation(name: str, *_args, **_kwargs):
        if name == "runtimeClaims:acquire":
            return {"granted": True, "claimId": "claim-1"}
        return None

    bridge.mutation.side_effect = _mutation

    def _query(name: str, *_args, **_kwargs):
        if name == "executionQuestions:hasPendingForTask":
            return False
        return {"title": "Test Task", "trust_level": "autonomous"}

    bridge.query.side_effect = _query
    return bridge


def _make_ctx(bridge: MagicMock | None = None) -> RuntimeContext:
    if bridge is None:
        bridge = _make_bridge()
    return RuntimeContext(bridge=bridge, agents_dir=Path("/tmp/test-agents"))


class TestHandleReviewTransition:
    """Happy path and error path tests for review transitions."""

    @pytest.mark.asyncio
    async def test_autonomous_no_reviewers_waits_for_explicit_approval(self) -> None:
        bridge = _make_bridge()
        worker = ReviewWorker(_make_ctx(bridge))

        task = {
            "id": "task-1",
            "title": "Done Task",
            "trust_level": TrustLevel.AUTONOMOUS,
            "reviewers": [],
            "awaiting_kickoff": None,
        }

        with patch("mc.runtime.workers.review.asyncio.to_thread", new=_sync_to_thread):
            await worker.handle_review_transition("task-1", task)

        bridge.update_task_status.assert_not_called()
        bridge.create_activity.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_awaiting_kickoff(self) -> None:
        bridge = _make_bridge()
        worker = ReviewWorker(_make_ctx(bridge))

        task = {
            "id": "task-1",
            "title": "Kickoff Task",
            "awaiting_kickoff": True,
        }

        with patch("mc.runtime.workers.review.asyncio.to_thread", new=_sync_to_thread):
            await worker.handle_review_transition("task-1", task)

        bridge.update_task_status.assert_not_called()
        bridge.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_task_with_pending_ask_user(self) -> None:
        bridge = _make_bridge()
        registry = MagicMock()
        registry.has_pending_ask.return_value = True
        worker = ReviewWorker(_make_ctx(bridge), ask_user_registry=registry)

        task = {
            "id": "task-1",
            "title": "Ask User Task",
            "awaiting_kickoff": None,
        }

        with patch("mc.runtime.workers.review.asyncio.to_thread", new=_sync_to_thread):
            await worker.handle_review_transition("task-1", task)

        bridge.update_task_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_paused_task_with_steps_not_auto_completed(self) -> None:
        """Story 7.4: paused tasks with steps must not auto-complete."""
        bridge = _make_bridge()
        bridge.get_steps_by_task.return_value = [
            {"id": "step-1", "status": "completed"},
            {"id": "step-2", "status": "assigned"},
        ]
        worker = ReviewWorker(_make_ctx(bridge))

        task = {
            "id": "task-1",
            "title": "Paused Task",
            "trust_level": TrustLevel.AUTONOMOUS,
            "reviewers": [],
            "awaiting_kickoff": None,
            "review_phase": ReviewPhase.EXECUTION_PAUSE,
        }

        with patch("mc.runtime.workers.review.asyncio.to_thread", new=_sync_to_thread):
            await worker.handle_review_transition("task-1", task)

        bridge.update_task_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_final_approval_with_steps_still_routes_to_reviewers(self) -> None:
        bridge = _make_bridge()
        bridge.get_steps_by_task.return_value = [
            {"id": "step-1", "status": "completed"},
            {"id": "step-2", "status": "completed"},
        ]
        worker = ReviewWorker(_make_ctx(bridge))
        worker._run_reviewer_agent = AsyncMock(  # type: ignore[attr-defined]
            return_value=ReviewResult(
                verdict="approved",
                issues=[],
                strengths=["Looks good"],
                scores={"overall": 0.98},
                vetoes_triggered=[],
                recommended_return_step=None,
            )
        )

        task = {
            "id": "task-1",
            "title": "Final Approval Task",
            "trust_level": TrustLevel.AUTONOMOUS,
            "reviewers": ["reviewer-bot"],
            "awaiting_kickoff": None,
            "review_phase": ReviewPhase.FINAL_APPROVAL,
        }

        with patch("mc.runtime.workers.review.asyncio.to_thread", new=_sync_to_thread):
            await worker.handle_review_transition("task-1", task)

        worker._run_reviewer_agent.assert_awaited_once_with("task-1", task, "reviewer-bot")  # type: ignore[attr-defined]
        assert bridge.send_message.call_count == 2
        assert bridge.create_activity.call_count >= 1

    @pytest.mark.asyncio
    async def test_manual_review_task_not_auto_completed(self) -> None:
        """Manual review tasks must wait for explicit user action."""
        bridge = _make_bridge()
        worker = ReviewWorker(_make_ctx(bridge))

        task = {
            "id": "task-1",
            "title": "Manual Review Task",
            "trust_level": TrustLevel.AUTONOMOUS,
            "reviewers": [],
            "awaiting_kickoff": None,
            "is_manual": True,
        }

        with patch("mc.runtime.workers.review.asyncio.to_thread", new=_sync_to_thread):
            await worker.handle_review_transition("task-1", task)

        bridge.update_task_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_routes_to_reviewers(self) -> None:
        bridge = _make_bridge()
        worker = ReviewWorker(_make_ctx(bridge))
        worker._run_reviewer_agent = AsyncMock(  # type: ignore[attr-defined]
            return_value=ReviewResult(
                verdict="approved",
                issues=[],
                strengths=["Looks good"],
                scores={"overall": 0.98},
                vetoes_triggered=[],
                recommended_return_step=None,
            )
        )

        task = {
            "id": "task-1",
            "title": "Review Task",
            "trust_level": TrustLevel.AUTONOMOUS,
            "reviewers": ["reviewer-bot"],
            "awaiting_kickoff": None,
        }

        with patch("mc.runtime.workers.review.asyncio.to_thread", new=_sync_to_thread):
            await worker.handle_review_transition("task-1", task)

        worker._run_reviewer_agent.assert_awaited_once_with("task-1", task, "reviewer-bot")  # type: ignore[attr-defined]
        review_requested = [
            call for call in bridge.create_activity.call_args_list if call.args[0] == ActivityEventType.REVIEW_REQUESTED
        ]
        assert len(review_requested) == 1
        assert any("reviewer-bot" in call.args[3] for call in bridge.send_message.call_args_list)

    @pytest.mark.asyncio
    async def test_reviewer_approval_executes_and_completes_task(self) -> None:
        bridge = _make_bridge()
        worker = ReviewWorker(_make_ctx(bridge))
        worker._run_reviewer_agent = AsyncMock(  # type: ignore[attr-defined]
            return_value=ReviewResult(
                verdict="approved",
                issues=[],
                strengths=["Looks good"],
                scores={"overall": 0.98},
                vetoes_triggered=[],
                recommended_return_step=None,
            )
        )

        task = {
            "id": "task-1",
            "title": "Review Task",
            "trust_level": TrustLevel.AUTONOMOUS,
            "reviewers": ["reviewer-bot"],
            "assigned_agent": "writer-bot",
            "awaiting_kickoff": None,
            "review_phase": ReviewPhase.FINAL_APPROVAL,
        }

        with patch("mc.runtime.workers.review.asyncio.to_thread", new=_sync_to_thread):
            await worker.handle_review_transition("task-1", task)

        worker._run_reviewer_agent.assert_awaited_once_with("task-1", task, "reviewer-bot")  # type: ignore[attr-defined]
        bridge.update_task_status.assert_called_once_with("task-1", TaskStatus.DONE, "reviewer-bot")

    @pytest.mark.asyncio
    async def test_reviewer_rejection_posts_feedback_and_reassigns_executor(self) -> None:
        bridge = _make_bridge()
        worker = ReviewWorker(_make_ctx(bridge))
        worker._run_reviewer_agent = AsyncMock(  # type: ignore[attr-defined]
            return_value=ReviewResult(
                verdict="rejected",
                issues=["Fix alignment"],
                strengths=[],
                scores={"overall": 0.41},
                vetoes_triggered=["alignment"],
                recommended_return_step=None,
            )
        )

        task = {
            "id": "task-1",
            "title": "Review Task",
            "trust_level": TrustLevel.AUTONOMOUS,
            "reviewers": ["reviewer-bot"],
            "assigned_agent": "writer-bot",
            "awaiting_kickoff": None,
            "review_phase": ReviewPhase.FINAL_APPROVAL,
            "state_version": 4,
            "status": TaskStatus.REVIEW,
        }

        with patch("mc.runtime.workers.review.asyncio.to_thread", new=_sync_to_thread):
            await worker.handle_review_transition("task-1", task)

        worker._run_reviewer_agent.assert_awaited_once_with("task-1", task, "reviewer-bot")  # type: ignore[attr-defined]
        bridge.transition_task_from_snapshot.assert_called_once()
        transition_args = bridge.transition_task_from_snapshot.call_args
        assert transition_args.args[0] == task
        assert transition_args.args[1] == TaskStatus.ASSIGNED
        assert transition_args.kwargs["agent_name"] == "writer-bot"
        assert any(
            call.args[4] == MessageType.REVIEW_FEEDBACK and "Fix alignment" in call.args[3]
            for call in bridge.send_message.call_args_list
        )
        bridge.update_task_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_human_approved_no_reviewers_requests_hitl(self) -> None:
        bridge = _make_bridge()
        worker = ReviewWorker(_make_ctx(bridge))

        task = {
            "id": "task-1",
            "title": "HITL Task",
            "trust_level": TrustLevel.HUMAN_APPROVED,
            "reviewers": [],
            "awaiting_kickoff": None,
        }

        with patch("mc.runtime.workers.review.asyncio.to_thread", new=_sync_to_thread):
            await worker.handle_review_transition("task-1", task)

        bridge.create_activity.assert_called_once()
        act_args = bridge.create_activity.call_args[0]
        assert act_args[0] == ActivityEventType.HITL_REQUESTED


class TestSendAgentMessage:
    @pytest.mark.asyncio
    async def test_sends_message(self) -> None:
        bridge = _make_bridge()
        bridge.send_message.return_value = "msg-id"
        worker = ReviewWorker(_make_ctx(bridge))

        with patch("mc.runtime.workers.review.asyncio.to_thread", new=_sync_to_thread):
            result = await worker.send_agent_message("task-1", "nanobot", "Hello")

        assert result == "msg-id"
        bridge.send_message.assert_called_once_with(
            "task-1", "nanobot", AuthorType.AGENT, "Hello", MessageType.WORK
        )


class TestHandleReviewFeedback:
    @pytest.mark.asyncio
    async def test_sends_feedback_and_creates_activity(self) -> None:
        bridge = _make_bridge()
        worker = ReviewWorker(_make_ctx(bridge))

        with patch("mc.runtime.workers.review.asyncio.to_thread", new=_sync_to_thread):
            await worker.handle_review_feedback("task-1", "reviewer-bot", "Needs changes")

        bridge.send_message.assert_called_once()
        msg_args = bridge.send_message.call_args[0]
        assert msg_args[3] == "Needs changes"
        assert msg_args[4] == MessageType.REVIEW_FEEDBACK

        bridge.create_activity.assert_called_once()
        act_args = bridge.create_activity.call_args[0]
        assert act_args[0] == ActivityEventType.REVIEW_FEEDBACK


class TestHandleReviewApproval:
    @pytest.mark.asyncio
    async def test_agent_reviewed_completes_task(self) -> None:
        bridge = _make_bridge()
        bridge.query.return_value = {
            "title": "Test",
            "trust_level": TrustLevel.AUTONOMOUS,
        }
        worker = ReviewWorker(_make_ctx(bridge))

        with patch("mc.runtime.workers.review.asyncio.to_thread", new=_sync_to_thread):
            await worker.handle_review_approval("task-1", "reviewer-bot")

        bridge.update_task_status.assert_called_once_with("task-1", TaskStatus.DONE, "reviewer-bot")

    @pytest.mark.asyncio
    async def test_human_approved_requests_hitl(self) -> None:
        bridge = _make_bridge()
        bridge.query.side_effect = lambda name, *_args, **_kwargs: (
            False
            if name == "executionQuestions:hasPendingForTask"
            else {"title": "Test", "trust_level": TrustLevel.HUMAN_APPROVED}
        )
        worker = ReviewWorker(_make_ctx(bridge))

        with patch("mc.runtime.workers.review.asyncio.to_thread", new=_sync_to_thread):
            await worker.handle_review_approval("task-1", "reviewer-bot")

        bridge.update_task_status.assert_not_called()
        # Should send system message about HITL
        assert bridge.send_message.call_count == 2  # approval + hitl message
        hitl_activities = [
            c
            for c in bridge.create_activity.call_args_list
            if c[0][0] == ActivityEventType.HITL_REQUESTED
        ]
        assert len(hitl_activities) == 1


class TestReviewWorkerProcessBatch:
    """Tests for batch deduplication."""

    @pytest.mark.asyncio
    async def test_deduplicates_tasks(self) -> None:
        bridge = _make_bridge()
        worker = ReviewWorker(_make_ctx(bridge))

        tasks = [
            {
                "id": "task-1",
                "title": "Review",
                "trust_level": TrustLevel.AUTONOMOUS,
                "reviewers": [],
                "awaiting_kickoff": None,
            },
            {
                "id": "task-1",
                "title": "Review",
                "trust_level": TrustLevel.AUTONOMOUS,
                "reviewers": [],
                "awaiting_kickoff": None,
            },
        ]

        with patch("mc.runtime.workers.review.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_batch(tasks)

        assert bridge.update_task_status.call_count == 0
        assert worker._known_review_task_ids == {"task-1"}

    @pytest.mark.asyncio
    async def test_prunes_stale_ids(self) -> None:
        bridge = _make_bridge()
        worker = ReviewWorker(_make_ctx(bridge))

        task = {
            "id": "task-1",
            "title": "Review",
            "trust_level": TrustLevel.AUTONOMOUS,
            "reviewers": [],
            "awaiting_kickoff": None,
        }

        with patch("mc.runtime.workers.review.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_batch([task])
            assert bridge.update_task_status.call_count == 0

            await worker.process_batch([])  # task leaves review
            await worker.process_batch([task])  # re-enters
            assert bridge.update_task_status.call_count == 0
