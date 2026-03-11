"""Tests for PlanningWorker — plan generation, materialization, validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.infrastructure.runtime_context import RuntimeContext
from mc.types import (
    ActivityEventType,
    ExecutionPlan,
    ExecutionPlanStep,
    TaskStatus,
)
from mc.workers.planning import PlanningWorker


async def _sync_to_thread(func, *args, **kwargs):
    """Run to_thread payloads synchronously in tests."""
    return func(*args, **kwargs)


def _make_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.create_task_directory.return_value = None
    bridge.list_agents.return_value = []
    bridge.update_execution_plan.return_value = None
    bridge.batch_create_steps.return_value = ["step-1"]
    bridge.kick_off_task.return_value = None
    bridge.update_task_status.return_value = None
    bridge.create_activity.return_value = None
    bridge.send_message.return_value = None
    return bridge


def _make_ctx(bridge: MagicMock | None = None) -> RuntimeContext:
    if bridge is None:
        bridge = _make_bridge()
    return RuntimeContext(bridge=bridge, agents_dir=Path("/tmp/test-agents"))


def _make_materializer() -> MagicMock:
    mat = MagicMock()
    mat.materialize.return_value = ["step-1"]
    return mat


def _make_dispatcher() -> MagicMock:
    disp = MagicMock()
    disp.dispatch_steps = AsyncMock()
    return disp


def _make_task(
    task_id: str = "task-1",
    title: str = "Plan task",
    description: str | None = "Plan this",
    assigned_agent: str | None = None,
) -> dict:
    return {
        "id": task_id,
        "title": title,
        "description": description,
        "assigned_agent": assigned_agent,
        "supervision_mode": "autonomous",
        "status": "planning",
        "trust_level": "autonomous",
        "is_manual": False,
        "files": [],
    }


def _make_plan() -> ExecutionPlan:
    return ExecutionPlan(
        steps=[
            ExecutionPlanStep(
                temp_id="step_1",
                title="Analyze request",
                description="Analyze scope and constraints",
                assigned_agent="nanobot",
                blocked_by=[],
                parallel_group=1,
                order=1,
            )
        ]
    )


class TestPlanningWorkerProcessTask:
    """Happy path and error path tests for PlanningWorker.process_task."""

    @pytest.mark.asyncio
    async def test_success_stores_plan_materializes_and_dispatches(self) -> None:
        bridge = _make_bridge()
        bridge.list_agents.return_value = [
            {
                "name": "nanobot",
                "display_name": "Owl",
                "role": "Generalist",
                "skills": ["general"],
                "enabled": True,
            }
        ]
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)
        task = _make_task()
        plan = _make_plan()

        scheduled_coroutines: list[object] = []

        def _capture_create_task(coro):
            scheduled_coroutines.append(coro)
            coro.close()
            return MagicMock()

        with (
            patch(
                "mc.workers.planning.asyncio.to_thread", new=_sync_to_thread
            ),
            patch(
                "mc.workers.planning.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
            patch("mc.workers.planning.TaskPlanner") as planner_cls,
        ):
            planner = planner_cls.return_value
            planner.plan_task = AsyncMock(return_value=plan)
            await worker.process_task(task)

        bridge.create_task_directory.assert_called_once_with("task-1")
        bridge.update_execution_plan.assert_called_once_with(
            "task-1", plan.to_dict()
        )
        materializer.materialize.assert_called_once()
        assert len(scheduled_coroutines) == 1

        # Verify activity events
        assert bridge.create_activity.call_count == 3
        first = bridge.create_activity.call_args_list[0][0]
        second = bridge.create_activity.call_args_list[1][0]
        third = bridge.create_activity.call_args_list[2][0]
        assert first[0] == ActivityEventType.TASK_ASSIGNED
        assert second[0] == ActivityEventType.TASK_PLANNING
        assert third[0] == ActivityEventType.TASK_PLANNING

    @pytest.mark.asyncio
    async def test_supervised_mode_defers_materialization(self) -> None:
        bridge = _make_bridge()
        bridge.list_agents.return_value = []
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)
        task = _make_task(task_id="task-supervised", title="Supervised")
        task["supervision_mode"] = "supervised"
        plan = _make_plan()

        with (
            patch(
                "mc.workers.planning.asyncio.to_thread", new=_sync_to_thread
            ),
            patch("mc.workers.planning.asyncio.create_task") as create_mock,
            patch("mc.workers.planning.TaskPlanner") as planner_cls,
        ):
            planner = planner_cls.return_value
            planner.plan_task = AsyncMock(return_value=plan)
            await worker.process_task(task)

        bridge.update_execution_plan.assert_called_once()
        materializer.materialize.assert_not_called()
        create_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_supervised_mode_posts_plan_review_request(self) -> None:
        bridge = _make_bridge()
        bridge.list_agents.return_value = []
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)
        task = _make_task(task_id="task-review", title="Review this plan")
        task["supervision_mode"] = "supervised"
        plan = _make_plan()

        with (
            patch(
                "mc.workers.planning.asyncio.to_thread", new=_sync_to_thread
            ),
            patch("mc.workers.planning.asyncio.create_task") as create_mock,
            patch("mc.workers.planning.TaskPlanner") as planner_cls,
        ):
            planner = planner_cls.return_value
            planner.plan_task = AsyncMock(return_value=plan)
            await worker.process_task(task)

        create_mock.assert_not_called()
        bridge.post_lead_agent_message.assert_called_once()
        call_args = bridge.post_lead_agent_message.call_args
        assert call_args.args[0] == "task-review"
        assert call_args.args[2] == "lead_agent_plan"
        assert "Approve" in call_args.args[1]
        assert call_args.kwargs["plan_review"] == {
            "kind": "request",
            "plan_generated_at": plan.generated_at,
        }

    @pytest.mark.asyncio
    async def test_failure_marks_task_failed(self) -> None:
        bridge = _make_bridge()
        bridge.list_agents.return_value = []
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)
        task = _make_task(task_id="task-fail", title="Failing plan")

        with (
            patch(
                "mc.workers.planning.asyncio.to_thread", new=_sync_to_thread
            ),
            patch("mc.workers.planning.TaskPlanner") as planner_cls,
        ):
            planner = planner_cls.return_value
            planner.plan_task = AsyncMock(
                side_effect=RuntimeError("planner exploded")
            )
            await worker.process_task(task)

        bridge.update_execution_plan.assert_not_called()
        bridge.update_task_status.assert_called_once()
        status_args = bridge.update_task_status.call_args[0]
        assert status_args[0] == "task-fail"
        assert status_args[1] == TaskStatus.FAILED

        # Should send error message
        bridge.send_message.assert_called_once()
        send_args = bridge.send_message.call_args[0]
        assert send_args[0] == "task-fail"
        assert "Plan generation failed" in send_args[3]

    @pytest.mark.asyncio
    async def test_skips_manual_tasks(self) -> None:
        bridge = _make_bridge()
        bridge.list_agents.return_value = []
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)
        task = _make_task()
        task["is_manual"] = True

        with patch(
            "mc.workers.planning.asyncio.to_thread", new=_sync_to_thread
        ):
            await worker.process_task(task)

        bridge.create_task_directory.assert_called_once()
        bridge.list_agents.assert_not_called()
        materializer.materialize.assert_not_called()

    @pytest.mark.asyncio
    async def test_passes_files_to_planner(self) -> None:
        bridge = _make_bridge()
        bridge.list_agents.return_value = [
            {
                "name": "nanobot",
                "display_name": "Owl",
                "role": "Generalist",
                "skills": ["general"],
                "enabled": True,
            }
        ]
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)

        files = [
            {"name": "invoice.pdf", "type": "application/pdf", "size": 867328}
        ]
        task = _make_task()
        task["files"] = files
        plan = _make_plan()

        def _capture_create_task(coro):
            coro.close()
            return MagicMock()

        with (
            patch(
                "mc.workers.planning.asyncio.to_thread", new=_sync_to_thread
            ),
            patch(
                "mc.workers.planning.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
            patch("mc.workers.planning.TaskPlanner") as planner_cls,
        ):
            planner = planner_cls.return_value
            planner.plan_task = AsyncMock(return_value=plan)
            await worker.process_task(task)

        call_kwargs = planner.plan_task.call_args[1]
        assert call_kwargs["files"] == files


class TestPlanningWorkerProcessBatch:
    """Tests for batch deduplication."""

    @pytest.mark.asyncio
    async def test_deduplicates_tasks(self) -> None:
        bridge = _make_bridge()
        bridge.list_agents.return_value = []
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)
        plan = _make_plan()

        tasks = [_make_task(), _make_task()]  # same ID

        def _capture_create_task(coro):
            coro.close()
            return MagicMock()

        with (
            patch(
                "mc.workers.planning.asyncio.to_thread", new=_sync_to_thread
            ),
            patch(
                "mc.workers.planning.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
            patch("mc.workers.planning.TaskPlanner") as planner_cls,
        ):
            planner = planner_cls.return_value
            planner.plan_task = AsyncMock(return_value=plan)
            await worker.process_batch(tasks)

        # Should only process once
        bridge.create_task_directory.assert_called_once()

    @pytest.mark.asyncio
    async def test_prunes_stale_ids(self) -> None:
        bridge = _make_bridge()
        bridge.list_agents.return_value = []
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)
        plan = _make_plan()

        def _capture_create_task(coro):
            coro.close()
            return MagicMock()

        with (
            patch(
                "mc.workers.planning.asyncio.to_thread", new=_sync_to_thread
            ),
            patch(
                "mc.workers.planning.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
            patch("mc.workers.planning.TaskPlanner") as planner_cls,
        ):
            planner = planner_cls.return_value
            planner.plan_task = AsyncMock(return_value=plan)

            await worker.process_batch([_make_task()])
            assert bridge.create_task_directory.call_count == 1

            await worker.process_batch([])  # task leaves planning

            await worker.process_batch([_make_task()])  # re-enters
            assert bridge.create_task_directory.call_count == 2
