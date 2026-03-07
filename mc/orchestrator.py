"""Task Orchestrator — thin coordinator that routes events to workers.

Receives subscription events and delegates to domain-specific workers:
- InboxWorker: new task processing, auto-title, initial routing
- PlanningWorker: plan generation, materialization, validation
- ReviewWorker: review routing, completion detection, post-review transitions
- KickoffResumeWorker: task kickoff and resume flows

Story 17.1: Orchestrator Worker Extraction (AC5).
Updated to accept RuntimeContext per Story 20.3.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from mc.plan_materializer import PlanMaterializer
from mc.provider_factory import create_provider
from mc.step_dispatcher import StepDispatcher
from mc.types import (
    LOW_AGENT_NAME,
    MessageType,
)

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge
    from mc.infrastructure.runtime_context import RuntimeContext

logger = logging.getLogger(__name__)

AUTO_TITLE_PROMPT = (
    "Create a simple title for this task description. "
    "Do not change the language used in the text.\n\n"
    "{description}"
)


async def generate_title_via_low_agent(
    bridge: "ConvexBridge",
    description: str,
) -> str | None:
    """Generate a concise title by delegating to the low-agent system agent.

    Reads the model configured on the low-agent from Convex. If the agent is
    not found or the LLM call fails, returns None.
    """
    # Fetch low-agent model config
    agent_data: dict | None = None
    try:
        agent_data = await asyncio.to_thread(
            bridge.get_agent_by_name, LOW_AGENT_NAME
        )
    except Exception:
        logger.warning(
            "[orchestrator] Failed to fetch low-agent config", exc_info=True
        )

    if not agent_data:
        logger.warning("[orchestrator] low-agent not found; skipping auto-title")
        return None

    low_model: str | None = agent_data.get("model") or None

    # Resolve tier reference to concrete model string
    if low_model and low_model.startswith("tier:"):
        try:
            raw_tiers = await asyncio.to_thread(
                bridge.query, "settings:get", {"key": "model_tiers"}
            )
            if raw_tiers:
                tiers = json.loads(raw_tiers)
                tier_name = low_model[len("tier:"):]
                low_model = tiers.get(tier_name) or None
                if low_model:
                    logger.info(
                        "[orchestrator] low-agent tier resolved to: %s",
                        low_model,
                    )
                else:
                    logger.info(
                        "[orchestrator] tier '%s' not configured; using default",
                        tier_name,
                    )
        except Exception:
            logger.warning(
                "[orchestrator] Failed to resolve tier for low-agent",
                exc_info=True,
            )
            low_model = None

    description = description[:5000]

    try:
        logger.info(
            "[orchestrator] Auto-title: creating provider with model=%r",
            low_model,
        )
        provider, resolved_model = create_provider(model=low_model)
        logger.info(
            "[orchestrator] Auto-title: calling LLM with model=%s",
            resolved_model,
        )
        response = await provider.chat(
            model=resolved_model,
            messages=[
                {
                    "role": "user",
                    "content": AUTO_TITLE_PROMPT.format(description=description),
                },
            ],
            temperature=0.3,
            max_tokens=60,
        )
        if response.finish_reason == "error":
            logger.warning(
                "[orchestrator] Auto-title LLM error: %s", response.content
            )
            return None
        title = (
            (response.content or "")
            .strip()
            .lstrip("#")
            .strip()
            .strip('"')
            .strip("'")
        )
        if not title:
            logger.warning(
                "[orchestrator] Auto-title LLM returned empty content"
            )
            return None
        logger.info(
            "[orchestrator] Auto-title generated via low-agent: '%s'", title
        )
        return title
    except Exception:
        logger.exception("[orchestrator] Auto-title generation failed")
        return None


class TaskOrchestrator:
    """Thin coordinator: creates workers, subscribes to events, routes to workers.

    All domain logic lives in workers (inbox, planning, review, kickoff).
    The orchestrator is the composition root.
    """

    def __init__(
        self,
        bridge_or_ctx: ConvexBridge | RuntimeContext,
        cron_service: Any | None = None,
        ask_user_registry: Any | None = None,
    ) -> None:
        # Accept either RuntimeContext (new) or bare bridge (backward compat).
        from mc.infrastructure.runtime_context import RuntimeContext

        if isinstance(bridge_or_ctx, RuntimeContext):
            self._ctx = bridge_or_ctx
            self._bridge = bridge_or_ctx.bridge
        else:
            # Legacy call site — wrap bridge in a RuntimeContext.
            self._ctx = RuntimeContext(bridge=bridge_or_ctx)
            self._bridge = bridge_or_ctx

        self._plan_materializer = PlanMaterializer(self._bridge)
        self._step_dispatcher = StepDispatcher(
            self._bridge,
            cron_service=cron_service,
            ask_user_registry=ask_user_registry,
        )

        # Shared kickoff ID set -- prevents double-dispatch between
        # planning (autonomous materialization) and kickoff watch.
        self._known_kickoff_ids: set[str] = set()

        # Create workers (lazy imports to avoid circular dependency:
        # workers import generate_title_via_low_agent from this module)
        from mc.workers.inbox import InboxWorker
        from mc.workers.kickoff import KickoffResumeWorker
        from mc.workers.planning import PlanningWorker
        from mc.workers.review import ReviewWorker

        self._inbox_worker = InboxWorker(self._ctx)
        self._planning_worker = PlanningWorker(
            self._ctx,
            self._plan_materializer,
            self._step_dispatcher,
            known_kickoff_ids=self._known_kickoff_ids,
        )
        self._review_worker = ReviewWorker(
            self._ctx, ask_user_registry=ask_user_registry
        )
        self._kickoff_worker = KickoffResumeWorker(
            self._ctx,
            self._plan_materializer,
            self._step_dispatcher,
            known_kickoff_ids=self._known_kickoff_ids,
        )

    # -- Subscription loops (coordination only) ---------------------------

    async def start_inbox_routing_loop(self) -> None:
        """Subscribe to inbox tasks and route to InboxWorker."""
        logger.info("[orchestrator] Starting inbox routing loop")
        queue = self._bridge.async_subscribe(
            "tasks:listByStatus", {"status": "inbox"}
        )
        while True:
            tasks = await queue.get()
            if tasks is None:
                continue
            await self._inbox_worker.process_batch(tasks)

    async def start_routing_loop(self) -> None:
        """Subscribe to planning tasks and route to PlanningWorker."""
        logger.info("[orchestrator] Starting planning routing loop")
        queue = self._bridge.async_subscribe(
            "tasks:listByStatus", {"status": "planning"}
        )
        while True:
            tasks = await queue.get()
            if tasks is None:
                continue
            await self._planning_worker.process_batch(tasks)

    async def start_review_routing_loop(self) -> None:
        """Subscribe to review tasks and route to ReviewWorker."""
        logger.info("[orchestrator] Starting review routing loop")
        queue = self._bridge.async_subscribe(
            "tasks:listByStatus", {"status": "review"}
        )
        while True:
            tasks = await queue.get()
            if tasks is None:
                continue
            await self._review_worker.process_batch(tasks)

    async def start_kickoff_watch_loop(self) -> None:
        """Subscribe to in_progress tasks and route to KickoffResumeWorker."""
        logger.info("[orchestrator] Starting kickoff watch loop")
        queue = self._bridge.async_subscribe(
            "tasks:listByStatus", {"status": "in_progress"}
        )
        while True:
            tasks = await queue.get()
            if tasks is None:
                continue
            await self._kickoff_worker.process_batch(tasks)

    # -- Delegation wrappers (preserve public API) -------------------------

    async def _process_inbox_task(self, task_data: dict[str, Any]) -> None:
        """Delegate to InboxWorker (backward compat for tests)."""
        await self._inbox_worker.process_task(task_data)

    async def _process_planning_task(self, task_data: dict[str, Any]) -> None:
        """Delegate to PlanningWorker (backward compat for tests)."""
        await self._planning_worker.process_task(task_data)

    async def _handle_review_transition(
        self, task_id: str, task: dict[str, Any]
    ) -> None:
        """Delegate to ReviewWorker (backward compat for tests)."""
        await self._review_worker.handle_review_transition(task_id, task)

    async def send_agent_message(
        self,
        task_id: str,
        agent_name: str,
        content: str,
        message_type: str = MessageType.WORK,
    ) -> Any:
        """Send a task-scoped message on behalf of an agent (FR26)."""
        return await self._review_worker.send_agent_message(
            task_id, agent_name, content, message_type
        )

    async def handle_review_feedback(
        self, task_id: str, reviewer_name: str, feedback: str
    ) -> None:
        """Handle reviewer feedback on a task (FR28)."""
        await self._review_worker.handle_review_feedback(
            task_id, reviewer_name, feedback
        )

    async def handle_agent_revision(
        self, task_id: str, agent_name: str, content: str
    ) -> None:
        """Handle an agent's revision in response to review feedback (FR29)."""
        await self._review_worker.handle_agent_revision(
            task_id, agent_name, content
        )

    async def handle_review_approval(
        self, task_id: str, reviewer_name: str
    ) -> None:
        """Handle reviewer approval of a task (FR30)."""
        await self._review_worker.handle_review_approval(
            task_id, reviewer_name
        )
