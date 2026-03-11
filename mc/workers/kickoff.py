"""Kickoff/resume worker — handles task kickoff and resume flows.

Extracted from mc.orchestrator per Story 17.1 (AC4).
Delegates to PlanMaterializer and StepDispatcher for actual execution.
Updated to accept RuntimeContext per Story 20.3.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from mc.types import (
    ActivityEventType,
    ExecutionPlan,
    StepStatus,
    TaskStatus,
)

if TYPE_CHECKING:
    from mc.infrastructure.runtime_context import RuntimeContext
    from mc.contexts.execution.step_dispatcher import StepDispatcher
    from mc.contexts.planning.materializer import PlanMaterializer

logger = logging.getLogger(__name__)


class KickoffResumeWorker:
    """Watches for kicked-off or resumed tasks that need step dispatch."""

    def __init__(
        self,
        ctx: RuntimeContext,
        plan_materializer: PlanMaterializer,
        step_dispatcher: StepDispatcher,
        *,
        known_kickoff_ids: set[str] | None = None,
    ) -> None:
        self._ctx = ctx
        self._bridge = ctx.bridge
        self._plan_materializer = plan_materializer
        self._step_dispatcher = step_dispatcher
        # Shared with planning worker to avoid double-dispatch
        self._known_kickoff_ids = (
            known_kickoff_ids if known_kickoff_ids is not None else set()
        )

    async def process_batch(self, tasks: list[dict[str, Any]]) -> None:
        """Process a batch of in_progress tasks from a subscription update.

        Handles two cases:
        1. New kick-off (approveAndKickOff): task has a plan but NO materialized
           steps -> materialize and dispatch.
        2. Resume (resumeTask): task has existing steps in assigned/blocked status
           (already materialized) -> dispatch_steps to continue execution.
        """
        # Prune IDs no longer in_progress so re-entries are handled.
        current_ids = {t.get("id") for t in tasks if t.get("id")}
        self._known_kickoff_ids &= current_ids

        for task_data in tasks:
            task_id = task_data.get("id")
            if not task_id or task_id in self._known_kickoff_ids:
                continue
            self._known_kickoff_ids.add(task_id)

            # Only process tasks with an execution plan
            if not task_data.get("execution_plan"):
                continue

            try:
                await self._process_task(task_id, task_data)
            except Exception:
                logger.error(
                    "[kickoff] Error processing task %s",
                    task_id,
                    exc_info=True,
                )

    async def _process_task(
        self, task_id: str, task_data: dict[str, Any]
    ) -> None:
        """Handle a single in_progress task for kickoff or resume."""
        steps = await asyncio.to_thread(
            self._bridge.get_steps_by_task, task_id
        )

        title = task_data.get("title", task_id)

        if steps:
            created_step_ids = await asyncio.to_thread(
                self._materialize_incremental_steps,
                task_id,
                task_data,
                steps,
            )
            if created_step_ids:
                logger.info(
                    "[kickoff] Task '%s': materialized %d incremental step(s) on resume",
                    title,
                    len(created_step_ids),
                )
                steps = await asyncio.to_thread(
                    self._bridge.get_steps_by_task, task_id
                )
            # Task has materialized steps -- this is a resumed task (Task 8.2).
            await self._handle_resume(task_id, title, steps)
            return

        # No steps -- this is a kicked-off task, materialize the plan.
        await self._handle_kickoff(task_id, title, task_data)

    async def _handle_resume(
        self, task_id: str, title: str, steps: list[dict[str, Any]]
    ) -> None:
        """Resume a task by dispatching assigned or unblocked-pending steps."""
        completed_step_ids = {
            str(step.get("id"))
            for step in steps
            if step.get("status") == StepStatus.COMPLETED and step.get("id")
        }
        dispatchable_step_ids = []
        for step in steps:
            step_id_str = str(step.get("id")) if step.get("id") else None
            if not step_id_str:
                continue
            status = step.get("status")
            if status == StepStatus.ASSIGNED:
                dispatchable_step_ids.append(step_id_str)
            elif status == StepStatus.PLANNED:
                # Dispatch if all blockers are already completed
                blocked_by = step.get("blocked_by") or []
                if all(str(b) in completed_step_ids for b in blocked_by):
                    dispatchable_step_ids.append(step_id_str)

        if dispatchable_step_ids:
            logger.info(
                "[kickoff] Detected resumed task '%s'; dispatching %d step(s) "
                "(assigned + unblocked pending)",
                title,
                len(dispatchable_step_ids),
            )
            asyncio.create_task(
                self._step_dispatcher.dispatch_steps(
                    task_id, dispatchable_step_ids
                )
            )
        else:
            logger.info(
                "[kickoff] Resumed task '%s' has no dispatchable steps "
                "(may still have running steps)",
                title,
            )

    async def _handle_kickoff(
        self, task_id: str, title: str, task_data: dict[str, Any]
    ) -> None:
        """Materialize and dispatch steps for a kicked-off task."""
        logger.info(
            "[kickoff] Detected kicked-off task '%s'; materializing...",
            title,
        )
        try:
            plan = ExecutionPlan.from_dict(task_data["execution_plan"])
            created_step_ids = await asyncio.to_thread(
                self._plan_materializer.materialize,
                task_id,
                plan,
                skip_kickoff=True,
            )
            asyncio.create_task(
                self._step_dispatcher.dispatch_steps(
                    task_id, created_step_ids
                )
            )
            logger.info(
                "[kickoff] Task '%s': materialized %d steps after kick-off",
                title,
                len(created_step_ids),
            )
        except Exception as exc:
            logger.error(
                "[kickoff] Materialization failed for kicked-off task %s",
                task_id,
                exc_info=True,
            )
            # The materializer's _mark_task_failed() tries FAILED, which
            # will silently fail since in_progress -> failed is invalid. We
            # transition to CRASHED instead (a universal target from any state).
            try:
                await asyncio.to_thread(
                    self._bridge.update_task_status,
                    task_id,
                    TaskStatus.CRASHED,
                    None,
                    f"Materialization failed after kick-off: "
                    f"{type(exc).__name__}: {exc}",
                )
                await asyncio.to_thread(
                    self._bridge.create_activity,
                    ActivityEventType.SYSTEM_ERROR,
                    f"Materialization failed for '{title}': "
                    f"{type(exc).__name__}: {exc}",
                    task_id,
                )
            except Exception:
                logger.error(
                    "[kickoff] Failed to mark task %s as crashed after "
                    "materialization failure",
                    task_id,
                    exc_info=True,
                )

    def _materialize_incremental_steps(
        self,
        task_id: str,
        task_data: dict[str, Any],
        steps: list[dict[str, Any]],
    ) -> list[str]:
        """Materialize any newly-added plan steps on top of existing step state."""
        raw_plan = task_data.get("execution_plan")
        if not raw_plan:
            return []

        plan = ExecutionPlan.from_dict(raw_plan)
        if not plan.steps:
            return []

        used_step_ids: set[str] = set()
        existing_by_order: dict[int, list[dict[str, Any]]] = {}
        for step in steps:
            order = step.get("order")
            if isinstance(order, int):
                existing_by_order.setdefault(order, []).append(step)

        temp_id_to_real_id: dict[str, str] = {}
        completed_step_ids = {
            str(step.get("id"))
            for step in steps
            if step.get("status") == StepStatus.COMPLETED and step.get("id")
        }

        for plan_step in plan.steps:
            if plan_step.temp_id == "__merge_alias__":
                continue
            candidates = [
                step
                for step in existing_by_order.get(plan_step.order, [])
                if step.get("id") and str(step.get("id")) not in used_step_ids
            ]
            matched_step = next(
                (step for step in candidates if step.get("title") == plan_step.title),
                candidates[0] if len(candidates) == 1 else None,
            )
            if matched_step and matched_step.get("id"):
                step_id = str(matched_step["id"])
                temp_id_to_real_id[plan_step.temp_id] = step_id
                used_step_ids.add(step_id)

        created_step_ids: list[str] = []
        for plan_step in plan.steps:
            if plan_step.temp_id == "__merge_alias__" or plan_step.temp_id in temp_id_to_real_id:
                continue

            blocked_by_ids: list[str] = []
            for dependency in plan_step.blocked_by:
                dependency_id = temp_id_to_real_id.get(dependency)
                if dependency_id is None:
                    raise RuntimeError(
                        f"Cannot materialize incremental step '{plan_step.temp_id}' "
                        f"because dependency '{dependency}' is missing from existing steps."
                    )
                blocked_by_ids.append(dependency_id)

            step_id = self._bridge.create_step(
                {
                    "task_id": task_id,
                    "title": plan_step.title,
                    "description": plan_step.description,
                    "assigned_agent": plan_step.assigned_agent,
                    "blocked_by": blocked_by_ids,
                    "parallel_group": plan_step.parallel_group,
                    "order": plan_step.order,
                }
            )
            temp_id_to_real_id[plan_step.temp_id] = step_id
            created_step_ids.append(step_id)

            if blocked_by_ids and all(dep in completed_step_ids for dep in blocked_by_ids):
                for dependency_id in blocked_by_ids:
                    self._bridge.check_and_unblock_dependents(dependency_id)

        return created_step_ids
