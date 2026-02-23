"""Task Orchestrator — LLM-based task planning, inbox routing, and review routing.

Routes inbox tasks via TaskPlanner (LLM reasoning with heuristic fallback).
Every task gets an ExecutionPlan. Handles review transitions (FR27).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from nanobot.mc.planner import TaskPlanner
from nanobot.mc.types import (
    AgentData,
    ActivityEventType,
    AuthorType,
    ExecutionPlan,
    ExecutionPlanStep,
    LEAD_AGENT_NAME,
    MessageType,
    TaskStatus,
    TrustLevel,
)

if TYPE_CHECKING:
    from nanobot.mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


def get_ready_steps(plan: ExecutionPlan) -> list[ExecutionPlanStep]:
    """Find steps that are ready to execute (all deps met, status pending)."""
    completed_ids = {s.step_id for s in plan.steps if s.status == "completed"}
    ready = []
    for step in plan.steps:
        if step.status != "pending":
            continue
        if all(dep in completed_ids for dep in step.depends_on):
            ready.append(step)
    return ready


class TaskOrchestrator:
    """Routes inbox tasks and handles review transitions."""

    def __init__(self, bridge: ConvexBridge) -> None:
        self._bridge = bridge
        self._lead_agent_name = LEAD_AGENT_NAME
        self._known_inbox_ids: set[str] = set()
        self._known_review_task_ids: set[str] = set()

    async def start_routing_loop(self) -> None:
        """Subscribe to inbox tasks and route them as they arrive."""
        logger.info("[orchestrator] Starting inbox routing loop")

        queue = self._bridge.async_subscribe(
            "tasks:listByStatus", {"status": "inbox"}
        )

        while True:
            tasks = await queue.get()
            if tasks is None:
                continue
            # Prune IDs no longer in inbox so tasks can re-enter
            # inbox (e.g. after retry) and be re-processed.
            current_ids = {t.get("id") for t in tasks if t.get("id")}
            self._known_inbox_ids &= current_ids
            for task_data in tasks:
                task_id = task_data.get("id")
                if not task_id or task_id in self._known_inbox_ids:
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
        """Route a single inbox task using LLM-based planning."""
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

        # Use LLM-based planner (falls back to heuristic on failure)
        planner = TaskPlanner()
        plan = await planner.plan_task(
            title, description, agents, explicit_agent=assigned_agent,
            files=task_data.get("files") or [],
        )

        logger.info(
            "[orchestrator] Task '%s': %d-step plan created",
            title,
            len(plan.steps),
        )

        await self._store_execution_plan(task_id, plan)

        # Determine the primary agent from the plan
        primary_agent = (
            plan.steps[0].assigned_agent if plan.steps else LEAD_AGENT_NAME
        )
        # Activity event is written by the Convex tasks:updateStatus mutation.
        await asyncio.to_thread(
            self._bridge.update_task_status,
            task_id,
            TaskStatus.ASSIGNED,
            primary_agent,
            f"Lead Agent planned '{title}' ({len(plan.steps)} steps)",
        )
        await self._dispatch_ready_steps(task_id, plan)

    async def _store_execution_plan(
        self, task_id: str, plan: ExecutionPlan
    ) -> None:
        """Store the execution plan on the task document in Convex."""
        await asyncio.to_thread(
            self._bridge.update_execution_plan,
            task_id,
            plan.to_dict(),
        )

    async def _dispatch_ready_steps(
        self, task_id: str, plan: ExecutionPlan
    ) -> None:
        """Dispatch all ready steps (deps met, pending) in parallel."""
        ready = get_ready_steps(plan)
        if not ready:
            return

        async def _dispatch_one(step: ExecutionPlanStep) -> None:
            step.status = "in_progress"
            logger.info(
                "[orchestrator] Dispatching step '%s' on task %s",
                step.step_id,
                task_id,
            )
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.TASK_STARTED,
                f"Step {step.step_id} started: {step.description}",
                task_id,
                step.assigned_agent,
            )

        # Dispatch all ready steps in parallel (FR22)
        await asyncio.gather(*[_dispatch_one(s) for s in ready])

        # Persist updated plan status
        await self._store_execution_plan(task_id, plan)

    async def complete_step(
        self,
        task_id: str,
        plan: ExecutionPlan,
        step_id: str,
        trust_level: str = TrustLevel.AUTONOMOUS,
    ) -> None:
        """Mark a step as completed, dispatch dependents, finalize if all done."""
        for step in plan.steps:
            if step.step_id == step_id:
                step.status = "completed"
                break

        # Dispatch any newly-unblocked steps
        await self._dispatch_ready_steps(task_id, plan)

        # Check if all steps are done
        if all(s.status == "completed" for s in plan.steps):
            final_status = (
                TaskStatus.DONE
                if trust_level == TrustLevel.AUTONOMOUS
                else TaskStatus.REVIEW
            )
            # Activity event is written by the Convex tasks:updateStatus mutation.
            await asyncio.to_thread(
                self._bridge.update_task_status,
                task_id,
                final_status,
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
