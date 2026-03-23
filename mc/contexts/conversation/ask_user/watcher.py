"""AskUserReplyWatcher — watches bounded task-message feeds for ask_user replies."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import TYPE_CHECKING, Any

from mc.bridge.runtime_claims import acquire_runtime_claim

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge
    from mc.contexts.conversation.ask_user.registry import AskUserRegistry

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 1.5
_FEED_LIMIT = 50
_SNAPSHOT_BACKLOG = 4


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
        self._feed_limit = _FEED_LIMIT
        self._subscription_tasks: dict[str, asyncio.Task[None]] = {}
        self._pending_snapshots: dict[str, deque[object]] = {}
        self._snapshot_event = asyncio.Event()

    async def run(self) -> None:
        logger.info("[ask_user_watcher] AskUserReplyWatcher started")
        version = self._registry.change_version
        await self._reconcile_subscriptions()
        while True:
            try:
                if not self._subscription_tasks:
                    version = await self._registry.wait_for_change(version)
                    await self._reconcile_subscriptions()
                    continue

                wait_for_change = asyncio.create_task(self._registry.wait_for_change(version))
                wait_for_snapshot = asyncio.create_task(self._snapshot_event.wait())
                done, pending = await asyncio.wait(
                    {wait_for_change, wait_for_snapshot},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()

                if wait_for_change in done:
                    version = wait_for_change.result()
                    await self._reconcile_subscriptions()
                    continue

                self._snapshot_event.clear()
                snapshots: list[tuple[str, object]] = []
                for task_id, pending in self._pending_snapshots.items():
                    while pending:
                        snapshots.append((task_id, pending.popleft()))
                found_work = False
                for task_id, snapshot in snapshots:
                    if isinstance(snapshot, dict) and snapshot.get("_error") is True:
                        logger.warning(
                            "[ask_user_watcher] Subscription failed for task %s: %s",
                            task_id,
                            snapshot.get("message", "unknown error"),
                        )
                        await self._restart_subscription(task_id)
                        continue
                    found_work = await self._process_task_snapshot(task_id, snapshot) or found_work
                if self._sleep_controller is not None:
                    if found_work:
                        await self._sleep_controller.record_work_found()
                    else:
                        await self._sleep_controller.record_idle()
            except asyncio.CancelledError:
                for task in self._subscription_tasks.values():
                    task.cancel()
                raise
            except Exception:
                logger.exception("[ask_user_watcher] Error in subscription loop")
                await asyncio.sleep(1)

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

    async def _reconcile_subscriptions(self) -> None:
        active_task_ids = self._registry.active_task_ids()
        stale_task_ids = set(self._subscription_tasks) - active_task_ids

        for task_id in stale_task_ids:
            task = self._subscription_tasks.pop(task_id)
            task.cancel()
            self._seen_messages.pop(task_id, None)
            self._pending_snapshots.pop(task_id, None)

        for task_id in active_task_ids:
            if task_id not in self._subscription_tasks:
                self._subscription_tasks[task_id] = asyncio.create_task(
                    self._consume_task_subscription(task_id)
                )

    async def _restart_subscription(self, task_id: str) -> None:
        current = self._subscription_tasks.pop(task_id, None)
        if current is not None:
            current.cancel()
        if self._registry.has_pending_ask(task_id):
            self._subscription_tasks[task_id] = asyncio.create_task(
                self._consume_task_subscription(task_id)
            )

    async def _consume_task_subscription(self, task_id: str) -> None:
        queue = self._bridge.async_subscribe(
            "messages:listRecentByTaskForAskUser",
            {"task_id": task_id, "limit": self._feed_limit},
        )
        while True:
            snapshot = await queue.get()
            pending = self._pending_snapshots.setdefault(task_id, deque(maxlen=_SNAPSHOT_BACKLOG))
            pending.append(snapshot)
            self._snapshot_event.set()

    async def _process_task_snapshot(self, task_id: str, snapshot: object) -> bool:
        if not isinstance(snapshot, list):
            return False
        messages = [msg for msg in snapshot if isinstance(msg, dict)]
        if not messages:
            self._seen_messages.setdefault(task_id, set())
            return False
        if task_id not in self._seen_messages:
            self._seen_messages[task_id] = {
                msg.get("_id") or msg.get("id") or ""
                for msg in messages
                if msg.get("_id") or msg.get("id")
            }
            return False

        seen = self._seen_messages[task_id]
        return await self._deliver_new_user_replies(task_id, messages, seen)

    async def _deliver_new_user_replies(
        self,
        task_id: str,
        messages: list[dict[str, Any]],
        seen: set[str],
    ) -> bool:
        delivered_any = False

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

        return delivered_any
