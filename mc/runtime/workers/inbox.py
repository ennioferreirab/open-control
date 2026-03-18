"""Inbox worker — handles new task processing, auto-title, and initial routing."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from mc.bridge.runtime_claims import acquire_runtime_claim, task_snapshot_claim_kind
from mc.contexts.planning.title_generation import generate_title_via_low_agent
from mc.contexts.routing.llm_delegator import LLMDelegationRouter
from mc.domain.workflow_ownership import is_workflow_generated_plan, is_workflow_owned_task
from mc.types import ExecutionPlan

if TYPE_CHECKING:
    from mc.contexts.execution.step_dispatcher import StepDispatcher
    from mc.contexts.planning.materializer import PlanMaterializer
    from mc.infrastructure.runtime_context import RuntimeContext

logger = logging.getLogger(__name__)


def _transition_applied_or_noop(task_id: str, to_status: str, result: Any) -> bool:
    if not isinstance(result, dict):
        logger.warning("[inbox] Task %s transition to %s returned %r", task_id, to_status, result)
        return False
    kind = result.get("kind")
    if kind == "applied":
        return True
    if kind == "noop":
        logger.info(
            "[inbox] Task %s transition to %s already applied (%s)",
            task_id,
            to_status,
            result.get("reason"),
        )
        return True
    if kind == "conflict":
        logger.warning(
            "[inbox] Task %s transition to %s skipped due to %s (current_status=%s, current_state_version=%s)",
            task_id,
            to_status,
            result.get("reason"),
            result.get("current_status"),
            result.get("current_state_version"),
        )
        return False
    logger.warning(
        "[inbox] Task %s transition to %s returned unknown result %r", task_id, to_status, result
    )
    return False


class InboxWorker:
    """Processes inbox tasks: auto-title generation, routing, and workflow dispatch."""

    def __init__(
        self,
        ctx: RuntimeContext,
        plan_materializer: PlanMaterializer | None = None,
        step_dispatcher: StepDispatcher | None = None,
    ) -> None:
        self._ctx = ctx
        self._bridge = ctx.bridge
        self._plan_materializer = plan_materializer
        self._step_dispatcher = step_dispatcher
        self._known_inbox_ids: set[str] = set()

    async def process_batch(self, tasks: list[dict[str, Any]]) -> None:
        """Process a batch of inbox tasks from a subscription update."""
        current_ids = {task.get("id") for task in tasks if task.get("id")}
        self._known_inbox_ids &= current_ids

        for task_data in tasks:
            task_id = task_data.get("id")
            if not task_id or task_id in self._known_inbox_ids:
                continue
            claimed = await asyncio.to_thread(
                acquire_runtime_claim,
                self._bridge,
                claim_kind=task_snapshot_claim_kind("inbox", task_data),
                entity_type="task",
                entity_id=task_id,
                metadata={"status": task_data.get("status", "inbox")},
            )
            if not claimed:
                logger.debug("[inbox] Claim denied for task %s", task_id)
                continue
            if task_data.get("is_manual"):
                self._known_inbox_ids.add(task_id)
                continue
            self._known_inbox_ids.add(task_id)
            try:
                await self.process_task(task_data)
            except Exception:
                logger.warning(
                    "[inbox] Error processing inbox task %s",
                    task_id,
                    exc_info=True,
                )

    async def process_task(self, task_data: dict[str, Any]) -> None:
        """Handle an inbox task: generate auto-title then transition to planning or assigned."""
        task_id = task_data.get("id")
        if not isinstance(task_id, str):
            logger.warning("[inbox] Task missing 'id' field, skipping")
            return
        if task_data.get("is_manual"):
            logger.info("[inbox] Skipping manual inbox task %s", task_id)
            return

        title = task_data.get("title", "")
        description = task_data.get("description")
        assigned_agent = task_data.get("assigned_agent")
        auto_title = task_data.get("auto_title")

        logger.info(
            "[inbox] Processing inbox task %s: auto_title=%r, has_description=%s, keys=%s",
            task_id,
            auto_title,
            bool(description),
            list(task_data.keys()),
        )

        if auto_title and description:
            generated_title = await generate_title_via_low_agent(self._bridge, description)
            if generated_title:
                title = generated_title
                await asyncio.to_thread(
                    self._bridge.mutation,
                    "tasks:updateTitle",
                    {"task_id": task_id, "title": title},
                )
                logger.info(
                    "[inbox] Auto-generated title for task %s: '%s'",
                    task_id,
                    title,
                )
            else:
                logger.warning(
                    "[inbox] Auto-title generation returned None for task %s; keeping placeholder title",
                    task_id,
                )
                try:
                    await asyncio.to_thread(
                        self._bridge.create_activity,
                        "system_error",
                        "Auto-title generation failed -- check gateway logs for details",
                        task_id,
                    )
                except Exception:
                    pass
        elif auto_title and not description:
            logger.warning(
                "[inbox] auto_title=True but no description for task %s",
                task_id,
            )

        # Workflow tasks with pre-materialized steps: go directly to in_progress.
        # Steps are materialized at task creation time (create squad / create workflow),
        # so no planning or kickoff phase is needed.
        execution_plan = task_data.get("execution_plan") or {}

        if is_workflow_owned_task(task_data) and (
            is_workflow_generated_plan(execution_plan) or execution_plan.get("steps")
        ):
            await self._materialize_and_dispatch_workflow(task_id, title, task_data, execution_plan)
            return

        # Human routing: operator-directed assignment bypasses lead-agent routing.
        routing_mode = task_data.get("routing_mode")
        if routing_mode == "human" and assigned_agent:
            result = await asyncio.to_thread(
                self._bridge.transition_task_from_snapshot,
                task_data,
                "assigned",
                reason=f"Human-routed task assigned to {assigned_agent}",
                agent_name=assigned_agent,
            )
            if not _transition_applied_or_noop(task_id, "assigned", result):
                return
            logger.info(
                "[inbox] Human-routed task %s ('%s') -> assigned to %s (operator-directed)",
                task_id,
                title,
                assigned_agent,
            )
            return

        # All other tasks: route through LLMDelegationRouter
        # Path A: assignedAgent present → explicit assignment
        # Path B: no agent (Auto) → LLM picks best agent
        router = LLMDelegationRouter(self._bridge)
        try:
            decision = await router.route(task_data)
        except RuntimeError as exc:
            logger.error(
                "[inbox] LLM delegation failed for task %s: %s",
                task_id,
                exc,
            )
            result = await asyncio.to_thread(
                self._bridge.transition_task_from_snapshot,
                task_data,
                "failed",
                reason=f"LLM delegation failed: {exc}",
            )
            if _transition_applied_or_noop(task_id, "failed", result):
                try:
                    await asyncio.to_thread(
                        self._bridge.create_activity,
                        "system_error",
                        f"Task delegation failed: {exc}. Retry or assign an agent manually.",
                        task_id,
                    )
                except Exception:
                    pass
            return

        # Persist routing metadata on the task document
        routing_decision_payload = {
            "target_agent": decision.target_agent,
            "reason": decision.reason,
            "reason_code": decision.reason_code,
            "registry_snapshot": decision.registry_snapshot,
            "routed_at": decision.routed_at,
        }
        try:
            await asyncio.to_thread(
                self._bridge.patch_routing_decision,
                task_id,
                "lead_agent",
                routing_decision_payload,
            )
        except Exception:
            logger.warning(
                "[inbox] Failed to persist routing decision for task %s; continuing",
                task_id,
                exc_info=True,
            )

        # Transition to assigned with the resolved agent
        await asyncio.to_thread(
            self._bridge.update_task_status,
            task_id,
            "assigned",
            decision.target_agent,
            f"Delegated to {decision.target_agent} ({decision.reason_code})",
        )
        logger.info(
            "[inbox] Task %s ('%s') -> assigned to %s (%s)",
            task_id,
            title,
            decision.target_agent,
            decision.reason_code,
        )

    async def _materialize_and_dispatch_workflow(
        self,
        task_id: str,
        title: str,
        task_data: dict[str, Any],
        execution_plan: dict[str, Any],
    ) -> None:
        """Materialize workflow steps and dispatch them for execution."""
        if not self._plan_materializer or not self._step_dispatcher:
            raise RuntimeError(
                f"Workflow task {task_id} requires plan_materializer and step_dispatcher"
            )

        plan = ExecutionPlan.from_dict(execution_plan)
        if not plan.steps:
            raise RuntimeError(f"Workflow task {task_id} has an empty execution plan")

        # Materialize steps into the Convex steps table
        step_ids = await asyncio.to_thread(self._plan_materializer.materialize, task_id, plan)

        logger.info(
            "[inbox] Workflow task %s ('%s') -> in_progress (%d steps materialized, dispatching)",
            task_id,
            title,
            len(step_ids),
        )

        # Dispatch first round of steps (unblocked steps get assigned to agents)
        await self._step_dispatcher.dispatch_steps(task_id, step_ids)
