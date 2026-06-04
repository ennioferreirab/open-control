"""Tests for ACP harness env helpers in strategies/acp.py."""

from __future__ import annotations

import os

import pytest

from mc.application.execution.strategies.acp import _build_harness_env, _resolve_profile_home
from mc.infrastructure.acp.harness_registry import get_harness


def test_resolve_profile_home_uses_hermes_profiles_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_PROFILES_ROOT", "/custom/profiles")
    result = _resolve_profile_home("research")
    assert result == "/custom/profiles/research"


def test_resolve_profile_home_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_PROFILES_ROOT", raising=False)
    result = _resolve_profile_home("research")
    assert result == os.path.join(os.path.expanduser("~"), ".hermes", "profiles", "research")


def test_build_harness_env_no_profile_env_returns_static_overrides() -> None:
    spec = get_harness("claude-code")
    assert spec.profile_env is None
    env = _build_harness_env(spec, profile=None)
    assert env == dict(spec.env_overrides)


def test_build_harness_env_injects_hermes_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_PROFILES_ROOT", "/profiles")
    spec = get_harness("hermes")
    env = _build_harness_env(spec, profile="coder")
    assert env["HERMES_HOME"] == "/profiles/coder"


def test_build_harness_env_raises_when_profile_required_but_missing() -> None:
    spec = get_harness("hermes")
    with pytest.raises(ValueError, match="requires a profile"):
        _build_harness_env(spec, profile=None)


def test_build_harness_env_codex_static_overrides_unchanged() -> None:
    spec = get_harness("codex")
    assert spec.profile_env is None
    env = _build_harness_env(spec, profile=None)
    assert env == {"OPENAI_API_KEY": None, "CODEX_API_KEY": None}
