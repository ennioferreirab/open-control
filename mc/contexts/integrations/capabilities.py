"""Platform capability flags for integration adapters."""

from __future__ import annotations

from enum import StrEnum


class PlatformCapability(StrEnum):
    INGEST_ITEM = "ingest_item"
    PUBLISH_STATUS = "publish_status"
    THREAD_MIRRORING = "thread_mirroring"
    STATUS_MAPPING = "status_mapping"
    BINARY_ATTACHMENTS = "binary_attachments"
    EXECUTION_RESUME_FROM_COMMENT = "execution_resume_from_comment"
    AGENT_SESSIONS = "agent_sessions"
    BIDIRECTIONAL_COMMENTS = "bidirectional_comments"
    LABELS_SYNC = "labels_sync"
    ASSIGNMENT_SYNC = "assignment_sync"
    WEBHOOK_INBOUND = "webhook_inbound"
    POLLING_INBOUND = "polling_inbound"
