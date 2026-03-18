"""Executor routing helpers extracted from TaskExecutor."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from mc.contexts.routing.llm_delegator import LLMDelegationRouter
from mc.types import (
    NANOBOT_AGENT_NAME,
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
) -> None:
    """Re-route lead-agent tasks through LLM delegation."""
    task_id = task_data["id"]
    title = task_data.get("title", "Untitled")

    logger.warning(
        "[executor] Lead Agent dispatch intercepted for task '%s'. "
        "Pure orchestrator invariant enforced; rerouting via LLM delegation.",
        title,
    )

    router = LLMDelegationRouter(bridge)
    try:
        decision = await router.route(task_data)
        rerouted_agent = decision.target_agent
    except RuntimeError as exc:
        logger.warning(
            "[executor] LLM delegation failed for lead-agent reroute on task '%s': %s; "
            "falling back to '%s'",
            title,
            exc,
            NANOBOT_AGENT_NAME,
        )
        rerouted_agent = NANOBOT_AGENT_NAME

    transition_result = await _transition_task_from_snapshot(
        bridge,
        task_data,
        TaskStatus.ASSIGNED,
        agent_name=rerouted_agent,
        reason=(
            f"Lead Agent dispatch intercepted for '{title}'. "
            f"Pure orchestrator invariant enforced; task re-routed to "
            f"{rerouted_agent} via LLM delegation."
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
