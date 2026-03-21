"""Adapter registry — maps platform names to adapter instances."""
from __future__ import annotations

import logging
from collections.abc import Callable

from mc.contexts.integrations.adapters.base import PlatformAdapter
from mc.contexts.integrations.config import IntegrationConfig

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """Registry of platform adapter instances, keyed by integration config ID."""

    def __init__(self) -> None:
        self._adapters: dict[str, PlatformAdapter] = {}
        self._factories: dict[str, Callable[[IntegrationConfig], PlatformAdapter]] = {}

    def register_factory(
        self, platform: str, factory: Callable[[IntegrationConfig], PlatformAdapter]
    ) -> None:
        """Register a factory for a platform."""
        self._factories[platform] = factory

    def create_adapter(self, config: IntegrationConfig) -> PlatformAdapter:
        """Create and register an adapter for the given config."""
        factory = self._factories.get(config.platform)
        if not factory:
            raise ValueError(f"No factory registered for platform '{config.platform}'")
        adapter = factory(config)
        self._adapters[config.id] = adapter
        return adapter

    def get_adapter(self, integration_id: str) -> PlatformAdapter | None:
        """Get a registered adapter by integration config ID."""
        return self._adapters.get(integration_id)

    def list_adapters(self) -> list[PlatformAdapter]:
        """Return all registered adapters."""
        return list(self._adapters.values())
