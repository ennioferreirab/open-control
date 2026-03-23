"""Outbound pipeline — detects MC events and publishes to external platforms."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from mc.contexts.integrations.capabilities import PlatformCapability
from mc.contexts.integrations.events import MC_COMMENT_PREFIX
from mc.contexts.integrations.status_mapping import resolve_status_outbound

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge
    from mc.contexts.integrations.mapping_service import MappingService
    from mc.contexts.integrations.registry import AdapterRegistry

logger = logging.getLogger(__name__)
PublishItemResult = Literal["published", "skipped", "failed"]


class OutboundPipeline:
    """Watches MC state changes and publishes them to external platforms."""

    def __init__(
        self,
        bridge: ConvexBridge,
        adapter_registry: AdapterRegistry,
        mapping_service: MappingService,
    ) -> None:
        self._bridge = bridge
        self._adapter_registry = adapter_registry
        self._mapping_service = mapping_service

    async def process_outbound_batch(self, config_id: str, since_timestamp: str) -> int:
        """Process outbound events for a config since a timestamp. Returns count published."""
        adapter = self._adapter_registry.get_adapter(config_id)
        if not adapter:
            logger.warning("No adapter for config %s", config_id)
            return 0

        pending = self._bridge.get_outbound_pending(config_id, since_timestamp)
        return await self.publish_pending(config_id, pending)

    async def publish_pending(self, config_id: str, pending: dict[str, list[dict]]) -> int:
        """Publish a prepared outbound payload for a config."""
        messages = pending.get("messages", [])
        activities = pending.get("activities", [])

        published = 0

        for item in messages:
            if await self.publish_message_item(config_id, item) == "published":
                published += 1

        for item in activities:
            if await self.publish_activity_item(config_id, item) == "published":
                published += 1

        return published

    async def publish_message_item(self, config_id: str, item: dict) -> PublishItemResult:
        """Publish one outbound message item and classify the result."""
        adapter = self._adapter_registry.get_adapter(config_id)
        if not adapter:
            logger.warning("No adapter for config %s", config_id)
            return "failed"
        if not adapter.supports(PlatformCapability.THREAD_MIRRORING):
            return "skipped"

        msg = item.get("message", {})
        mapping = item.get("mapping", {})
        external_id = mapping.get("external_id") or mapping.get("externalId") or ""
        if not external_id:
            return "skipped"

        content = msg.get("content", "")
        if content.strip().startswith(MC_COMMENT_PREFIX):
            return "skipped"

        author = msg.get("author_name") or msg.get("authorName") or "MC"
        msg_type = msg.get("type", "")

        if msg_type == "step_completion":
            body = f"**Step completed** by {author}\n\n{content}"
        elif msg_type == "system_error":
            body = f"**System error**\n\n{content}"
        elif msg_type == "lead_agent_chat":
            body = f"**{author}** (plan)\n\n{content}"
        else:
            body = content

        try:
            await adapter.publish_comment(external_id, body, author=author)
            return "published"
        except Exception:
            logger.exception("Failed to publish comment to %s for %s", external_id, config_id)
            return "failed"

    async def publish_activity_item(self, config_id: str, item: dict) -> PublishItemResult:
        """Publish one outbound activity item and classify the result."""
        adapter = self._adapter_registry.get_adapter(config_id)
        if not adapter:
            logger.warning("No adapter for config %s", config_id)
            return "failed"
        if not adapter.supports(PlatformCapability.PUBLISH_STATUS):
            return "skipped"

        activity = item.get("activity", {})
        mapping = item.get("mapping", {})
        external_id = mapping.get("external_id") or mapping.get("externalId") or ""
        event_type = activity.get("event_type") or activity.get("eventType") or ""

        if not external_id:
            return "skipped"
        if event_type not in (
            "task_completed",
            "task_started",
            "task_assigned",
            "task_crashed",
            "task_retrying",
        ):
            return "skipped"

        status_map = {
            "task_completed": "done",
            "task_started": "in_progress",
            "task_assigned": "assigned",
            "task_crashed": "crashed",
            "task_retrying": "retrying",
        }
        mc_status = status_map.get(event_type, "")
        if not mc_status:
            return "skipped"

        mapped_status = resolve_status_outbound(mc_status)
        if not mapped_status:
            return "skipped"

        try:
            await adapter.publish_status_change(external_id, mc_status, mapped_status)
            return "published"
        except Exception:
            logger.exception("Failed to publish status to %s for %s", external_id, config_id)
            return "failed"
