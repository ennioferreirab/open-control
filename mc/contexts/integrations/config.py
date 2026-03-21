"""Python-side integration configuration dataclass."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SyncDirection(StrEnum):
    INBOUND_ONLY = "inbound_only"
    OUTBOUND_ONLY = "outbound_only"
    BIDIRECTIONAL = "bidirectional"


@dataclass
class IntegrationConfig:
    """Python-side representation of Convex integrationConfigs table."""

    id: str
    platform: str
    name: str
    enabled: bool
    board_id: str
    api_key: str | None = None
    webhook_secret: str | None = None
    webhook_id: str | None = None
    external_project_id: str | None = None
    external_project_name: str | None = None
    status_mapping: dict[str, Any] | None = None
    sync_direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    thread_mirroring: bool = True
    sync_attachments: bool = False
    sync_labels: bool = False
    last_sync_at: str | None = None
    last_error: str | None = None
