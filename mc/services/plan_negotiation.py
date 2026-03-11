"""PlanNegotiationSupervisor — manages per-task plan negotiation loops.

Extracted from mc/gateway.py _run_plan_negotiation_manager (Story 17.2, AC #3).
Subscribes to tasks in review/in_progress and spawns per-task negotiation loops.
Pre-kickoff review tasks are negotiable, and paused review tasks remain
negotiable while they still have an execution plan to refine.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from mc.contexts.planning.negotiation import start_plan_negotiation_loop

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


def _has_execution_plan(task_data: dict[str, Any]) -> bool:
    """Return True when task_data carries a non-empty execution plan."""
    plan = task_data.get("execution_plan") or task_data.get("executionPlan")
    return bool(isinstance(plan, dict) and plan.get("steps"))


def _is_manual_review_without_plan(task_data: dict[str, Any]) -> bool:
    """Return True when a manual review task is waiting for its first plan."""
    return (
        task_data.get("status", "") == "review"
        and bool(task_data.get("is_manual") or task_data.get("isManual"))
        and not bool(task_data.get("awaiting_kickoff") or task_data.get("awaitingKickoff"))
        and not _has_execution_plan(task_data)
    )


class PlanNegotiationSupervisor:
    """Manages per-task plan negotiation loops.

    Subscribes to tasks in both review and in_progress statuses. For each task
    that enters a negotiable state, spawns a start_plan_negotiation_loop
    coroutine. Prevents duplicate loops.

    Constructor dependencies:
        bridge: ConvexBridge instance for Convex communication.
        ask_user_registry: Optional AskUserRegistry for routing ask_user replies.
    """

    def __init__(
        self,
        bridge: "ConvexBridge",
        ask_user_registry: Any | None = None,
        sleep_controller: Any | None = None,
    ) -> None:
        self._bridge = bridge
        self._ask_user_registry = ask_user_registry
        self._sleep_controller = sleep_controller
        self._active_negotiation_ids: set[str] = set()
        self._cron_requeued_ids: set[str] = set()

    def mark_cron_requeued(self, task_id: str) -> None:
        """Mark a task as cron-requeued so the supervisor skips it."""
        self._cron_requeued_ids.add(task_id)

    async def _spawn_loop_if_needed(self, task_id: str) -> None:
        """Spawn a plan negotiation loop for task_id if not already active."""
        if task_id in self._active_negotiation_ids:
            return
        self._active_negotiation_ids.add(task_id)
        logger.info(
            "[plan_negotiation] Spawning plan negotiation loop for task %s",
            task_id,
        )

        async def _run_and_cleanup() -> None:
            try:
                await start_plan_negotiation_loop(
                    self._bridge,
                    task_id,
                    ask_user_registry=self._ask_user_registry,
                    sleep_controller=self._sleep_controller,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "[plan_negotiation] Plan negotiation loop for task %s crashed",
                    task_id,
                )
            finally:
                self._active_negotiation_ids.discard(task_id)
                logger.info(
                    "[plan_negotiation] Plan negotiation loop for task %s ended",
                    task_id,
                )

        asyncio.create_task(_run_and_cleanup())

    async def process_batch(self, tasks_batch: object) -> None:
        """Process a batch of tasks from a subscription queue.

        Spawns negotiation loops for tasks that are in a negotiable state.
        Skips cron-requeued tasks.
        """
        if not tasks_batch or isinstance(tasks_batch, dict):
            return

        for task_data in tasks_batch:  # type: ignore[union-attr]
            task_id = task_data.get("id")
            if not task_id:
                continue

            task_status = task_data.get("status", "")
            awaiting_kickoff = task_data.get("awaiting_kickoff", False)
            has_execution_plan = _has_execution_plan(task_data)

            if task_status == "in_progress" or (
                task_status == "review"
                and (
                    awaiting_kickoff
                    or has_execution_plan
                    or _is_manual_review_without_plan(task_data)
                )
            ):
                # Skip cron-requeued tasks
                if task_id in self._cron_requeued_ids:
                    self._cron_requeued_ids.discard(task_id)
                    logger.info(
                        "[plan_negotiation] Skipping plan negotiation for task %s (cron requeue)",
                        task_id,
                    )
                    continue
                await self._spawn_loop_if_needed(task_id)

    async def run(self) -> None:
        """Run the plan negotiation manager loop.

        Subscribes to review and in_progress task lists and processes batches.
        Runs until cancelled.
        """
        logger.info("[plan_negotiation] Plan negotiation supervisor started")

        review_queue = self._bridge.async_subscribe(
            "tasks:listByStatus",
            {"status": "review"},
            poll_interval=5.0,
            sleep_controller=self._sleep_controller,
        )
        in_progress_queue = self._bridge.async_subscribe(
            "tasks:listByStatus",
            {"status": "in_progress"},
            poll_interval=5.0,
            sleep_controller=self._sleep_controller,
        )

        async def _drain_queue(queue: asyncio.Queue) -> None:  # type: ignore[type-arg]
            while True:
                try:
                    batch = await queue.get()
                    await self.process_batch(batch)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning("[plan_negotiation] Error reading queue: %s", exc)

        reader_tasks = [
            asyncio.create_task(_drain_queue(review_queue)),
            asyncio.create_task(_drain_queue(in_progress_queue)),
        ]
        try:
            await asyncio.gather(*reader_tasks)
        finally:
            for t in reader_tasks:
                t.cancel()
