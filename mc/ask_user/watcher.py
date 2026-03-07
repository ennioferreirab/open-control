"""AskUserReplyWatcher — polls task threads for user replies to pending ask_user calls.

Runs as an asyncio loop in the gateway. Checks tasks with active ask_user calls
(via AskUserRegistry) and delivers user replies to the waiting AskUserHandler.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mc.ask_user.registry import AskUserRegistry
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 1.5


class AskUserReplyWatcher:
    """Watches task threads for user replies to ask_user questions.

    Only polls tasks that have an active pending ask_user (via registry).
    Delivers the first unseen user message as the reply.

    When a ``conversation_service`` is provided (Story 20.2), incoming
    user replies are routed through ConversationService for unified
    intent classification before delivery.
    """

    def __init__(
        self,
        bridge: ConvexBridge,
        registry: AskUserRegistry,
        conversation_service: Any | None = None,
    ) -> None:
        self._bridge = bridge
        self._registry = registry
        self._conversation_service = conversation_service
        self._seen_messages: dict[str, set[str]] = {}

    async def run(self) -> None:
        """Main polling loop."""
        logger.info("[ask_user_watcher] AskUserReplyWatcher started")
        while True:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[ask_user_watcher] Error in polling loop")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _poll_once(self) -> None:
        """Check all tasks with pending ask_user calls for new user messages."""
        active_task_ids = self._registry.active_task_ids()
        if not active_task_ids:
            return

        for task_id in active_task_ids:
            if not self._registry.has_pending_ask(task_id):
                continue

            try:
                messages = await asyncio.to_thread(
                    self._bridge.get_task_messages, task_id
                )
            except Exception:
                logger.debug(
                    "[ask_user_watcher] Could not fetch messages for task %s", task_id
                )
                continue

            if not messages:
                if task_id not in self._seen_messages:
                    self._seen_messages[task_id] = set()
                continue

            if task_id not in self._seen_messages:
                self._seen_messages[task_id] = {
                    m.get("_id") or m.get("id") or ""
                    for m in messages
                    if m.get("_id") or m.get("id")
                }
                continue

            seen = self._seen_messages[task_id]

            for msg in messages:
                msg_id = msg.get("_id") or msg.get("id") or ""
                if not msg_id or msg_id in seen:
                    continue
                seen.add(msg_id)

                author_type = msg.get("author_type") or msg.get("authorType") or ""
                if author_type != "user":
                    continue

                content = (msg.get("content") or "").strip()
                if not content:
                    continue

                # When ConversationService is available (Story 20.2), classify
                # the message to confirm it's a manual_reply (not an @mention
                # that should be routed differently).
                if self._conversation_service is not None:
                    try:
                        task_data = await asyncio.to_thread(
                            self._bridge.get_task, task_id
                        )
                        if task_data is None:
                            task_data = {}
                        result = self._conversation_service.classify(
                            content, task_data, task_id=task_id
                        )
                        from mc.services.conversation_intent import (
                            ConversationIntent,
                        )
                        if result.intent == ConversationIntent.MENTION:
                            # @mention takes priority — skip delivery, let
                            # MentionWatcher handle it.
                            logger.debug(
                                "[ask_user_watcher] Skipping reply for task %s "
                                "— classified as mention",
                                task_id,
                            )
                            continue
                    except Exception:
                        logger.debug(
                            "[ask_user_watcher] Classification failed for "
                            "task %s — falling back to direct delivery",
                            task_id,
                        )

                delivered = self._registry.deliver_reply(task_id, content)
                if delivered:
                    logger.info(
                        "[ask_user_watcher] Delivered user reply for task %s: %r",
                        task_id,
                        content[:80],
                    )
                    break

        stale_ids = set(self._seen_messages) - set(self._registry._handlers)
        for tid in stale_ids:
            del self._seen_messages[tid]
