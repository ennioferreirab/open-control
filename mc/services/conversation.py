"""Unified Conversation Service -- routes all thread messages through a single pipeline.

Provides:
- Unified message classification (delegates to IntentResolver)
- Shared context assembly for all conversation types
- Shared response posting for all conversation types

All conversation code paths (mentions, follow-ups, plan-chat, ask-user replies,
plain comments) flow through this service.

Story 17.3 -- AC2: ConversationService.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from mc.mentions.handler import handle_all_mentions
from mc.plan_negotiator import handle_plan_negotiation
from mc.services.conversation_intent import (
    ConversationIntent,
    ConversationIntentResolver,
    ResolveResult,
)

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


def build_thread_context(
    messages: list[dict[str, Any]],
    *,
    max_messages: int = 20,
) -> str:
    """Build thread context using the shared ThreadContextBuilder.

    Thin wrapper around mc.application.execution.thread_context_builder
    for use by the conversation service.
    """
    from mc.application.execution.thread_context_builder import (
        build_thread_context as _build,
    )

    return _build(messages, max_messages=max_messages)


class ConversationService:
    """Unified service for processing all thread messages.

    Delegates intent classification to ConversationIntentResolver, then
    dispatches to the appropriate handler based on the resolved intent.

    Usage:
        svc = ConversationService(bridge=bridge, ask_user_registry=registry)
        result = await svc.handle_message(task_id, content, task_data)
        # result.intent tells the caller what happened
    """

    def __init__(
        self,
        bridge: "ConvexBridge",
        ask_user_registry: Any | None = None,
    ) -> None:
        self._bridge = bridge
        self._ask_user_registry = ask_user_registry
        self._intent_resolver = ConversationIntentResolver(bridge=bridge)

    def classify(
        self,
        content: str,
        task_data: dict[str, Any],
        task_id: str | None = None,
    ) -> ResolveResult:
        """Classify a message without dispatching any side effects.

        Useful when callers want to inspect the intent before deciding
        what action to take.

        Args:
            content: Raw message text from the user.
            task_data: Task document dict (snake_case keys).
            task_id: Optional task ID (used for ask_user pending check).

        Returns:
            ResolveResult with the classified intent and metadata.
        """
        has_pending_ask = False
        if task_id and self._ask_user_registry is not None:
            has_pending_ask = self._ask_user_registry.has_pending_ask(task_id)

        return self._intent_resolver.resolve(
            content=content,
            task_data=task_data,
            has_pending_ask=has_pending_ask,
        )

    async def build_context(
        self,
        task_id: str,
        *,
        max_messages: int = 20,
    ) -> str:
        """Assemble shared thread context for any conversation type.

        Uses the unified ThreadContextBuilder (from Story 16.1).
        Callers can layer additional context (mention metadata, plan
        context) on top of this shared base.

        Args:
            task_id: Convex task _id.
            max_messages: Truncation window size (default 20).

        Returns:
            Formatted context string, or "" if no relevant context.
        """
        try:
            messages = await asyncio.to_thread(
                self._bridge.get_task_messages, task_id
            )
        except Exception:
            logger.warning(
                "[conversation] Failed to fetch messages for task %s",
                task_id,
                exc_info=True,
            )
            return ""

        if not messages:
            return ""

        return build_thread_context(messages, max_messages=max_messages)

    async def handle_message(
        self,
        task_id: str,
        content: str,
        task_data: dict[str, Any],
    ) -> ResolveResult:
        """Process a user message through the unified conversation pipeline.

        1. Classify the message intent
        2. Dispatch to the appropriate handler
        3. Return the resolve result for caller inspection

        Args:
            task_id: Convex task _id.
            content: Raw message text from the user.
            task_data: Task document dict (snake_case keys).

        Returns:
            ResolveResult with the classified intent and metadata.
        """
        result = self.classify(content, task_data, task_id=task_id)
        task_title = task_data.get("title", "")

        if result.intent == ConversationIntent.MENTION:
            await self._dispatch_mention(task_id, content, task_title)

        elif result.intent == ConversationIntent.PLAN_CHAT:
            await self._dispatch_plan_chat(task_id, content, task_data)

        elif result.intent == ConversationIntent.MANUAL_REPLY:
            # manual_reply: the caller (AskUserReplyWatcher) handles delivery.
            # We just return the intent so the caller knows to deliver the reply.
            logger.debug(
                "[conversation] manual_reply for task %s — caller handles delivery",
                task_id,
            )

        elif result.intent == ConversationIntent.FOLLOW_UP:
            # follow_up: the caller decides what to do (e.g., route to CC
            # thread reply, or inject context into active agent session).
            logger.debug(
                "[conversation] follow_up for task %s — caller handles routing",
                task_id,
            )

        elif result.intent == ConversationIntent.COMMENT:
            # comment: no agent action needed.
            logger.debug("[conversation] comment on task %s — no action", task_id)

        return result

    async def post_response(
        self,
        task_id: str,
        author_name: str,
        content: str,
        *,
        author_type: str = "agent",
        message_type: str = "work",
    ) -> None:
        """Post a response message to a task thread.

        Shared response posting for all conversation types.

        Args:
            task_id: Convex task _id.
            author_name: Display name of the author.
            content: Response content.
            author_type: Author type (default "agent").
            message_type: Message type (default "work").
        """
        try:
            await asyncio.to_thread(
                self._bridge.send_message,
                task_id,
                author_name,
                author_type,
                content,
                message_type,
            )
        except Exception:
            logger.error(
                "[conversation] Failed to post response for task %s",
                task_id,
                exc_info=True,
            )

    # ── Private dispatch methods ─────────────────────────────────────

    async def _dispatch_mention(
        self, task_id: str, content: str, task_title: str
    ) -> None:
        """Dispatch @mention handling. Does NOT change task status."""
        logger.info(
            "[conversation] Dispatching mention for task %s", task_id
        )
        await handle_all_mentions(
            bridge=self._bridge,
            task_id=task_id,
            content=content,
            task_title=task_title,
        )

    async def _dispatch_plan_chat(
        self, task_id: str, content: str, task_data: dict[str, Any]
    ) -> None:
        """Dispatch plan negotiation chat."""
        current_plan = (
            task_data.get("execution_plan")
            or task_data.get("executionPlan")
            or {}
        )
        task_status = task_data.get("status", "review")

        logger.info(
            "[conversation] Dispatching plan_chat for task %s (status=%s)",
            task_id,
            task_status,
        )
        await handle_plan_negotiation(
            self._bridge,
            task_id,
            content,
            current_plan,
            task_status=task_status,
        )
