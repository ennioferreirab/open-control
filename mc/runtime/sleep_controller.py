"""Gateway-wide runtime sleep state and polling coordination."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

GatewaySleepMode = Literal["sleep", "active"]
GatewaySleepReason = Literal["startup", "idle", "manual", "work_found"]

RUNTIME_SETTINGS_KEY = "gateway_sleep_runtime"
CONTROL_SETTINGS_KEY = "gateway_sleep_control"
ACTIVE_POLL_INTERVAL_SECONDS = 5
SLEEP_POLL_INTERVAL_SECONDS = 300
AUTO_SLEEP_AFTER_SECONDS = 300
CONTROL_POLL_INTERVAL_SECONDS = 1


class RuntimeSleepController:
    """Central sleep/wake controller shared across gateway pollers."""

    def __init__(
        self,
        bridge: ConvexBridge,
        *,
        time_fn: Callable[[], float] = time.monotonic,
        sleep_poll_interval_seconds: int = SLEEP_POLL_INTERVAL_SECONDS,
        active_poll_interval_seconds: int = ACTIVE_POLL_INTERVAL_SECONDS,
        auto_sleep_after_seconds: int = AUTO_SLEEP_AFTER_SECONDS,
    ) -> None:
        self._bridge = bridge
        self._time_fn = time_fn
        self._sleep_poll_interval_seconds = sleep_poll_interval_seconds
        self._active_poll_interval_seconds = active_poll_interval_seconds
        self._auto_sleep_after_seconds = auto_sleep_after_seconds
        self._mode: GatewaySleepMode = "active"
        self._manual_requested = False
        self._reason: GatewaySleepReason = "startup"
        self._last_transition_at = self._utc_now()
        self._last_work_found_at: str | None = None
        self._last_actionable_at = self._time_fn()
        self._state_event: asyncio.Event = asyncio.Event()
        self._last_control_signature: tuple[str, str] | None = None
        self._lock = asyncio.Lock()

    @property
    def mode(self) -> GatewaySleepMode:
        return self._mode

    @property
    def manual_requested(self) -> bool:
        return self._manual_requested

    def current_poll_interval(self, active_interval_seconds: float) -> float:
        if self._mode == "sleep":
            return float(self._sleep_poll_interval_seconds)
        return float(active_interval_seconds)

    async def initialize(self) -> None:
        await self._persist_runtime(force=True)

    async def record_idle(self) -> None:
        async with self._lock:
            if self._mode != "active":
                return
            idle_seconds = self._time_fn() - self._last_actionable_at
            if idle_seconds < self._auto_sleep_after_seconds:
                return
            await self._transition_locked("sleep", reason="idle", manual_requested=False)

    async def record_work_found(self) -> None:
        async with self._lock:
            self._last_actionable_at = self._time_fn()
            self._last_work_found_at = self._utc_now()
            await self._transition_locked("active", reason="work_found", manual_requested=False)

    async def apply_manual_mode(self, mode: GatewaySleepMode) -> None:
        async with self._lock:
            manual_requested = mode == "sleep"
            if mode == "active":
                self._last_actionable_at = self._time_fn()
            await self._transition_locked(mode, reason="manual", manual_requested=manual_requested)

    async def wait_for_next_cycle(self, active_interval_seconds: float) -> None:
        while True:
            event = self._state_event
            delay = self.current_poll_interval(active_interval_seconds)
            try:
                await asyncio.wait_for(event.wait(), timeout=delay)
            except TimeoutError:
                return
            if self._mode == "active":
                return

    async def poll_control_once(self) -> None:
        raw = await asyncio.to_thread(
            self._bridge.query,
            "settings:getGatewaySleepControl",
            {},
        )
        if not raw:
            return

        mode = raw.get("mode")
        requested_at = raw.get("requestedAt") or raw.get("requested_at")
        if mode not in {"sleep", "active"} or not requested_at:
            return

        signature = (mode, requested_at)
        if signature == self._last_control_signature:
            return

        self._last_control_signature = signature
        await self.apply_manual_mode(mode)

    async def watch_control(self) -> None:
        while True:
            try:
                await self.poll_control_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.debug("[sleep] Control poll failed", exc_info=True)
            await asyncio.sleep(CONTROL_POLL_INTERVAL_SECONDS)

    def runtime_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "mode": self._mode,
            "pollIntervalSeconds": (
                self._sleep_poll_interval_seconds
                if self._mode == "sleep"
                else self._active_poll_interval_seconds
            ),
            "configuredAutoSleepAfterSeconds": self._auto_sleep_after_seconds,
            "manualRequested": self._manual_requested,
            "reason": self._reason,
            "lastTransitionAt": self._last_transition_at,
        }
        if self._last_work_found_at is not None:
            payload["lastWorkFoundAt"] = self._last_work_found_at
        return payload

    async def _transition_locked(
        self,
        mode: GatewaySleepMode,
        *,
        reason: GatewaySleepReason,
        manual_requested: bool,
    ) -> None:
        should_notify = self._mode != mode
        should_persist = (
            should_notify or self._manual_requested != manual_requested or self._reason != reason
        )
        prev_mode = self._mode
        self._mode = mode
        self._manual_requested = manual_requested
        self._reason = reason
        if should_persist:
            self._last_transition_at = self._utc_now()
            await self._persist_runtime(force=True)
        if should_notify:
            logger.info(
                "[sleep] %s → %s (reason=%s, manual=%s)",
                prev_mode,
                mode,
                reason,
                manual_requested,
            )
            old_event = self._state_event
            self._state_event = asyncio.Event()
            old_event.set()

    async def _persist_runtime(self, *, force: bool = False) -> None:
        payload = self.runtime_payload()
        await asyncio.to_thread(
            self._bridge.mutation,
            "settings:set",
            {
                "key": RUNTIME_SETTINGS_KEY,
                "value": json.dumps(payload),
            },
        )

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(UTC).isoformat()
