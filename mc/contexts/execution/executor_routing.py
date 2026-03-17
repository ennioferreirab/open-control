"""Executor routing helpers extracted from TaskExecutor."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from mc.contexts.planning.planner import TaskPlanner
from mc.types import (
    NANOBOT_AGENT_NAME,
    AgentData,
    AuthorType,
    MessageType,
    TaskStatus,
    TrustLevel,
    is_lead_agent,
)

logger = logging.getLogger(__name__)


async def _transition_task_from_snapshot(
    bridge: Any,
    task_data: dict[str, Any],
    to_status: str,
    *,
    reason: str,
    agent_name: str | None = None,
    review_phase: str | None = None,
    awaiting_kickoff: bool | None = None,
    retry_on_stale: bool = False,
) -> Any:
    task_id = str(task_data.get("id") or "")
    result = await asyncio.to_thread(
        bridge.transition_task_from_snapshot,
        task_data,
        to_status,
        reason=reason,
        agent_name=agent_name,
        review_phase=review_phase,
        awaiting_kickoff=awaiting_kickoff,
    )
    if (
        retry_on_stale
        and isinstance(result, dict)
        and result.get("kind") == "conflict"
        and result.get("reason") == "stale_state"
        and task_id
    ):
        fresh_task = await asyncio.to_thread(bridge.get_task, task_id)
        if isinstance(fresh_task, dict) and fresh_task.get("status") == task_data.get("status"):
            logger.info(
                "[executor] Retrying task %s transition to %s with refreshed state_version",
                task_id,
                to_status,
            )
            result = await asyncio.to_thread(
                bridge.transition_task_from_snapshot,
                fresh_task,
                to_status,
                reason=reason,
                agent_name=agent_name,
                review_phase=review_phase,
                awaiting_kickoff=awaiting_kickoff,
            )
    return result


async def pickup_task(
    executor: Any,
    task_data: dict[str, Any],
    planner_cls: type[TaskPlanner] = TaskPlanner,
) -> None:
    """Transition assigned task to in_progress and start execution."""
    task_id = task_data["id"]
    title = task_data.get("title", "Untitled")
    description = task_data.get("description")
    agent_name = task_data.get("assigned_agent") or NANOBOT_AGENT_NAME
    trust_level = task_data.get("trust_level", TrustLevel.AUTONOMOUS)
    try:
        if is_lead_agent(agent_name):
            await reroute_lead_agent_task(
                executor._bridge,
                task_data,
                planner_cls=planner_cls,
            )
            return

        transition_result = await _transition_task_from_snapshot(
            executor._bridge,
            task_data,
            TaskStatus.IN_PROGRESS,
            agent_name=agent_name,
            reason=f"Agent {agent_name} started work on '{title}'",
            retry_on_stale=True,
        )
        if not isinstance(transition_result, dict) or transition_result.get("kind") != "applied":
            logger.warning(
                "[executor] Skipping execution for task %s because pickup transition did not apply: %s",
                task_id,
                transition_result,
            )
            return

        await asyncio.to_thread(
            executor._bridge.send_message,
            task_id,
            "System",
            AuthorType.SYSTEM,
            f"Agent {agent_name} has started work on this task.",
            MessageType.SYSTEM_EVENT,
        )

        logger.info(
            "[executor] Task '%s' picked up by '%s' — now in_progress",
            title,
            agent_name,
        )

        await executor._execute_task(
            task_id, title, description, agent_name, trust_level, task_data
        )
    finally:
        executor._known_assigned_ids.discard(task_id)


async def reroute_lead_agent_task(
    bridge: Any,
    task_data: dict[str, Any],
    planner_cls: type[TaskPlanner] = TaskPlanner,
) -> None:
    """Re-route lead-agent tasks through the planner."""
    from mc.infrastructure.config import filter_agent_fields

    task_id = task_data["id"]
    title = task_data.get("title", "Untitled")
    description = task_data.get("description")

    logger.warning(
        "[executor] Lead Agent dispatch intercepted for task '%s'. "
        "Pure orchestrator invariant enforced; rerouting via planner.",
        title,
    )

    try:
        agents_data = await asyncio.to_thread(bridge.list_agents)
        agents = [AgentData(**filter_agent_fields(a)) for a in agents_data]
        agents = [a for a in agents if a.enabled is not False]
    except Exception:
        logger.warning(
            "[executor] Failed to list agents while rerouting lead-agent "
            "task '%s'; using planner fallback",
            title,
            exc_info=True,
        )
        agents = []

    planner = planner_cls(bridge)
    plan = await planner.plan_task(
        title=title,
        description=description,
        agents=agents,
        files=task_data.get("files") or [],
    )

    rerouted_agent = next(
        (
            step.assigned_agent
            for step in plan.steps
            if step.assigned_agent and not is_lead_agent(step.assigned_agent)
        ),
        None,
    )
    if not rerouted_agent:
        rerouted_agent = NANOBOT_AGENT_NAME
        logger.warning(
            "[executor] Lead-agent reroute produced no executable assignee; "
            "using '%s' for task '%s'",
            rerouted_agent,
            title,
        )

    await asyncio.to_thread(bridge.update_execution_plan, task_id, plan.to_dict())
    transition_result = await _transition_task_from_snapshot(
        bridge,
        task_data,
        TaskStatus.ASSIGNED,
        agent_name=rerouted_agent,
        reason=(
            f"Lead Agent dispatch intercepted for '{title}'. "
            f"Pure orchestrator invariant enforced; task re-routed to "
            f"{rerouted_agent} via planner."
        ),
        retry_on_stale=True,
    )
    if not isinstance(transition_result, dict) or transition_result.get("kind") != "applied":
        logger.warning(
            "[executor] Skipping reroute side effects for task %s because assign transition did not apply: %s",
            task_id,
            transition_result,
        )
        return
    await asyncio.to_thread(
        bridge.send_message,
        task_id,
        "System",
        AuthorType.SYSTEM,
        (
            "Lead Agent is a pure orchestrator and cannot execute tasks "
            f"directly. Task re-routed to {rerouted_agent}."
        ),
        MessageType.SYSTEM_EVENT,
    )
