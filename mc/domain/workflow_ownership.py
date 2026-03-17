"""Helpers for determining whether a task is owned by workflow execution."""

from __future__ import annotations

from typing import Any, Mapping


def is_workflow_generated_plan(plan: Any) -> bool:
    """Return True when a plan was compiled by the workflow engine."""
    return isinstance(plan, Mapping) and (
        plan.get("generatedBy") == "workflow" or plan.get("generated_by") == "workflow"
    )


def is_workflow_owned_task(task_data: Mapping[str, Any]) -> bool:
    """Return True for explicit workflow tasks and legacy workflow-plan tasks."""
    work_mode = task_data.get("work_mode") or task_data.get("workMode")
    if work_mode == "ai_workflow":
        return True
    if work_mode is not None:
        return False

    execution_plan = task_data.get("execution_plan") or task_data.get("executionPlan") or {}
    return is_workflow_generated_plan(execution_plan)
