"""
Mention Watcher — global @mention detection loop for all task threads.

Polls for new user messages across ALL tasks regardless of status and dispatches
@mention handling when a message contains @agent-name patterns. This is the
single, authoritative handler for @mentions across all task statuses (inbox,
assigned, in_progress, review, done, crashed, retrying, etc.).

The PlanNegotiator skips @mention messages (leaving them for this watcher),
so there is no double-processing.

Story: "Mencionar agentes via @arroba em qualquer task"
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

# How often to poll for new messages (seconds)
POLL_INTERVAL_SECONDS = 10

# Max seen message IDs to keep in memory before pruning
_SEEN_IDS_MAX = 5000

# Overlap window to handle clock drift between Python and Convex (seconds)
_OVERLAP_SECONDS = 30


def _log_task_exception(task: asyncio.Task) -> None:  # type: ignore[type-arg]
    """Callback to log exceptions from fire-and-forget asyncio tasks."""
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc is not None:
        logger.error(
            "[mention_watcher] Background task failed: %s", exc, exc_info=exc
        )


class MentionWatcher:
    """Polls all user messages globally and dispatches @mention handling.

    Uses a single query (messages:listRecentUserMessages) per cycle instead
    of polling per-status + per-task. Deduplicates via _seen_message_ids.

    When a ``conversation_service`` is provided (Story 20.2), @mention
    detections are routed through ConversationService.handle_message()
    for unified intent classification before dispatch.
    """

    def __init__(
        self,
        bridge: "ConvexBridge",
        conversation_service: Any | None = None,
    ) -> None:
        self._bridge = bridge
        self._conversation_service = conversation_service
        self._seen_message_ids: set[str] = set()
        self._startup_timestamp: str = _now_iso()
        self._last_poll_timestamp: str | None = None

    async def run(self) -> None:
        """Main polling loop: watch for @mentions in all task threads."""
        logger.info("[mention_watcher] MentionWatcher started")

        while True:
            try:
                await self._poll_all_tasks()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[mention_watcher] Error in polling loop")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _poll_all_tasks(self) -> None:
        """Poll recent user messages globally and check for @mentions."""
        if self._last_poll_timestamp:
            base = datetime.fromisoformat(self._last_poll_timestamp)
            since = (base - timedelta(seconds=_OVERLAP_SECONDS)).isoformat()
        else:
            since = self._startup_timestamp

        self._last_poll_timestamp = _now_iso()

        messages = await asyncio.to_thread(
            self._bridge.get_recent_user_messages,
            since,
        )

        if not messages:
            return

        for msg in messages:
            msg_id = msg.get("_id") or msg.get("id") or ""
            if not msg_id or msg_id in self._seen_message_ids:
                continue
            self._seen_message_ids.add(msg_id)

            content = msg.get("content", "")
            if not content.strip():
                continue

            from mc.mentions.handler import handle_all_mentions, is_mention_message

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

            task_data: dict[str, Any] = {}
            try:
                task_data = await asyncio.to_thread(
                    self._bridge.query,
                    "tasks:getById",
                    {"task_id": task_id},
                ) or {}
            except Exception:
                logger.debug(
                    "[mention_watcher] Could not fetch task %s", task_id
                )

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


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()
