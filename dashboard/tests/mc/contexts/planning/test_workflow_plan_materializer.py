"""Tests for workflow metadata preservation during plan materialization."""

from __future__ import annotations

from unittest.mock import MagicMock

from mc.contexts.planning.materializer import PlanMaterializer
from mc.types import ExecutionPlan, ExecutionPlanStep, WorkflowStepType


def _make_workflow_step(
    temp_id: str,
    title: str,
    description: str,
    workflow_step_type: str = WorkflowStepType.AGENT,
    workflow_step_id: str | None = None,
    agent_spec_id: str | None = None,
    review_spec_id: str | None = None,
    on_reject_step_id: str | None = None,
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
        workflow_step_id=workflow_step_id or temp_id,
        workflow_step_type=workflow_step_type,
        agent_spec_id=agent_spec_id,
        review_spec_id=review_spec_id,
        on_reject_step_id=on_reject_step_id,
    )


def test_workflow_agent_step_metadata_preserved() -> None:
    """Workflow agent step type is preserved in the batch create payload."""
    bridge = MagicMock()
    bridge.batch_create_steps.return_value = ["step-a"]

    plan = ExecutionPlan(
        steps=[
            _make_workflow_step(
                "step_1",
                "Analyze",
                "Analyze requirements",
                workflow_step_type=WorkflowStepType.AGENT,
                workflow_step_id="analyze-step",
                agent_spec_id="agent-spec-123",
            )
        ]
    )

    PlanMaterializer(bridge).materialize("task-1", plan)

    _, payload = bridge.batch_create_steps.call_args[0]
    step_payload = payload[0]
    assert step_payload["workflow_step_id"] == "analyze-step"
    assert step_payload["workflow_step_type"] == "agent"
    assert step_payload["agent_spec_id"] == "agent-spec-123"


def test_human_step_type_survives_materialization() -> None:
    """Human step type is preserved so dispatcher can route correctly."""
    bridge = MagicMock()
    bridge.batch_create_steps.return_value = ["step-a"]

    plan = ExecutionPlan(
        steps=[
            _make_workflow_step(
                "step_1",
                "Review docs",
                "Human reviews the documents",
                workflow_step_type=WorkflowStepType.HUMAN,
                workflow_step_id="review-docs",
            )
        ]
    )

    PlanMaterializer(bridge).materialize("task-1", plan)

    _, payload = bridge.batch_create_steps.call_args[0]
    assert payload[0]["workflow_step_type"] == "human"
    assert payload[0]["workflow_step_id"] == "review-docs"


def test_checkpoint_step_type_survives_materialization() -> None:
    """Checkpoint step type is preserved."""
    bridge = MagicMock()
    bridge.batch_create_steps.return_value = ["step-a"]

    plan = ExecutionPlan(
        steps=[
            _make_workflow_step(
                "step_1",
                "Checkpoint",
                "Quality gate checkpoint",
                workflow_step_type=WorkflowStepType.CHECKPOINT,
                workflow_step_id="quality-gate",
            )
        ]
    )

    PlanMaterializer(bridge).materialize("task-1", plan)

    _, payload = bridge.batch_create_steps.call_args[0]
    assert payload[0]["workflow_step_type"] == "checkpoint"


def test_review_step_type_with_review_spec_id_preserved() -> None:
    """Review step preserves reviewSpecId for the dispatcher."""
    bridge = MagicMock()
    bridge.batch_create_steps.return_value = ["step-a"]

    plan = ExecutionPlan(
        steps=[
            _make_workflow_step(
                "step_1",
                "Review output",
                "Review the agent output",
                workflow_step_type=WorkflowStepType.REVIEW,
                workflow_step_id="output-review",
                review_spec_id="review-spec-456",
                on_reject_step_id="step_0",
            )
        ]
    )

    PlanMaterializer(bridge).materialize("task-1", plan)

    _, payload = bridge.batch_create_steps.call_args[0]
    step_payload = payload[0]
    assert step_payload["workflow_step_type"] == "review"
    assert step_payload["review_spec_id"] == "review-spec-456"
    assert step_payload["on_reject_step_id"] == "step_0"


def test_dependency_mapping_still_works_with_workflow_metadata() -> None:
    """Dependency mapping (blockedByTempIds) still works when metadata is present."""
    bridge = MagicMock()
    bridge.batch_create_steps.return_value = ["step-a", "step-b"]

    plan = ExecutionPlan(
        steps=[
            _make_workflow_step(
                "step_1",
                "Analyze",
                "Analyze data",
                workflow_step_type=WorkflowStepType.AGENT,
                workflow_step_id="analyze",
                agent_spec_id="agent-spec-1",
            ),
            _make_workflow_step(
                "step_2",
                "Review",
                "Review analysis",
                workflow_step_type=WorkflowStepType.REVIEW,
                workflow_step_id="review",
                review_spec_id="review-spec-1",
                blocked_by=["step_1"],
            ),
        ]
    )

    PlanMaterializer(bridge).materialize("task-1", plan)

    _, payload = bridge.batch_create_steps.call_args[0]
    assert payload[0]["blocked_by_temp_ids"] == []
    assert payload[1]["blocked_by_temp_ids"] == ["step_1"]
    assert payload[1]["workflow_step_type"] == "review"
    assert payload[1]["review_spec_id"] == "review-spec-1"


def test_plain_steps_without_workflow_metadata_unaffected() -> None:
    """Non-workflow steps (no metadata fields) behave exactly as before."""
    bridge = MagicMock()
    bridge.batch_create_steps.return_value = ["step-a", "step-b"]

    plan = ExecutionPlan(
        steps=[
            ExecutionPlanStep(
                temp_id="step_1",
                title="Analyze",
                description="Analyze requirements",
                assigned_agent="nanobot",
                blocked_by=[],
                parallel_group=1,
                order=1,
            ),
            ExecutionPlanStep(
                temp_id="step_2",
                title="Implement",
                description="Implement changes",
                assigned_agent="nanobot",
                blocked_by=["step_1"],
                parallel_group=2,
                order=2,
            ),
        ]
    )

    PlanMaterializer(bridge).materialize("task-1", plan)

    _, payload = bridge.batch_create_steps.call_args[0]
    # Workflow metadata fields should NOT be present for plain steps
    assert "workflow_step_id" not in payload[0]
    assert "workflow_step_type" not in payload[0]
    assert "agent_spec_id" not in payload[0]
    assert payload[1]["blocked_by_temp_ids"] == ["step_1"]
