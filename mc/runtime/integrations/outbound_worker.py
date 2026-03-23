"""Outbound sync worker — polls MC events and syncs to external platforms."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge
    from mc.contexts.integrations.pipeline.outbound import OutboundPipeline
    from mc.runtime.sleep_controller import RuntimeSleepController

logger = logging.getLogger(__name__)
OUTBOUND_FEED_LIMIT = 50
PUBLISHED_IDS_MAX = 5000
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class IntegrationOutboundWorker:
    """Subscribes to outbound-ready MC events and syncs them outward."""

    def __init__(
        self,
        bridge: ConvexBridge,
        outbound_pipeline: OutboundPipeline,
        sleep_controller: RuntimeSleepController | None = None,
        poll_interval_seconds: float = 10.0,
    ) -> None:
        self._bridge = bridge
        self._pipeline = outbound_pipeline
        self._sleep_controller = sleep_controller
        self._poll_interval = poll_interval_seconds
        self._feed_limit = OUTBOUND_FEED_LIMIT
        self._config_tasks: dict[str, asyncio.Task[None]] = {}
        self._published_message_ids: dict[str, dict[str, None]] = {}
        self._published_activity_ids: dict[str, dict[str, None]] = {}
        self._last_processed_at: dict[str, datetime] = {}

    async def run(self) -> None:
        """Main subscription loop."""
        logger.info("[integration-outbound] Worker started (interval=%.1fs)", self._poll_interval)
        while True:
            try:
                queue = self._bridge.async_subscribe("integrations:getEnabledConfigs", {})
                while True:
                    snapshot = await queue.get()
                    if snapshot is None:
                        continue
                    if isinstance(snapshot, dict) and snapshot.get("_error") is True:
                        logger.warning(
                            "[integration-outbound] Config subscription failed: %s",
                            snapshot.get("message", "unknown error"),
                        )
                        break
                    await self._reconcile_config_subscriptions(
                        snapshot if isinstance(snapshot, list) else []
                    )
            except asyncio.CancelledError:
                logger.info("[integration-outbound] Worker cancelled")
                for task in self._config_tasks.values():
                    task.cancel()
                raise
            except Exception:
                logger.exception("[integration-outbound] Subscription loop error")
                await asyncio.sleep(1)

    async def _reconcile_config_subscriptions(self, configs: list[dict[str, Any]]) -> None:
        enabled_ids = {
            str(config.get("id", ""))
            for config in configs
            if config.get("enabled") and str(config.get("id", "")).strip()
        }

        stale_ids = set(self._config_tasks) - enabled_ids
        for config_id in stale_ids:
            task = self._config_tasks.pop(config_id)
            task.cancel()
            self._published_message_ids.pop(config_id, None)
            self._published_activity_ids.pop(config_id, None)
            self._last_processed_at.pop(config_id, None)

        for config_id in enabled_ids:
            if config_id not in self._config_tasks:
                self._last_processed_at.setdefault(config_id, _EPOCH)
                self._config_tasks[config_id] = asyncio.create_task(
                    self._run_config_subscription(config_id)
                )

    async def _run_config_subscription(self, config_id: str) -> None:
        while True:
            try:
                queue = self._bridge.async_subscribe(
                    "integrations:listRecentOutboundPendingByConfig",
                    {"config_id": config_id, "limit": self._feed_limit},
                )
                while True:
                    snapshot = await queue.get()
                    if snapshot is None:
                        continue
                    if isinstance(snapshot, dict) and snapshot.get("_error") is True:
                        logger.warning(
                            "[integration-outbound] Outbound feed failed for %s: %s",
                            config_id,
                            snapshot.get("message", "unknown error"),
                        )
                        break
                    found_work = await self._process_config_snapshot(config_id, snapshot)
                    if self._sleep_controller is not None:
                        if found_work:
                            await self._sleep_controller.record_work_found()
                        else:
                            await self._sleep_controller.record_idle()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "[integration-outbound] Error processing subscription for config %s",
                    config_id,
                )
            await asyncio.sleep(1)

    async def _process_config_snapshot(self, config_id: str, snapshot: object) -> bool:
        if not isinstance(snapshot, dict):
            return False

        found_work = False
        if snapshot.get("message_window_full") or snapshot.get("activity_window_full"):
            gap_pending = self._bridge.get_outbound_pending(
                config_id,
                self._last_processed_at.setdefault(config_id, _EPOCH).isoformat(),
            )
            found_work = await self._publish_pending_items(config_id, gap_pending) or found_work

        snapshot_pending = {
            "messages": snapshot.get("messages", []),
            "activities": snapshot.get("activities", []),
        }
        return await self._publish_pending_items(config_id, snapshot_pending) or found_work

    async def _publish_pending_items(
        self,
        config_id: str,
        pending: dict[str, list[dict[str, Any]]],
    ) -> bool:
        found_work = False

        for item in pending.get("messages", []):
            message_id = self._extract_nested_id(item, "message")
            if not message_id or self._was_published(config_id, "message", message_id):
                continue
            result = await self._pipeline.publish_message_item(config_id, item)
            if result == "failed":
                continue
            self._remember_published(config_id, "message", message_id)
            self._update_watermark(config_id, {"messages": [item], "activities": []})
            found_work = found_work or result == "published"

        for item in pending.get("activities", []):
            activity_id = self._extract_nested_id(item, "activity")
            if not activity_id or self._was_published(config_id, "activity", activity_id):
                continue
            result = await self._pipeline.publish_activity_item(config_id, item)
            if result == "failed":
                continue
            self._remember_published(config_id, "activity", activity_id)
            self._update_watermark(config_id, {"messages": [], "activities": [item]})
            found_work = found_work or result == "published"

        return found_work

    def _extract_nested_id(self, item: dict[str, Any], field: str) -> str:
        nested = item.get(field, {})
        return str(nested.get("id") or nested.get("_id") or "")

    def _was_published(self, config_id: str, kind: str, item_id: str) -> bool:
        store = self._published_store(config_id, kind)
        return item_id in store

    def _remember_published(self, config_id: str, kind: str, item_id: str) -> None:
        store = self._published_store(config_id, kind)
        store[item_id] = None
        while len(store) > PUBLISHED_IDS_MAX:
            store.pop(next(iter(store)))

    def _published_store(self, config_id: str, kind: str) -> dict[str, None]:
        if kind == "message":
            return self._published_message_ids.setdefault(config_id, {})
        return self._published_activity_ids.setdefault(config_id, {})

    def _filter_unseen_pending(
        self,
        config_id: str,
        pending: dict[str, list[dict[str, Any]]],
    ) -> dict[str, list[dict[str, Any]]]:
        return {
            "messages": [
                item
                for item in pending.get("messages", [])
                if (message_id := self._extract_nested_id(item, "message"))
                and not self._was_published(config_id, "message", message_id)
            ],
            "activities": [
                item
                for item in pending.get("activities", [])
                if (activity_id := self._extract_nested_id(item, "activity"))
                and not self._was_published(config_id, "activity", activity_id)
            ],
        }

    def _update_watermark(self, config_id: str, pending: dict[str, list[dict[str, Any]]]) -> None:
        current = self._last_processed_at.setdefault(config_id, datetime.now(UTC))

        for item in pending.get("messages", []):
            timestamp = _parse_iso(item.get("message", {}).get("timestamp"))
            if timestamp is not None and timestamp > current:
                current = timestamp

        for item in pending.get("activities", []):
            timestamp = _parse_iso(item.get("activity", {}).get("timestamp"))
            if timestamp is not None and timestamp > current:
                current = timestamp

        self._last_processed_at[config_id] = current


def _parse_iso(value: object) -> datetime | None:
    """Parse an ISO 8601 timestamp into UTC."""
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
