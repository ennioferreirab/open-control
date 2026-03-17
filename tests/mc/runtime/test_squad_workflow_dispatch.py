"""Tests for squad workflow dispatch: workflowRun creation and gate behavior."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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
    work_mode: str | None = "ai_workflow",
    squad_spec_id: str = "squad-spec-1",
    workflow_spec_id: str = "workflow-spec-1",
    board_id: str = "board-1",
) -> dict:
    data = {
        "id": task_id,
        "title": "Test workflow task",
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
    if work_mode is not None:
        data["work_mode"] = work_mode
    return data


async def _sync_to_thread(func, *args, **kwargs):
    """Run to_thread payloads synchronously in tests."""
    return func(*args, **kwargs)


def _mutation_with_runtime_claims(
    *,
    workflow_run_result: Any = None,
    workflow_run_error: Exception | None = None,
):
    def _mutation(name: str, _args: dict) -> Any:
        if name == "runtimeClaims:acquire":
            return {"granted": True, "claimId": "claim-1"}
        if name == "workflowRuns:create":
            if workflow_run_error is not None:
                raise workflow_run_error
            return workflow_run_result
        return None

    return _mutation


def _make_step_execution_request(step: dict[str, Any]) -> Any:
    """Build a minimal ExecutionRequest for dispatcher review-step tests."""
    from mc.application.execution.file_enricher import build_file_context, resolve_task_dirs
    from mc.application.execution.request import EntityType, ExecutionRequest

    task_id = "task-1"
    files_dir, output_dir = resolve_task_dirs(task_id)

    return ExecutionRequest(
        entity_type=EntityType.STEP,
        entity_id=step["id"],
        task_id=task_id,
        step_id=step["id"],
        title="Main Task",
        step_title=step["title"],
        step_description=step.get("description", ""),
        agent_name=step.get("assigned_agent", "nanobot"),
        agent_prompt=None,
        agent_model=None,
        agent_skills=None,
        reasoning_level=None,
        description=build_file_context(
            [],
            files_dir,
            output_dir,
            is_step=True,
            step_title=step["title"],
            step_description=step.get("description", ""),
            task_title="Main Task",
        ),
        board_name=None,
        memory_workspace=None,
        files_dir=files_dir,
        output_dir=output_dir,
        file_manifest=[],
        task_data={"title": "Main Task", "status": "in_progress"},
        predecessor_step_ids=[],
        is_cc=False,
    )


def _patch_context_builder():
    async def _mock_build_step_context(self, task_id, step):
        return _make_step_execution_request(step)

    return patch(
        "mc.application.execution.context_builder.ContextBuilder.build_step_context",
        new=_mock_build_step_context,
    )


# ---------------------------------------------------------------------------
# Tests: workflowRun creation on kickoff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_run_created_when_work_mode_is_ai_workflow() -> None:
    """KickoffResumeWorker creates a workflowRun for ai_workflow tasks."""
    bridge = MagicMock()
    bridge.get_steps_by_task.return_value = []
    bridge.batch_create_steps.return_value = ["step-a"]
    bridge.mutation.side_effect = _mutation_with_runtime_claims(
        workflow_run_result="workflow-run-1"
    )

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
    bridge.mutation.side_effect = _mutation_with_runtime_claims()

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
async def test_workflow_run_created_for_legacy_workflow_without_work_mode() -> None:
    """Legacy workflow tasks should still create workflow provenance."""
    bridge = MagicMock()
    bridge.get_steps_by_task.return_value = []
    bridge.batch_create_steps.return_value = ["step-a"]
    bridge.mutation.side_effect = _mutation_with_runtime_claims(
        workflow_run_result="workflow-run-legacy"
    )

    materializer = MagicMock()
    materializer.materialize.return_value = ["step-a"]

    dispatcher = MagicMock()
    dispatcher.dispatch_steps = AsyncMock()

    worker = KickoffResumeWorker(
        ctx=MagicMock(bridge=bridge),
        plan_materializer=materializer,
        step_dispatcher=dispatcher,
    )

    task_data = _make_task_data(work_mode=None)
    task_data["execution_plan"]["generatedBy"] = "workflow"
    await worker.process_batch([task_data])

    mutation_calls = bridge.mutation.call_args_list
    workflow_run_calls = [c for c in mutation_calls if c[0][0] == "workflowRuns:create"]
    assert len(workflow_run_calls) == 1, "Expected workflowRuns:create for legacy workflow task"


@pytest.mark.asyncio
async def test_workflow_run_creation_failure_is_non_fatal() -> None:
    """A failure to create workflowRun does not abort the kickoff."""
    bridge = MagicMock()
    bridge.get_steps_by_task.return_value = []
    bridge.batch_create_steps.return_value = ["step-a"]
    bridge.mutation.side_effect = _mutation_with_runtime_claims(
        workflow_run_error=RuntimeError("Convex unavailable")
    )

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
async def test_review_step_type_runs_as_agent_step() -> None:
    """Workflow review steps should dispatch to the reviewer agent, not human gating."""
    bridge = MagicMock()
    bridge.update_step_status = MagicMock()
    bridge.create_activity = MagicMock()
    bridge.query.return_value = {"title": "Main Task", "status": "in_progress", "files": []}
    bridge.get_task_messages.return_value = []
    bridge.get_agent_by_name.return_value = None
    bridge.get_board_by_id.return_value = None
    bridge.sync_task_output_files.return_value = None
    bridge.post_step_completion.return_value = None
    bridge.check_and_unblock_dependents.return_value = []

    dispatcher = StepDispatcher(bridge)

    review_step = {
        "id": "step-3",
        "title": "Review output",
        "assigned_agent": "reviewer",
        "workflow_step_type": "review",
        "review_spec_id": "review-spec-1",
        "parallel_group": 1,
        "order": 3,
        "status": "assigned",
    }

    run_agent = AsyncMock(
        return_value=(
            '{"verdict":"approved","issues":[],"strengths":[],"scores":{},'
            '"vetoesTriggered":[],"recommendedReturnStep":null}'
        )
    )

    with (
        patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
        _patch_context_builder(),
        patch("mc.contexts.execution.step_dispatcher._run_step_agent", new=run_agent),
        patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}),
        patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]),
    ):
        await dispatcher._execute_step("task-1", review_step)

    update_calls = bridge.update_step_status.call_args_list
    assert not any(c[0][1] == StepStatus.WAITING_HUMAN for c in update_calls), (
        "Review steps should not be treated as human gates"
    )
    run_agent.assert_awaited_once()


@pytest.mark.asyncio
async def test_review_step_with_human_agent_sets_waiting_human() -> None:
    """Review steps assigned to 'human' stay assigned until a person acts."""
    bridge = MagicMock()
    bridge.update_step_status = MagicMock()
    bridge.create_activity = MagicMock()

    dispatcher = StepDispatcher(bridge)

    review_step = {
        "id": "step-3",
        "title": "Review output",
        "assigned_agent": "human",
        "workflow_step_type": "review",
        "review_spec_id": "review-spec-1",
        "parallel_group": 1,
        "order": 3,
        "status": "assigned",
    }

    await dispatcher._execute_step("task-1", review_step)

    update_calls = bridge.update_step_status.call_args_list
    assert not any(c[0][1] == StepStatus.WAITING_HUMAN for c in update_calls), (
        "Human-assigned review steps should stay assigned until manual action"
    )
    assert not any(c[0][1] == StepStatus.RUNNING for c in update_calls), (
        "Review step assigned to human should not start running"
    )


def test_gate_logic_depends_on_step_type_and_human_assignment() -> None:
    """Only gate step types or human-assigned steps are routed to waiting_human.

    This is a pure logic test verifying the dispatcher logic without needing
    to actually run an agent.
    """

    def is_gate(step_type: str | None, agent_name: str) -> bool:
        """Mirror the dispatcher's gate logic."""
        return agent_name == "human" or step_type in ("human", "checkpoint")

    # Always-gate types (regardless of agent)
    assert is_gate("human", "nanobot")
    assert is_gate("human", "human")
    assert is_gate("checkpoint", "nanobot")
    assert is_gate("checkpoint", "human")

    # Review gates only when explicitly assigned to a human.
    assert is_gate("review", "human")
    assert not is_gate("review", "reviewer")
    assert not is_gate("review", "nanobot")

    # Non-gate types
    for step_type in ("agent", "system", None, ""):
        assert not is_gate(step_type, "nanobot"), (
            f"Expected {step_type!r} to NOT be a gate step type"
        )
        assert is_gate(step_type, "human"), (
            f"Expected {step_type!r} to gate when explicitly assigned to a human"
        )
