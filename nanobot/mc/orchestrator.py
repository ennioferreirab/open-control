"""Task Orchestrator — planning routing and review routing.

Routes planning tasks via TaskPlanner (LLM reasoning with heuristic fallback)
and stores execution plans. Handles review transitions (FR27).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from nanobot.mc.plan_materializer import PlanMaterializer
from nanobot.mc.planner import TaskPlanner
from nanobot.mc.step_dispatcher import StepDispatcher
from nanobot.mc.types import (
    AgentData,
    ActivityEventType,
    AuthorType,
    ExecutionPlan,
    LEAD_AGENT_NAME,
    MessageType,
    TaskStatus,
    TrustLevel,
)

if TYPE_CHECKING:
    from nanobot.mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


class TaskOrchestrator:
    """Routes planning tasks and handles review transitions."""

    def __init__(self, bridge: ConvexBridge) -> None:
        self._bridge = bridge
        self._lead_agent_name = LEAD_AGENT_NAME
        self._plan_materializer = PlanMaterializer(bridge)
        self._step_dispatcher = StepDispatcher(bridge)
        self._known_planning_ids: set[str] = set()
        self._known_review_task_ids: set[str] = set()
        self._known_kickoff_ids: set[str] = set()

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

        # Fetch all enabled agents (filter extra Convex fields)
        from nanobot.mc.gateway import filter_agent_fields

        agents_data = await asyncio.to_thread(self._bridge.list_agents)
        agents = [AgentData(**filter_agent_fields(a)) for a in agents_data]
        agents = [a for a in agents if a.enabled is not False]

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
            ActivityEventType.TASK_PLANNING,
            f"Lead Agent started planning for '{title}'",
            task_id,
            self._lead_agent_name,
        )

        try:
            # Use LLM-based planner (falls back to heuristic on failure).
            planner = TaskPlanner()
            plan = await planner.plan_task(
                title,
                description,
                agents,
                explicit_agent=assigned_agent,
                files=task_data.get("files") or [],
            )

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
            # Transition to reviewing_plan so the dashboard can show the kick-off UI
            await asyncio.to_thread(
                self._bridge.update_task_status,
                task_id,
                TaskStatus.REVIEWING_PLAN,
                None,
                f"Plan ready for review: '{title}'",
            )
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.TASK_PLANNING,
                f"Plan ready for review -- awaiting user kick-off for '{title}'",
                task_id,
                self._lead_agent_name,
            )
            logger.info(
                "[orchestrator] Task '%s' transitioned to reviewing_plan; "
                "awaiting user kick-off.",
                title,
            )
            return

        try:
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

    # Backwards-compatible shim while callers migrate to planning terminology.
    async def _process_inbox_task(self, task_data: dict[str, Any]) -> None:
        await self._process_planning_task(task_data)

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
            for task_data in tasks:
                task_id = task_data.get("id")
                if not task_id or task_id in self._known_review_task_ids:
                    continue
                self._known_review_task_ids.add(task_id)
                await self._handle_review_transition(task_id, task_data)

    async def start_kickoff_watch_loop(self) -> None:
        """Watch for kicked-off tasks that need materialization.

        Subscribes to in_progress tasks. When a new in_progress task appears
        that has an execution plan but no materialized steps, it was just
        kicked off via approveAndKickOff -- materialize and dispatch.
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

                # Only process tasks with a plan but no materialized steps
                if not task_data.get("execution_plan"):
                    continue

                steps = await asyncio.to_thread(
                    self._bridge.get_steps_by_task, task_id
                )
                if steps:
                    continue  # Already materialized

                title = task_data.get("title", task_id)
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

    async def _handle_review_transition(
        self, task_id: str, task: dict[str, Any]
    ) -> None:
        """Handle a task entering review state (FR27)."""
        reviewers: list[str] = task.get("reviewers") or []
        trust_level = task.get("trust_level", TrustLevel.AUTONOMOUS)
        title = task.get("title", "Untitled")

        if not reviewers and trust_level == TrustLevel.AUTONOMOUS:
            logger.info(
                "[orchestrator] Task '%s' is autonomous with no reviewers — "
                "auto-completing to done.",
                title,
            )
            await asyncio.to_thread(
                self._bridge.update_task_status,
                task_id,
                TaskStatus.DONE,
            )
            return

        if reviewers:
            reviewer_names = ", ".join(reviewers)
            logger.info(
                "[orchestrator] Routing review for task '%s' to: %s",
                title,
                reviewer_names,
            )
            await asyncio.to_thread(
                self._bridge.send_message,
                task_id,
                "system",
                AuthorType.SYSTEM,
                f"Review requested. Awaiting review from: {reviewer_names}",
                MessageType.SYSTEM_EVENT,
            )
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.REVIEW_REQUESTED,
                f"Review requested from {reviewer_names} for '{title}'",
                task_id,
            )

        if trust_level == TrustLevel.HUMAN_APPROVED and not reviewers:
            logger.info(
                "[orchestrator] Human approval requested for task '%s'.",
                title,
            )
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.HITL_REQUESTED,
                f"Human approval requested for '{title}'",
                task_id,
            )

    async def send_agent_message(
        self,
        task_id: str,
        agent_name: str,
        content: str,
        message_type: str = MessageType.WORK,
    ) -> Any:
        """Send a task-scoped message on behalf of an agent (FR26)."""
        logger.info(
            "[orchestrator] Agent '%s' sending message on task %s",
            agent_name,
            task_id,
        )
        result = await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            agent_name,
            AuthorType.AGENT,
            content,
            message_type,
        )
        return result

    async def handle_review_feedback(
        self, task_id: str, reviewer_name: str, feedback: str
    ) -> None:
        """Handle reviewer feedback on a task (FR28)."""
        logger.info(
            "[orchestrator] Reviewer '%s' providing feedback on task %s",
            reviewer_name,
            task_id,
        )
        await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            reviewer_name,
            AuthorType.AGENT,
            feedback,
            MessageType.REVIEW_FEEDBACK,
        )
        task = await asyncio.to_thread(
            self._bridge.query, "tasks:getById", {"task_id": task_id}
        )
        title = task.get("title", "Untitled") if task else "Untitled"
        await asyncio.to_thread(
            self._bridge.create_activity,
            ActivityEventType.REVIEW_FEEDBACK,
            f"{reviewer_name} provided feedback on '{title}'",
            task_id,
            reviewer_name,
        )

    async def handle_agent_revision(
        self, task_id: str, agent_name: str, content: str
    ) -> None:
        """Handle an agent's revision in response to review feedback (FR29)."""
        logger.info(
            "[orchestrator] Agent '%s' submitting revision on task %s",
            agent_name,
            task_id,
        )
        await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            agent_name,
            AuthorType.AGENT,
            content,
            MessageType.WORK,
        )

    async def handle_review_approval(
        self, task_id: str, reviewer_name: str
    ) -> None:
        """Handle reviewer approval of a task (FR30)."""
        logger.info(
            "[orchestrator] Reviewer '%s' approving task %s",
            reviewer_name,
            task_id,
        )
        await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            reviewer_name,
            AuthorType.AGENT,
            f"Approved by {reviewer_name}",
            MessageType.APPROVAL,
        )
        task = await asyncio.to_thread(
            self._bridge.query, "tasks:getById", {"task_id": task_id}
        )
        title = task.get("title", "Untitled") if task else "Untitled"
        trust_level = (
            task.get("trust_level", TrustLevel.AUTONOMOUS)
            if task
            else TrustLevel.AUTONOMOUS
        )

        await asyncio.to_thread(
            self._bridge.create_activity,
            ActivityEventType.REVIEW_APPROVED,
            f"{reviewer_name} approved '{title}'",
            task_id,
            reviewer_name,
        )

        if trust_level == TrustLevel.AGENT_REVIEWED:
            await asyncio.to_thread(
                self._bridge.update_task_status,
                task_id,
                TaskStatus.DONE,
                reviewer_name,
            )
        elif trust_level == TrustLevel.HUMAN_APPROVED:
            await asyncio.to_thread(
                self._bridge.send_message,
                task_id,
                "system",
                AuthorType.SYSTEM,
                "Agent review passed. Awaiting human approval.",
                MessageType.SYSTEM_EVENT,
            )
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.HITL_REQUESTED,
                f"Human approval requested for '{title}'",
                task_id,
            )
