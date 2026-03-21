"""Bidirectional status mapping between external platforms and MC task statuses."""

from __future__ import annotations

# Default inbound mapping: Linear workflow state type -> MC task status.
# Only maps to statuses accepted by validateInboundStatus:
# inbox, assigned, in_progress, review, done.
DEFAULT_INBOUND_STATUS_MAP: dict[str, str] = {
    "triage": "inbox",
    "backlog": "inbox",
    "unstarted": "inbox",
    "started": "in_progress",
    "completed": "done",
    "canceled": "done",
}

# Default outbound mapping: MC task status -> Linear workflow state type
DEFAULT_OUTBOUND_STATUS_MAP: dict[str, str] = {
    "inbox": "unstarted",
    "assigned": "started",
    "in_progress": "started",
    "review": "started",
    "done": "completed",
    "deleted": "canceled",
    "crashed": "started",
    "retrying": "started",
    "ready": "backlog",
    "failed": "canceled",
}


def resolve_status_inbound(
    external_status: str,
    custom_mapping: dict[str, str] | None = None,
) -> str | None:
    """Map external platform status to MC task status. Returns None if unmapped."""
    mapping = custom_mapping if custom_mapping is not None else DEFAULT_INBOUND_STATUS_MAP
    return mapping.get(external_status)


def resolve_status_outbound(
    mc_status: str,
    custom_mapping: dict[str, str] | None = None,
) -> str | None:
    """Map MC task status to external platform status. Returns None if unmapped."""
    mapping = custom_mapping if custom_mapping is not None else DEFAULT_OUTBOUND_STATUS_MAP
    return mapping.get(mc_status)
