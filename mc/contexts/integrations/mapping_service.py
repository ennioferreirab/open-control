"""Mapping service — MC ↔ external entity lookup via bridge."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


class MappingService:
    """Manages MC ↔ external entity mappings via the bridge."""

    def __init__(self, bridge: ConvexBridge) -> None:
        self._bridge = bridge

    def get_mc_task_id(self, config_id: str, external_id: str) -> str | None:
        """Look up MC task ID from an external item ID."""
        mapping = self._bridge._integrations.get_mapping_by_external(
            config_id, "issue", external_id,
        )
        return mapping.get("internal_id") if mapping else None

    def get_external_id(self, config_id: str, mc_task_id: str) -> str | None:
        """Look up external item ID from an MC task ID."""
        mapping = self._bridge._integrations.get_mapping_by_internal(
            config_id, "task", mc_task_id,
        )
        return mapping.get("external_id") if mapping else None

    def get_mapping_for_task(self, mc_task_id: str) -> dict[str, Any] | None:
        """Get the first mapping for an MC task (any platform)."""
        mappings = self._bridge._integrations.get_mappings_by_internal_id(mc_task_id)
        return mappings[0] if mappings else None
