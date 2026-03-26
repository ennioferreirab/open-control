"""TTL-based cache for Convex settings queries.

Reduces redundant bridge.query("settings:get", ...) calls for frequently
accessed settings like global_orientation_prompt and task_timeout_minutes.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 60


class SettingsCache:
    """In-memory cache for Convex settings with per-key TTL expiry.

    Thread-safe under CPython GIL (single-threaded asyncio runtime).

    Args:
        bridge: ConvexBridge instance for querying settings.
        ttl_seconds: Time-to-live for cached values.
    """

    def __init__(self, bridge: Any, ttl_seconds: float = DEFAULT_TTL_SECONDS) -> None:
        self._bridge = bridge
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any:
        """Fetch a setting value, returning cached result if within TTL.

        Args:
            key: The settings key to look up.

        Returns:
            The setting value from cache or Convex, or None if not found.
        """
        now = time.monotonic()
        entry = self._cache.get(key)
        if entry is not None:
            value, cached_at = entry
            if now - cached_at < self._ttl:
                return value

        # Cache miss or expired -- query Convex
        try:
            value = self._bridge.query("settings:get", {"key": key})
        except Exception:
            logger.warning("[settings-cache] Failed to fetch setting '%s'", key, exc_info=True)
            # Return stale value if available
            if entry is not None:
                return entry[0]
            return None

        self._cache[key] = (value, now)
        return value

    def invalidate(self, key: str) -> None:
        """Remove a specific key from the cache."""
        self._cache.pop(key, None)

    def invalidate_all(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()
