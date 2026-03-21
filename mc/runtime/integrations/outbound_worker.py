"""Outbound sync worker — polls MC events and syncs to external platforms."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge
    from mc.contexts.integrations.pipeline.outbound import OutboundPipeline
    from mc.runtime.sleep_controller import RuntimeSleepController

logger = logging.getLogger(__name__)


class IntegrationOutboundWorker:
    """Polls for MC events to sync outward to external platforms."""

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
        self._last_poll: dict[str, str] = {}  # config_id → timestamp

    async def run(self) -> None:
        """Main polling loop."""
        logger.info("[integration-outbound] Worker started (interval=%.1fs)", self._poll_interval)
        while True:
            try:
                await self._poll_cycle()
            except asyncio.CancelledError:
                logger.info("[integration-outbound] Worker cancelled")
                raise
            except Exception:
                logger.exception("[integration-outbound] Poll cycle error")

            interval = self._get_poll_interval()
            await asyncio.sleep(interval)

    async def _poll_cycle(self) -> None:
        """Run one poll cycle across all enabled configs."""
        configs = self._bridge.get_enabled_integration_configs()

        for config in configs:
            config_id = config.get("id", "")
            if not config_id:
                continue

            since = self._last_poll.get(config_id, datetime.now(UTC).isoformat())
            now = datetime.now(UTC).isoformat()

            try:
                count = await self._pipeline.process_outbound_batch(config_id, since)
                if count > 0:
                    logger.info(
                        "[integration-outbound] Published %d events for config %s",
                        count,
                        config_id,
                    )
            except Exception:
                logger.exception(
                    "[integration-outbound] Failed processing config %s", config_id
                )

            self._last_poll[config_id] = now

    def _get_poll_interval(self) -> float:
        """Respect sleep controller if available."""
        if self._sleep_controller and hasattr(self._sleep_controller, "is_sleeping"):
            if self._sleep_controller.is_sleeping:
                return self._poll_interval * 6  # 60s in sleep mode
        return self._poll_interval
