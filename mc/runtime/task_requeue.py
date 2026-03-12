"""Cron requeue helpers extracted from the runtime gateway."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from mc.runtime.cron_delivery import PendingDeliveries
from mc.types import AuthorType, MessageType, NANOBOT_AGENT_NAME, is_lead_agent

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


async def _requeue_cron_task(
    bridge: "ConvexBridge",
    cron_job_id: str,
    task_id: str,
    message: str,
    agent: str | None = None,
    plan_negotiation_supervisor: Any | None = None,
) -> str | None:
    """Re-queue an existing task for cron execution."""
    try:
        task = await asyncio.to_thread(bridge.query, "tasks:getById", {"task_id": task_id})
    except Exception:
        logger.warning(
            "[gateway] Could not fetch cron origin task %s — creating new task instead",
            task_id,
        )
        create_args: dict[str, Any] = {"title": message, "active_cron_job_id": cron_job_id}
        if agent:
            create_args["assigned_agent"] = agent
        return await asyncio.to_thread(bridge.mutation, "tasks:create", create_args)

    if not task:
        logger.warning("[gateway] Cron origin task %s not found — creating new task", task_id)
        create_args = {"title": message, "active_cron_job_id": cron_job_id}
        if agent:
            create_args["assigned_agent"] = agent
        return await asyncio.to_thread(bridge.mutation, "tasks:create", create_args)

    current_status = task.get("status", "")
    if current_status in ("in_progress", "assigned", "deleted"):
        logger.info("[gateway] Cron origin task %s is '%s' — skipping re-queue", task_id, current_status)
        return None

    agent_name = agent or task.get("assigned_agent") or NANOBOT_AGENT_NAME
    if is_lead_agent(agent_name):
        logger.warning(
            "[gateway] Cron task %s had lead-agent assignment; using %s "
            "(pure orchestrator invariant)",
            task_id,
            NANOBOT_AGENT_NAME,
        )
        agent_name = NANOBOT_AGENT_NAME

    await asyncio.to_thread(
        bridge.send_message,
        task_id,
        "Cron",
        AuthorType.USER,
        f"\U0001f514 Cron triggered: {message}",
        MessageType.USER_MESSAGE,
    )
    await asyncio.to_thread(
        bridge.mutation,
        "tasks:markActiveCronJob",
        {"task_id": task_id, "cron_job_id": cron_job_id},
    )
    await asyncio.to_thread(
        bridge.update_task_status,
        task_id,
        "assigned",
        agent_name,
        f"Cron re-queued task to {agent_name}",
    )
    if plan_negotiation_supervisor is not None:
        plan_negotiation_supervisor.mark_cron_requeued(task_id)
    logger.info("[gateway] Cron re-queued task %s → assigned to %s", task_id, agent_name)
    return task_id


async def on_cron_job(
    bridge: "ConvexBridge",
    job: Any,
    pending_deliveries: PendingDeliveries,
    plan_negotiation_supervisor: Any | None = None,
) -> str | None:
    """Re-queue the originating task or create a new task when a cron job fires."""
    logger.info("[gateway] Cron job '%s' fired", job.name)
    task_id_for_delivery: str | None = None
    try:
        if job.payload.task_id:
            task_id_for_delivery = await _requeue_cron_task(
                bridge,
                job.id,
                job.payload.task_id,
                job.payload.message,
                agent=job.payload.agent,
                plan_negotiation_supervisor=plan_negotiation_supervisor,
            )
        else:
            create_args: dict[str, Any] = {
                "title": job.payload.message,
                "active_cron_job_id": job.id,
            }
            if job.payload.agent:
                create_args["assigned_agent"] = job.payload.agent
            task_id_for_delivery = await asyncio.to_thread(
                bridge.mutation,
                "tasks:create",
                create_args,
            )
    except Exception:
        logger.exception("[gateway] Failed to handle cron job '%s'", job.name)

    if (
        task_id_for_delivery
        and job.payload.deliver
        and job.payload.channel
        and job.payload.to
        and job.payload.channel != "mc"
    ):
        pending_deliveries[task_id_for_delivery] = (
            job.payload.channel,
            job.payload.to,
        )

    return task_id_for_delivery
