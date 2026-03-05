"""End-to-end integration tests: changing tier_reasoning_levels in settings
changes the actual parameters sent to the provider API.

Flow under test:
    Convex settings (mock bridge)
        → TierResolver.resolve_reasoning_level("tier:standard-medium")
        → LiteLLMProvider.chat(reasoning_level=...)
        → acompletion(**kwargs)  ← we verify kwargs here

This directly answers: "does changing the reasoning config produce the
expected effect on requests sent to providers?"
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.tier_resolver import TierResolver
from nanobot.providers.litellm_provider import LiteLLMProvider

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SONNET = "anthropic/claude-sonnet-4-6-20250514"

_DEFAULT_TIERS = {
    "standard-low": "anthropic/claude-haiku-4-5",
    "standard-medium": SONNET,
    "standard-high": "anthropic/claude-opus-4-6",
}


def _make_bridge(reasoning_map: dict) -> MagicMock:
    """Return a mock ConvexBridge whose settings:get returns the given maps."""
    bridge = MagicMock()
    tier_json = json.dumps(_DEFAULT_TIERS)
    reasoning_json = json.dumps(reasoning_map)

    def _query(key: str, args: dict) -> str | None:
        setting_key = args.get("key", "")
        if setting_key == "model_tiers":
            return tier_json
        if setting_key == "tier_reasoning_levels":
            return reasoning_json
        return None

    bridge.query.side_effect = _query
    return bridge


def _fake_acompletion_response() -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock(
        message=MagicMock(content="ok", tool_calls=None),
        finish_reason="stop",
    )]
    resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    return resp


async def _call_provider(reasoning_level: str | None) -> dict:
    """Call LiteLLMProvider.chat() with the given reasoning_level; return acompletion kwargs."""
    provider = LiteLLMProvider(api_key="test-key")
    with patch(
        "nanobot.providers.litellm_provider.acompletion",
        new=AsyncMock(return_value=_fake_acompletion_response()),
    ) as mock_ac:
        await provider.chat(
            messages=[{"role": "user", "content": "hello"}],
            model=SONNET,
            reasoning_level=reasoning_level,
        )
    _, kwargs = mock_ac.call_args
    return kwargs


# ===========================================================================
# 1. Settings → TierResolver → reasoning_level value
# ===========================================================================

class TestSettingsToReasoningLevel:
    """Changing tier_reasoning_levels in Convex is reflected by TierResolver."""

    def test_low_setting_returns_low(self) -> None:
        bridge = _make_bridge({"standard-medium": "low"})
        resolver = TierResolver(bridge)
        assert resolver.resolve_reasoning_level("tier:standard-medium") == "low"

    def test_medium_setting_returns_medium(self) -> None:
        bridge = _make_bridge({"standard-medium": "medium"})
        resolver = TierResolver(bridge)
        assert resolver.resolve_reasoning_level("tier:standard-medium") == "medium"

    def test_max_setting_returns_max(self) -> None:
        bridge = _make_bridge({"standard-medium": "max"})
        resolver = TierResolver(bridge)
        assert resolver.resolve_reasoning_level("tier:standard-medium") == "max"

    def test_empty_setting_returns_none(self) -> None:
        bridge = _make_bridge({})
        resolver = TierResolver(bridge)
        assert resolver.resolve_reasoning_level("tier:standard-medium") is None

    def test_changing_setting_and_invalidating_cache_picks_up_new_value(self) -> None:
        bridge = _make_bridge({"standard-medium": "low"})
        resolver = TierResolver(bridge)

        assert resolver.resolve_reasoning_level("tier:standard-medium") == "low"

        # Simulate user changing setting in the UI
        bridge.query.side_effect = lambda key, args: (
            json.dumps(_DEFAULT_TIERS) if args.get("key") == "model_tiers"
            else json.dumps({"standard-medium": "max"})
        )
        resolver.invalidate_cache()

        assert resolver.resolve_reasoning_level("tier:standard-medium") == "max"


# ===========================================================================
# 2. reasoning_level → acompletion kwargs
# ===========================================================================

class TestReasoningLevelToApiKwargs:
    """The resolved reasoning level reaches acompletion with the correct params.

    SONNET = claude-sonnet-4-6-20250514 → adaptive model path:
      reasoning_effort kwarg (LiteLLM maps it to output_config.effort internally)
      No forced temp=1.0, no budget_tokens.
    """

    @pytest.mark.asyncio
    async def test_low_sends_effort_low_adaptive(self) -> None:
        kwargs = await _call_provider("low")
        assert kwargs.get("reasoning_effort") == "low"
        assert "output_config" not in kwargs
        assert "thinking" not in kwargs
        assert kwargs.get("temperature") != 1.0  # NOT forced to 1.0 in adaptive mode

    @pytest.mark.asyncio
    async def test_medium_sends_effort_medium_adaptive(self) -> None:
        kwargs = await _call_provider("medium")
        assert kwargs.get("reasoning_effort") == "medium"
        assert "output_config" not in kwargs

    @pytest.mark.asyncio
    async def test_max_sends_effort_high_adaptive_on_sonnet(self) -> None:
        # "max" is clamped to "high" on Sonnet 4.6 (only Opus 4.6 supports "max")
        kwargs = await _call_provider("max")
        assert kwargs.get("reasoning_effort") == "high"
        assert "output_config" not in kwargs

    @pytest.mark.asyncio
    async def test_none_sends_no_thinking(self) -> None:
        kwargs = await _call_provider(None)
        assert "thinking" not in kwargs
        assert "reasoning_effort" not in kwargs
        assert "output_config" not in kwargs


# ===========================================================================
# 3. Full chain: settings → TierResolver → acompletion kwargs
# ===========================================================================

class TestFullChainSettingsToApiCall:
    """Full integration: Convex settings → TierResolver → provider.chat() → acompletion.

    This is the key test: does *changing* tier_reasoning_levels in settings
    change what gets sent to the provider API?
    """

    @pytest.mark.asyncio
    async def test_settings_low_produces_effort_low_in_api_call(self) -> None:
        # Arrange: settings say standard-medium → reasoning "low"
        bridge = _make_bridge({"standard-medium": "low"})
        resolver = TierResolver(bridge)

        model = resolver.resolve_model("tier:standard-medium")
        reasoning_level = resolver.resolve_reasoning_level("tier:standard-medium")

        assert model == SONNET
        assert reasoning_level == "low"

        # Act: call provider with resolved values
        kwargs = await _call_provider(reasoning_level)

        # Assert: LiteLLM receives reasoning_effort kwarg (mapped to output_config.effort internally)
        assert kwargs.get("reasoning_effort") == "low", (
            f"Expected reasoning_effort=low for 'low' reasoning; got {kwargs}"
        )
        assert "output_config" not in kwargs

    @pytest.mark.asyncio
    async def test_settings_medium_produces_effort_medium_in_api_call(self) -> None:
        bridge = _make_bridge({"standard-medium": "medium"})
        resolver = TierResolver(bridge)

        reasoning_level = resolver.resolve_reasoning_level("tier:standard-medium")
        assert reasoning_level == "medium"

        kwargs = await _call_provider(reasoning_level)
        assert kwargs.get("reasoning_effort") == "medium"
        assert "output_config" not in kwargs

    @pytest.mark.asyncio
    async def test_settings_off_produces_no_thinking_in_api_call(self) -> None:
        bridge = _make_bridge({})  # no reasoning configured
        resolver = TierResolver(bridge)

        reasoning_level = resolver.resolve_reasoning_level("tier:standard-medium")
        assert reasoning_level is None

        kwargs = await _call_provider(reasoning_level)
        assert "thinking" not in kwargs, (
            "No thinking param expected when reasoning is off"
        )

    @pytest.mark.asyncio
    async def test_changing_setting_changes_api_params(self) -> None:
        """The main regression guard: changing settings changes API call params.

        SONNET (4.6 model) uses reasoning_effort kwarg (LiteLLM maps to output_config.effort).
        'max' is clamped to 'high' on Sonnet 4.6.
        """
        # Round 1: reasoning = "low" → reasoning_effort = "low"
        bridge = _make_bridge({"standard-medium": "low"})
        resolver = TierResolver(bridge)

        level_1 = resolver.resolve_reasoning_level("tier:standard-medium")
        kwargs_1 = await _call_provider(level_1)

        assert kwargs_1.get("reasoning_effort") == "low", (
            f"Round 1 (low): expected reasoning_effort=low, got {kwargs_1}"
        )

        # Round 2: user changes setting to "max" → reasoning_effort = "high" (clamped on Sonnet 4.6)
        bridge.query.side_effect = lambda key, args: (
            json.dumps(_DEFAULT_TIERS) if args.get("key") == "model_tiers"
            else json.dumps({"standard-medium": "max"})
        )
        resolver.invalidate_cache()

        level_2 = resolver.resolve_reasoning_level("tier:standard-medium")
        assert level_2 == "max"
        kwargs_2 = await _call_provider(level_2)

        assert kwargs_2.get("reasoning_effort") == "high", (
            f"Round 2 (max→high on Sonnet): expected reasoning_effort=high, got {kwargs_2}"
        )

        # Round 3: user turns reasoning off
        bridge.query.side_effect = lambda key, args: (
            json.dumps(_DEFAULT_TIERS) if args.get("key") == "model_tiers"
            else json.dumps({})  # empty = off
        )
        resolver.invalidate_cache()

        level_3 = resolver.resolve_reasoning_level("tier:standard-medium")
        assert level_3 is None
        kwargs_3 = await _call_provider(level_3)

        assert "thinking" not in kwargs_3, (
            f"Round 3 (off): thinking should be absent, got {kwargs_3}"
        )
        assert "output_config" not in kwargs_3, (
            f"Round 3 (off): output_config should be absent, got {kwargs_3}"
        )
