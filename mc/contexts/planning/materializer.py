"""Materialize execution plans into Convex step records."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mc.domain.utils import as_positive_int
from mc.types import (
    HUMAN_AGENT_NAME,
    NANOBOT_AGENT_NAME,
    ActivityEventType,
    ExecutionPlan,
    TaskStatus,
    WorkflowStepType,
)

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


class PlanMaterializer:
    """Convert an ExecutionPlan into concrete step documents in Convex."""

    def __init__(self, bridge: ConvexBridge) -> None:
        self._bridge = bridge

    def materialize(
        self, task_id: str, plan: ExecutionPlan, *, skip_kickoff: bool = False
    ) -> list[str]:
        """Materialize steps for a task and transition the task to active state.

        Args:
            task_id: Convex task _id.
            plan: Execution plan to materialize.
            skip_kickoff: When True, skip the kick_off_task() call. Used for
                supervised tasks where approveAndKickOff already transitioned
                the task to in_progress.
        """
        try:
            if not plan.steps:
                raise ValueError(f"Cannot materialize empty execution plan for task {task_id}")

            self._validate_dependencies(plan)
            steps_payload = self._build_steps_payload(plan)

            created_step_ids = self._bridge.batch_create_steps(task_id, steps_payload)
            if len(created_step_ids) != len(steps_payload):
                raise RuntimeError(
                    "steps:batchCreate returned an unexpected number of created step IDs"
                )

            if not skip_kickoff:
                self._bridge.kick_off_task(task_id, len(created_step_ids))

            logger.info(
                "[materializer] Materialized %d steps for task %s",
                len(created_step_ids),
                task_id,
            )
            return created_step_ids
        except Exception as exc:
            logger.error(
                "[materializer] Failed to materialize plan for task %s: %s",
                task_id,
                exc,
            )
            self._mark_task_failed(task_id, exc)
            raise

    def _validate_dependencies(self, plan: ExecutionPlan) -> None:
        """Ensure all blocked_by refs point to known temp IDs in this plan."""
        all_temp_ids = {step.temp_id for step in plan.steps}

        for step in plan.steps:
            for dep in step.blocked_by:
                if dep not in all_temp_ids:
                    raise ValueError(f"Step '{step.temp_id}' references unknown dependency '{dep}'")
                if dep == step.temp_id:
                    raise ValueError(f"Step '{step.temp_id}' cannot depend on itself")

    def _build_steps_payload(self, plan: ExecutionPlan) -> list[dict[str, object]]:
        """Build snake_case payload accepted by bridge.batch_create_steps()."""
        payload: list[dict[str, object]] = []

        for index, step in enumerate(plan.steps, start=1):
            if step.temp_id == "__merge_alias__":
                continue  # Visual-only alias, not a real step
            title = (step.title or step.description or f"Step {index}").strip()
            description = (step.description or title).strip()
            # Human/checkpoint workflow steps must keep "human" as the
            # assigned agent so the UI renders them correctly instead of
            # falling back to "nanobot".
            if step.workflow_step_type in (
                WorkflowStepType.HUMAN,
                WorkflowStepType.CHECKPOINT,
            ):
                assigned_agent = HUMAN_AGENT_NAME
            else:
                assigned_agent = (
                    step.assigned_agent or NANOBOT_AGENT_NAME
                ).strip() or NANOBOT_AGENT_NAME

            entry: dict[str, object] = {
                "temp_id": step.temp_id,
                "title": title,
                "description": description,
                "assigned_agent": assigned_agent,
                "blocked_by_temp_ids": [dep for dep in step.blocked_by if dep],
                "parallel_group": as_positive_int(step.parallel_group, default=1),
                "order": as_positive_int(step.order, default=index),
            }

            # Preserve workflow metadata when present.
            if step.workflow_step_id is not None:
                entry["workflow_step_id"] = step.workflow_step_id
            if step.workflow_step_type is not None:
                entry["workflow_step_type"] = step.workflow_step_type
            if step.agent_id is not None:
                entry["agent_id"] = step.agent_id
            if step.agent_spec_id is not None:
                entry["agent_spec_id"] = step.agent_spec_id
            if step.review_spec_id is not None:
                entry["review_spec_id"] = step.review_spec_id
            if step.on_reject_step_id is not None:
                entry["on_reject_step_id"] = step.on_reject_step_id

            payload.append(entry)

        return payload

    def _mark_task_failed(self, task_id: str, exc: Exception) -> None:
        """Best-effort transition to failed and log activity."""
        description = f"Plan materialization failed: {type(exc).__name__}: {exc}"

        try:
            self._bridge.update_task_status(
                task_id,
                TaskStatus.FAILED,
                description=description,
            )
        except Exception:
            logger.exception(
                "[materializer] Failed to set task %s status to failed",
                task_id,
            )

        try:
            self._bridge.create_activity(
                ActivityEventType.SYSTEM_ERROR,
                description,
                task_id=task_id,
            )
        except Exception:
            logger.exception(
                "[materializer] Failed to create failure activity for task %s",
                task_id,
            )
