"""Tests for sync-time model resolution per backend."""

from __future__ import annotations

from mc.infrastructure.agent_bootstrap import _resolve_synced_model

DEFAULT = "cc/claude-sonnet-4-6"


def test_claude_code_unset_inherits_default() -> None:
    assert _resolve_synced_model("claude-code", None, DEFAULT) == DEFAULT


def test_unset_backend_defaults_to_claude_code_and_inherits() -> None:
    assert _resolve_synced_model(None, None, DEFAULT) == DEFAULT


def test_claude_code_bare_name_gets_prefixed_default() -> None:
    assert _resolve_synced_model("claude-code", "claude-sonnet-4-6", DEFAULT) == DEFAULT


def test_claude_code_explicit_model_kept() -> None:
    assert _resolve_synced_model("claude-code", "cc/opus", DEFAULT) == "cc/opus"


def test_codex_unset_stays_none() -> None:
    """A codex agent must not inherit the cc/ default — it would mis-route."""
    assert _resolve_synced_model("codex", None, DEFAULT) is None


def test_codex_explicit_model_kept() -> None:
    assert _resolve_synced_model("codex", "high", DEFAULT) == "high"
    assert _resolve_synced_model("codex", "gpt-5.5", DEFAULT) == "gpt-5.5"
