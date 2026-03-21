"""Inbound pipeline — normalizes and deduplicates external events."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mc.contexts.integrations.events import IntegrationEvent

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge
    from mc.contexts.integrations.mapping_service import MappingService
    from mc.contexts.integrations.registry import AdapterRegistry

logger = logging.getLogger(__name__)


class InboundPipeline:
    """Processes external events into MC state changes."""

    def __init__(
        self,
        bridge: ConvexBridge,
        adapter_registry: AdapterRegistry,
        mapping_service: MappingService,
    ) -> None:
        self._bridge = bridge
        self._adapter_registry = adapter_registry
        self._mapping_service = mapping_service
        self._processed_keys: set[str] = set()

    async def process_webhook(
        self,
        integration_id: str,
        raw_payload: dict[str, Any],
        headers: dict[str, str],
    ) -> list[IntegrationEvent]:
        """Full inbound pipeline: normalize → dedup → validate."""
        adapter = self._adapter_registry.get_adapter(integration_id)
        if not adapter:
            logger.warning("No adapter for integration %s", integration_id)
            return []

        events = await adapter.normalize_webhook(raw_payload, headers)

        # Dedup
        new_events = []
        for event in events:
            if event.idempotency_key and event.idempotency_key in self._processed_keys:
                logger.debug("Skipping duplicate event %s", event.idempotency_key)
                continue
            if event.idempotency_key:
                self._processed_keys.add(event.idempotency_key)
            new_events.append(event)

        return new_events
