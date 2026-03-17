"""Inbox worker — handles new task processing, auto-title, and initial routing."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from mc.bridge.runtime_claims import acquire_runtime_claim, task_snapshot_claim_kind
from mc.contexts.planning.title_generation import generate_title_via_low_agent
from mc.contexts.routing.router import DirectDelegationRouter
from mc.domain.workflow_ownership import is_workflow_generated_plan, is_workflow_owned_task

if TYPE_CHECKING:
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
    """Processes inbox tasks: auto-title generation and routing to planning/assigned."""

    def __init__(self, ctx: RuntimeContext) -> None:
        self._ctx = ctx
        self._bridge = ctx.bridge
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

        # Layer 2 defense: bypass planning for workflow missions whose execution
        # plan was already compiled at launch time.  Routing them through
        # planning would overwrite the workflow plan with a lead-agent plan.
        execution_plan = task_data.get("execution_plan") or task_data.get("executionPlan") or {}
        is_workflow_plan = is_workflow_generated_plan(execution_plan)
        work_mode = task_data.get("work_mode") or task_data.get("workMode")

        if is_workflow_owned_task(task_data) and is_workflow_plan:
            result = await asyncio.to_thread(
                self._bridge.transition_task_from_snapshot,
                task_data,
                "review",
                reason=f"Workflow plan ready for kick-off: '{title}'",
                awaiting_kickoff=True,
                review_phase="plan_review",
            )
            if not _transition_applied_or_noop(task_id, "review", result):
                return
            logger.info(
                "[inbox] Workflow task %s ('%s') -> review (awaitingKickoff); bypassing planning",
                task_id,
                title,
            )
            return

        # Human routing: operator-directed assignment bypasses lead-agent routing.
        routing_mode = task_data.get("routing_mode") or task_data.get("routingMode")
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

        # Direct delegation: route through the DirectDelegationRouter
        if work_mode == "direct_delegate":
            router = DirectDelegationRouter(self._bridge)
            decision = await asyncio.to_thread(router.route, task_data)

            if decision is None:
                # No suitable agent — fail explicitly (planning rejects direct_delegate)
                logger.warning(
                    "[inbox] No routing target for direct-delegate task %s; marking as failed",
                    task_id,
                )
                result = await asyncio.to_thread(
                    self._bridge.transition_task_from_snapshot,
                    task_data,
                    "failed",
                    reason="No delegatable agent available for direct delegation",
                )
                if _transition_applied_or_noop(task_id, "failed", result):
                    try:
                        await asyncio.to_thread(
                            self._bridge.create_activity,
                            "system_error",
                            "No delegatable agent available. Check agent configuration and retry.",
                            task_id,
                        )
                    except Exception:
                        pass
                return
            else:
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
                    f"Direct delegation to {decision.target_agent}",
                )
                logger.info(
                    "[inbox] Direct-delegate task %s ('%s') -> assigned to %s (%s)",
                    task_id,
                    title,
                    decision.target_agent,
                    decision.reason_code,
                )
                return

        next_status = "assigned" if assigned_agent else "planning"
        result = await asyncio.to_thread(
            self._bridge.transition_task_from_snapshot,
            task_data,
            next_status,
            reason=f"Inbox task routed to {next_status}",
        )
        if not _transition_applied_or_noop(task_id, next_status, result):
            return
        logger.info(
            "[inbox] Inbox task %s ('%s') -> %s",
            task_id,
            title,
            next_status,
        )
