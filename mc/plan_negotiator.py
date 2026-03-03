"""Plan Negotiation Handler — allows users to chat with the Lead Agent to modify
an execution plan before kick-off or during execution.

Implements Story 4.5 AC4 and AC10 (pre-kickoff plan chat) and Story 7.3 (thread-based
negotiation during both review and in_progress phases):
- Subscribes to user thread messages on review (awaitingKickoff) and in_progress tasks.
- Dispatches each user message to the LLM.
- Either updates the execution plan and explains the change, or responds
  with a clarification/acknowledgment message.
- During execution: only allows modifications to pending/blocked steps; locked steps
  (assigned, running, completed) cannot be changed.

Also handles @mention routing: when a user message contains @agent-name, the
mention_handler is invoked to dispatch the message to the mentioned agent directly.
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

EXECUTION_CONTEXT_PROMPT = """\

Current execution state:
- Steps that CAN be modified (planned or blocked): {modifiable_steps}
- Steps that are LOCKED (assigned, running, completed, waiting_human, or crashed — cannot be modified): {locked_steps}

If the user asks to modify a locked step, respond with action=clarify and explain \
that the step is already in progress or completed and cannot be changed.
"""

# Step statuses that are "in flight" or done — cannot be modified mid-execution
LOCKED_STEP_STATUSES = {"assigned", "running", "completed", "waiting_human", "crashed"}
# Step statuses that can still be modified
MODIFIABLE_STEP_STATUSES = {"planned", "blocked"}


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
    task_status: str = "review",
    current_steps: list[dict[str, Any]] | None = None,
) -> None:
    """Handle a single user plan negotiation message.

    Calls the LLM with the current plan and user's request.  Depending on the
    LLM response:
    - If the LLM updates the plan: writes the new plan to Convex AND posts an
      explanation as a lead_agent_chat message.
    - If the LLM asks for clarification / acknowledges: posts only the chat
      message, leaving the plan unchanged.

    During execution (task_status == "in_progress"), the LLM prompt is augmented
    with the current step execution states so the LLM knows which steps are locked.

    Args:
        bridge: ConvexBridge instance for Convex mutations.
        task_id: Convex task _id.
        user_message: The user's plan-change request (raw text).
        current_plan: Current execution plan as a dict (camelCase keys).
        task_status: Current task status ("review" or "in_progress"). Defaults to "review".
        current_steps: Current materialized steps from Convex (used for in_progress context).
                       If None and task is in_progress, steps will be fetched from bridge.
    """
    logger.info(
        "[plan_negotiator] Processing plan negotiation for task %s (status=%s): %r",
        task_id,
        task_status,
        user_message[:100],
    )

    try:
        from nanobot.mc.provider_factory import create_provider

        current_plan_json = json.dumps(current_plan, indent=2)
        user_prompt = NEGOTIATION_USER_PROMPT.format(
            current_plan_json=current_plan_json,
            user_message=user_message,
        )

        # Build execution context for in_progress tasks
        # Also build a set of locked step titles for post-LLM enforcement
        locked_step_titles: set[str] = set()
        system_prompt = NEGOTIATION_SYSTEM_PROMPT
        if task_status == "in_progress":
            # Fetch steps if not provided
            steps = current_steps
            if steps is None:
                steps = await asyncio.to_thread(bridge.get_steps_by_task, task_id)
            if steps:
                modifiable = [
                    s.get("title", s.get("id", "?"))
                    for s in steps
                    if s.get("status", "") in MODIFIABLE_STEP_STATUSES
                ]
                locked = [
                    s.get("title", s.get("id", "?"))
                    for s in steps
                    if s.get("status", "") in LOCKED_STEP_STATUSES
                ]
                locked_step_titles = {
                    s.get("title", "")
                    for s in steps
                    if s.get("status", "") in LOCKED_STEP_STATUSES and s.get("title")
                }
                execution_context = EXECUTION_CONTEXT_PROMPT.format(
                    modifiable_steps=", ".join(modifiable) if modifiable else "none",
                    locked_steps=", ".join(locked) if locked else "none",
                )
                system_prompt = NEGOTIATION_SYSTEM_PROMPT + execution_context
                logger.debug(
                    "[plan_negotiator] Added execution context for task %s: "
                    "%d modifiable, %d locked steps",
                    task_id,
                    len(modifiable),
                    len(locked),
                )

        provider, model = create_provider()
        llm_response = await asyncio.wait_for(
            provider.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )
        raw_response = llm_response.content or ""

        response_data = _parse_negotiation_response(raw_response)
        action = response_data.get("action", "clarify")

        if action == "update_plan":
            updated_plan_dict = response_data.get("updated_plan")
            explanation = response_data.get(
                "explanation", "I've updated the plan as requested."
            )

            if updated_plan_dict and isinstance(updated_plan_dict, dict):
                # Enforcement: when task is in_progress, veto update_plan responses
                # that touch steps already in flight (assigned/running/completed).
                # This prevents the LLM from modifying locked steps even if it
                # ignores the system-prompt instruction to respond with clarify.
                if task_status == "in_progress" and locked_step_titles:
                    proposed_titles = {
                        step.get("title", "")
                        for step in updated_plan_dict.get("steps", [])
                        if step.get("title")
                    }
                    touched_locked = proposed_titles & locked_step_titles
                    if touched_locked:
                        locked_list = ", ".join(sorted(touched_locked))
                        logger.info(
                            "[plan_negotiator] Vetoed update_plan for task %s: "
                            "proposed plan touches locked steps: %s",
                            task_id,
                            locked_list,
                        )
                        await asyncio.to_thread(
                            bridge.post_lead_agent_message,
                            task_id,
                            f"I cannot modify the following steps because they are already "
                            f"in progress or completed: {locked_list}. Only steps that "
                            f"have not started yet can be changed.",
                            ThreadMessageType.LEAD_AGENT_CHAT,
                        )
                        return

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


def _is_negotiable_status(task: dict[str, Any]) -> bool:
    """Return True if the task is in a status where plan negotiation is active.

    Active statuses:
    - "review" with awaitingKickoff=True (pre-kickoff plan review)
    - "in_progress" (during execution — only pending/blocked steps can change)
    """
    status = task.get("status", "")
    if status == "in_progress":
        return True
    if status == "review" and task.get("awaiting_kickoff"):
        return True
    return False


async def start_plan_negotiation_loop(
    bridge: "ConvexBridge",
    task_id: str,
    poll_interval: float = 2.0,
) -> None:
    """Subscribe to main thread messages for a task in review or in_progress status
    and dispatch each new user message to the plan negotiation handler.

    Subscribes to messages:listByTask (the full task thread) and filters for
    user messages only. Runs until the task leaves a negotiable status or is
    no longer found.

    Story 7.3: Replaces the old messages:listPlanChat subscription with
    messages:listByTask so that the Lead Agent responds to messages in the
    main thread — both during pre-kickoff review and during execution.

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
        "messages:listByTask",
        {"task_id": task_id},
        poll_interval=poll_interval,
    )

    seen_message_ids: set[str] = set()
    # Cap on seen IDs to prevent unbounded growth in long-running tasks.
    # When the cap is exceeded the oldest IDs are trimmed by rebuilding the set
    # from the current subscription batch (all current IDs become "seen").
    _SEEN_IDS_MAX = 1000

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

        # Check that the task is still in a negotiable status
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

        if not _is_negotiable_status(task):
            task_status = task.get("status", "")
            logger.info(
                "[plan_negotiator] Task %s is now '%s'; stopping negotiation loop",
                task_id,
                task_status,
            )
            break

        task_status = task.get("status", "")

        # Get current plan from task
        current_plan = task.get("execution_plan") or task.get("executionPlan") or {}

        # Process only new user messages (not ones we've already seen).
        # Pruning happens AFTER processing so that new messages in the current
        # batch are never incorrectly marked as seen before they are dispatched.
        for msg in messages:
            msg_id = msg.get("_id") or msg.get("id") or ""
            author_type = msg.get("author_type") or msg.get("authorType") or ""

            if msg_id in seen_message_ids:
                continue
            seen_message_ids.add(msg_id)

            # Only process user messages (skip agent completions, system events,
            # and the Lead Agent's own responses to avoid an infinite loop)
            if author_type != "user":
                continue

            content = msg.get("content", "")
            if not content.strip():
                continue

            logger.info(
                "[plan_negotiator] New user message on task %s (status=%s): %r",
                task_id,
                task_status,
                content[:80],
            )

            # Check for @mentions — dispatch to mention_handler if present.
            # A message that is purely a @mention (e.g. "@researcher help me")
            # is handled by the mention_handler and NOT forwarded to the plan
            # negotiator (to avoid the Lead Agent responding to agent-directed
            # messages).
            # A message with both @mentions and plan-change text is handled by
            # the mention_handler only — the @mention takes priority.
            from nanobot.mc.mention_handler import is_mention_message, handle_all_mentions

            if is_mention_message(content):
                task_title = task.get("title", "")
                mention_task = asyncio.create_task(
                    handle_all_mentions(
                        bridge=bridge,
                        task_id=task_id,
                        content=content,
                        task_title=task_title,
                    )
                )
                mention_task.add_done_callback(_log_task_exception)
                # Skip plan negotiation for @mention messages
                continue

            # Dispatch to plan negotiation handler as a background task with error logging
            bg_task = asyncio.create_task(
                handle_plan_negotiation(
                    bridge,
                    task_id,
                    content,
                    current_plan,
                    task_status=task_status,
                )
            )
            bg_task.add_done_callback(_log_task_exception)

        # Prune seen_message_ids if it grows too large. Done after processing
        # so that new messages in the current batch are never skipped.
        # Since the subscription returns the full current message list each time,
        # we rebuild the set from the current batch (all returned IDs become "seen").
        if len(seen_message_ids) > _SEEN_IDS_MAX:
            seen_message_ids = {
                m.get("_id") or m.get("id") or ""
                for m in messages
                if m.get("_id") or m.get("id")
            }
            logger.debug(
                "[plan_negotiator] Pruned seen_message_ids for task %s (now %d)",
                task_id,
                len(seen_message_ids),
            )
