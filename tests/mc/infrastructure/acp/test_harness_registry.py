"""Tests for the ACP harness registry."""

from __future__ import annotations

import pytest

from mc.infrastructure.acp.harness_registry import get_harness, resolve_model


def test_get_harness_claude_code() -> None:
    spec = get_harness("claude-code")
    assert spec.name == "claude-code"
    assert spec.launch_command == ("npx", "-y", "@agentclientprotocol/claude-agent-acp")
    assert spec.model_tiers == {"low": "haiku", "medium": "sonnet", "high": "default"}
    assert spec.native_acp is False


def test_get_harness_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown harness"):
        get_harness("nope")


def test_resolve_model_maps_tier_labels() -> None:
    spec = get_harness("claude-code")
    assert resolve_model(spec, "low") == "haiku"
    assert resolve_model(spec, "medium") == "sonnet"
    assert resolve_model(spec, "high") == "default"


def test_resolve_model_passes_through_concrete() -> None:
    spec = get_harness("claude-code")
    assert resolve_model(spec, "anthropic/claude-sonnet-4-6") == "anthropic/claude-sonnet-4-6"
    assert resolve_model(spec, None) is None
