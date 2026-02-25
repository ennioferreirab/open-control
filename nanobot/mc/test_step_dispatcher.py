"""Unit tests for StepDispatcher."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanobot.mc.step_dispatcher import StepDispatcher
from nanobot.mc.types import ActivityEventType, AuthorType, MessageType, StepStatus, TaskStatus


async def _sync_to_thread(func, *args, **kwargs):
    """Run to_thread payloads synchronously in tests."""
    return func(*args, **kwargs)


def _step(
    step_id: str,
    title: str,
    *,
    status: str = "assigned",
    parallel_group: int = 1,
    order: int = 1,
    blocked_by: list[str] | None = None,
    assigned_agent: str = "general-agent",
) -> dict[str, Any]:
    return {
        "id": step_id,
        "task_id": "task-1",
        "title": title,
        "description": f"Do {title}",
        "assigned_agent": assigned_agent,
        "status": status,
        "parallel_group": parallel_group,
        "order": order,
        "blocked_by": blocked_by or [],
    }


def _make_stateful_bridge(
    steps: list[dict[str, Any]],
    dependency_map: dict[str, list[str]] | None = None,
) -> tuple[MagicMock, dict[str, dict[str, Any]]]:
    bridge = MagicMock()
    state = {step["id"]: dict(step) for step in steps}
    dependency_map = dependency_map or {}

    def _ordered_steps() -> list[dict[str, Any]]:
        sorted_steps = sorted(
            state.values(),
            key=lambda step: (int(step.get("parallel_group", 1)), int(step.get("order", 1))),
        )
        return [dict(step) for step in sorted_steps]

    def _update_step_status(
        step_id: str, status: str, error_message: str | None = None
    ) -> None:
        state[step_id]["status"] = status
        if error_message is not None:
            state[step_id]["error_message"] = error_message

    def _check_and_unblock_dependents(step_id: str) -> list[str]:
        unblocked: list[str] = []
        for dependent_id in dependency_map.get(step_id, []):
            dependent = state.get(dependent_id)
            if not dependent or dependent.get("status") != StepStatus.BLOCKED:
                continue
            blocked_by_ids = dependent.get("blocked_by", [])
            if all(state[dep_id]["status"] == StepStatus.COMPLETED for dep_id in blocked_by_ids):
                dependent["status"] = StepStatus.ASSIGNED
                unblocked.append(dependent_id)
        return unblocked

    bridge.get_steps_by_task.side_effect = lambda _task_id: _ordered_steps()
    bridge.update_step_status.side_effect = _update_step_status
    bridge.check_and_unblock_dependents.side_effect = _check_and_unblock_dependents
    bridge.update_task_status.return_value = None
    bridge.create_activity.return_value = None
    bridge.get_task_messages.return_value = []
    bridge.query.return_value = {"title": "Main Task"}
    bridge.get_board_by_id.return_value = None
    bridge.send_message.return_value = None

    return bridge, state


class TestStepDispatcher:
    @pytest.mark.asyncio
    async def test_dispatch_single_step_completes_task(self) -> None:
        bridge, state = _make_stateful_bridge([_step("step-1", "Analyze", order=1)])
        dispatcher = StepDispatcher(bridge)

        with (
            patch("nanobot.mc.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "nanobot.mc.step_dispatcher._load_agent_config",
                return_value=(None, None, None),
            ),
            patch(
                "nanobot.mc.step_dispatcher._maybe_inject_orientation",
                side_effect=lambda agent_name, prompt: prompt,
            ),
            patch(
                "nanobot.mc.step_dispatcher._run_step_agent",
                new=AsyncMock(return_value="step output"),
            ),
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert state["step-1"]["status"] == StepStatus.COMPLETED
        bridge.update_task_status.assert_called_once_with(
            "task-1",
            TaskStatus.DONE,
            None,
            "All 1 steps completed",
        )
        bridge.create_activity.assert_any_call(
            ActivityEventType.TASK_DISPATCH_STARTED,
            "Steps dispatched in autonomous mode",
            "task-1",
        )
        bridge.create_activity.assert_any_call(
            ActivityEventType.STEP_DISPATCHED,
            "Agent general-agent started step: Analyze",
            "task-1",
            "general-agent",
        )
        bridge.create_activity.assert_any_call(
            ActivityEventType.STEP_DISPATCHED,
            "Agent general-agent completed step: Analyze",
            "task-1",
            "general-agent",
        )
        bridge.create_activity.assert_any_call(
            ActivityEventType.TASK_COMPLETED,
            "Task completed -- all 1 steps finished",
            "task-1",
        )

    @pytest.mark.asyncio
    async def test_dispatch_parallel_group_runs_concurrently(self) -> None:
        bridge, state = _make_stateful_bridge(
            [
                _step("step-1", "Parallel A", parallel_group=1, order=1),
                _step("step-2", "Parallel B", parallel_group=1, order=2),
            ]
        )
        dispatcher = StepDispatcher(bridge)

        running = 0
        peak_running = 0

        async def _run_agent(*args, **kwargs):
            nonlocal running, peak_running
            running += 1
            peak_running = max(peak_running, running)
            await asyncio.sleep(0.01)
            running -= 1
            return f"done {kwargs['task_title']}"

        with (
            patch("nanobot.mc.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "nanobot.mc.step_dispatcher._load_agent_config",
                return_value=(None, None, None),
            ),
            patch(
                "nanobot.mc.step_dispatcher._maybe_inject_orientation",
                side_effect=lambda agent_name, prompt: prompt,
            ),
            patch("nanobot.mc.step_dispatcher._run_step_agent", side_effect=_run_agent),
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1", "step-2"])

        assert state["step-1"]["status"] == StepStatus.COMPLETED
        assert state["step-2"]["status"] == StepStatus.COMPLETED
        assert peak_running == 2

    @pytest.mark.asyncio
    async def test_dispatch_sequential_groups_order(self) -> None:
        bridge, state = _make_stateful_bridge(
            [
                _step("step-1", "Group 1", parallel_group=1, order=1),
                _step("step-2", "Group 2", parallel_group=2, order=2),
            ]
        )
        dispatcher = StepDispatcher(bridge)
        execution_order: list[str] = []

        async def _run_agent(*args, **kwargs):
            execution_order.append(kwargs["task_title"])
            return "ok"

        with (
            patch("nanobot.mc.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "nanobot.mc.step_dispatcher._load_agent_config",
                return_value=(None, None, None),
            ),
            patch(
                "nanobot.mc.step_dispatcher._maybe_inject_orientation",
                side_effect=lambda agent_name, prompt: prompt,
            ),
            patch("nanobot.mc.step_dispatcher._run_step_agent", side_effect=_run_agent),
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1", "step-2"])

        assert execution_order == ["Group 1", "Group 2"]
        assert state["step-1"]["status"] == StepStatus.COMPLETED
        assert state["step-2"]["status"] == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_step_crash_does_not_cancel_sibling(self) -> None:
        bridge, state = _make_stateful_bridge(
            [
                _step("step-1", "Crash", parallel_group=1, order=1),
                _step("step-2", "Sibling", parallel_group=1, order=2),
            ]
        )
        dispatcher = StepDispatcher(bridge)

        async def _run_agent(*args, **kwargs):
            title = kwargs["task_title"]
            if title == "Crash":
                await asyncio.sleep(0.005)
                raise RuntimeError("boom")
            await asyncio.sleep(0.01)
            return "ok"

        with (
            patch("nanobot.mc.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "nanobot.mc.step_dispatcher._load_agent_config",
                return_value=(None, None, None),
            ),
            patch(
                "nanobot.mc.step_dispatcher._maybe_inject_orientation",
                side_effect=lambda agent_name, prompt: prompt,
            ),
            patch("nanobot.mc.step_dispatcher._run_step_agent", side_effect=_run_agent),
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1", "step-2"])

        assert state["step-1"]["status"] == StepStatus.CRASHED
        assert state["step-2"]["status"] == StepStatus.COMPLETED
        bridge.update_task_status.assert_not_called()
        bridge.send_message.assert_any_call(
            "task-1",
            "System",
            AuthorType.SYSTEM,
            'Step "Crash" crashed:\n```\nRuntimeError: boom\n```\nAgent: general-agent',
            MessageType.SYSTEM_EVENT,
        )

    @pytest.mark.asyncio
    async def test_dependency_unblocking_triggers_dispatch(self) -> None:
        bridge, state = _make_stateful_bridge(
            [
                _step("step-1", "Root", status=StepStatus.ASSIGNED, parallel_group=1, order=1),
                _step(
                    "step-2",
                    "Blocked",
                    status=StepStatus.BLOCKED,
                    parallel_group=2,
                    order=2,
                    blocked_by=["step-1"],
                ),
            ],
            dependency_map={"step-1": ["step-2"]},
        )
        dispatcher = StepDispatcher(bridge)
        titles: list[str] = []

        async def _run_agent(*args, **kwargs):
            titles.append(kwargs["task_title"])
            return "ok"

        with (
            patch("nanobot.mc.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "nanobot.mc.step_dispatcher._load_agent_config",
                return_value=(None, None, None),
            ),
            patch(
                "nanobot.mc.step_dispatcher._maybe_inject_orientation",
                side_effect=lambda agent_name, prompt: prompt,
            ),
            patch("nanobot.mc.step_dispatcher._run_step_agent", side_effect=_run_agent),
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1", "step-2"])

        assert titles == ["Root", "Blocked"]
        assert state["step-1"]["status"] == StepStatus.COMPLETED
        assert state["step-2"]["status"] == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_all_steps_completed_transitions_task_to_done(self) -> None:
        bridge, _state = _make_stateful_bridge(
            [
                _step("step-1", "One", status=StepStatus.ASSIGNED, parallel_group=1, order=1),
                _step("step-2", "Two", status=StepStatus.ASSIGNED, parallel_group=1, order=2),
            ]
        )
        dispatcher = StepDispatcher(bridge)

        with (
            patch("nanobot.mc.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "nanobot.mc.step_dispatcher._load_agent_config",
                return_value=(None, None, None),
            ),
            patch(
                "nanobot.mc.step_dispatcher._maybe_inject_orientation",
                side_effect=lambda agent_name, prompt: prompt,
            ),
            patch(
                "nanobot.mc.step_dispatcher._run_step_agent",
                new=AsyncMock(return_value="ok"),
            ),
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1", "step-2"])

        bridge.update_task_status.assert_called_once_with(
            "task-1",
            TaskStatus.DONE,
            None,
            "All 2 steps completed",
        )
