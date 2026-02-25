"""Plan Negotiation Handler — allows users to chat with the Lead Agent to modify
an execution plan before kick-off.

Implements Story 4.5 AC4 and AC10:
- Subscribes to lead_agent_chat messages on reviewing_plan tasks.
- Dispatches each user message to the LLM.
- Either updates the execution plan and explains the change, or responds
  with a clarification/acknowledgment message.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING, Any

from nanobot.mc.types import (
    ExecutionPlan,
    LEAD_AGENT_NAME,
    ThreadMessageType,
)

if TYPE_CHECKING:
    from nanobot.mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

LLM_TIMEOUT_SECONDS = 30


def _log_task_exception(task: asyncio.Task) -> None:  # type: ignore[type-arg]
    """Callback to log exceptions from fire-and-forget asyncio tasks."""
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc is not None:
        logger.error(
            "[plan_negotiator] Background task failed: %s", exc, exc_info=exc
        )

NEGOTIATION_SYSTEM_PROMPT = """\
You are the Lead Agent, responsible for managing and refining execution plans
for a multi-agent system. A user is reviewing a plan and may ask you to make
changes such as adding steps, removing steps, reassigning steps to different
agents, or reordering steps.

Your job is to:
1. Understand the user's request.
2. Decide whether you can modify the plan directly or need clarification.
3. Respond clearly with either a modified plan or a clarification question.

RESPONSE FORMAT — you MUST respond with a JSON object:

If you can apply the change, respond with:
{
  "action": "update_plan",
  "updated_plan": {
    "steps": [
      {
        "tempId": "step_1",
        "title": "Short step title",
        "description": "What this step does",
        "assignedAgent": "agent-name",
        "blockedBy": [],
        "parallelGroup": 1,
        "order": 1
      }
    ]
  },
  "explanation": "A human-readable explanation of what you changed and why."
}

If you need clarification or are acknowledging without a plan change, respond with:
{
  "action": "clarify",
  "message": "Your clarification question or acknowledgment message here."
}

Rules for the plan:
- tempId must be "step_1", "step_2", etc.
- NEVER assign "lead-agent" to any step — lead-agent only plans, it never executes.
- blockedBy is a list of tempIds that must complete before this step starts.
- Steps with no blockers that can run simultaneously share the same parallelGroup number.
- order is the display/execution order (1, 2, 3, ...).
- Preserve the existing plan structure as much as possible; only change what the user requests.
"""

NEGOTIATION_USER_PROMPT = """\
Current execution plan:
{current_plan_json}

User request: {user_message}

Please respond with a JSON object as described in the system prompt.
"""


def _parse_negotiation_response(raw: str) -> dict[str, Any]:
    """Parse LLM response JSON, handling markdown code fences."""
    text = raw.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)

    # Try to extract a JSON object if there's surrounding text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        text = match.group(0)

    return json.loads(text)


async def handle_plan_negotiation(
    bridge: "ConvexBridge",
    task_id: str,
    user_message: str,
    current_plan: dict[str, Any],
) -> None:
    """Handle a single user plan negotiation message.

    Calls the LLM with the current plan and user's request.  Depending on the
    LLM response:
    - If the LLM updates the plan: writes the new plan to Convex AND posts an
      explanation as a lead_agent_chat message.
    - If the LLM asks for clarification / acknowledges: posts only the chat
      message, leaving the plan unchanged.

    Args:
        bridge: ConvexBridge instance for Convex mutations.
        task_id: Convex task _id.
        user_message: The user's plan-change request (raw text).
        current_plan: Current execution plan as a dict (camelCase keys).
    """
    logger.info(
        "[plan_negotiator] Processing plan negotiation for task %s: %r",
        task_id,
        user_message[:100],
    )

    try:
        from nanobot.mc.provider_factory import create_provider

        current_plan_json = json.dumps(current_plan, indent=2)
        user_prompt = NEGOTIATION_USER_PROMPT.format(
            current_plan_json=current_plan_json,
            user_message=user_message,
        )

        provider, model = create_provider()
        raw_response = await asyncio.wait_for(
            asyncio.to_thread(
                provider.chat,
                model=model,
                messages=[
                    {"role": "system", "content": NEGOTIATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )

        response_data = _parse_negotiation_response(raw_response)
        action = response_data.get("action", "clarify")

        if action == "update_plan":
            updated_plan_dict = response_data.get("updated_plan")
            explanation = response_data.get(
                "explanation", "I've updated the plan as requested."
            )

            if updated_plan_dict and isinstance(updated_plan_dict, dict):
                # Validate and normalize the plan via ExecutionPlan dataclass
                try:
                    new_plan = ExecutionPlan.from_dict(updated_plan_dict)
                    # Re-serialize to ensure consistent camelCase keys
                    normalized_dict = new_plan.to_dict()
                except Exception as parse_exc:
                    logger.warning(
                        "[plan_negotiator] Could not parse updated plan for task %s: %s; "
                        "responding with explanation only",
                        task_id,
                        parse_exc,
                    )
                    # Fall through to clarify path
                    await asyncio.to_thread(
                        bridge.post_lead_agent_message,
                        task_id,
                        "I tried to update the plan but encountered an issue "
                        "processing the result. The plan has not been changed. "
                        "Please try rephrasing your request.",
                        ThreadMessageType.LEAD_AGENT_CHAT,
                    )
                    return

                # Write updated plan to Convex
                await asyncio.to_thread(
                    bridge.update_execution_plan,
                    task_id,
                    normalized_dict,
                )
                logger.info(
                    "[plan_negotiator] Updated execution plan for task %s (%d steps)",
                    task_id,
                    len(new_plan.steps),
                )

                # Post explanation as lead_agent_chat
                await asyncio.to_thread(
                    bridge.post_lead_agent_message,
                    task_id,
                    explanation,
                    ThreadMessageType.LEAD_AGENT_CHAT,
                )
            else:
                logger.warning(
                    "[plan_negotiator] action=update_plan but no valid updated_plan "
                    "in response for task %s; treating as clarify",
                    task_id,
                )
                message = response_data.get(
                    "message", "I'm ready to update the plan — could you clarify?"
                )
                await asyncio.to_thread(
                    bridge.post_lead_agent_message,
                    task_id,
                    message,
                    ThreadMessageType.LEAD_AGENT_CHAT,
                )

        else:
            # action == "clarify" or any unrecognised action
            message = response_data.get(
                "message",
                "I'm here to help! Please describe what changes you'd like.",
            )
            await asyncio.to_thread(
                bridge.post_lead_agent_message,
                task_id,
                message,
                ThreadMessageType.LEAD_AGENT_CHAT,
            )

    except asyncio.TimeoutError:
        logger.error(
            "[plan_negotiator] LLM timed out for task %s after %ds",
            task_id,
            LLM_TIMEOUT_SECONDS,
        )
        await asyncio.to_thread(
            bridge.post_lead_agent_message,
            task_id,
            "I'm sorry, I timed out processing your request. Please try again.",
            ThreadMessageType.LEAD_AGENT_CHAT,
        )

    except Exception as exc:
        logger.error(
            "[plan_negotiator] Unexpected error for task %s: %s",
            task_id,
            exc,
            exc_info=True,
        )
        await asyncio.to_thread(
            bridge.post_lead_agent_message,
            task_id,
            "I encountered an unexpected error processing your request. "
            "Please try again or rephrase your message.",
            ThreadMessageType.LEAD_AGENT_CHAT,
        )


async def start_plan_negotiation_loop(
    bridge: "ConvexBridge",
    task_id: str,
    poll_interval: float = 2.0,
) -> None:
    """Subscribe to lead_agent_chat messages for a task in reviewing_plan status
    and dispatch each new user message to the plan negotiation handler.

    Runs until the task leaves reviewing_plan status or the task is no longer found.

    Args:
        bridge: ConvexBridge instance.
        task_id: Convex task _id to monitor.
        poll_interval: Seconds between polls. Defaults to 2.0.
    """
    logger.info(
        "[plan_negotiator] Starting plan negotiation loop for task %s",
        task_id,
    )

    queue = bridge.async_subscribe(
        "messages:listPlanChat",
        {"task_id": task_id},
        poll_interval=poll_interval,
    )

    seen_message_ids: set[str] = set()

    while True:
        messages = await queue.get()

        # Check for polling errors
        if isinstance(messages, dict) and messages.get("_error"):
            logger.error(
                "[plan_negotiator] Subscription error for task %s: %s",
                task_id,
                messages.get("message"),
            )
            break

        if not messages:
            continue

        # Check that the task is still in reviewing_plan status
        try:
            task = await asyncio.to_thread(
                bridge.query, "tasks:getById", {"task_id": task_id}
            )
        except Exception:
            logger.exception(
                "[plan_negotiator] Failed to fetch task %s; stopping loop", task_id
            )
            break

        if not task:
            logger.info(
                "[plan_negotiator] Task %s not found; stopping loop", task_id
            )
            break

        task_status = task.get("status", "")
        if task_status != "reviewing_plan":
            logger.info(
                "[plan_negotiator] Task %s is now '%s'; stopping loop",
                task_id,
                task_status,
            )
            break

        # Get current plan from task
        current_plan = task.get("execution_plan") or task.get("executionPlan") or {}

        # Process only new user messages (not ones we've already seen)
        for msg in messages:
            msg_id = msg.get("_id") or msg.get("id") or ""
            author_type = msg.get("author_type") or msg.get("authorType") or ""

            if msg_id in seen_message_ids:
                continue
            seen_message_ids.add(msg_id)

            # Only process user messages (the Lead Agent's own responses are skipped)
            if author_type != "user":
                continue

            content = msg.get("content", "")
            if not content.strip():
                continue

            logger.info(
                "[plan_negotiator] New user message on task %s: %r",
                task_id,
                content[:80],
            )

            # Dispatch to handler as a background task with error logging
            task = asyncio.create_task(
                handle_plan_negotiation(bridge, task_id, content, current_plan)
            )
            task.add_done_callback(_log_task_exception)
