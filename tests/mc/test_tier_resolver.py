"""Tests for the model tier resolver (Story 11.1)."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock

import pytest

from mc.types import (
    VALID_TIER_NAMES,
    extract_tier_name,
    is_tier_reference,
)

# ---------------------------------------------------------------------------
# Unit tests for tier reference helpers in types.py (AC2)
# ---------------------------------------------------------------------------


class TestIsTierReference:
    """is_tier_reference() identifies tier-prefixed model strings."""

    def test_valid_tier_reference(self) -> None:
        assert is_tier_reference("tier:standard-high") is True

    def test_all_valid_tiers(self) -> None:
        for tier in VALID_TIER_NAMES:
            assert is_tier_reference(f"tier:{tier}") is True

    def test_non_tier_model_string(self) -> None:
        assert is_tier_reference("anthropic/claude-opus-4-6") is False

    def test_none_returns_false(self) -> None:
        assert is_tier_reference(None) is False

    def test_empty_string_returns_false(self) -> None:
        assert is_tier_reference("") is False

    def test_just_prefix_returns_true(self) -> None:
        # "tier:" with no tier name still starts with prefix
        assert is_tier_reference("tier:") is True

    def test_case_sensitive(self) -> None:
        assert is_tier_reference("TIER:standard-high") is False
        assert is_tier_reference("Tier:standard-high") is False


class TestExtractTierName:
    """extract_tier_name() strips prefix and validates tier name."""

    def test_valid_tier_extraction(self) -> None:
        assert extract_tier_name("tier:standard-high") == "standard-high"

    def test_all_valid_tiers(self) -> None:
        for tier in VALID_TIER_NAMES:
            assert extract_tier_name(f"tier:{tier}") == tier

    def test_non_tier_string_returns_none(self) -> None:
        assert extract_tier_name("anthropic/claude-opus-4-6") is None

    def test_empty_string_returns_none(self) -> None:
        assert extract_tier_name("") is None

    def test_invalid_tier_name_returns_none(self) -> None:
        assert extract_tier_name("tier:invalid-tier") is None

    def test_just_prefix_returns_none(self) -> None:
        assert extract_tier_name("tier:") is None


# ---------------------------------------------------------------------------
# Unit tests for TierResolver (AC3)
# ---------------------------------------------------------------------------


def _make_bridge(tier_map: dict[str, str | None] | None = None) -> MagicMock:
    """Create a mock ConvexBridge that returns tier mappings from settings."""
    bridge = MagicMock()
    if tier_map is not None:
        bridge.query.return_value = json.dumps(tier_map)
    else:
        bridge.query.return_value = None
    return bridge


DEFAULT_TIERS = {
    "standard-low": "anthropic/claude-haiku-3-5",
    "standard-medium": "anthropic/claude-sonnet-4-6",
    "standard-high": "anthropic/claude-opus-4-6",
    "reasoning-low": None,
    "reasoning-medium": None,
    "reasoning-high": None,
}


class TestTierResolverPassThrough:
    """Non-tier model strings pass through unchanged."""

    def test_direct_model_string(self) -> None:
        from mc.infrastructure.providers.tier_resolver import TierResolver

        bridge = _make_bridge(DEFAULT_TIERS)
        resolver = TierResolver(bridge)
        assert resolver.resolve_model("anthropic/claude-opus-4-6") == "anthropic/claude-opus-4-6"

    def test_none_returns_none(self) -> None:
        from mc.infrastructure.providers.tier_resolver import TierResolver

        bridge = _make_bridge(DEFAULT_TIERS)
        resolver = TierResolver(bridge)
        assert resolver.resolve_model(None) is None

    def test_empty_string_returns_none(self) -> None:
        from mc.infrastructure.providers.tier_resolver import TierResolver

        bridge = _make_bridge(DEFAULT_TIERS)
        resolver = TierResolver(bridge)
        assert resolver.resolve_model("") is None


class TestTierResolverResolution:
    """Tier references resolve to actual model strings."""

    def test_standard_high_resolves(self) -> None:
        from mc.infrastructure.providers.tier_resolver import TierResolver

        bridge = _make_bridge(DEFAULT_TIERS)
        resolver = TierResolver(bridge)
        assert resolver.resolve_model("tier:standard-high") == "anthropic/claude-opus-4-6"

    def test_standard_medium_resolves(self) -> None:
        from mc.infrastructure.providers.tier_resolver import TierResolver

        bridge = _make_bridge(DEFAULT_TIERS)
        resolver = TierResolver(bridge)
        assert resolver.resolve_model("tier:standard-medium") == "anthropic/claude-sonnet-4-6"

    def test_standard_low_resolves(self) -> None:
        from mc.infrastructure.providers.tier_resolver import TierResolver

        bridge = _make_bridge(DEFAULT_TIERS)
        resolver = TierResolver(bridge)
        assert resolver.resolve_model("tier:standard-low") == "anthropic/claude-haiku-3-5"


class TestTierResolverNullTier:
    """Null-mapped tiers raise ValueError."""

    def test_null_reasoning_tier_raises(self) -> None:
        from mc.infrastructure.providers.tier_resolver import TierResolver

        bridge = _make_bridge(DEFAULT_TIERS)
        resolver = TierResolver(bridge)
        with pytest.raises(ValueError, match="not configured"):
            resolver.resolve_model("tier:reasoning-low")

    def test_null_reasoning_high_raises(self) -> None:
        from mc.infrastructure.providers.tier_resolver import TierResolver

        bridge = _make_bridge(DEFAULT_TIERS)
        resolver = TierResolver(bridge)
        with pytest.raises(ValueError, match="not configured"):
            resolver.resolve_model("tier:reasoning-high")


class TestTierResolverUnknownTier:
    """Unknown tier names raise ValueError."""

    def test_unknown_tier_raises(self) -> None:
        from mc.infrastructure.providers.tier_resolver import TierResolver

        bridge = _make_bridge(DEFAULT_TIERS)
        resolver = TierResolver(bridge)
        # "tier:invalid-tier" has valid prefix but extract_tier_name returns None
        with pytest.raises(ValueError, match="Unknown tier"):
            resolver.resolve_model("tier:invalid-tier")


class TestTierResolverMissingSettings:
    """Missing model_tiers setting raises ValueError."""

    def test_no_settings_raises(self) -> None:
        from mc.infrastructure.providers.tier_resolver import TierResolver

        bridge = _make_bridge(None)  # settings:get returns None
        resolver = TierResolver(bridge)
        with pytest.raises(ValueError, match="not configured"):
            resolver.resolve_model("tier:standard-high")


class TestTierResolverCache:
    """60-second TTL cache avoids repeated Convex queries."""

    def test_second_call_uses_cache(self) -> None:
        from mc.infrastructure.providers.tier_resolver import TierResolver

        bridge = _make_bridge(DEFAULT_TIERS)
        resolver = TierResolver(bridge)

        # First call populates cache
        resolver.resolve_model("tier:standard-high")
        # Second call should use cache — query NOT called again
        resolver.resolve_model("tier:standard-medium")

        # settings:get should only be called twice (model_tiers + tier_reasoning_levels)
        assert bridge.query.call_count == 2

    def test_cache_expires_after_ttl(self) -> None:
        from mc.infrastructure.providers.tier_resolver import TierResolver

        bridge = _make_bridge(DEFAULT_TIERS)
        resolver = TierResolver(bridge)

        # First call populates cache (2 queries)
        resolver.resolve_model("tier:standard-high")
        assert bridge.query.call_count == 2

        # Simulate cache expiry by backdating _cache_time
        resolver._cache_time = time.monotonic() - 61.0

        # Next call should refresh (2 more queries)
        resolver.resolve_model("tier:standard-high")
        assert bridge.query.call_count == 4

    def test_invalidate_cache_forces_refresh(self) -> None:
        from mc.infrastructure.providers.tier_resolver import TierResolver

        bridge = _make_bridge(DEFAULT_TIERS)
        resolver = TierResolver(bridge)

        resolver.resolve_model("tier:standard-high")
        assert bridge.query.call_count == 2

        resolver.invalidate_cache()

        resolver.resolve_model("tier:standard-high")
        assert bridge.query.call_count == 4
