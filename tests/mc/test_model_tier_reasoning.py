"""Tests for model tier + reasoning settings integration.

Verifies two concerns for the `standard-medium` (Sonnet) tier:

1. MODEL RESOLUTION — `tier:standard-medium` must resolve to the Sonnet model
   ID stored in the `model_tiers` Convex setting. This already works.

2. REASONING LEVEL — changing `tier_reasoning_levels["standard-medium"]` in
   Settings must propagate to the actual `provider.chat()` call. Currently
   this is NOT implemented: the `tier_reasoning_levels` setting is persisted
   by the UI but never read by the Python backend. Tests marked with
   ``xfail`` document the missing behaviour and will start passing once the
   feature is implemented.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from mc.infrastructure.providers.tier_resolver import TierResolver

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SONNET_MODEL = "anthropic/claude-sonnet-4-6-20250514"

DEFAULT_TIERS = {
    "standard-low": "anthropic/claude-haiku-4-5",
    "standard-medium": SONNET_MODEL,
    "standard-high": "anthropic/claude-opus-4-6",
    "reasoning-low": None,
    "reasoning-medium": None,
    "reasoning-high": None,
}

DEFAULT_REASONING_LEVELS: dict[str, str] = {
    # all off by default
}


def _make_bridge(
    tier_map: dict | None = None,
    reasoning_map: dict | None = None,
) -> MagicMock:
    """Create a mock ConvexBridge that returns settings from Convex."""
    bridge = MagicMock()
    tier_json = json.dumps(tier_map) if tier_map is not None else None
    reasoning_json = json.dumps(reasoning_map) if reasoning_map is not None else None

    def _query(key: str, args: dict) -> str | None:  # type: ignore[override]
        setting_key = args.get("key", "")
        if setting_key == "model_tiers":
            return tier_json
        if setting_key == "tier_reasoning_levels":
            return reasoning_json
        return None

    bridge.query.side_effect = _query
    return bridge


# ===========================================================================
# 1. MODEL RESOLUTION — these tests should PASS
# ===========================================================================


class TestStandardMediumModelResolution:
    """tier:standard-medium resolves to the Sonnet model from model_tiers."""

    def test_tier_standard_medium_resolves_to_sonnet(self) -> None:
        """Changing Settings → Model Tier → Medium model is reflected in resolution."""
        bridge = _make_bridge(tier_map=DEFAULT_TIERS)
        resolver = TierResolver(bridge)

        resolved = resolver.resolve_model("tier:standard-medium")

        assert resolved == SONNET_MODEL, (
            f"Expected standard-medium → {SONNET_MODEL!r}, got {resolved!r}"
        )

    def test_changing_medium_model_in_settings_changes_resolution(self) -> None:
        """If the user changes standard-medium in Settings to a different model, it's used."""
        new_model = "anthropic/claude-sonnet-4-7"
        updated_tiers = {**DEFAULT_TIERS, "standard-medium": new_model}
        bridge = _make_bridge(tier_map=updated_tiers)
        resolver = TierResolver(bridge)

        resolved = resolver.resolve_model("tier:standard-medium")

        assert resolved == new_model

    def test_tier_standard_medium_non_tier_string_passthrough(self) -> None:
        """A direct model ID is returned unchanged (no resolution)."""
        bridge = _make_bridge(tier_map=DEFAULT_TIERS)
        resolver = TierResolver(bridge)

        direct = resolver.resolve_model(SONNET_MODEL)

        assert direct == SONNET_MODEL


# ===========================================================================
# 2. REASONING RESOLUTION — tests document the MISSING feature (xfail)
# ===========================================================================


class TestReasoningLevelResolutionOnTierResolver:
    """TierResolver should be able to resolve reasoning levels for a tier.

    These tests are currently xfail because TierResolver only resolves
    model IDs; it has no ``resolve_reasoning_level()`` method yet.
    """

    def test_resolve_reasoning_level_exists(self) -> None:
        """TierResolver exposes a resolve_reasoning_level() method."""
        bridge = _make_bridge(
            tier_map=DEFAULT_TIERS,
            reasoning_map={"standard-medium": "low"},
        )
        resolver = TierResolver(bridge)

        # This will raise AttributeError until the method is added
        level = resolver.resolve_reasoning_level("tier:standard-medium")  # type: ignore[attr-defined]
        assert level == "low"

    def test_resolve_reasoning_level_off_when_not_configured(self) -> None:
        """Unconfigured reasoning → None/off, not an error."""
        bridge = _make_bridge(
            tier_map=DEFAULT_TIERS,
            reasoning_map={},  # nothing set
        )
        resolver = TierResolver(bridge)

        level = resolver.resolve_reasoning_level("tier:standard-medium")  # type: ignore[attr-defined]
        assert level is None or level == ""

    def test_changing_reasoning_level_in_settings_is_reflected(self) -> None:
        """After cache invalidation, a new reasoning level in settings is returned."""
        bridge = _make_bridge(
            tier_map=DEFAULT_TIERS,
            reasoning_map={"standard-medium": "low"},
        )
        resolver = TierResolver(bridge)

        level_before = resolver.resolve_reasoning_level("tier:standard-medium")  # type: ignore[attr-defined]
        assert level_before == "low"

        # Simulate user updating the setting to "medium"
        bridge.query.side_effect = None
        bridge.query.return_value = json.dumps({"standard-medium": "medium"})
        resolver.invalidate_cache()

        level_after = resolver.resolve_reasoning_level("tier:standard-medium")  # type: ignore[attr-defined]
        assert level_after == "medium"


# ===========================================================================
# 3. EXECUTOR-LEVEL — reasoning must reach provider.chat() (xfail)
# ===========================================================================


class TestReasoningPropagationToProviderChat:
    """When tier_reasoning_levels is set, provider.chat() must receive the
    reasoning/thinking parameter for the configured tier.

    Currently xfail: executor._execute_task never reads tier_reasoning_levels
    and AgentLoop / provider.chat() have no reasoning parameter.
    """

    @pytest.mark.asyncio
    async def test_standard_medium_reasoning_low_reaches_provider_chat(self) -> None:
        """When reasoning_level='low' is passed, provider.chat() receives it."""
        from mc.executor import _run_agent_on_task

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=MagicMock(
            content="done", has_tool_calls=False, tool_calls=[], reasoning_content=None,
            thinking_blocks=None, finish_reason="stop",
        ))
        mock_provider.get_default_model = MagicMock(return_value=SONNET_MODEL)

        with patch(
            "mc.executor._make_provider",
            return_value=(mock_provider, SONNET_MODEL),
        ):
            await _run_agent_on_task(
                agent_name="test-agent",
                agent_prompt="You are a test agent.",
                agent_model=SONNET_MODEL,
                reasoning_level="low",
                task_title="Test task",
                task_description="Do something",
            )

        chat_calls = mock_provider.chat.call_args_list
        assert chat_calls, "provider.chat() was never called"

        # Verify reasoning_level was threaded through to provider.chat()
        last_kwargs = chat_calls[-1].kwargs
        assert last_kwargs.get("reasoning_level") == "low", (
            f"provider.chat() was NOT called with reasoning_level='low'.\n"
            f"Actual kwargs: {last_kwargs}"
        )

    @pytest.mark.asyncio
    async def test_standard_medium_reasoning_off_does_not_pass_thinking(self) -> None:
        """When reasoning is off (default), provider.chat() is NOT called with thinking.

        This passes today because reasoning is never sent — it's a regression guard:
        once reasoning IS implemented, calls with reasoning=off must still omit the
        thinking param.
        """
        from mc.executor import _run_agent_on_task

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=MagicMock(
            content="done", has_tool_calls=False, tool_calls=[], reasoning_content=None,
            thinking_blocks=None, finish_reason="stop",
        ))
        mock_provider.get_default_model = MagicMock(return_value=SONNET_MODEL)

        with patch(
            "mc.executor._make_provider",
            return_value=(mock_provider, SONNET_MODEL),
        ):
            await _run_agent_on_task(
                agent_name="test-agent",
                agent_prompt="You are a test agent.",
                agent_model=SONNET_MODEL,
                task_title="Test task",
                task_description="Do something",
            )

        chat_calls = mock_provider.chat.call_args_list
        assert chat_calls, "provider.chat() was never called"

        last_kwargs = chat_calls[-1].kwargs
        # When reasoning is off, these params should be absent
        assert "thinking" not in last_kwargs, (
            "thinking was unexpectedly present when reasoning is off"
        )


# ===========================================================================
# 4. TIER RESOLVER — verify the standard-medium model ID format is correct
# ===========================================================================


class TestSonnetModelIdFormat:
    """Guard against accidentally mapping standard-medium to a non-Sonnet model."""

    def test_standard_medium_maps_to_sonnet_pattern(self) -> None:
        """The resolved model ID for standard-medium must contain 'sonnet'."""
        bridge = _make_bridge(tier_map=DEFAULT_TIERS)
        resolver = TierResolver(bridge)

        resolved = resolver.resolve_model("tier:standard-medium")
        assert resolved is not None
        assert "sonnet" in resolved.lower(), (
            f"standard-medium should map to a Sonnet model, got: {resolved!r}"
        )

    def test_standard_low_maps_to_haiku_pattern(self) -> None:
        """standard-low maps to Haiku (sanity check the tier ladder)."""
        bridge = _make_bridge(tier_map=DEFAULT_TIERS)
        resolver = TierResolver(bridge)

        resolved = resolver.resolve_model("tier:standard-low")
        assert resolved is not None
        assert "haiku" in resolved.lower(), (
            f"standard-low should map to a Haiku model, got: {resolved!r}"
        )

    def test_standard_high_maps_to_opus_pattern(self) -> None:
        """standard-high maps to Opus (sanity check the tier ladder)."""
        bridge = _make_bridge(tier_map=DEFAULT_TIERS)
        resolver = TierResolver(bridge)

        resolved = resolver.resolve_model("tier:standard-high")
        assert resolved is not None
        assert "opus" in resolved.lower(), (
            f"standard-high should map to an Opus model, got: {resolved!r}"
        )


class TestLiteLLMProviderReasoningInjection:
    """LiteLLMProvider.chat() injects correct params for each reasoning level."""

    @pytest.mark.asyncio
    async def test_anthropic_model_low_reasoning_injects_thinking(self) -> None:
        from nanobot.providers.litellm_provider import LiteLLMProvider

        provider = LiteLLMProvider(api_key="test-key")
        fake_response = MagicMock()
        fake_response.choices = [MagicMock(
            message=MagicMock(content="ok", tool_calls=None),
            finish_reason="stop",
        )]
        fake_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        with patch("nanobot.providers.litellm_provider.acompletion", new=AsyncMock(return_value=fake_response)) as mock_ac:
            await provider.chat(
                messages=[{"role": "user", "content": "hello"}],
                model="anthropic/claude-sonnet-4-6-20250514",
                reasoning_level="low",
            )

        _, kwargs = mock_ac.call_args
        # claude-sonnet-4-6 → adaptive: LiteLLM reasoning_effort kwarg (maps to output_config.effort)
        assert kwargs.get("reasoning_effort") == "low"
        assert "output_config" not in kwargs
        assert kwargs.get("temperature") != 1.0  # NOT forced in adaptive mode

    @pytest.mark.asyncio
    async def test_anthropic_model_medium_reasoning_injects_thinking(self) -> None:
        from nanobot.providers.litellm_provider import LiteLLMProvider

        provider = LiteLLMProvider(api_key="test-key")
        fake_response = MagicMock()
        fake_response.choices = [MagicMock(
            message=MagicMock(content="ok", tool_calls=None),
            finish_reason="stop",
        )]
        fake_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        with patch("nanobot.providers.litellm_provider.acompletion", new=AsyncMock(return_value=fake_response)) as mock_ac:
            await provider.chat(
                messages=[{"role": "user", "content": "hello"}],
                model="anthropic/claude-sonnet-4-6-20250514",
                reasoning_level="medium",
            )

        _, kwargs = mock_ac.call_args
        # claude-sonnet-4-6 → adaptive: LiteLLM reasoning_effort kwarg (maps to output_config.effort)
        assert kwargs.get("reasoning_effort") == "medium"
        assert "output_config" not in kwargs

    @pytest.mark.asyncio
    async def test_anthropic_model_none_reasoning_omits_thinking(self) -> None:
        from nanobot.providers.litellm_provider import LiteLLMProvider

        provider = LiteLLMProvider(api_key="test-key")
        fake_response = MagicMock()
        fake_response.choices = [MagicMock(
            message=MagicMock(content="ok", tool_calls=None),
            finish_reason="stop",
        )]
        fake_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        with patch("nanobot.providers.litellm_provider.acompletion", new=AsyncMock(return_value=fake_response)) as mock_ac:
            await provider.chat(
                messages=[{"role": "user", "content": "hello"}],
                model="anthropic/claude-sonnet-4-6-20250514",
                reasoning_level=None,
            )

        _, kwargs = mock_ac.call_args
        assert "thinking" not in kwargs
        assert "reasoning_effort" not in kwargs

    @pytest.mark.asyncio
    async def test_openai_model_reasoning_injects_reasoning_effort(self) -> None:
        from nanobot.providers.litellm_provider import LiteLLMProvider

        provider = LiteLLMProvider(api_key="test-key")
        fake_response = MagicMock()
        fake_response.choices = [MagicMock(
            message=MagicMock(content="ok", tool_calls=None),
            finish_reason="stop",
        )]
        fake_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        with patch("nanobot.providers.litellm_provider.acompletion", new=AsyncMock(return_value=fake_response)) as mock_ac:
            await provider.chat(
                messages=[{"role": "user", "content": "hello"}],
                model="openai/gpt-4o",
                reasoning_level="max",
            )

        _, kwargs = mock_ac.call_args
        assert kwargs.get("reasoning_effort") == "high"
        assert "thinking" not in kwargs
