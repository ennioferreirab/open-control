"""Bridge repository for integration tables."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.bridge.adapter import _BridgeClientAdapter

logger = logging.getLogger(__name__)


class IntegrationRepository:
    """Data access for integrationConfigs, integrationMappings, integrationEvents."""

    def __init__(self, client: _BridgeClientAdapter) -> None:
        self._client = client

    def get_enabled_configs(self) -> list[dict[str, Any]]:
        """Return all enabled integration configs."""
        return self._client.query("integrations:getEnabledConfigs") or []

    def get_configs_by_platform(self, platform: str) -> list[dict[str, Any]]:
        """Return configs for a given platform."""
        return self._client.query("integrations:getConfigsByPlatform", {"platform": platform}) or []

    def get_mapping_by_external(
        self, config_id: str, external_type: str, external_id: str
    ) -> dict[str, Any] | None:
        """Look up mapping by config + external entity."""
        return self._client.query(
            "integrations:getMappingByExternal",
            {"config_id": config_id, "external_type": external_type, "external_id": external_id},
        )

    def get_mapping_by_internal(
        self, config_id: str, internal_type: str, internal_id: str
    ) -> dict[str, Any] | None:
        """Look up mapping by config + internal entity."""
        return self._client.query(
            "integrations:getMappingByInternal",
            {"config_id": config_id, "internal_type": internal_type, "internal_id": internal_id},
        )

    def get_mappings_by_internal_id(self, internal_id: str) -> list[dict[str, Any]]:
        """Return all mappings for an internal ID."""
        return (
            self._client.query("integrations:getMappingsByInternalId", {"internal_id": internal_id})
            or []
        )

    def upsert_mapping(
        self,
        config_id: str,
        platform: str,
        external_id: str,
        external_type: str,
        internal_id: str,
        internal_type: str,
        external_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create or update a mapping record."""
        return self._client.mutation(
            "integrations:upsertMapping",
            {
                "config_id": config_id,
                "platform": platform,
                "external_id": external_id,
                "external_type": external_type,
                "internal_id": internal_id,
                "internal_type": internal_type,
                "external_url": external_url,
                "metadata": metadata,
            },
        )

    def create_event(
        self,
        config_id: str,
        event_id: str,
        event_type: str,
        direction: str,
        status: str,
        external_id: str | None = None,
        internal_id: str | None = None,
        payload: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> str:
        """Create an integration event record."""
        return self._client.mutation(
            "integrations:createEvent",
            {
                "config_id": config_id,
                "event_id": event_id,
                "event_type": event_type,
                "direction": direction,
                "status": status,
                "external_id": external_id,
                "internal_id": internal_id,
                "payload": payload,
                "error_message": error_message,
            },
        )

    def mark_event_processed(self, event_id: str) -> None:
        """Mark an event as processed."""
        self._client.mutation("integrations:markEventProcessed", {"event_id": event_id})

    def get_outbound_pending(self, config_id: str, since_timestamp: str) -> dict[str, Any]:
        """Return messages and activities since timestamp for mapped tasks."""
        return self._client.query(
            "integrations:getOutboundPending",
            {"config_id": config_id, "since_timestamp": since_timestamp},
        ) or {"messages": [], "activities": []}
