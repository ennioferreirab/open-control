"""AskUserReplyWatcher — polls task threads for user replies to pending ask_user calls."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from mc.bridge.runtime_claims import acquire_runtime_claim

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge
    from mc.contexts.conversation.ask_user.registry import AskUserRegistry

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 1.5


class AskUserReplyWatcher:
    """Watch task threads for user replies to ask_user questions."""

    def __init__(
        self,
        bridge: ConvexBridge,
        registry: AskUserRegistry,
        conversation_service: Any | None = None,
        sleep_controller: Any | None = None,
    ) -> None:
        self._bridge = bridge
        self._registry = registry
        self._conversation_service = conversation_service
        self._sleep_controller = sleep_controller
        self._seen_messages: dict[str, set[str]] = {}

    async def run(self) -> None:
        logger.info("[ask_user_watcher] AskUserReplyWatcher started")
        while True:
            try:
                if self._sleep_controller is not None and self._sleep_controller.mode == "sleep":
                    await self._sleep_controller.wait_for_next_cycle(POLL_INTERVAL_SECONDS)
                found_work = await self._poll_once()
                if self._sleep_controller is not None:
                    if found_work:
                        await self._sleep_controller.record_work_found()
                    else:
                        await self._sleep_controller.record_idle()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[ask_user_watcher] Error in polling loop")
            if self._sleep_controller is not None:
                await self._sleep_controller.wait_for_next_cycle(POLL_INTERVAL_SECONDS)
            else:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _poll_once(self) -> bool:
        active_task_ids = self._registry.active_task_ids()
        if not active_task_ids:
            return False

        delivered_any = False

        for task_id in active_task_ids:
            if not self._registry.has_pending_ask(task_id):
                continue

            try:
                messages = await asyncio.to_thread(self._bridge.get_task_messages, task_id)
            except Exception:
                logger.debug("[ask_user_watcher] Could not fetch messages for task %s", task_id)
                continue

            if not messages:
                if task_id not in self._seen_messages:
                    self._seen_messages[task_id] = set()
                continue

            if task_id not in self._seen_messages:
                self._seen_messages[task_id] = {
                    msg.get("_id") or msg.get("id") or ""
                    for msg in messages
                    if msg.get("_id") or msg.get("id")
                }
                continue

            seen = self._seen_messages[task_id]

            for msg in messages:
                msg_id = msg.get("_id") or msg.get("id") or ""
                if not msg_id or msg_id in seen:
                    continue

                author_type = msg.get("author_type") or msg.get("authorType") or ""
                if author_type != "user":
                    seen.add(msg_id)
                    continue

                content = (msg.get("content") or "").strip()
                if not content:
                    seen.add(msg_id)
                    continue

                claimed = await asyncio.to_thread(
                    acquire_runtime_claim,
                    self._bridge,
                    claim_kind="ask-user-reply",
                    entity_type="message",
                    entity_id=msg_id,
                    metadata={"taskId": task_id},
                )
                if not claimed:
                    continue
                seen.add(msg_id)

                if self._conversation_service is not None:
                    try:
                        task_data = await asyncio.to_thread(self._bridge.get_task, task_id)
                        if task_data is None:
                            task_data = {}
                        result = self._conversation_service.classify(
                            content, task_data, task_id=task_id
                        )
                        from mc.contexts.conversation.intent import ConversationIntent

                        if result.intent == ConversationIntent.MENTION:
                            logger.debug(
                                "[ask_user_watcher] Skipping reply for task %s -- classified as mention",
                                task_id,
                            )
                            continue
                    except Exception:
                        logger.debug(
                            "[ask_user_watcher] Classification failed for task %s -- falling back to direct delivery",
                            task_id,
                        )

                delivered = self._registry.deliver_reply(task_id, content)
                if delivered:
                    delivered_any = True
                    logger.info(
                        "[ask_user_watcher] Delivered user reply for task %s: %r",
                        task_id,
                        content[:80],
                    )
                    break

        stale_ids = set(self._seen_messages) - set(self._registry._handlers)
        for task_id in stale_ids:
            del self._seen_messages[task_id]
        return delivered_any
