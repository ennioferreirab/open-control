"""Planning worker — handles plan generation, materialization, and validation."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from mc.contexts.planning.planner import TaskPlanner
from mc.contexts.planning.review_messages import (
    build_plan_review_message,
    build_plan_review_metadata,
)
from mc.types import (
    LEAD_AGENT_NAME,
    NANOBOT_AGENT_NAME,
    ActivityEventType,
    AgentData,
    AuthorType,
    ExecutionPlan,
    MessageType,
    TaskStatus,
)

if TYPE_CHECKING:
    from mc.contexts.execution.step_dispatcher import StepDispatcher
    from mc.contexts.planning.materializer import PlanMaterializer
    from mc.infrastructure.runtime_context import RuntimeContext

logger = logging.getLogger(__name__)


class PlanningWorker:
    """Processes planning tasks: generates plans, materializes steps, dispatches."""

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
        self._lead_agent_name = LEAD_AGENT_NAME
        self._known_planning_ids: set[str] = set()
        self._known_kickoff_ids = known_kickoff_ids if known_kickoff_ids is not None else set()

    async def process_batch(self, tasks: list[dict[str, Any]]) -> None:
        """Process a batch of planning tasks from a subscription update."""
        current_ids = {task.get("id") for task in tasks if task.get("id")}
        self._known_planning_ids &= current_ids

        for task_data in tasks:
            task_id = task_data.get("id")
            if not task_id or task_id in self._known_planning_ids:
                continue
            self._known_planning_ids.add(task_id)
            try:
                await self.process_task(task_data)
            except Exception:
                logger.warning(
                    "[planning] Error processing planning task %s",
                    task_id,
                    exc_info=True,
                )

    async def process_task(self, task_data: dict[str, Any]) -> None:
        """Process a single planning task using LLM-based planning."""
        task_id = task_data.get("id")
        title = task_data.get("title", "")
        description = task_data.get("description")
        assigned_agent = task_data.get("assigned_agent")

        if not task_id:
            logger.warning("[planning] Skipping task with no id: %s", task_data)
            return

        await asyncio.to_thread(self._bridge.create_task_directory, task_id)

        if task_data.get("is_manual"):
            logger.info("[planning] Skipping manual task '%s' (%s)", title, task_id)
            return

        # Layer 3 defense: bypass the LLM planner for workflow missions whose
        # execution plan was already compiled at launch time.  Invoking the
        # lead-agent planner here would overwrite the workflow plan.
        raw_plan = task_data.get("execution_plan") or task_data.get("executionPlan") or {}
        work_mode = task_data.get("work_mode") or task_data.get("workMode")
        if work_mode == "ai_workflow" and raw_plan.get("generatedBy") == "workflow":
            logger.info(
                "[planning] Workflow task '%s' (%s): skipping LLM planner, using pre-compiled plan",
                title,
                task_id,
            )
            await self._dispatch_workflow_plan(task_id, title, raw_plan, task_data)
            return

        from mc.contexts.planning.planner import _is_delegatable
        from mc.infrastructure.config import filter_agent_fields

        agents_data = await asyncio.to_thread(self._bridge.list_agents)
        agents = [AgentData(**filter_agent_fields(agent)) for agent in agents_data]
        agents = [
            agent for agent in agents if agent.enabled is not False and _is_delegatable(agent)
        ]

        board_id = task_data.get("board_id")
        if board_id:
            try:
                board = await asyncio.to_thread(self._bridge.get_board_by_id, board_id)
                if board:
                    board_enabled_agents = board.get("enabled_agents") or []
                    if board_enabled_agents:
                        agents = [
                            agent
                            for agent in agents
                            if agent.name in board_enabled_agents
                            or getattr(agent, "is_system", False)
                        ]
                        logger.info(
                            "[planning] Board '%s': filtering to %d agent(s): %s",
                            board.get("name", board_id),
                            len(agents),
                            [agent.name for agent in agents],
                        )
            except Exception:
                logger.warning(
                    "[planning] Failed to fetch board config for task %s, using all agents",
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
            # Use the Lead Agent's configured model for planning.
            # Lead Agent is excluded from the delegatable agents list,
            # so we look it up from the full agents_data.
            lead_agent_raw = next(
                (a for a in agents_data if a.get("name") == self._lead_agent_name), None
            )
            planning_model = lead_agent_raw.get("model") if lead_agent_raw else None
            planning_reasoning_level = None

            # If the Lead Agent model is a tier reference, resolve it.
            if planning_model:
                from mc.types import is_tier_reference

                if is_tier_reference(planning_model):
                    try:
                        from mc.infrastructure.providers.tier_resolver import TierResolver

                        tier_resolver = TierResolver(self._bridge)
                        planning_reasoning_level = tier_resolver.resolve_reasoning_level(
                            planning_model
                        )
                        planning_model = tier_resolver.resolve_model(planning_model)
                    except (ValueError, Exception) as exc:
                        logger.warning(
                            "[planning] Tier resolution failed for lead-agent model: %s", exc
                        )

            logger.info("[planning] Using lead-agent model for planning: %s", planning_model)

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

            source_agent = task_data.get("source_agent")
            if source_agent:
                for step in plan.steps:
                    if step.assigned_agent == source_agent:
                        logger.warning(
                            "[planning] Circular delegation detected: step '%s' would route back to source agent '%s'; reassigning to '%s'",
                            step.temp_id,
                            source_agent,
                            NANOBOT_AGENT_NAME,
                        )
                        step.assigned_agent = NANOBOT_AGENT_NAME

            logger.info(
                "[planning] Task '%s': %d-step plan created",
                title,
                len(plan.steps),
            )

            await self._store_execution_plan(task_id, plan)
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.TASK_PLANNING,
                f"Lead Agent generated execution plan for '{title}' ({len(plan.steps)} steps)",
                task_id,
                self._lead_agent_name,
            )
        except Exception as exc:
            logger.error(
                "[planning] Plan generation failed for task '%s': %s",
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
                f"Plan generation failed for '{title}': {type(exc).__name__}: {exc}",
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
            # Transition to review with awaitingKickoff so the dashboard
            # shows the kick-off UI
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
                "[planning] Task '%s' transitioned to review (awaitingKickoff); awaiting user kick-off.",
                title,
            )
            await asyncio.to_thread(
                self._bridge.post_lead_agent_message,
                task_id,
                build_plan_review_message(plan),
                "lead_agent_plan",
                plan_review=build_plan_review_metadata(plan),
            )
            return

        try:
            # Pre-register task_id so kickoff worker won't treat the
            # newly-in_progress task as a "resumed" task and double-dispatch it.
            self._known_kickoff_ids.add(task_id)
            created_step_ids = await asyncio.to_thread(
                self._plan_materializer.materialize,
                task_id,
                plan,
            )
            logger.info(
                "[planning] Task '%s': materialized %d step records",
                title,
                len(created_step_ids),
            )
            asyncio.create_task(self._step_dispatcher.dispatch_steps(task_id, created_step_ids))
            logger.info(
                "[planning] Task '%s': step dispatch started (autonomous mode)",
                title,
            )
        except Exception as exc:
            logger.error(
                "[planning] Plan materialization failed for task '%s': %s",
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

    async def _store_execution_plan(self, task_id: str, plan: ExecutionPlan) -> None:
        """Store the execution plan on the task document in Convex."""
        await asyncio.to_thread(
            self._bridge.update_execution_plan,
            task_id,
            plan.to_dict(),
        )

    async def _dispatch_workflow_plan(
        self,
        task_id: str,
        title: str,
        raw_plan: dict[str, Any],
        task_data: dict[str, Any],
    ) -> None:
        """Materialize and dispatch a pre-compiled workflow execution plan.

        This is the Layer 3 bypass path for ai_workflow tasks.  The workflow
        plan is already stored on the task document — we must NOT overwrite it.
        We parse it, materialize steps, and dispatch without touching the plan.
        """
        plan = ExecutionPlan.from_dict(raw_plan)

        supervision_mode = task_data.get("supervision_mode", "autonomous")
        if supervision_mode != "autonomous":
            # Transition to review with awaitingKickoff so the dashboard shows
            # the kick-off UI for the pre-compiled workflow plan.
            await asyncio.to_thread(
                self._bridge.update_task_status,
                task_id,
                TaskStatus.REVIEW,
                None,
                f"Workflow plan ready for review: '{title}'",
                True,  # awaiting_kickoff
            )
            logger.info(
                "[planning] Workflow task '%s' transitioned to review (awaitingKickoff).",
                title,
            )
            return

        try:
            self._known_kickoff_ids.add(task_id)
            created_step_ids = await asyncio.to_thread(
                self._plan_materializer.materialize,
                task_id,
                plan,
            )
            logger.info(
                "[planning] Workflow task '%s': materialized %d step records",
                title,
                len(created_step_ids),
            )
            asyncio.create_task(self._step_dispatcher.dispatch_steps(task_id, created_step_ids))
            logger.info(
                "[planning] Workflow task '%s': step dispatch started (autonomous mode)",
                title,
            )
        except Exception as exc:
            logger.error(
                "[planning] Workflow plan materialization failed for task '%s': %s",
                title,
                exc,
                exc_info=True,
            )
            await asyncio.to_thread(
                self._bridge.update_task_status,
                task_id,
                TaskStatus.FAILED,
            )
            await asyncio.to_thread(
                self._bridge.send_message,
                task_id,
                "System",
                AuthorType.SYSTEM,
                (
                    "Workflow plan materialization failed:\n"
                    f"```\n{type(exc).__name__}: {exc}\n```\n"
                    "Task marked as failed."
                ),
                MessageType.SYSTEM_EVENT,
            )
