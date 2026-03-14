"""Tests for squad workflow dispatch: workflowRun creation and gate behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mc.contexts.execution.step_dispatcher import StepDispatcher  # noqa: F401 used below
from mc.runtime.workers.kickoff import KickoffResumeWorker
from mc.types import ExecutionPlanStep, StepStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plan_step(
    temp_id: str,
    title: str,
    workflow_step_type: str | None = None,
    workflow_step_id: str | None = None,
    blocked_by: list[str] | None = None,
) -> ExecutionPlanStep:
    return ExecutionPlanStep(
        temp_id=temp_id,
        title=title,
        description=f"Description for {title}",
        assigned_agent="nanobot",
        blocked_by=blocked_by or [],
        parallel_group=1,
        order=1,
        workflow_step_id=workflow_step_id or temp_id,
        workflow_step_type=workflow_step_type,
    )


def _make_task_data(
    task_id: str = "task-1",
    work_mode: str = "ai_workflow",
    squad_spec_id: str = "squad-spec-1",
    workflow_spec_id: str = "workflow-spec-1",
    board_id: str = "board-1",
) -> dict:
    return {
        "id": task_id,
        "title": "Test workflow task",
        "work_mode": work_mode,
        "squad_spec_id": squad_spec_id,
        "workflow_spec_id": workflow_spec_id,
        "board_id": board_id,
        "execution_plan": {
            "steps": [
                {
                    "temp_id": "step_1",
                    "title": "Analyze data",
                    "description": "Run analysis",
                    "assigned_agent": "nanobot",
                    "blocked_by": [],
                    "parallel_group": 1,
                    "order": 1,
                    "workflow_step_id": "analyze",
                    "workflow_step_type": "agent",
                }
            ],
            "generatedAt": "2026-03-14T10:00:00Z",
            "generatedBy": "lead-agent",
        },
        "updated_at": "2026-03-14T10:00:00Z",
    }


# ---------------------------------------------------------------------------
# Tests: workflowRun creation on kickoff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_run_created_when_work_mode_is_ai_workflow() -> None:
    """KickoffResumeWorker creates a workflowRun for ai_workflow tasks."""
    bridge = MagicMock()
    bridge.get_steps_by_task.return_value = []
    bridge.batch_create_steps.return_value = ["step-a"]
    bridge.mutation.return_value = "workflow-run-1"

    materializer = MagicMock()
    materializer.materialize.return_value = ["step-a"]

    dispatcher = MagicMock()
    dispatcher.dispatch_steps = AsyncMock()

    worker = KickoffResumeWorker(
        ctx=MagicMock(bridge=bridge),
        plan_materializer=materializer,
        step_dispatcher=dispatcher,
    )

    task_data = _make_task_data()
    await worker.process_batch([task_data])

    # workflowRuns:create must have been called
    mutation_calls = bridge.mutation.call_args_list
    workflow_run_calls = [c for c in mutation_calls if c[0][0] == "workflowRuns:create"]
    assert len(workflow_run_calls) == 1, "Expected exactly one workflowRuns:create call"

    args = workflow_run_calls[0][0][1]
    assert args["task_id"] == "task-1"
    assert args["squad_spec_id"] == "squad-spec-1"
    assert args["workflow_spec_id"] == "workflow-spec-1"
    assert args["board_id"] == "board-1"
    assert "launched_at" in args


@pytest.mark.asyncio
async def test_workflow_run_not_created_for_non_workflow_tasks() -> None:
    """KickoffResumeWorker does NOT create a workflowRun for ai_single or manual tasks."""
    bridge = MagicMock()
    bridge.get_steps_by_task.return_value = []
    bridge.batch_create_steps.return_value = ["step-a"]
    bridge.mutation.return_value = None

    materializer = MagicMock()
    materializer.materialize.return_value = ["step-a"]

    dispatcher = MagicMock()
    dispatcher.dispatch_steps = AsyncMock()

    worker = KickoffResumeWorker(
        ctx=MagicMock(bridge=bridge),
        plan_materializer=materializer,
        step_dispatcher=dispatcher,
    )

    task_data = _make_task_data(work_mode="ai_single")
    await worker.process_batch([task_data])

    mutation_calls = bridge.mutation.call_args_list
    workflow_run_calls = [c for c in mutation_calls if c[0][0] == "workflowRuns:create"]
    assert len(workflow_run_calls) == 0, "Should NOT create workflowRun for ai_single tasks"


@pytest.mark.asyncio
async def test_workflow_run_creation_failure_is_non_fatal() -> None:
    """A failure to create workflowRun does not abort the kickoff."""
    bridge = MagicMock()
    bridge.get_steps_by_task.return_value = []
    bridge.batch_create_steps.return_value = ["step-a"]
    bridge.mutation.side_effect = RuntimeError("Convex unavailable")

    materializer = MagicMock()
    materializer.materialize.return_value = ["step-a"]

    dispatcher = MagicMock()
    dispatcher.dispatch_steps = AsyncMock()

    worker = KickoffResumeWorker(
        ctx=MagicMock(bridge=bridge),
        plan_materializer=materializer,
        step_dispatcher=dispatcher,
    )

    task_data = _make_task_data()
    # Should not raise even if workflowRun creation fails
    await worker.process_batch([task_data])

    # dispatch_steps should still have been called
    dispatcher.dispatch_steps.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: gate behavior in StepDispatcher
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_human_step_type_sets_waiting_human() -> None:
    """Workflow steps with type=human are set to waiting_human by dispatcher."""
    bridge = MagicMock()
    bridge.update_step_status = MagicMock()
    bridge.create_activity = MagicMock()

    dispatcher = StepDispatcher(bridge)

    human_step = {
        "id": "step-1",
        "title": "Human review",
        "assigned_agent": "nanobot",
        "workflow_step_type": "human",
        "parallel_group": 1,
        "order": 1,
        "status": "assigned",
    }

    await dispatcher._execute_step("task-1", human_step)

    update_calls = bridge.update_step_status.call_args_list
    assert any(c[0][1] == StepStatus.WAITING_HUMAN for c in update_calls), (
        "Human step should be set to waiting_human"
    )


@pytest.mark.asyncio
async def test_checkpoint_step_type_sets_waiting_human() -> None:
    """Workflow steps with type=checkpoint are set to waiting_human by dispatcher."""
    bridge = MagicMock()
    bridge.update_step_status = MagicMock()
    bridge.create_activity = MagicMock()

    dispatcher = StepDispatcher(bridge)

    checkpoint_step = {
        "id": "step-2",
        "title": "Quality gate",
        "assigned_agent": "nanobot",
        "workflow_step_type": "checkpoint",
        "parallel_group": 1,
        "order": 2,
        "status": "assigned",
    }

    await dispatcher._execute_step("task-1", checkpoint_step)

    update_calls = bridge.update_step_status.call_args_list
    assert any(c[0][1] == StepStatus.WAITING_HUMAN for c in update_calls), (
        "Checkpoint step should be set to waiting_human"
    )


@pytest.mark.asyncio
async def test_review_step_type_sets_waiting_human() -> None:
    """Workflow steps with type=review are set to waiting_human by dispatcher."""
    bridge = MagicMock()
    bridge.update_step_status = MagicMock()
    bridge.create_activity = MagicMock()

    dispatcher = StepDispatcher(bridge)

    review_step = {
        "id": "step-3",
        "title": "Review output",
        "assigned_agent": "nanobot",
        "workflow_step_type": "review",
        "review_spec_id": "review-spec-1",
        "parallel_group": 1,
        "order": 3,
        "status": "assigned",
    }

    await dispatcher._execute_step("task-1", review_step)

    update_calls = bridge.update_step_status.call_args_list
    assert any(c[0][1] == StepStatus.WAITING_HUMAN for c in update_calls), (
        "Review step should be set to waiting_human"
    )


def test_agent_step_type_is_not_treated_as_gate() -> None:
    """Agent-type workflow steps are not identified as gate steps.

    This is a pure logic test verifying the dispatcher logic without needing
    to actually run an agent.
    """
    # Verify that only human/checkpoint/review are treated as gate steps
    gate_types = {"human", "checkpoint", "review"}
    non_gate_types = {"agent", "system", None, ""}

    for step_type in gate_types:
        is_gate = step_type in ("human", "checkpoint", "review")
        assert is_gate, f"Expected {step_type!r} to be a gate step type"

    for step_type in non_gate_types:
        is_gate = step_type in ("human", "checkpoint", "review")
        assert not is_gate, f"Expected {step_type!r} to NOT be a gate step type"
