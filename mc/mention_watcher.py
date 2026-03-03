"""
Mention Watcher — global @mention detection loop for all task threads.

Polls for new user messages across all tasks and dispatches @mention handling
when a message contains @agent-name patterns. Works independently of the
plan_negotiation_loop so mentions work in tasks of any status (done, crashed,
in_progress, review, etc.).

The plan_negotiator already handles @mentions for tasks in review/in_progress
(to avoid double-processing). This watcher covers all other task statuses.

Story: "Mencionar agentes via @arroba em qualquer task"
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

# How often to poll for new messages (seconds)
POLL_INTERVAL_SECONDS = 3

# Statuses handled by plan_negotiator (mentions already covered there)
_NEGOTIATION_STATUSES = frozenset({"review", "in_progress"})

# Max seen message IDs to keep in memory before pruning
_SEEN_IDS_MAX = 5000


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
    """Polls all task messages and dispatches @mention handling.

    Subscribes to a global recent-messages feed (or polls per-task) to
    detect @mentions in user messages and invoke the mention_handler.

    Design notes:
    - Uses a single global poll of recent messages (tasks:listRecentUserMessages
      or a similar query) to avoid per-task subscriptions.
    - Falls back to polling tasks:listByStatus for all active tasks if no
      global messages query is available.
    - Deduplicates via seen_message_ids to avoid double-processing.
    - Skips tasks in review/in_progress because the plan_negotiator already
      handles @mentions for those.
    """

    def __init__(self, bridge: "ConvexBridge") -> None:
        self._bridge = bridge
        self._seen_message_ids: set[str] = set()
        # Track tasks whose messages we've subscribed to
        self._watched_task_ids: set[str] = set()
        # Per-task seen message IDs (for tasks we watch directly)
        self._per_task_seen: dict[str, set[str]] = {}

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
        """Poll all tasks and check their messages for @mentions."""
        # Fetch all tasks (we need to check messages across all statuses)
        # We use a broad query to get tasks that could have user messages
        all_tasks: list[dict[str, Any]] = []

        for status in ("done", "crashed", "review", "in_progress", "inbox", "assigned", "retrying"):
            try:
                tasks = await asyncio.to_thread(
                    self._bridge.query,
                    "tasks:listByStatus",
                    {"status": status},
                )
                if isinstance(tasks, list):
                    all_tasks.extend(tasks)
            except Exception:
                logger.debug(
                    "[mention_watcher] Could not fetch tasks with status=%s", status
                )

        for task_data in all_tasks:
            task_id = task_data.get("id")
            task_status = task_data.get("status", "")
            task_title = task_data.get("title", "")

            if not task_id:
                continue

            # Skip tasks in statuses already handled by plan_negotiator
            # (review with awaitingKickoff and in_progress)
            # We still process review tasks WITHOUT awaitingKickoff and
            # in_progress tasks to catch @mentions the plan_negotiator
            # might skip (non-negotiable messages).
            # Actually, plan_negotiator handles ALL user messages for
            # in_progress and review(awaitingKickoff) — including @mentions.
            # So we skip those to avoid double-processing.
            awaiting_kickoff = task_data.get("awaiting_kickoff", False)
            if task_status == "in_progress":
                continue  # plan_negotiator handles this
            if task_status == "review" and awaiting_kickoff:
                continue  # plan_negotiator handles this

            # Fetch messages for this task
            try:
                messages = await asyncio.to_thread(
                    self._bridge.get_task_messages, task_id
                )
            except Exception:
                logger.debug(
                    "[mention_watcher] Could not fetch messages for task %s", task_id
                )
                continue

            if not messages:
                continue

            # Initialize per-task seen set
            if task_id not in self._per_task_seen:
                # On first encounter, mark all existing messages as seen
                # to avoid re-processing old messages on startup
                self._per_task_seen[task_id] = {
                    m.get("_id") or m.get("id") or ""
                    for m in messages
                    if m.get("_id") or m.get("id")
                }
                continue

            seen = self._per_task_seen[task_id]

            for msg in messages:
                msg_id = msg.get("_id") or msg.get("id") or ""
                author_type = msg.get("author_type") or msg.get("authorType") or ""

                if msg_id in seen:
                    continue
                seen.add(msg_id)

                # Only process user messages
                if author_type != "user":
                    continue

                content = msg.get("content", "")
                if not content.strip():
                    continue

                # Check for @mentions
                from mc.mention_handler import is_mention_message, handle_all_mentions

                if not is_mention_message(content):
                    continue

                logger.info(
                    "[mention_watcher] @mention detected in task %s (status=%s): %r",
                    task_id,
                    task_status,
                    content[:80],
                )

                # Dispatch mention handling as a background task
                bg_task = asyncio.create_task(
                    handle_all_mentions(
                        bridge=self._bridge,
                        task_id=task_id,
                        content=content,
                        task_title=task_title,
                    )
                )
                bg_task.add_done_callback(_log_task_exception)

            # Prune seen IDs if too large
            if len(seen) > _SEEN_IDS_MAX:
                # Rebuild from current message batch
                self._per_task_seen[task_id] = {
                    m.get("_id") or m.get("id") or ""
                    for m in messages
                    if m.get("_id") or m.get("id")
                }
