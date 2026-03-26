"""
Timeout Detection — periodic checker for stalled tasks.

Implements FR39 (stalled task detection) and FR42 (per-task timeout override).

The checker runs on a configurable interval (default 60s) and:
- Flags in_progress tasks that exceed their timeout threshold
- Reads global timeout settings from the Convex settings table
- Respects per-task timeout overrides on the task document
- Tracks already-flagged tasks to avoid duplicate alerts
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from mc.bridge.runtime_claims import acquire_runtime_claim
from mc.types import ActivityEventType, AuthorType, MessageType

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

DEFAULT_TASK_TIMEOUT_MINUTES = 30
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
    """Periodic checker for stalled tasks."""

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

    async def start(self) -> None:
        """Periodically check for stalled tasks and timed-out reviews."""
        logger.info("[timeout] Timeout checker started")
        while True:
            try:
                if self._sleep_controller is None or self._sleep_controller.mode == "active":
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
        now = datetime.now(UTC)
        found_work = False

        task_timeout_minutes = await self._get_setting(
            "task_timeout_minutes", DEFAULT_TASK_TIMEOUT_MINUTES
        )

        in_progress_tasks = await asyncio.to_thread(
            self._bridge.query, "tasks:listByStatusLite", {"status": "in_progress"}
        )
        for task in in_progress_tasks or []:
            found_work = await self._check_task_stall(task, now, task_timeout_minutes) or found_work

        return found_work

    async def _get_setting(self, key: str, default: int) -> int:
        """Read a timeout setting from Convex, falling back to default.

        Uses the bridge's settings_cache if available for TTL-based caching.
        """
        try:
            from mc.bridge.settings_cache import SettingsCache

            settings_cache = getattr(self._bridge, "settings_cache", None)
            if isinstance(settings_cache, SettingsCache):
                value = await asyncio.to_thread(settings_cache.get, key)
            else:
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
            updated_at = updated_at.replace(tzinfo=UTC)

        elapsed = now - updated_at
        if elapsed > timedelta(minutes=timeout_minutes):
            claimed = await asyncio.to_thread(
                acquire_runtime_claim,
                self._bridge,
                claim_kind=f"timeout-stalled:{updated_at_str}",
                entity_type="task",
                entity_id=task_id,
                metadata={"status": task.get("status", "in_progress")},
                lease_seconds=self._check_interval * 2,
            )
            if not claimed:
                return False
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
            {"task_id": task_id, "stalled_at": datetime.now(UTC).isoformat()},
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
