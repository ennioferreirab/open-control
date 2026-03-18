"""Plan Negotiation Handler — allows users to chat with the Lead Agent to modify
an execution plan before kick-off, while paused in review, or during execution.

Implements Story 4.5 AC4 and AC10 (pre-kickoff plan chat) and Story 7.3 (thread-based
negotiation during both review and in_progress phases):
- Subscribes to user thread messages on review tasks with an execution plan and
  in_progress tasks.
- Dispatches each user message to the LLM.
- Either updates the execution plan and explains the change, or responds
  with a clarification/acknowledgment message.
- During execution: only allows modifications to pending/blocked steps; locked steps
  (assigned, running, completed) cannot be changed.

Also handles @mention routing: when a user message contains @agent-name, the
mention_handler is invoked to dispatch the message to the mentioned agent directly.
As of Story 13.3, the PlanNegotiator skips @mention messages (the MentionWatcher
is the authoritative handler), but the old dispatch code is kept as a safety net.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING, Any, cast

from mc.contexts.interaction.service import has_pending_execution_question
from mc.contexts.planning.parser import parse_plan_payload
from mc.contexts.planning.planner import TaskPlanner
from mc.contexts.planning.review_messages import (
    build_plan_review_message,
    build_plan_review_metadata,
)
from mc.types import (
    ActivityEventType,
    AgentData,
    ExecutionPlan,
    TaskStatus,
    ThreadMessageType,
)

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

LLM_TIMEOUT_SECONDS = 30


def _log_task_exception(task: asyncio.Task) -> None:  # type: ignore[type-arg]
    """Callback to log exceptions from fire-and-forget asyncio tasks."""
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc is not None:
        logger.error("[plan_negotiator] Background task failed: %s", exc, exc_info=exc)


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
- Steps that are LOCKED (assigned, running, completed, waiting_human, crashed, or deleted — cannot be modified): {locked_steps}

If the user asks to modify a locked step, respond with action=clarify and explain \
that the step is already in progress or completed and cannot be changed.
"""

# Step statuses that are "in flight" or done — cannot be modified mid-execution
LOCKED_STEP_STATUSES = {"assigned", "running", "completed", "waiting_human", "crashed", "deleted"}
# Step statuses that can still be modified
MODIFIABLE_STEP_STATUSES = {"planned", "blocked"}


def _has_execution_plan(task: dict[str, Any]) -> bool:
    """Return True when task_data carries a non-empty execution plan."""
    plan = task.get("execution_plan") or task.get("executionPlan")
    return bool(isinstance(plan, dict) and plan.get("steps"))


def _extract_plan_review(message: dict[str, Any]) -> dict[str, Any] | None:
    """Return plan-review metadata from either snake_case or camelCase payloads."""
    plan_review = message.get("plan_review")
    if isinstance(plan_review, dict):
        return plan_review
    plan_review = message.get("planReview")
    if isinstance(plan_review, dict):
        return plan_review
    return None


def _has_current_plan_review_request(
    messages: list[dict[str, Any]],
    *,
    plan_generated_at: str | None,
) -> bool:
    """Return True when the thread already contains a review request for the active plan."""
    if not plan_generated_at:
        return False

    for message in messages:
        if (message.get("type") or message.get("message_type")) != "lead_agent_plan":
            continue
        plan_review = _extract_plan_review(message)
        if not isinstance(plan_review, dict):
            continue
        if (
            plan_review.get("kind") == "request"
            and plan_review.get("plan_generated_at") == plan_generated_at
        ):
            return True

    return False


def _parse_negotiation_response(raw: str) -> dict[str, Any]:
    """Parse LLM response JSON, handling markdown code fences."""
    text = raw.strip()
    if not text:
        return {"action": "clarify", "message": "(No response from model)"}

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)

    # Try to extract a JSON object if there's surrounding text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        text = match.group(0)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # LLM returned non-JSON text — treat as a clarification message
        return {"action": "clarify", "message": raw.strip()}


async def handle_plan_negotiation(
    bridge: ConvexBridge,
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
        from mc.infrastructure.providers.factory import create_provider

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
            explanation = response_data.get("explanation", "I've updated the plan as requested.")

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
                    new_plan = parse_plan_payload(updated_plan_dict)
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
                if task_status == "review":
                    await asyncio.to_thread(
                        bridge.post_lead_agent_message,
                        task_id,
                        build_plan_review_message(new_plan),
                        ThreadMessageType.LEAD_AGENT_PLAN,
                        plan_review=build_plan_review_metadata(new_plan),
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

    except TimeoutError:
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


async def create_initial_plan_from_message(
    bridge: ConvexBridge,
    task_id: str,
    user_message: str,
    *,
    task_data: dict[str, Any],
) -> None:
    """Generate the first execution plan for a manual review task from thread input."""
    title = task_data.get("title", "")
    description = task_data.get("description")
    assigned_agent = task_data.get("assigned_agent") or task_data.get("assignedAgent")
    files = task_data.get("files") or []

    logger.info(
        "[plan_negotiator] Creating initial execution plan for manual review task %s",
        task_id,
    )

    description_parts = []
    if isinstance(description, str) and description.strip():
        description_parts.append(description.strip())
    description_parts.append(
        f"User guidance for the initial execution plan:\n{user_message.strip()}"
    )
    planning_description = "\n\n".join(description_parts)

    try:
        from mc.contexts.planning.planner import _is_delegatable
        from mc.infrastructure.config import filter_agent_fields
        from mc.infrastructure.providers.tier_resolver import TierResolver

        agents_data = await asyncio.to_thread(bridge.list_agents)
        agents = [AgentData(**filter_agent_fields(agent)) for agent in agents_data]
        agents = [
            agent for agent in agents if agent.enabled is not False and _is_delegatable(agent)
        ]

        board_id = task_data.get("board_id") or task_data.get("boardId")
        if board_id:
            try:
                board = await asyncio.to_thread(bridge.get_board_by_id, board_id)
                if board:
                    board_enabled_agents = (
                        board.get("enabled_agents") or board.get("enabledAgents") or []
                    )
                    if board_enabled_agents:
                        agents = [
                            agent
                            for agent in agents
                            if agent.name in board_enabled_agents
                            or getattr(agent, "is_system", False)
                        ]
            except Exception:
                logger.warning(
                    "[plan_negotiator] Failed to load board config for task %s",
                    task_id,
                    exc_info=True,
                )

        planning_model = None
        planning_reasoning_level = None
        try:
            tier_resolver = TierResolver(bridge)
            planning_model = tier_resolver.resolve_model("tier:standard-medium")
            planning_reasoning_level = tier_resolver.resolve_reasoning_level("tier:standard-medium")
        except Exception as exc:
            logger.debug(
                "[plan_negotiator] Could not resolve planning tier for task %s: %s",
                task_id,
                exc,
            )

        planner = TaskPlanner(bridge)
        plan = await planner.plan_task(
            title,
            planning_description,
            agents,
            explicit_agent=assigned_agent,
            files=files,
            model=planning_model,
            reasoning_level=planning_reasoning_level,
        )

        await asyncio.to_thread(bridge.update_execution_plan, task_id, plan.to_dict())
        await asyncio.to_thread(
            bridge.update_task_status,
            task_id,
            TaskStatus.REVIEW,
            None,
            f"Initial plan ready for review: '{title}'",
            True,
        )
        await asyncio.to_thread(
            bridge.create_activity,
            ActivityEventType.TASK_PLANNING,
            f"Lead Agent created the initial execution plan for '{title}' from review conversation",
            task_id,
            "lead-agent",
        )
        await asyncio.to_thread(
            bridge.post_lead_agent_message,
            task_id,
            build_plan_review_message(plan),
            ThreadMessageType.LEAD_AGENT_PLAN,
            plan_review=build_plan_review_metadata(plan),
        )
    except Exception:
        logger.exception(
            "[plan_negotiator] Failed to create initial execution plan for task %s",
            task_id,
        )
        await asyncio.to_thread(
            bridge.post_lead_agent_message,
            task_id,
            "I couldn't create the initial execution plan from that message. "
            "Please try again with a bit more detail about the changes you want.",
            ThreadMessageType.LEAD_AGENT_CHAT,
        )


def _is_negotiable_status(task: dict[str, Any]) -> bool:
    """Return True if the task is in a status where plan negotiation is active.

    Active statuses:
    - "review" with awaitingKickoff=True (pre-kickoff plan review)
    - "review" with an execution_plan (paused plan revision before resume)
    - "in_progress" with an execution_plan (during planned execution)

    Tasks assigned directly via sendThreadMessage (no execution plan) are NOT
    negotiable — lead-agent should not intercept direct agent assignments.
    """
    status = task.get("status", "")
    review_phase = task.get("review_phase") or task.get("reviewPhase")
    has_execution_plan = _has_execution_plan(task)
    if status == "in_progress":
        # Only negotiable if there's an execution plan to negotiate.
        # Tasks sent directly to an agent via thread message have no plan.
        return has_execution_plan
    if status == "review":
        return bool(
            review_phase == "plan_review"
            or task.get("awaiting_kickoff")
            or task.get("awaitingKickoff")
            or has_execution_plan
        )
    return False


async def start_plan_negotiation_loop(
    bridge: ConvexBridge,
    task_id: str,
    poll_interval: float = 2.0,
    ask_user_registry: Any | None = None,
    sleep_controller: Any | None = None,
) -> None:
    """Subscribe to main thread messages for a task in review or in_progress status
    and dispatch each new user message to the plan negotiation handler.

    Subscribes to messages:listByTask (the full task thread) and filters for
    user messages only. Runs until the task leaves a negotiable status or is
    no longer found.

    When ask_user_registry is provided, user messages are skipped while an
    ask_user call is pending for the task — those replies are handled by the
    AskUserReplyWatcher instead.

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
        sleep_controller=sleep_controller,
    )

    seen_message_ids: set[str] = set()
    # Cap on seen IDs to prevent unbounded growth in long-running tasks.
    # When the cap is exceeded the oldest IDs are trimmed by rebuilding the set
    # from the current subscription batch (all current IDs become "seen").
    seen_ids_max = 1000

    while True:
        messages = cast(list[dict[str, Any]], await queue.get())

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
            task = await asyncio.to_thread(bridge.query, "tasks:getById", {"task_id": task_id})
        except Exception:
            logger.exception("[plan_negotiator] Failed to fetch task %s; stopping loop", task_id)
            break

        if not task:
            logger.info("[plan_negotiator] Task %s not found; stopping loop", task_id)
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
        awaiting_kickoff = bool(task.get("awaiting_kickoff") or task.get("awaitingKickoff"))
        review_phase = task.get("review_phase") or task.get("reviewPhase")

        # Get current plan from task
        current_plan = task.get("execution_plan") or task.get("executionPlan") or {}
        current_plan_generated_at = (
            current_plan.get("generated_at") or current_plan.get("generatedAt")
            if isinstance(current_plan, dict)
            else None
        )

        if (
            task_status == "review"
            and (review_phase == "plan_review" or awaiting_kickoff)
            and _has_execution_plan(task)
            and not _has_current_plan_review_request(
                messages,
                plan_generated_at=current_plan_generated_at,
            )
        ):
            try:
                plan = ExecutionPlan.from_dict(current_plan)
                await asyncio.to_thread(
                    bridge.post_lead_agent_message,
                    task_id,
                    build_plan_review_message(plan),
                    ThreadMessageType.LEAD_AGENT_PLAN,
                    plan_review=build_plan_review_metadata(plan),
                )
                logger.info(
                    "[plan_negotiator] Backfilled missing plan review request for task %s",
                    task_id,
                )
            except Exception:
                logger.exception(
                    "[plan_negotiator] Failed to backfill missing plan review request for task %s",
                    task_id,
                )

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

            plan_review = _extract_plan_review(msg)
            if isinstance(plan_review, dict) and plan_review.get("kind") == "decision":
                logger.debug(
                    "[plan_negotiator] Skipping plan review decision on task %s",
                    task_id,
                )
                continue

            # Skip if an ask_user call is pending — that reply belongs to the
            # AskUserReplyWatcher, not to the plan negotiator.
            if (
                ask_user_registry is not None and ask_user_registry.has_pending_ask(task_id)
            ) or has_pending_execution_question(bridge, task_id):
                logger.debug(
                    "[plan_negotiator] Skipping user message for task %s — ask_user pending",
                    task_id,
                )
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

            # Skip @mention messages — the MentionWatcher handles all
            # @mentions across every task status, so the PlanNegotiator
            # must not also process them (avoids double-processing).
            from mc.contexts.conversation.mentions.handler import (
                handle_all_mentions,
                is_mention_message,
            )

            if is_mention_message(content):
                logger.debug(
                    "[plan_negotiator] Skipping @mention message (handled by MentionWatcher): %s",
                    content[:80],
                )
                continue

            # Safety net: old @mention dispatch code (kept in case the guard
            # above has a bug — this block is unreachable when is_mention_message
            # works correctly, but remains as defense-in-depth).
            # Check for @mentions — dispatch to mention_handler if present.
            # A message that is purely a @mention (e.g. "@researcher help me")
            # is handled by the mention_handler and NOT forwarded to the plan
            # negotiator (to avoid the Lead Agent responding to agent-directed
            # messages).
            # A message with both @mentions and plan-change text is handled by
            # the mention_handler only — the @mention takes priority.
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

            is_lead_agent_conversation = bool(
                msg.get("lead_agent_conversation") or msg.get("leadAgentConversation")
            )

            # Plain thread replies belong to the task thread only. The plan negotiator
            # should run exclusively for explicit Lead Agent conversations, otherwise
            # ask_user answers and normal comments can be hijacked after the task
            # resumes to in_progress.
            if not is_lead_agent_conversation:
                logger.debug(
                    "[plan_negotiator] Skipping plain thread reply for task %s (status=%s)",
                    task_id,
                    task_status,
                )
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
        if len(seen_message_ids) > seen_ids_max:
            seen_message_ids = {
                m.get("_id") or m.get("id") or "" for m in messages if m.get("_id") or m.get("id")
            }
            logger.debug(
                "[plan_negotiator] Pruned seen_message_ids for task %s (now %d)",
                task_id,
                len(seen_message_ids),
            )
