"""Tests for RuntimeContext adoption across workers (Story 20.3).

Verifies that all workers accept RuntimeContext instead of bare bridge,
and that they correctly access bridge and services via the context.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.infrastructure.runtime_context import RuntimeContext
from mc.workers.inbox import InboxWorker
from mc.workers.kickoff import KickoffResumeWorker
from mc.workers.planning import PlanningWorker
from mc.workers.review import ReviewWorker


async def _sync_to_thread(func, *args, **kwargs):
    """Run to_thread payloads synchronously in tests."""
    return func(*args, **kwargs)


def _make_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.update_task_status.return_value = None
    bridge.mutation.return_value = None
    bridge.create_activity.return_value = None
    bridge.create_task_directory.return_value = None
    bridge.list_agents.return_value = []
    bridge.update_execution_plan.return_value = None
    bridge.batch_create_steps.return_value = ["step-1"]
    bridge.kick_off_task.return_value = None
    bridge.send_message.return_value = None
    bridge.get_steps_by_task.return_value = []
    bridge.query.return_value = {"title": "Test Task", "trust_level": "autonomous"}
    return bridge


def _make_ctx(bridge: MagicMock | None = None) -> RuntimeContext:
    """Create a RuntimeContext with a mock bridge."""
    if bridge is None:
        bridge = _make_bridge()
    return RuntimeContext(
        bridge=bridge,
        agents_dir=Path("/tmp/test-agents"),
        admin_key="test-admin-key",
        admin_url="http://localhost:3210",
    )


class TestInboxWorkerAcceptsRuntimeContext:
    """InboxWorker must accept RuntimeContext as its sole constructor arg."""

    def test_constructor_accepts_runtime_context(self) -> None:
        ctx = _make_ctx()
        worker = InboxWorker(ctx)
        assert worker._ctx is ctx
        assert worker._bridge is ctx.bridge

    @pytest.mark.asyncio
    async def test_process_task_uses_bridge_from_context(self) -> None:
        bridge = _make_bridge()
        ctx = _make_ctx(bridge)
        worker = InboxWorker(ctx)

        task = {
            "id": "task-1",
            "title": "Do something",
            "description": "Details",
            "assigned_agent": None,
            "is_manual": False,
        }

        with patch("mc.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        bridge.update_task_status.assert_called_once_with("task-1", "planning")


class TestPlanningWorkerAcceptsRuntimeContext:
    """PlanningWorker must accept RuntimeContext as its constructor arg."""

    def test_constructor_accepts_runtime_context(self) -> None:
        ctx = _make_ctx()
        materializer = MagicMock()
        dispatcher = MagicMock()
        worker = PlanningWorker(ctx, materializer, dispatcher)
        assert worker._ctx is ctx
        assert worker._bridge is ctx.bridge

    @pytest.mark.asyncio
    async def test_process_task_uses_bridge_from_context(self) -> None:
        bridge = _make_bridge()
        bridge.list_agents.return_value = []
        ctx = _make_ctx(bridge)
        materializer = MagicMock()
        materializer.materialize.return_value = ["step-1"]
        dispatcher = MagicMock()
        dispatcher.dispatch_steps = AsyncMock()
        worker = PlanningWorker(ctx, materializer, dispatcher)

        task = {
            "id": "task-1",
            "title": "Plan task",
            "description": "Plan this",
            "assigned_agent": None,
            "supervision_mode": "autonomous",
            "status": "planning",
            "trust_level": "autonomous",
            "is_manual": True,
            "files": [],
        }

        with patch("mc.workers.planning.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        bridge.create_task_directory.assert_called_once_with("task-1")


class TestReviewWorkerAcceptsRuntimeContext:
    """ReviewWorker must accept RuntimeContext as its constructor arg."""

    def test_constructor_accepts_runtime_context(self) -> None:
        ctx = _make_ctx()
        worker = ReviewWorker(ctx)
        assert worker._ctx is ctx
        assert worker._bridge is ctx.bridge

    @pytest.mark.asyncio
    async def test_process_task_uses_bridge_from_context(self) -> None:
        bridge = _make_bridge()
        ctx = _make_ctx(bridge)
        worker = ReviewWorker(ctx)

        task = {
            "id": "task-1",
            "title": "Done Task",
            "trust_level": "autonomous",
            "reviewers": [],
            "awaiting_kickoff": None,
        }

        with patch("mc.workers.review.asyncio.to_thread", new=_sync_to_thread):
            await worker.handle_review_transition("task-1", task)

        bridge.update_task_status.assert_called_once()


class TestKickoffResumeWorkerAcceptsRuntimeContext:
    """KickoffResumeWorker must accept RuntimeContext as its constructor arg."""

    def test_constructor_accepts_runtime_context(self) -> None:
        ctx = _make_ctx()
        materializer = MagicMock()
        dispatcher = MagicMock()
        worker = KickoffResumeWorker(ctx, materializer, dispatcher)
        assert worker._ctx is ctx
        assert worker._bridge is ctx.bridge

    @pytest.mark.asyncio
    async def test_process_batch_uses_bridge_from_context(self) -> None:
        bridge = _make_bridge()
        bridge.get_steps_by_task.return_value = []
        ctx = _make_ctx(bridge)
        materializer = MagicMock()
        materializer.materialize.return_value = ["step-1"]
        dispatcher = MagicMock()
        dispatcher.dispatch_steps = AsyncMock()
        worker = KickoffResumeWorker(ctx, materializer, dispatcher)

        plan_dict = {
            "steps": [
                {
                    "tempId": "step_1",
                    "title": "Do something",
                    "description": "Do something useful",
                    "assignedAgent": "nanobot",
                    "blockedBy": [],
                    "parallelGroup": 1,
                    "order": 1,
                }
            ],
            "generatedAt": "2024-01-01T00:00:00Z",
            "generatedBy": "lead-agent",
        }

        task_data = {
            "id": "task-1",
            "title": "Kicked Off",
            "execution_plan": plan_dict,
        }

        def _capture_create_task(coro):
            coro.close()
            return MagicMock()

        with (
            patch(
                "mc.workers.kickoff.asyncio.to_thread", new=_sync_to_thread
            ),
            patch(
                "mc.workers.kickoff.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
        ):
            await worker.process_batch([task_data])

        materializer.materialize.assert_called_once()
