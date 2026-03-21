"""Abstract PlatformAdapter protocol for external integration providers."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from mc.contexts.integrations.capabilities import PlatformCapability
from mc.contexts.integrations.events import IntegrationEvent


@runtime_checkable
class PlatformAdapter(Protocol):
    @property
    def platform_name(self) -> str: ...

    @property
    def capabilities(self) -> frozenset[PlatformCapability]: ...

    def supports(self, capability: PlatformCapability) -> bool: ...

    # --- Inbound ---
    async def fetch_item(self, external_id: str) -> IntegrationEvent: ...

    async def normalize_webhook(
        self, raw_payload: dict[str, Any], headers: dict[str, str]
    ) -> list[IntegrationEvent]: ...

    async def verify_webhook_signature(
        self, raw_body: bytes, headers: dict[str, str], signing_secret: str
    ) -> bool: ...

    # --- Outbound ---
    async def publish_status_change(
        self, external_id: str, mc_status: str, mapped_status: str
    ) -> None: ...

    async def publish_comment(
        self, external_id: str, body: str, author: str | None = None
    ) -> str | None: ...

    async def close_item(
        self, external_id: str, final_status: str, summary: str | None = None
    ) -> None: ...

    async def publish_labels(self, external_id: str, labels: list[str]) -> None: ...

    # --- Lifecycle ---
    async def validate_credentials(self) -> bool: ...
