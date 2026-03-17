"""Helpers for acquiring persistent runtime claims via Convex."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

DEFAULT_LEASE_SECONDS = 300


def _owner_id(bridge: Any) -> str:
    owner_id = getattr(bridge, "_runtime_claim_owner_id", None)
    if owner_id:
        return owner_id
    owner_id = f"runtime:{uuid4()}"
    setattr(bridge, "_runtime_claim_owner_id", owner_id)
    return owner_id


def acquire_runtime_claim(
    bridge: Any,
    *,
    claim_kind: str,
    entity_type: str,
    entity_id: str,
    metadata: dict[str, Any] | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> bool:
    """Acquire a persistent lease-backed claim for a runtime work item."""
    now = datetime.now(timezone.utc)
    result = bridge.mutation(
        "runtimeClaims:acquire",
        {
            "claim_kind": claim_kind,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "owner_id": _owner_id(bridge),
            "lease_expires_at": (now + timedelta(seconds=lease_seconds)).isoformat(),
            "metadata": metadata,
        },
    )
    if isinstance(result, dict) and "granted" in result:
        return bool(result["granted"])
    logger.debug(
        "[runtime_claims] Unexpected acquire response for %s/%s: %r; proceeding",
        claim_kind,
        entity_id,
        result,
    )
    return True


def task_snapshot_claim_kind(scope: str, task_data: dict[str, Any]) -> str:
    state_version = task_data.get("state_version", task_data.get("stateVersion", 0))
    status = task_data.get("status", "unknown")
    review_phase = task_data.get("review_phase") or task_data.get("reviewPhase") or "none"
    return f"{scope}:v{state_version}:{status}:{review_phase}"
