"""Task Orchestrator — planning routing and review routing.

Routes planning tasks via TaskPlanner (LLM reasoning with heuristic fallback)
and stores execution plans. Handles review transitions (FR27).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from mc.plan_materializer import PlanMaterializer
from mc.planner import TaskPlanner
from mc.provider_factory import create_provider
from mc.review_handler import ReviewHandler
from mc.step_dispatcher import StepDispatcher
from mc.types import (
    LEAD_AGENT_NAME,
    LOW_AGENT_NAME,
    NANOBOT_AGENT_NAME,
    ActivityEventType,
    AgentData,
    AuthorType,
    ExecutionPlan,
    MessageType,
    StepStatus,
    TaskStatus,
)

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

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
        logger.warning("[orchestrator] Failed to fetch low-agent config", exc_info=True)

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
                    logger.info("[orchestrator] low-agent tier resolved to: %s", low_model)
                else:
                    logger.info("[orchestrator] tier '%s' not configured; using default", tier_name)
        except Exception:
            logger.warning("[orchestrator] Failed to resolve tier for low-agent", exc_info=True)
            low_model = None

    description = description[:5000]

    try:
        logger.info("[orchestrator] Auto-title: creating provider with model=%r", low_model)
        provider, resolved_model = create_provider(model=low_model)
        logger.info("[orchestrator] Auto-title: calling LLM with model=%s", resolved_model)
        response = await provider.chat(
            model=resolved_model,
            messages=[
                {"role": "user", "content": AUTO_TITLE_PROMPT.format(description=description)},
            ],
            temperature=0.3,
            max_tokens=60,
        )
        if response.finish_reason == "error":
            logger.warning("[orchestrator] Auto-title LLM error: %s", response.content)
            return None
        title = (response.content or "").strip().lstrip("#").strip().strip('"').strip("'")
        if not title:
            logger.warning("[orchestrator] Auto-title LLM returned empty content")
            return None
        logger.info("[orchestrator] Auto-title generated via low-agent: '%s'", title)
        return title
    except Exception:
        logger.exception("[orchestrator] Auto-title generation failed")
        return None


class TaskOrchestrator:
    """Routes planning tasks and handles review transitions."""

    def __init__(self, bridge: ConvexBridge, cron_service: Any | None = None,
                 ask_user_registry: Any | None = None) -> None:
        self._bridge = bridge
        self._ask_user_registry = ask_user_registry
        self._lead_agent_name = LEAD_AGENT_NAME
        self._plan_materializer = PlanMaterializer(bridge)
        self._step_dispatcher = StepDispatcher(bridge, cron_service=cron_service,
                                                ask_user_registry=ask_user_registry)
        self._review_handler = ReviewHandler(bridge, ask_user_registry=ask_user_registry)
        self._known_inbox_ids: set[str] = set()
        self._known_planning_ids: set[str] = set()
        self._known_kickoff_ids: set[str] = set()
        self._known_retry_ids: set[str] = set()

    async def start_inbox_routing_loop(self) -> None:
        """Subscribe to inbox tasks, generate auto-title, then transition to planning/assigned."""
        logger.info("[orchestrator] Starting inbox routing loop")

        queue = self._bridge.async_subscribe(
            "tasks:listByStatus", {"status": "inbox"}
        )

        while True:
            tasks = await queue.get()
            if tasks is None:
                continue
            current_ids = {t.get("id") for t in tasks if t.get("id")}
            self._known_inbox_ids &= current_ids
            for task_data in tasks:
                task_id = task_data.get("id")
                if not task_id or task_id in self._known_inbox_ids:
                    continue
                # Skip manual tasks — stay in inbox, user manages them
                if task_data.get("is_manual"):
                    self._known_inbox_ids.add(task_id)
                    continue
                self._known_inbox_ids.add(task_id)
                try:
                    await self._process_inbox_task(task_data)
                except Exception:
                    logger.warning(
                        "[orchestrator] Error processing inbox task %s",
                        task_id,
                        exc_info=True,
                    )

    async def _process_inbox_task(self, task_data: dict[str, Any]) -> None:
        """Handle an inbox task: generate auto-title then transition to planning or assigned."""
        task_id = task_data.get("id")

        # Skip manual tasks — stay in inbox, user manages them via dashboard
        if task_data.get("is_manual"):
            logger.info("[orchestrator] Skipping manual inbox task %s", task_id)
            return

        title = task_data.get("title", "")
        description = task_data.get("description")
        assigned_agent = task_data.get("assigned_agent")
        auto_title = task_data.get("auto_title")

        logger.info(
            "[orchestrator] Processing inbox task %s: auto_title=%r, has_description=%s, keys=%s",
            task_id,
            auto_title,
            bool(description),
            list(task_data.keys()),
        )

        # Auto-title: generate a concise title from description if requested
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
                    "[orchestrator] Auto-generated title for task %s: '%s'",
                    task_id,
                    title,
                )
            else:
                logger.warning(
                    "[orchestrator] Auto-title generation returned None for task %s; "
                    "keeping placeholder title",
                    task_id,
                )
                try:
                    await asyncio.to_thread(
                        self._bridge.create_activity,
                        "system_error",
                        "Auto-title generation failed — check gateway logs for details",
                        task_id,
                    )
                except Exception:
                    pass  # best-effort
        elif auto_title and not description:
            logger.warning(
                "[orchestrator] auto_title=True but no description for task %s",
                task_id,
            )

        # Transition: if already assigned, go to "assigned"; otherwise "planning"
        next_status = "assigned" if assigned_agent else "planning"
        await asyncio.to_thread(
            self._bridge.update_task_status,
            task_id,
            next_status,
        )
        logger.info(
            "[orchestrator] Inbox task %s ('%s') → %s",
            task_id,
            title,
            next_status,
        )

    async def start_routing_loop(self) -> None:
        """Subscribe to planning tasks and plan them as they arrive."""
        logger.info("[orchestrator] Starting planning routing loop")

        queue = self._bridge.async_subscribe(
            "tasks:listByStatus", {"status": "planning"}
        )

        while True:
            tasks = await queue.get()
            if tasks is None:
                continue
            # Prune IDs no longer in planning so tasks can re-enter and be
            # re-processed.
            current_ids = {t.get("id") for t in tasks if t.get("id")}
            self._known_planning_ids &= current_ids
            for task_data in tasks:
                task_id = task_data.get("id")
                if not task_id or task_id in self._known_planning_ids:
                    continue
                self._known_planning_ids.add(task_id)
                try:
                    await self._process_planning_task(task_data)
                except Exception:
                    logger.warning(
                        "[orchestrator] Error processing planning task %s",
                        task_id,
                        exc_info=True,
                    )

    async def _process_planning_task(self, task_data: dict[str, Any]) -> None:
        """Process a single planning task using LLM-based planning."""
        task_id = task_data.get("id")
        title = task_data.get("title", "")
        description = task_data.get("description")
        assigned_agent = task_data.get("assigned_agent")

        if not task_id:
            logger.warning("[orchestrator] Skipping task with no id: %s", task_data)
            return

        # Create filesystem directory structure for this task
        await asyncio.to_thread(self._bridge.create_task_directory, task_id)

        # Skip manual tasks — they are user-managed via dashboard drag-and-drop
        if task_data.get("is_manual"):
            logger.info("[orchestrator] Skipping manual task '%s' (%s)", title, task_id)
            return

        # Fetch all enabled, delegatable agents (filter extra Convex fields)
        from mc.infrastructure.config import filter_agent_fields
        from mc.planner import _is_delegatable

        agents_data = await asyncio.to_thread(self._bridge.list_agents)
        agents = [AgentData(**filter_agent_fields(a)) for a in agents_data]
        agents = [a for a in agents if a.enabled is not False and _is_delegatable(a)]

        # Filter agents by board's enabledAgents (AC5)
        board_id = task_data.get("board_id")
        if board_id:
            try:
                board = await asyncio.to_thread(
                    self._bridge.get_board_by_id, board_id
                )
                if board:
                    board_enabled_agents = board.get("enabled_agents") or []
                    if board_enabled_agents:
                        agents = [
                            a for a in agents
                            if a.name in board_enabled_agents or getattr(a, "is_system", False)
                        ]
                        logger.info(
                            "[orchestrator] Board '%s': filtering to %d agent(s): %s",
                            board.get("name", board_id),
                            len(agents),
                            [a.name for a in agents],
                        )
            except Exception:
                logger.warning(
                    "[orchestrator] Failed to fetch board config for task %s, using all agents",
                    task_id,
                    exc_info=True,
                )

        await asyncio.to_thread(
            self._bridge.create_activity,
            ActivityEventType.TASK_ASSIGNED,
            "Task assigned to Lead Agent",
            task_id,
            self._lead_agent_name,
        )
        await asyncio.to_thread(
            self._bridge.create_activity,
            ActivityEventType.TASK_PLANNING,
            f"Lead Agent started planning for '{title}'",
            task_id,
            self._lead_agent_name,
        )

        try:
            # Resolve a fast model for planning (Sonnet-tier, not Opus).
            planning_model = None
            planning_reasoning_level = None
            try:
                from mc.tier_resolver import TierResolver
                tier_resolver = TierResolver(self._bridge)
                planning_model = tier_resolver.resolve_model("tier:standard-medium")
                planning_reasoning_level = tier_resolver.resolve_reasoning_level(
                    "tier:standard-medium"
                )
            except (ValueError, Exception) as exc:
                logger.debug("[orchestrator] Could not resolve planning tier: %s", exc)

            # Use LLM-based planner (falls back to heuristic on failure).
            planner = TaskPlanner(self._bridge)
            plan = await planner.plan_task(
                title,
                description,
                agents,
                explicit_agent=assigned_agent,
                files=task_data.get("files") or [],
                model=planning_model,
                reasoning_level=planning_reasoning_level,
            )

            # Prevent circular delegation: if a step would route back to the
            # agent that delegated this task, reassign it to the default agent.
            source_agent = task_data.get("source_agent")
            if source_agent:
                for step in plan.steps:
                    if step.assigned_agent == source_agent:
                        logger.warning(
                            "[orchestrator] Circular delegation detected: step '%s' would "
                            "route back to source agent '%s'; reassigning to '%s'",
                            step.temp_id,
                            source_agent,
                            NANOBOT_AGENT_NAME,
                        )
                        step.assigned_agent = NANOBOT_AGENT_NAME

            logger.info(
                "[orchestrator] Task '%s': %d-step plan created",
                title,
                len(plan.steps),
            )

            await self._store_execution_plan(task_id, plan)
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.TASK_PLANNING,
                f"Lead Agent generated execution plan for '{title}' "
                f"({len(plan.steps)} steps)",
                task_id,
                self._lead_agent_name,
            )
        except Exception as exc:
            logger.error(
                "[orchestrator] Plan generation failed for task '%s': %s",
                title,
                exc,
                exc_info=True,
            )

            await asyncio.to_thread(
                self._bridge.update_task_status,
                task_id,
                TaskStatus.FAILED,
                None,
                f"Plan generation failed: {exc}",
            )
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.TASK_FAILED,
                f"Plan generation failed for '{title}': "
                f"{type(exc).__name__}: {exc}",
                task_id,
                self._lead_agent_name,
            )
            await asyncio.to_thread(
                self._bridge.send_message,
                task_id,
                "System",
                AuthorType.SYSTEM,
                (
                    "Plan generation failed:\n"
                    f"```\n{type(exc).__name__}: {exc}\n```\n"
                    "Retry this task to try again."
                ),
                MessageType.SYSTEM_EVENT,
            )
            return

        supervision_mode = task_data.get("supervision_mode", "autonomous")
        if supervision_mode != "autonomous":
            # Transition to review with awaitingKickoff so the dashboard shows the kick-off UI
            await asyncio.to_thread(
                self._bridge.update_task_status,
                task_id,
                TaskStatus.REVIEW,
                None,
                f"Plan ready for review: '{title}'",
                True,  # awaiting_kickoff
            )
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.TASK_PLANNING,
                f"Plan ready for review -- awaiting user kick-off for '{title}'",
                task_id,
                self._lead_agent_name,
            )
            logger.info(
                "[orchestrator] Task '%s' transitioned to review (awaitingKickoff); "
                "awaiting user kick-off.",
                title,
            )
            return

        try:
            # Pre-register task_id so start_kickoff_watch_loop won't treat the
            # newly-in_progress task as a "resumed" task and double-dispatch it.
            self._known_kickoff_ids.add(task_id)
            created_step_ids = await asyncio.to_thread(
                self._plan_materializer.materialize,
                task_id,
                plan,
            )
            logger.info(
                "[orchestrator] Task '%s': materialized %d step records",
                title,
                len(created_step_ids),
            )
            asyncio.create_task(
                self._step_dispatcher.dispatch_steps(task_id, created_step_ids)
            )
            logger.info(
                "[orchestrator] Task '%s': step dispatch started (autonomous mode)",
                title,
            )
        except Exception as exc:
            logger.error(
                "[orchestrator] Plan materialization failed for task '%s': %s",
                title,
                exc,
                exc_info=True,
            )
            await asyncio.to_thread(
                self._bridge.send_message,
                task_id,
                "System",
                AuthorType.SYSTEM,
                (
                    "Plan materialization failed:\n"
                    f"```\n{type(exc).__name__}: {exc}\n```\n"
                    "Task marked as failed."
                ),
                MessageType.SYSTEM_EVENT,
            )

    async def _store_execution_plan(
        self, task_id: str, plan: ExecutionPlan
    ) -> None:
        """Store the execution plan on the task document in Convex."""
        await asyncio.to_thread(
            self._bridge.update_execution_plan,
            task_id,
            plan.to_dict(),
        )

    async def start_review_routing_loop(self) -> None:
        """Subscribe to review tasks and handle review transitions."""
        logger.info("[orchestrator] Starting review routing loop")

        queue = self._bridge.async_subscribe(
            "tasks:listByStatus", {"status": "review"}
        )

        while True:
            tasks = await queue.get()
            if tasks is None:
                continue
            # Prune IDs no longer in review so tasks can re-enter and be
            # re-processed (e.g., after step execution completes → review).
            current_ids = {t.get("id") for t in tasks if t.get("id")}
            self._review_handler._known_review_task_ids &= current_ids
            for task_data in tasks:
                task_id = task_data.get("id")
                if not task_id or task_id in self._review_handler._known_review_task_ids:
                    continue
                self._review_handler._known_review_task_ids.add(task_id)
                await self._review_handler._handle_review_transition(task_id, task_data)

    async def start_kickoff_watch_loop(self) -> None:
        """Watch for kicked-off or resumed tasks that need step dispatch.

        Subscribes to in_progress tasks. Handles two cases:
        1. New kick-off (approveAndKickOff): task has a plan but NO materialized steps
           → materialize and dispatch.
        2. Resume (resumeTask): task has existing steps in assigned/blocked status
           (already materialized). → dispatch_steps to continue execution (AC 5, Task 8).
        """
        logger.info("[orchestrator] Starting kickoff watch loop")

        queue = self._bridge.async_subscribe(
            "tasks:listByStatus", {"status": "in_progress"}
        )

        while True:
            tasks = await queue.get()
            if tasks is None:
                continue

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

                steps = await asyncio.to_thread(
                    self._bridge.get_steps_by_task, task_id
                )

                title = task_data.get("title", task_id)

                if steps:
                    # Task has materialized steps — this is a resumed task (Task 8.2).
                    # Find assigned OR unblocked-pending steps to dispatch (do NOT re-materialize).
                    # "assigned" steps are ready to run immediately.
                    # "pending" steps whose all blockers are "completed" are also dispatchable —
                    # they were waiting for a dependency that completed before the pause.
                    from mc.types import StepStatus as _StepStatus
                    completed_step_ids = {
                        str(step.get("id"))
                        for step in steps
                        if step.get("status") == _StepStatus.COMPLETED and step.get("id")
                    }
                    dispatchable_step_ids = []
                    for step in steps:
                        step_id_str = str(step.get("id")) if step.get("id") else None
                        if not step_id_str:
                            continue
                        status = step.get("status")
                        if status == _StepStatus.ASSIGNED:
                            dispatchable_step_ids.append(step_id_str)
                        elif status == _StepStatus.PLANNED:
                            # Dispatch if all blockers are already completed
                            blocked_by = step.get("blocked_by") or []
                            if all(str(b) in completed_step_ids for b in blocked_by):
                                dispatchable_step_ids.append(step_id_str)
                    if dispatchable_step_ids:
                        logger.info(
                            "[orchestrator] Detected resumed task '%s'; dispatching %d step(s) (assigned + unblocked pending)",
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
                            "[orchestrator] Resumed task '%s' has no dispatchable steps (may still have running steps)",
                            title,
                        )
                    continue  # Do NOT re-materialize

                logger.info(
                    "[orchestrator] Detected kicked-off task '%s'; materializing...",
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
                        "[orchestrator] Task '%s': materialized %d steps after kick-off",
                        title,
                        len(created_step_ids),
                    )
                except Exception as exc:
                    logger.error(
                        "[orchestrator] Materialization failed for kicked-off task %s",
                        task_id,
                        exc_info=True,
                    )
                    # Note: the materializer's _mark_task_failed() tries FAILED, which
                    # will silently fail since in_progress -> failed is invalid. We
                    # transition to CRASHED instead (a universal target from any state).
                    try:
                        await asyncio.to_thread(
                            self._bridge.update_task_status,
                            task_id,
                            TaskStatus.CRASHED,
                            None,
                            f"Materialization failed after kick-off: {type(exc).__name__}: {exc}",
                        )
                        await asyncio.to_thread(
                            self._bridge.create_activity,
                            ActivityEventType.SYSTEM_ERROR,
                            f"Materialization failed for '{title}': {type(exc).__name__}: {exc}",
                            task_id,
                        )
                    except Exception:
                        logger.error(
                            "[orchestrator] Failed to mark task %s as crashed after materialization failure",
                            task_id,
                            exc_info=True,
                        )

    async def start_retry_watch_loop(self) -> None:
        """Watch retrying tasks and re-enter them into the execution pipeline."""
        logger.info("[orchestrator] Starting retry watch loop")

        queue = self._bridge.async_subscribe(
            "tasks:listByStatus", {"status": "retrying"}
        )

        while True:
            tasks = await queue.get()
            if tasks is None:
                continue

            current_ids = {t.get("id") for t in tasks if t.get("id")}
            self._known_retry_ids &= current_ids

            for task_data in tasks:
                task_id = task_data.get("id")
                if not task_id or task_id in self._known_retry_ids:
                    continue
                self._known_retry_ids.add(task_id)

                steps = await asyncio.to_thread(
                    self._bridge.get_steps_by_task, task_id
                )
                execution_plan = task_data.get("execution_plan") or task_data.get("executionPlan")

                if steps:
                    assigned_step_ids = [
                        str(step.get("id"))
                        for step in steps
                        if step.get("status") == StepStatus.ASSIGNED and step.get("id")
                    ]
                    await asyncio.to_thread(
                        self._bridge.update_task_status,
                        task_id,
                        TaskStatus.IN_PROGRESS,
                    )
                    if assigned_step_ids:
                        asyncio.create_task(
                            self._step_dispatcher.dispatch_steps(
                                task_id, assigned_step_ids
                            )
                        )
                    continue

                if execution_plan:
                    await asyncio.to_thread(
                        self._bridge.update_task_status,
                        task_id,
                        TaskStatus.IN_PROGRESS,
                    )
                    plan = ExecutionPlan.from_dict(execution_plan)
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

    # -- Review delegation wrappers (implementation in ReviewHandler) ----------

    async def _handle_review_transition(
        self, task_id: str, task: dict[str, Any]
    ) -> None:
        """Handle a task entering review state (FR27). Delegates to ReviewHandler."""
        await self._review_handler._handle_review_transition(task_id, task)

    async def send_agent_message(
        self,
        task_id: str,
        agent_name: str,
        content: str,
        message_type: str = MessageType.WORK,
    ) -> Any:
        """Send a task-scoped message on behalf of an agent (FR26). Delegates to ReviewHandler."""
        return await self._review_handler.send_agent_message(
            task_id, agent_name, content, message_type
        )

    async def handle_review_feedback(
        self, task_id: str, reviewer_name: str, feedback: str
    ) -> None:
        """Handle reviewer feedback on a task (FR28). Delegates to ReviewHandler."""
        await self._review_handler.handle_review_feedback(
            task_id, reviewer_name, feedback
        )

    async def handle_agent_revision(
        self, task_id: str, agent_name: str, content: str
    ) -> None:
        """Handle an agent's revision in response to review feedback (FR29). Delegates to ReviewHandler."""
        await self._review_handler.handle_agent_revision(
            task_id, agent_name, content
        )

    async def handle_review_approval(
        self, task_id: str, reviewer_name: str
    ) -> None:
        """Handle reviewer approval of a task (FR30). Delegates to ReviewHandler."""
        await self._review_handler.handle_review_approval(
            task_id, reviewer_name
        )
