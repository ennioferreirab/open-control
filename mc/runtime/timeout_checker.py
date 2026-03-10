"""
Timeout Detection and Escalation — periodic checker for stalled tasks and
timed-out reviews.

Implements FR39 (stalled task detection), FR40 (inter-agent timeout escalation),
and FR42 (per-task timeout override).

The checker runs on a configurable interval (default 60s) and:
- Flags in_progress tasks that exceed their timeout threshold
- Escalates review tasks with reviewers that exceed the inter-agent timeout
- Reads global timeout settings from the Convex settings table
- Respects per-task timeout overrides on the task document
- Tracks already-flagged tasks to avoid duplicate alerts
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from mc.types import ActivityEventType, AuthorType, MessageType

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

DEFAULT_TASK_TIMEOUT_MINUTES = 30
DEFAULT_INTER_AGENT_TIMEOUT_MINUTES = 10
CHECK_INTERVAL_SECONDS = 60


def _format_duration(td: timedelta) -> str:
    """Format a timedelta as a human-readable string."""
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


class TimeoutChecker:
    """Periodic checker for stalled tasks and timed-out reviews."""

    def __init__(
        self,
        bridge: ConvexBridge,
        sleep_controller: Any | None = None,
        *,
        check_interval_seconds: int = CHECK_INTERVAL_SECONDS,
    ) -> None:
        self._bridge = bridge
        self._sleep_controller = sleep_controller
        self._check_interval = check_interval_seconds
        self._flagged_stalled: set[str] = set()
        self._flagged_reviews: set[str] = set()

    async def start(self) -> None:
        """Periodically check for stalled tasks and timed-out reviews."""
        logger.info("[timeout] Timeout checker started")
        while True:
            try:
                found_work = await self.check_timeouts()
                if self._sleep_controller is not None:
                    if found_work:
                        await self._sleep_controller.record_work_found()
                    else:
                        await self._sleep_controller.record_idle()
            except Exception:
                logger.exception("[timeout] Timeout check failed")
            if self._sleep_controller is not None:
                await self._sleep_controller.wait_for_next_cycle(self._check_interval)
            else:
                await asyncio.sleep(self._check_interval)

    async def check_timeouts(self) -> bool:
        """Run a single timeout check cycle."""
        now = datetime.now(timezone.utc)
        found_work = False

        # Read global timeout settings
        task_timeout_minutes = await self._get_setting(
            "task_timeout_minutes", DEFAULT_TASK_TIMEOUT_MINUTES
        )
        inter_agent_timeout_minutes = await self._get_setting(
            "inter_agent_timeout_minutes", DEFAULT_INTER_AGENT_TIMEOUT_MINUTES
        )

        # Check in_progress tasks for stalling
        in_progress_tasks = await asyncio.to_thread(
            self._bridge.query, "tasks:listByStatus", {"status": "in_progress"}
        )
        for task in in_progress_tasks or []:
            found_work = await self._check_task_stall(task, now, task_timeout_minutes) or found_work

        # Check review tasks for inter-agent timeout
        review_tasks = await asyncio.to_thread(
            self._bridge.query, "tasks:listByStatus", {"status": "review"}
        )
        for task in review_tasks or []:
            found_work = (
                await self._check_review_timeout(task, now, inter_agent_timeout_minutes)
                or found_work
            )
        return found_work

    async def _get_setting(self, key: str, default: int) -> int:
        """Read a timeout setting from Convex, falling back to default."""
        try:
            value = await asyncio.to_thread(self._bridge.query, "settings:get", {"key": key})
            if value is not None:
                return int(value)
        except (ValueError, TypeError):
            logger.warning("[timeout] Invalid setting value for '%s', using default", key)
        return default

    async def _check_task_stall(
        self, task: dict[str, Any], now: datetime, global_timeout: int
    ) -> bool:
        """Check a single in_progress task for stalling."""
        task_id = task.get("id")
        if not task_id or task_id in self._flagged_stalled:
            return False

        # Per-task override > global default > hardcoded fallback
        timeout_minutes = task.get("task_timeout") or global_timeout
        updated_at_str = task.get("updated_at")
        if not updated_at_str:
            return False

        updated_at = datetime.fromisoformat(updated_at_str)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        elapsed = now - updated_at
        if elapsed > timedelta(minutes=timeout_minutes):
            await self._flag_stalled_task(task_id, task, elapsed)
            return True
        return False

    async def _flag_stalled_task(
        self, task_id: str, task: dict[str, Any], elapsed: timedelta
    ) -> None:
        """Flag a stalled task with an activity event and thread message."""
        title = task.get("title", "Untitled")
        duration = _format_duration(elapsed)

        self._flagged_stalled.add(task_id)
        logger.warning("[timeout] Task '%s' stalled -- in progress for %s", title, duration)

        # Mark task as stalled on the document
        await asyncio.to_thread(
            self._bridge.mutation,
            "tasks:markStalled",
            {"task_id": task_id, "stalled_at": datetime.now(timezone.utc).isoformat()},
        )

        # Activity event
        await asyncio.to_thread(
            self._bridge.create_activity,
            ActivityEventType.SYSTEM_ERROR,
            f"Task '{title}' stalled -- in progress for {duration}",
            task_id,
        )

        # Thread message
        await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            "System",
            AuthorType.SYSTEM,
            f"Task stalled. In progress for {duration}. Consider checking on the assigned agent.",
            MessageType.SYSTEM_EVENT,
        )

    async def _check_review_timeout(
        self, task: dict[str, Any], now: datetime, global_timeout: int
    ) -> bool:
        """Check a single review task for inter-agent timeout."""
        task_id = task.get("id")
        if not task_id or task_id in self._flagged_reviews:
            return False

        # Only check tasks with configured reviewers
        reviewers = task.get("reviewers")
        if not reviewers:
            return False

        # Per-task override > global default > hardcoded fallback
        timeout_minutes = task.get("inter_agent_timeout") or global_timeout
        updated_at_str = task.get("updated_at")
        if not updated_at_str:
            return False

        updated_at = datetime.fromisoformat(updated_at_str)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        elapsed = now - updated_at
        if elapsed > timedelta(minutes=timeout_minutes):
            await self._escalate_review(task_id, task, elapsed)
            return True
        return False

    async def _escalate_review(
        self, task_id: str, task: dict[str, Any], elapsed: timedelta
    ) -> None:
        """Escalate a timed-out review with an activity event and thread message."""
        title = task.get("title", "Untitled")
        duration = _format_duration(elapsed)

        self._flagged_reviews.add(task_id)
        logger.warning(
            "[timeout] Review for '%s' timed out after %s -- escalating", title, duration
        )

        # Activity event
        await asyncio.to_thread(
            self._bridge.create_activity,
            ActivityEventType.SYSTEM_ERROR,
            f"Review for '{title}' timed out -- escalating",
            task_id,
        )

        # Thread message
        await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            "System",
            AuthorType.SYSTEM,
            f"Review timed out after {duration}. Escalating to Lead Agent for re-routing.",
            MessageType.SYSTEM_EVENT,
        )
