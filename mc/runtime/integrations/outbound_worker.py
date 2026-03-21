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
                found_work = await self._poll_cycle()
                if self._sleep_controller is not None:
                    if found_work:
                        await self._sleep_controller.record_work_found()
                    else:
                        await self._sleep_controller.record_idle()
            except asyncio.CancelledError:
                logger.info("[integration-outbound] Worker cancelled")
                raise
            except Exception:
                logger.exception("[integration-outbound] Poll cycle error")

            if self._sleep_controller is not None:
                await self._sleep_controller.wait_for_next_cycle(self._poll_interval)
            else:
                await asyncio.sleep(self._poll_interval)

    async def _poll_cycle(self) -> bool:
        """Run one poll cycle across all enabled configs. Returns True if work found."""
        configs = self._bridge.get_enabled_integration_configs()
        found_work = False

        for config in configs:
            config_id = config.get("id", "")
            if not config_id:
                continue

            since = self._last_poll.get(config_id, datetime.now(UTC).isoformat())
            now = datetime.now(UTC).isoformat()

            try:
                count = await self._pipeline.process_outbound_batch(config_id, since)
                if count > 0:
                    found_work = True
                    logger.info(
                        "[integration-outbound] Published %d events for config %s",
                        count,
                        config_id,
                    )
            except Exception:
                logger.exception("[integration-outbound] Failed processing config %s", config_id)

            self._last_poll[config_id] = now

        return found_work
