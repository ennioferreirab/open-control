"""Module-level TTL cache for tagAttributes:list queries.

The tag attributes catalog changes rarely (admin-only operations), so a
5-minute TTL is safe and eliminates redundant Convex queries across
context_builder, post_processing, and cc_executor.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

TAG_ATTRIBUTES_TTL_SECONDS = 300  # 5 minutes

_cache: list[dict[str, Any]] | None = None
_cache_time: float = 0.0


def get_tag_attributes(bridge: Any) -> list[dict[str, Any]]:
    """Return the tag attribute catalog, using a 5-minute TTL cache.

    Args:
        bridge: ConvexBridge instance for querying Convex.

    Returns:
        List of tag attribute records (snake_case keys).
    """
    global _cache, _cache_time

    now = time.monotonic()
    if _cache is not None and now - _cache_time < TAG_ATTRIBUTES_TTL_SECONDS:
        return _cache

    try:
        result = bridge.query("tagAttributes:list", {})
        if isinstance(result, list):
            _cache = result
            _cache_time = now
            return _cache
    except Exception:
        logger.warning("[tag-attrs-cache] Failed to fetch tagAttributes:list", exc_info=True)

    # Return stale cache if available, otherwise empty
    return _cache if _cache is not None else []


def invalidate() -> None:
    """Force a refresh on the next get_tag_attributes() call."""
    global _cache, _cache_time
    _cache = None
    _cache_time = 0.0
