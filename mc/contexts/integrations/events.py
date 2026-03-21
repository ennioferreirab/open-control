"""Canonical integration event model shared across all platform adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class IntegrationEventType(StrEnum):
    ITEM_CREATED = "item_created"
    ITEM_UPDATED = "item_updated"
    STATUS_CHANGED = "status_changed"
    COMMENT_ADDED = "comment_added"
    COMMENT_UPDATED = "comment_updated"
    ATTACHMENT_ADDED = "attachment_added"
    ASSIGNMENT_CHANGED = "assignment_changed"
    LABEL_CHANGED = "label_changed"
    ITEM_DELETED = "item_deleted"
    ITEM_ARCHIVED = "item_archived"


class EventDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


@dataclass(frozen=True)
class IntegrationEvent:
    event_id: str
    event_type: IntegrationEventType
    direction: EventDirection
    timestamp: str  # ISO 8601
    platform: str
    integration_id: str
    external_id: str | None = None
    mc_task_id: str | None = None
    mc_message_id: str | None = None
    title: str | None = None
    description: str | None = None
    status: str | None = None  # External status value (raw)
    mc_status: str | None = None  # Mapped MC status
    comment_body: str | None = None
    author: str | None = None
    assignee: str | None = None
    labels: list[str] = field(default_factory=list)
    attachment_url: str | None = None
    attachment_name: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""
