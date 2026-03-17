"""Tests for KickoffResumeWorker — task kickoff and resume flows."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.infrastructure.runtime_context import RuntimeContext
from mc.runtime.workers.kickoff import KickoffResumeWorker
from mc.types import (
    ActivityEventType,
    StepStatus,
    TaskStatus,
)


async def _sync_to_thread(func, *args, **kwargs):
    """Run to_thread payloads synchronously in tests."""
    return func(*args, **kwargs)


def _make_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.update_task_status.return_value = None
    bridge.create_activity.return_value = None
    bridge.get_steps_by_task.return_value = []
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


def _make_plan_dict() -> dict:
    return {
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


class TestKickoffWorkerKickoff:
    """Tests for new kick-off (materialize and dispatch)."""

    @pytest.mark.asyncio
    async def test_materializes_and_dispatches_on_kickoff(self) -> None:
        bridge = _make_bridge()
        bridge.get_steps_by_task.return_value = []  # No existing steps
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = KickoffResumeWorker(_make_ctx(bridge), materializer, dispatcher)

        scheduled_coroutines: list[object] = []

        def _capture_create_task(coro):
            scheduled_coroutines.append(coro)
            coro.close()
            return MagicMock()

        task_data = {
            "id": "task-1",
            "title": "Kicked Off",
            "execution_plan": _make_plan_dict(),
        }

        with (
            patch("mc.runtime.workers.kickoff.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.kickoff.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
        ):
            await worker.process_batch([task_data])

        materializer.materialize.assert_called_once()
        call_kwargs = materializer.materialize.call_args
        assert call_kwargs[0][0] == "task-1"
        assert call_kwargs[1]["skip_kickoff"] is True
        assert len(scheduled_coroutines) == 1

    @pytest.mark.asyncio
    async def test_kickoff_materialization_failure_marks_crashed(self) -> None:
        bridge = _make_bridge()
        bridge.get_steps_by_task.return_value = []
        materializer = _make_materializer()
        materializer.materialize.side_effect = RuntimeError("mat failed")
        dispatcher = _make_dispatcher()
        worker = KickoffResumeWorker(_make_ctx(bridge), materializer, dispatcher)

        task_data = {
            "id": "task-1",
            "title": "Failing Kickoff",
            "execution_plan": _make_plan_dict(),
        }

        with patch("mc.runtime.workers.kickoff.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_batch([task_data])

        bridge.transition_task_from_snapshot.assert_called_once()
        args = bridge.transition_task_from_snapshot.call_args
        assert args.args[1] == TaskStatus.CRASHED

        bridge.create_activity.assert_called_once()
        act_args = bridge.create_activity.call_args[0]
        assert act_args[0] == ActivityEventType.SYSTEM_ERROR

    @pytest.mark.asyncio
    async def test_skips_tasks_without_execution_plan(self) -> None:
        bridge = _make_bridge()
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = KickoffResumeWorker(_make_ctx(bridge), materializer, dispatcher)

        task_data = {
            "id": "task-1",
            "title": "No Plan",
        }

        with patch("mc.runtime.workers.kickoff.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_batch([task_data])

        materializer.materialize.assert_not_called()
        bridge.get_steps_by_task.assert_not_called()


class TestKickoffWorkerResume:
    """Tests for resume (dispatching existing assigned/unblocked steps)."""

    @pytest.mark.asyncio
    async def test_dispatches_assigned_steps_on_resume(self) -> None:
        bridge = _make_bridge()
        bridge.get_steps_by_task.return_value = [
            {"id": "step-1", "status": StepStatus.ASSIGNED, "blocked_by": []},
            {"id": "step-2", "status": StepStatus.COMPLETED, "blocked_by": []},
        ]
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = KickoffResumeWorker(_make_ctx(bridge), materializer, dispatcher)

        scheduled_coroutines: list[object] = []

        def _capture_create_task(coro):
            scheduled_coroutines.append(coro)
            coro.close()
            return MagicMock()

        task_data = {
            "id": "task-1",
            "title": "Resumed",
            "execution_plan": _make_plan_dict(),
        }

        with (
            patch("mc.runtime.workers.kickoff.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.kickoff.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
        ):
            await worker.process_batch([task_data])

        # Should NOT re-materialize
        materializer.materialize.assert_not_called()
        # Should dispatch the assigned step
        assert len(scheduled_coroutines) == 1

    @pytest.mark.asyncio
    async def test_dispatches_unblocked_planned_steps(self) -> None:
        bridge = _make_bridge()
        bridge.get_steps_by_task.return_value = [
            {"id": "step-1", "status": StepStatus.COMPLETED, "blocked_by": []},
            {
                "id": "step-2",
                "status": StepStatus.PLANNED,
                "blocked_by": ["step-1"],
            },
        ]
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = KickoffResumeWorker(_make_ctx(bridge), materializer, dispatcher)

        scheduled_coroutines: list[object] = []

        def _capture_create_task(coro):
            scheduled_coroutines.append(coro)
            coro.close()
            return MagicMock()

        task_data = {
            "id": "task-1",
            "title": "Resumed Unblocked",
            "execution_plan": _make_plan_dict(),
        }

        with (
            patch("mc.runtime.workers.kickoff.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.kickoff.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
        ):
            await worker.process_batch([task_data])

        materializer.materialize.assert_not_called()
        assert len(scheduled_coroutines) == 1

    @pytest.mark.asyncio
    async def test_materializes_incremental_steps_before_resume_dispatch(self) -> None:
        bridge = _make_bridge()
        bridge.get_steps_by_task.side_effect = [
            [
                {
                    "id": "step-1",
                    "title": "Do something",
                    "order": "1",
                    "status": StepStatus.COMPLETED,
                    "blocked_by": [],
                }
            ],
            [
                {
                    "id": "step-1",
                    "title": "Do something",
                    "order": 1,
                    "status": StepStatus.COMPLETED,
                    "blocked_by": [],
                },
                {
                    "id": "step-2",
                    "title": "New follow-up",
                    "order": 2,
                    "status": StepStatus.PLANNED,
                    "blocked_by": ["step-1"],
                },
            ],
        ]
        bridge.create_step.return_value = "step-2"
        bridge.check_and_unblock_dependents.return_value = ["step-2"]
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = KickoffResumeWorker(_make_ctx(bridge), materializer, dispatcher)

        scheduled_coroutines: list[object] = []

        def _capture_create_task(coro):
            scheduled_coroutines.append(coro)
            coro.close()
            return MagicMock()

        task_data = {
            "id": "task-1",
            "title": "Resumed Incremental",
            "execution_plan": {
                "steps": [
                    {
                        "tempId": "step_1",
                        "title": "Do something",
                        "description": "Existing work",
                        "assignedAgent": "nanobot",
                        "blockedBy": [],
                        "parallelGroup": 1,
                        "order": 1,
                    },
                    {
                        "tempId": "step_2",
                        "title": "New follow-up",
                        "description": "Continue after the first step",
                        "assignedAgent": "nanobot",
                        "blockedBy": ["step_1"],
                        "parallelGroup": 2,
                        "order": 2,
                    },
                ],
                "generatedAt": "2024-01-01T00:00:00Z",
                "generatedBy": "lead-agent",
            },
        }

        with (
            patch("mc.runtime.workers.kickoff.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.kickoff.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
        ):
            await worker.process_batch([task_data])

        materializer.materialize.assert_not_called()
        bridge.create_step.assert_called_once()
        bridge.check_and_unblock_dependents.assert_called_once_with("step-1")
        assert len(scheduled_coroutines) == 1

    @pytest.mark.asyncio
    async def test_no_dispatchable_steps_logs_without_error(self) -> None:
        bridge = _make_bridge()
        bridge.get_steps_by_task.return_value = [
            {"id": "step-1", "status": StepStatus.RUNNING, "blocked_by": []},
        ]
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = KickoffResumeWorker(_make_ctx(bridge), materializer, dispatcher)

        task_data = {
            "id": "task-1",
            "title": "All Running",
            "execution_plan": _make_plan_dict(),
        }

        with (
            patch("mc.runtime.workers.kickoff.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.runtime.workers.kickoff.asyncio.create_task") as create_mock,
        ):
            await worker.process_batch([task_data])

        materializer.materialize.assert_not_called()
        create_mock.assert_not_called()


class TestKickoffWorkerProcessBatch:
    """Tests for batch deduplication."""

    @pytest.mark.asyncio
    async def test_deduplicates_tasks(self) -> None:
        bridge = _make_bridge()
        bridge.get_steps_by_task.return_value = []
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = KickoffResumeWorker(_make_ctx(bridge), materializer, dispatcher)

        task = {
            "id": "task-1",
            "title": "Kicked",
            "execution_plan": _make_plan_dict(),
        }

        def _capture_create_task(coro):
            coro.close()
            return MagicMock()

        with (
            patch("mc.runtime.workers.kickoff.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.kickoff.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
        ):
            await worker.process_batch([task, task])

        # Only processed once
        materializer.materialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_prunes_stale_ids(self) -> None:
        bridge = _make_bridge()
        bridge.get_steps_by_task.return_value = []
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = KickoffResumeWorker(_make_ctx(bridge), materializer, dispatcher)

        task = {
            "id": "task-1",
            "title": "Kicked",
            "execution_plan": _make_plan_dict(),
        }

        def _capture_create_task(coro):
            coro.close()
            return MagicMock()

        with (
            patch("mc.runtime.workers.kickoff.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.kickoff.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
        ):
            await worker.process_batch([task])
            assert materializer.materialize.call_count == 1

            await worker.process_batch([])  # task leaves in_progress
            await worker.process_batch([task])  # re-enters
            assert materializer.materialize.call_count == 2

    @pytest.mark.asyncio
    async def test_shared_kickoff_ids_prevent_double_dispatch(self) -> None:
        """When planning worker pre-registers an ID, kickoff worker skips it."""
        bridge = _make_bridge()
        bridge.get_steps_by_task.return_value = []
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        shared_ids: set[str] = {"task-1"}  # Pre-registered by planning
        worker = KickoffResumeWorker(
            _make_ctx(bridge), materializer, dispatcher, known_kickoff_ids=shared_ids
        )

        task = {
            "id": "task-1",
            "title": "Already dispatched",
            "execution_plan": _make_plan_dict(),
        }

        with patch("mc.runtime.workers.kickoff.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_batch([task])

        # Should skip because ID was pre-registered
        materializer.materialize.assert_not_called()

    @pytest.mark.asyncio
    async def test_reprocesses_same_task_id_when_updated_at_changes(self) -> None:
        bridge = _make_bridge()
        bridge.get_steps_by_task.return_value = [
            {"id": "step-1", "status": StepStatus.PLANNED, "blocked_by": []},
        ]
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = KickoffResumeWorker(_make_ctx(bridge), materializer, dispatcher)

        scheduled_coroutines: list[object] = []

        def _capture_create_task(coro):
            scheduled_coroutines.append(coro)
            coro.close()
            return MagicMock()

        task = {
            "id": "task-1",
            "title": "Resumed",
            "updated_at": "2026-03-11T06:00:00Z",
            "execution_plan": _make_plan_dict(),
        }
        updated_task = {
            **task,
            "updated_at": "2026-03-11T06:00:05Z",
        }

        with (
            patch("mc.runtime.workers.kickoff.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.kickoff.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
        ):
            await worker.process_batch([task])
            await worker.process_batch([updated_task])

        materializer.materialize.assert_not_called()
        assert len(scheduled_coroutines) == 2
