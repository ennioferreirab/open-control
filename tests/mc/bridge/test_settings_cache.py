"""Tests for SettingsCache TTL behavior."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from mc.bridge.settings_cache import SettingsCache


class TestSettingsCache:
    """Test TTL-based caching for settings queries."""

    def test_cache_hit_within_ttl(self) -> None:
        """Cached value is returned without querying Convex on subsequent calls."""
        bridge = MagicMock()
        bridge.query.return_value = "some-value"
        cache = SettingsCache(bridge, ttl_seconds=60)

        first = cache.get("my_key")
        second = cache.get("my_key")

        assert first == "some-value"
        assert second == "some-value"
        assert bridge.query.call_count == 1

    def test_cache_miss_after_ttl(self) -> None:
        """Expired entries trigger a new Convex query."""
        bridge = MagicMock()
        bridge.query.return_value = "old-value"
        cache = SettingsCache(bridge, ttl_seconds=0.01)

        first = cache.get("my_key")
        assert first == "old-value"

        # Wait for TTL to expire
        time.sleep(0.02)

        bridge.query.return_value = "new-value"
        second = cache.get("my_key")

        assert second == "new-value"
        assert bridge.query.call_count == 2

    def test_different_keys_are_independent(self) -> None:
        """Each key has its own cache entry."""
        bridge = MagicMock()
        bridge.query.side_effect = lambda _fn, args: f"value-for-{args['key']}"
        cache = SettingsCache(bridge, ttl_seconds=60)

        a = cache.get("key_a")
        b = cache.get("key_b")

        assert a == "value-for-key_a"
        assert b == "value-for-key_b"
        assert bridge.query.call_count == 2

    def test_returns_stale_on_query_failure(self) -> None:
        """On query failure, returns stale cached value if available."""
        bridge = MagicMock()
        bridge.query.return_value = "cached-value"
        cache = SettingsCache(bridge, ttl_seconds=0.01)

        first = cache.get("my_key")
        assert first == "cached-value"

        time.sleep(0.02)
        bridge.query.side_effect = RuntimeError("Convex down")

        second = cache.get("my_key")
        assert second == "cached-value"

    def test_returns_none_on_first_query_failure(self) -> None:
        """On first query failure with no stale data, returns None."""
        bridge = MagicMock()
        bridge.query.side_effect = RuntimeError("Convex down")
        cache = SettingsCache(bridge, ttl_seconds=60)

        result = cache.get("my_key")
        assert result is None

    def test_invalidate_key(self) -> None:
        """Invalidating a key forces re-query on next get."""
        bridge = MagicMock()
        bridge.query.return_value = "first"
        cache = SettingsCache(bridge, ttl_seconds=60)

        cache.get("my_key")
        bridge.query.return_value = "second"
        cache.invalidate("my_key")
        result = cache.get("my_key")

        assert result == "second"
        assert bridge.query.call_count == 2

    def test_invalidate_all(self) -> None:
        """Invalidating all keys forces re-query for all."""
        bridge = MagicMock()
        bridge.query.return_value = "value"
        cache = SettingsCache(bridge, ttl_seconds=60)

        cache.get("key_a")
        cache.get("key_b")
        assert bridge.query.call_count == 2

        cache.invalidate_all()
        cache.get("key_a")
        cache.get("key_b")
        assert bridge.query.call_count == 4
