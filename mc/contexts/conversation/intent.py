"""Conversation Intent Resolver -- classifies thread messages into intents.

Determines what kind of action a user message should trigger:
- comment: plain comment, no agent action
- mention: @mention of an agent
- follow_up: non-mention follow-up to an agent in an active task
- plan_chat: plan discussion/negotiation (review + awaitingKickoff, or in_progress with plan)
- manual_reply: human reply in manual/human task (ask_user pending)

Story 17.3 -- AC1: ConversationIntentResolver.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from mc.domain.workflow_ownership import is_workflow_owned_task

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


class ConversationIntent(Enum):
    """Intent types for thread messages."""

    COMMENT = "comment"
    MENTION = "mention"
    FOLLOW_UP = "follow_up"
    PLAN_CHAT = "plan_chat"
    MANUAL_REPLY = "manual_reply"


@dataclass
class ResolveResult:
    """Result of intent resolution.

    Attributes:
        intent: The classified intent type.
        content: The original message content.
        task_data: Task document dict (snake_case keys).
        mentioned_agents: List of (agent_name, query) tuples for mention intents.
    """

    intent: ConversationIntent
    content: str
    task_data: dict[str, Any]
    mentioned_agents: list[tuple[str, str]] = field(default_factory=list)


def _is_negotiable_status(task_data: dict[str, Any]) -> bool:
    """Return True if the task is in a status where plan negotiation is active.

    Only workflow-backed tasks (workMode=ai_workflow) are eligible for plan
    negotiation. Direct-delegate and human-routed tasks use normal thread
    behavior instead.

    Active statuses (workflow only):
    - "review" with awaiting_kickoff=True (pre-kickoff plan review)
    - "in_progress" with an execution_plan (during planned execution)
    """
    if not is_workflow_owned_task(task_data):
        return False

    status = task_data.get("status", "")
    review_phase = task_data.get("review_phase") or task_data.get("reviewPhase")
    if status == "in_progress":
        plan = task_data.get("execution_plan") or task_data.get("executionPlan")
        return bool(plan and isinstance(plan, dict) and plan.get("steps"))
    if status == "review" and (review_phase == "plan_review" or task_data.get("awaiting_kickoff")):
        return True
    return False


# Statuses where a non-mention message is treated as a follow-up to the
# assigned agent (rather than a plain comment).
_ACTIVE_TASK_STATUSES = frozenset(
    {
        "assigned",
        "in_progress",
        "review",
        "retrying",
    }
)


class ConversationIntentResolver:
    """Classifies thread messages into conversation intents.

    Uses message content, task state, and thread context to determine
    the intent of a user's message.
    """

    def __init__(self, bridge: ConvexBridge) -> None:
        self._bridge = bridge

    def resolve(
        self,
        content: str,
        task_data: dict[str, Any],
        has_pending_ask: bool = False,
    ) -> ResolveResult:
        """Classify a user message into a conversation intent.

        Priority order:
        1. Empty/whitespace content => comment
        2. @mention detected => mention (always, regardless of status)
        3. ask_user pending => manual_reply
        4. Negotiable task (review+kickoff or in_progress+plan) => plan_chat
        5. Active task with assigned agent => follow_up
        6. Otherwise => comment

        Args:
            content: Raw message text from the user.
            task_data: Task document dict (snake_case keys).
            has_pending_ask: Whether an ask_user call is pending for this task.

        Returns:
            ResolveResult with the classified intent and metadata.
        """
        # 1. Empty content => comment
        if not content or not content.strip():
            return ResolveResult(
                intent=ConversationIntent.COMMENT,
                content=content or "",
                task_data=task_data,
            )

        # 2. @mention always takes priority
        from mc.contexts.conversation.mentions.handler import extract_mentions

        mentions = extract_mentions(content)
        if mentions:
            return ResolveResult(
                intent=ConversationIntent.MENTION,
                content=content,
                task_data=task_data,
                mentioned_agents=mentions,
            )

        # 3. ask_user pending => manual_reply
        if has_pending_ask:
            return ResolveResult(
                intent=ConversationIntent.MANUAL_REPLY,
                content=content,
                task_data=task_data,
            )

        # 4. Negotiable task => plan_chat
        if _is_negotiable_status(task_data):
            return ResolveResult(
                intent=ConversationIntent.PLAN_CHAT,
                content=content,
                task_data=task_data,
            )

        # 5. Active task with assigned agent => follow_up
        status = task_data.get("status", "")
        assigned_agent = task_data.get("assigned_agent")
        if status in _ACTIVE_TASK_STATUSES and assigned_agent:
            return ResolveResult(
                intent=ConversationIntent.FOLLOW_UP,
                content=content,
                task_data=task_data,
            )

        # 6. Default => comment
        return ResolveResult(
            intent=ConversationIntent.COMMENT,
            content=content,
            task_data=task_data,
        )
