"""Unit tests for plan materialization into Convex step records."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mc.contexts.planning.materializer import PlanMaterializer
from mc.types import ActivityEventType, ExecutionPlan, ExecutionPlanStep, TaskStatus


def _step(
    temp_id: str,
    title: str,
    description: str,
    blocked_by: list[str] | None = None,
) -> ExecutionPlanStep:
    return ExecutionPlanStep(
        temp_id=temp_id,
        title=title,
        description=description,
        assigned_agent="nanobot",
        blocked_by=blocked_by or [],
        parallel_group=1,
        order=1,
    )


def test_materialize_simple_plan_with_no_dependencies() -> None:
    bridge = MagicMock()
    bridge.batch_create_steps.return_value = ["step-a", "step-b"]

    plan = ExecutionPlan(
        steps=[
            _step("step_1", "Analyze", "Analyze requirements"),
            _step("step_2", "Implement", "Implement changes"),
        ]
    )

    created = PlanMaterializer(bridge).materialize("task-1", plan)

    assert created == ["step-a", "step-b"]
    bridge.batch_create_steps.assert_called_once()
    task_id, payload = bridge.batch_create_steps.call_args[0]
    assert task_id == "task-1"
    assert payload[0]["blocked_by_temp_ids"] == []
    assert payload[1]["blocked_by_temp_ids"] == []
    bridge.kick_off_task.assert_called_once_with("task-1", 2)
    bridge.update_task_status.assert_not_called()


def test_materialize_plan_with_dependencies_keeps_blocked_by_temp_ids() -> None:
    bridge = MagicMock()
    bridge.batch_create_steps.return_value = ["step-a", "step-b"]

    plan = ExecutionPlan(
        steps=[
            _step("step_1", "Prepare", "Prepare data"),
            _step("step_2", "Process", "Process data", blocked_by=["step_1"]),
        ]
    )

    PlanMaterializer(bridge).materialize("task-1", plan)

    _, payload = bridge.batch_create_steps.call_args[0]
    assert payload[0]["blocked_by_temp_ids"] == []
    assert payload[1]["blocked_by_temp_ids"] == ["step_1"]


def test_materialize_rejects_unknown_dependencies() -> None:
    bridge = MagicMock()
    plan = ExecutionPlan(
        steps=[
            _step("step_1", "Prepare", "Prepare data"),
            _step("step_2", "Process", "Process data", blocked_by=["step_999"]),
        ]
    )

    with pytest.raises(ValueError, match="unknown dependency"):
        PlanMaterializer(bridge).materialize("task-1", plan)

    bridge.batch_create_steps.assert_not_called()
    bridge.kick_off_task.assert_not_called()
    bridge.update_task_status.assert_called_once()
    assert bridge.update_task_status.call_args[0][1] == TaskStatus.FAILED
    bridge.create_activity.assert_called_once()
    assert bridge.create_activity.call_args[0][0] == ActivityEventType.SYSTEM_ERROR


def test_materialize_marks_task_failed_when_batch_create_raises() -> None:
    bridge = MagicMock()
    bridge.batch_create_steps.side_effect = RuntimeError("convex unavailable")
    plan = ExecutionPlan(steps=[_step("step_1", "Analyze", "Analyze requirements")])

    with pytest.raises(RuntimeError, match="convex unavailable"):
        PlanMaterializer(bridge).materialize("task-1", plan)

    bridge.kick_off_task.assert_not_called()
    bridge.update_task_status.assert_called_once()
    bridge.create_activity.assert_called_once()


def test_materialize_requires_step_count_match_from_batch_create() -> None:
    bridge = MagicMock()
    bridge.batch_create_steps.return_value = ["step-a"]
    plan = ExecutionPlan(
        steps=[
            _step("step_1", "Analyze", "Analyze requirements"),
            _step("step_2", "Implement", "Implement changes"),
        ]
    )

    with pytest.raises(RuntimeError, match="unexpected number"):
        PlanMaterializer(bridge).materialize("task-1", plan)

    bridge.kick_off_task.assert_not_called()
    bridge.update_task_status.assert_called_once()
    bridge.create_activity.assert_called_once()


def test_materialize_rejects_empty_plan() -> None:
    bridge = MagicMock()
    plan = ExecutionPlan(steps=[])

    with pytest.raises(ValueError, match="empty execution plan"):
        PlanMaterializer(bridge).materialize("task-1", plan)

    bridge.batch_create_steps.assert_not_called()
    bridge.kick_off_task.assert_not_called()
    bridge.update_task_status.assert_called_once()
    bridge.create_activity.assert_called_once()


def test_materialize_skip_kickoff_does_not_call_kick_off_task() -> None:
    """Story 4.6: skip_kickoff=True skips the kick_off_task call.

    Used by the kickoff watch loop when the task is already in_progress
    (transitioned by the approveAndKickOff Convex mutation).
    """
    bridge = MagicMock()
    bridge.batch_create_steps.return_value = ["step-a"]

    plan = ExecutionPlan(steps=[_step("step_1", "Analyze", "Analyze requirements")])

    created = PlanMaterializer(bridge).materialize("task-1", plan, skip_kickoff=True)

    assert created == ["step-a"]
    bridge.batch_create_steps.assert_called_once()
    # kick_off_task must NOT be called when skip_kickoff=True
    bridge.kick_off_task.assert_not_called()


def test_materialize_default_calls_kick_off_task() -> None:
    """Story 4.6: Default behavior (skip_kickoff=False) still calls kick_off_task."""
    bridge = MagicMock()
    bridge.batch_create_steps.return_value = ["step-a"]

    plan = ExecutionPlan(steps=[_step("step_1", "Analyze", "Analyze requirements")])

    PlanMaterializer(bridge).materialize("task-1", plan)

    bridge.kick_off_task.assert_called_once_with("task-1", 1)
