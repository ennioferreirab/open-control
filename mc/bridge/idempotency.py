"""Helpers for attaching stable idempotency keys to retry-safe Convex writes."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SUPPORTED_MUTATIONS = {
    "messages:create",
    "messages:postStepCompletion",
    "messages:postLeadAgentMessage",
    "activities:create",
    "tasks:transition",
    "steps:transition",
}


def ensure_idempotency_key(
    function_name: str,
    camel_args: dict[str, Any],
) -> dict[str, Any]:
    """Attach a deterministic idempotencyKey to supported mutations."""
    if function_name not in SUPPORTED_MUTATIONS:
        return camel_args
    if camel_args.get("idempotencyKey"):
        return camel_args

    payload = json.dumps(camel_args, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return {
        **camel_args,
        "idempotencyKey": f"{function_name}:{digest}",
    }
