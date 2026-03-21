"""Boot integration adapters from Convex config at gateway startup."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mc.contexts.integrations.config import IntegrationConfig

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge
    from mc.contexts.integrations.registry import AdapterRegistry

logger = logging.getLogger(__name__)


class IntegrationSyncService:
    """Loads active integration configs and creates adapter instances."""

    def __init__(self, bridge: ConvexBridge, adapter_registry: AdapterRegistry) -> None:
        self._bridge = bridge
        self._registry = adapter_registry

    def initialize(self) -> int:
        """Load all enabled configs, create adapters, validate credentials.

        Returns count of active integrations.
        """
        configs = self._bridge.get_enabled_integration_configs()
        active = 0

        for raw_config in configs:
            try:
                config = IntegrationConfig(
                    id=raw_config.get("id", ""),
                    platform=raw_config.get("platform", ""),
                    name=raw_config.get("name", ""),
                    enabled=raw_config.get("enabled", False),
                    board_id=raw_config.get("board_id", ""),
                    api_key=raw_config.get("api_key"),
                    webhook_secret=raw_config.get("webhook_secret"),
                    webhook_id=raw_config.get("webhook_id"),
                    external_project_id=raw_config.get("external_project_id"),
                    external_project_name=raw_config.get("external_project_name"),
                    status_mapping=raw_config.get("status_mapping"),
                    sync_direction=raw_config.get("sync_direction", "bidirectional"),
                    thread_mirroring=raw_config.get("thread_mirroring", True),
                    sync_attachments=raw_config.get("sync_attachments", False),
                    sync_labels=raw_config.get("sync_labels", False),
                )
                self._registry.create_adapter(config)
                active += 1
                logger.info(
                    "[integration-sync] Created %s adapter for '%s' (id=%s)",
                    config.platform,
                    config.name,
                    config.id,
                )
            except Exception:
                logger.exception(
                    "[integration-sync] Failed to create adapter for config %s",
                    raw_config.get("id", "unknown"),
                )

        return active
