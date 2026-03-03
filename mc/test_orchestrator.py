"""Unit tests for planning-oriented TaskOrchestrator behavior."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.orchestrator import TaskOrchestrator, generate_title_via_low_agent
from mc.types import ActivityEventType, AuthorType, ExecutionPlan, ExecutionPlanStep, MessageType, TaskStatus


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


class TestPlanningRoutingLoop:
    @pytest.mark.asyncio
    async def test_start_routing_loop_subscribes_to_planning_status(self) -> None:
        bridge = _make_bridge()
        queue: asyncio.Queue[list[dict] | None] = asyncio.Queue()
        bridge.async_subscribe.return_value = queue
        orchestrator = TaskOrchestrator(bridge)

        loop_task = asyncio.create_task(orchestrator.start_routing_loop())
        await asyncio.sleep(0.01)
        loop_task.cancel()
        with suppress(asyncio.CancelledError):
            await loop_task

        bridge.async_subscribe.assert_called_once_with(
            "tasks:listByStatus", {"status": "planning"}
        )


class TestProcessPlanningTask:
    @pytest.mark.asyncio
    async def test_success_stores_execution_plan_materializes_and_starts_dispatch(
        self,
    ) -> None:
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
        orchestrator = TaskOrchestrator(bridge)
        orchestrator._step_dispatcher = MagicMock()
        orchestrator._step_dispatcher.dispatch_steps = AsyncMock()
        task = _make_task()
        scheduled_coroutines: list[object] = []

        plan = ExecutionPlan(
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

        def _capture_create_task(coro):
            scheduled_coroutines.append(coro)
            coro.close()
            return MagicMock()

        with (
            patch("mc.orchestrator.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.orchestrator.asyncio.create_task", side_effect=_capture_create_task),
            patch("mc.orchestrator.TaskPlanner") as planner_cls,
        ):
            planner = planner_cls.return_value
            planner.plan_task = AsyncMock(return_value=plan)
            await orchestrator._process_planning_task(task)

        bridge.create_task_directory.assert_called_once_with("task-1")
        bridge.update_execution_plan.assert_called_once_with("task-1", plan.to_dict())
        bridge.update_task_status.assert_not_called()
        bridge.batch_create_steps.assert_called_once()
        bridge.kick_off_task.assert_called_once_with("task-1", 1)
        orchestrator._step_dispatcher.dispatch_steps.assert_called_once_with("task-1", ["step-1"])
        assert len(scheduled_coroutines) == 1

        assert bridge.create_activity.call_count == 3
        first_activity = bridge.create_activity.call_args_list[0][0]
        second_activity = bridge.create_activity.call_args_list[1][0]
        third_activity = bridge.create_activity.call_args_list[2][0]
        assert first_activity[0] == ActivityEventType.TASK_ASSIGNED
        assert second_activity[0] == ActivityEventType.TASK_PLANNING
        assert third_activity[0] == ActivityEventType.TASK_PLANNING

    @pytest.mark.asyncio
    async def test_supervised_mode_defers_materialization(self) -> None:
        bridge = _make_bridge()
        bridge.list_agents.return_value = []
        orchestrator = TaskOrchestrator(bridge)
        orchestrator._step_dispatcher = MagicMock()
        orchestrator._step_dispatcher.dispatch_steps = AsyncMock()
        task = _make_task(task_id="task-supervised", title="Supervised")
        task["supervision_mode"] = "supervised"

        plan = ExecutionPlan(
            steps=[
                ExecutionPlanStep(
                    temp_id="step_1",
                    title="Draft",
                    description="Draft response",
                    assigned_agent="nanobot",
                    blocked_by=[],
                    parallel_group=1,
                    order=1,
                )
            ]
        )

        with (
            patch("mc.orchestrator.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.orchestrator.asyncio.create_task") as create_task_mock,
            patch("mc.orchestrator.TaskPlanner") as planner_cls,
        ):
            planner = planner_cls.return_value
            planner.plan_task = AsyncMock(return_value=plan)
            await orchestrator._process_planning_task(task)

        bridge.update_execution_plan.assert_called_once_with("task-supervised", plan.to_dict())
        bridge.batch_create_steps.assert_not_called()
        bridge.kick_off_task.assert_not_called()
        create_task_mock.assert_not_called()
        orchestrator._step_dispatcher.dispatch_steps.assert_not_called()

    @pytest.mark.asyncio
    async def test_failure_marks_task_failed_and_reports_error(self) -> None:
        bridge = _make_bridge()
        bridge.list_agents.return_value = []
        orchestrator = TaskOrchestrator(bridge)
        task = _make_task(task_id="task-fail", title="Failing plan")

        with (
            patch("mc.orchestrator.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.orchestrator.TaskPlanner") as planner_cls,
        ):
            planner = planner_cls.return_value
            planner.plan_task = AsyncMock(side_effect=RuntimeError("planner exploded"))
            await orchestrator._process_planning_task(task)

        bridge.update_execution_plan.assert_not_called()
        bridge.update_task_status.assert_called_once()
        status_args = bridge.update_task_status.call_args[0]
        assert status_args[0] == "task-fail"
        assert status_args[1] == TaskStatus.FAILED

        failed_events = [
            c for c in bridge.create_activity.call_args_list
            if c[0][0] == ActivityEventType.TASK_FAILED
        ]
        assert len(failed_events) == 1

        bridge.send_message.assert_called_once()
        send_args = bridge.send_message.call_args[0]
        assert send_args[0] == "task-fail"
        assert send_args[1] == "System"
        assert send_args[2] == AuthorType.SYSTEM
        assert "Plan generation failed" in send_args[3]
        assert send_args[4] == MessageType.SYSTEM_EVENT

    @pytest.mark.asyncio
    async def test_process_planning_task_passes_files_to_planner(self) -> None:
        """AC #1 (FR-F28): orchestrator passes task files to planner.plan_task()."""
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
        orchestrator = TaskOrchestrator(bridge)
        orchestrator._step_dispatcher = MagicMock()
        orchestrator._step_dispatcher.dispatch_steps = AsyncMock()

        files = [
            {"name": "invoice.pdf", "type": "application/pdf", "size": 867328},
            {"name": "notes.md", "type": "text/markdown", "size": 12288},
        ]
        task = _make_task()
        task["files"] = files

        plan = ExecutionPlan(
            steps=[
                ExecutionPlanStep(
                    temp_id="step_1",
                    title="Process files",
                    description="Process the attached files",
                    assigned_agent="nanobot",
                    blocked_by=[],
                    parallel_group=1,
                    order=1,
                )
            ]
        )

        captured_plan_task_kwargs: list[dict] = []

        async def _capture_plan_task(*args, **kwargs):
            captured_plan_task_kwargs.append(kwargs)
            return plan

        def _capture_create_task(coro):
            coro.close()
            return MagicMock()

        with (
            patch("mc.orchestrator.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.orchestrator.asyncio.create_task", side_effect=_capture_create_task),
            patch("mc.orchestrator.TaskPlanner") as planner_cls,
        ):
            planner = planner_cls.return_value
            planner.plan_task = AsyncMock(side_effect=_capture_plan_task)
            await orchestrator._process_planning_task(task)

        # Verify planner.plan_task was called with the task's files
        planner.plan_task.assert_called_once()
        call_kwargs = planner.plan_task.call_args[1]
        assert "files" in call_kwargs
        assert call_kwargs["files"] == files


class TestHandleReviewTransitionPausedTask:
    """Story 7.4: _handle_review_transition must NOT auto-complete paused tasks (C1 fix)."""

    @pytest.mark.asyncio
    async def test_paused_task_with_steps_is_not_auto_completed(self) -> None:
        """C1 fix: An autonomous task that enters review with materialized steps (paused)
        must NOT be auto-completed to done.

        Without the fix, _handle_review_transition would see:
            trust_level=autonomous, no reviewers → auto-complete to done.
        With the fix, it detects existing steps and skips processing.
        """
        bridge = _make_bridge()
        # Simulate a paused task: has materialized steps
        bridge.get_steps_by_task.return_value = [
            {"id": "step-1", "status": "completed"},
            {"id": "step-2", "status": "assigned"},
        ]
        orchestrator = TaskOrchestrator(bridge)

        paused_task = {
            "id": "task-1",
            "title": "Paused Task",
            "trust_level": "autonomous",
            "supervision_mode": "autonomous",
            "reviewers": [],
            "awaiting_kickoff": None,
        }

        with patch("mc.orchestrator.asyncio.to_thread", new=_sync_to_thread):
            await orchestrator._handle_review_transition("task-1", paused_task)

        # Task must NOT be auto-completed to done
        bridge.update_task_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_review_task_without_steps_is_auto_completed(self) -> None:
        """Regression: autonomous tasks without steps (normal review completion) still auto-complete."""
        bridge = _make_bridge()
        # No materialized steps — this is a normal review completion
        bridge.get_steps_by_task.return_value = []
        orchestrator = TaskOrchestrator(bridge)

        review_task = {
            "id": "task-1",
            "title": "Completed Task",
            "trust_level": "autonomous",
            "supervision_mode": "autonomous",
            "reviewers": [],
            "awaiting_kickoff": None,
        }

        with patch("mc.orchestrator.asyncio.to_thread", new=_sync_to_thread):
            await orchestrator._handle_review_transition("task-1", review_task)

        # Task SHOULD be auto-completed (no steps = normal autonomous review)
        bridge.update_task_status.assert_called_once_with("task-1", TaskStatus.DONE)


class TestGenerateTitleViaLowAgent:
    @pytest.mark.asyncio
    async def test_returns_title_from_llm(self):
        bridge = _make_bridge()
        bridge.get_agent_by_name.return_value = {"model": "tier:standard-low"}

        mock_response = MagicMock()
        mock_response.finish_reason = "stop"
        mock_response.content = "  My Generated Title  "

        mock_provider = AsyncMock()
        mock_provider.chat.return_value = mock_response

        with patch(
            "mc.orchestrator.create_provider",
            return_value=(mock_provider, "anthropic/claude-haiku"),
        ):
            with patch(
                "mc.orchestrator.asyncio.to_thread",
                side_effect=_sync_to_thread,
            ):
                result = await generate_title_via_low_agent(bridge, "Do something useful")

        assert result == "My Generated Title"

    @pytest.mark.asyncio
    async def test_returns_none_on_llm_error(self):
        bridge = _make_bridge()
        bridge.get_agent_by_name.return_value = {"model": "tier:standard-low"}

        mock_response = MagicMock()
        mock_response.finish_reason = "error"
        mock_response.content = "oops"

        mock_provider = AsyncMock()
        mock_provider.chat.return_value = mock_response

        with patch(
            "mc.orchestrator.create_provider",
            return_value=(mock_provider, "anthropic/claude-haiku"),
        ):
            with patch(
                "mc.orchestrator.asyncio.to_thread",
                side_effect=_sync_to_thread,
            ):
                result = await generate_title_via_low_agent(bridge, "Do something useful")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_low_agent_not_found(self):
        bridge = _make_bridge()
        bridge.get_agent_by_name.return_value = None

        with patch(
            "mc.orchestrator.asyncio.to_thread",
            side_effect=_sync_to_thread,
        ):
            result = await generate_title_via_low_agent(bridge, "Do something useful")

        assert result is None

    @pytest.mark.asyncio
    async def test_truncates_long_descriptions(self):
        bridge = _make_bridge()
        bridge.get_agent_by_name.return_value = {"model": "tier:standard-low"}

        mock_response = MagicMock()
        mock_response.finish_reason = "stop"
        mock_response.content = "Short Title"

        mock_provider = AsyncMock()
        mock_provider.chat.return_value = mock_response

        long_desc = "x" * 10000

        with patch(
            "mc.orchestrator.create_provider",
            return_value=(mock_provider, "anthropic/claude-haiku"),
        ):
            with patch(
                "mc.orchestrator.asyncio.to_thread",
                side_effect=_sync_to_thread,
            ):
                result = await generate_title_via_low_agent(bridge, long_desc)

        # Verify the prompt was truncated
        call_messages = mock_provider.chat.call_args[1]["messages"]
        assert len(call_messages[0]["content"]) <= 5100  # prompt header + 5000 char description
        assert result == "Short Title"
