"""Tests for the ACP harness registry."""

from __future__ import annotations

import pytest

from mc.infrastructure.acp.harness_registry import (
    get_harness,
    is_registered_harness,
    resolve_model,
)


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


def test_get_harness_codex() -> None:
    spec = get_harness("codex")
    assert spec.name == "codex"
    assert spec.launch_command == ("npx", "-y", "@zed-industries/codex-acp")
    assert spec.native_acp is False
    # Codex has no model env var; it takes the model via session/set_model.
    assert spec.model_env is None
    assert spec.model_via_session is True
    assert spec.session_param_style == "standard"
    # API-key env must be unset so the ChatGPT subscription credentials win.
    assert spec.env_overrides == {"OPENAI_API_KEY": None, "CODEX_API_KEY": None}


def test_resolve_model_maps_codex_tiers() -> None:
    spec = get_harness("codex")
    assert resolve_model(spec, "low") == "gpt-5.4-mini"
    assert resolve_model(spec, "medium") == "gpt-5.4"
    assert resolve_model(spec, "high") == "gpt-5.5"


def test_claude_code_defaults_unchanged() -> None:
    spec = get_harness("claude-code")
    assert spec.model_env == "ANTHROPIC_MODEL"
    assert spec.session_param_style == "claude_code"
    assert spec.model_via_session is False
    assert spec.env_overrides == {}


def test_is_registered_harness() -> None:
    assert is_registered_harness("claude-code") is True
    assert is_registered_harness("codex") is True
    assert is_registered_harness("hermes") is True
    assert is_registered_harness(None) is False


def test_get_harness_hermes() -> None:
    spec = get_harness("hermes")
    assert spec.name == "hermes"
    assert spec.launch_command == ("uvx", "--from", "hermes-agent[acp,mcp]==0.15.2", "hermes-acp")
    assert spec.native_acp is True
    assert spec.model_env is None
    assert spec.session_param_style == "standard"
    assert spec.model_via_session is False
    assert spec.profile_env == "HERMES_HOME"


def test_hermes_model_tiers_empty() -> None:
    spec = get_harness("hermes")
    assert spec.model_tiers == {}
    assert resolve_model(spec, "high") == "high"
    assert resolve_model(spec, None) is None
