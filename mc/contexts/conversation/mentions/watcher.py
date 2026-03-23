"""
Conversation-owned mention watcher for task-thread @mentions.

Subscribes to new user messages across ALL tasks regardless of status and
dispatches @mention handling when a message contains @agent-name patterns.
This is the single, authoritative handler for @mentions across all task
statuses (inbox, assigned, in_progress, review, done, crashed, retrying, etc.).

The PlanNegotiator skips @mention messages (leaving them for this watcher),
so there is no double-processing.

Story: "Mencionar agentes via @arroba em qualquer task"
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from mc.bridge.runtime_claims import acquire_runtime_claim

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

# Compatibility knob kept for configuration/tests. The live watcher now uses
# a reactive Convex subscription rather than timer-based polling.
POLL_INTERVAL_SECONDS = 10

# Max seen message IDs to keep in memory before pruning
_SEEN_IDS_MAX = 5000

# Bounded snapshot size for the mention watcher subscription feed.
_FEED_LIMIT = 50


def _log_task_exception(task: asyncio.Task) -> None:  # type: ignore[type-arg]
    """Callback to log exceptions from fire-and-forget asyncio tasks."""
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc is not None:
        logger.error("[mention_watcher] Background task failed: %s", exc, exc_info=exc)


class MentionWatcher:
    """Consumes the global user-message feed and dispatches @mention handling.

    The steady-state path is a native Convex subscription backed by a bounded
    watcher feed. A one-shot gap-fill query is used only when a full bounded
    snapshot indicates the subscription may have skipped older messages during
    reconnects or bursts. Deduplication is enforced via _seen_message_ids.

    When a ``conversation_service`` is provided (Story 20.2), @mention
    detections are routed through ConversationService.handle_message()
    for unified intent classification before dispatch.
    """

    def __init__(
        self,
        bridge: ConvexBridge,
        conversation_service: Any | None = None,
        sleep_controller: Any | None = None,
        *,
        poll_interval_seconds: int = POLL_INTERVAL_SECONDS,
    ) -> None:
        self._bridge = bridge
        self._conversation_service = conversation_service
        self._sleep_controller = sleep_controller
        self._poll_interval = poll_interval_seconds
        self._feed_limit = _FEED_LIMIT
        self._seen_message_ids: set[str] = set()
        self._startup_at = datetime.now(UTC)
        self._last_processed_at = self._startup_at

    async def run(self) -> None:
        """Main subscription loop: watch for @mentions in all task threads."""
        logger.info("[mention_watcher] MentionWatcher started")

        while True:
            try:
                queue = self._bridge.async_subscribe(
                    "messages:listRecentUserMessagesForWatcher",
                    {"limit": self._feed_limit},
                    sleep_controller=self._sleep_controller,
                )
                while True:
                    snapshot = await queue.get()
                    if snapshot is None:
                        continue
                    if isinstance(snapshot, dict) and snapshot.get("_error") is True:
                        logger.warning(
                            "[mention_watcher] Watcher feed subscription failed: %s",
                            snapshot.get("message", "unknown error"),
                        )
                        break
                    await self._process_feed_snapshot(snapshot)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[mention_watcher] Error in subscription loop")
                await asyncio.sleep(1)

    async def _poll_all_tasks(self) -> bool:
        """One-shot compatibility path for tests and manual gap fills."""
        messages = await asyncio.to_thread(
            self._bridge.get_recent_user_messages,
            self._last_processed_at.isoformat(),
        )
        return await self._process_messages(messages)

    async def _process_feed_snapshot(self, snapshot: object) -> bool:
        """Process one bounded subscription snapshot, filling gaps when needed."""
        if not isinstance(snapshot, list):
            return False

        messages = [msg for msg in snapshot if isinstance(msg, dict)]
        if not messages:
            return False

        if self._needs_gap_fill(messages):
            gap_messages = await asyncio.to_thread(
                self._bridge.get_recent_user_messages,
                self._last_processed_at.isoformat(),
                limit=self._feed_limit,
            )
            await self._process_messages(gap_messages)

        return await self._process_messages(messages)

    async def _process_messages(self, messages: list[dict[str, Any]]) -> bool:
        """Process message docs in ascending order and dispatch @mentions."""
        if not messages:
            return False
        found_work = False
        latest_seen_at = self._last_processed_at

        for msg in messages:
            msg_timestamp = _parse_iso(msg.get("timestamp"))
            if msg_timestamp is not None and msg_timestamp < self._startup_at:
                continue

            msg_id = msg.get("_id") or msg.get("id") or ""
            if not msg_id or msg_id in self._seen_message_ids:
                if msg_timestamp is not None and msg_timestamp > latest_seen_at:
                    latest_seen_at = msg_timestamp
                continue
            claimed = await asyncio.to_thread(
                acquire_runtime_claim,
                self._bridge,
                claim_kind="mention-message",
                entity_type="message",
                entity_id=msg_id,
                metadata={"messageType": "user_message"},
            )
            if not claimed:
                logger.debug("[mention_watcher] Claim denied for message %s", msg_id)
                if msg_timestamp is not None and msg_timestamp > latest_seen_at:
                    latest_seen_at = msg_timestamp
                continue
            self._seen_message_ids.add(msg_id)
            if msg_timestamp is not None and msg_timestamp > latest_seen_at:
                latest_seen_at = msg_timestamp

            content = msg.get("content", "")
            if not content.strip():
                continue

            from mc.contexts.conversation.mentions.handler import (
                handle_all_mentions,
                is_mention_message,
            )

            if not is_mention_message(content):
                continue

            task_id = msg.get("task_id")
            if not task_id:
                continue

            logger.info(
                "[mention_watcher] @mention detected in task %s: %r",
                task_id,
                content[:80],
            )
            found_work = True

            task_data: dict[str, Any] = {}
            try:
                task_data = (
                    await asyncio.to_thread(
                        self._bridge.query,
                        "tasks:getById",
                        {"task_id": task_id},
                    )
                    or {}
                )
            except Exception:
                logger.debug("[mention_watcher] Could not fetch task %s", task_id)

            task_title = task_data.get("title", "")

            if self._conversation_service is not None:
                bg_task = asyncio.create_task(
                    self._conversation_service.handle_message(
                        task_id=task_id,
                        content=content,
                        task_data=task_data,
                    )
                )
            else:
                bg_task = asyncio.create_task(
                    handle_all_mentions(
                        bridge=self._bridge,
                        task_id=task_id,
                        content=content,
                        task_title=task_title,
                    )
                )
            bg_task.add_done_callback(_log_task_exception)

        if len(self._seen_message_ids) > _SEEN_IDS_MAX:
            current_ids = {
                msg.get("_id") or msg.get("id") or ""
                for msg in messages
                if msg.get("_id") or msg.get("id")
            }
            self._seen_message_ids = current_ids
        self._last_processed_at = latest_seen_at
        return found_work

    def _needs_gap_fill(self, messages: list[dict[str, Any]]) -> bool:
        """Detect when a bounded snapshot may have skipped older unseen messages."""
        if len(messages) < self._feed_limit:
            return False
        oldest_timestamp = _parse_iso(messages[0].get("timestamp"))
        if oldest_timestamp is None:
            return False
        return oldest_timestamp > self._last_processed_at


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def _parse_iso(value: object) -> datetime | None:
    """Parse an ISO 8601 timestamp, accepting both Z and offset variants."""
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
