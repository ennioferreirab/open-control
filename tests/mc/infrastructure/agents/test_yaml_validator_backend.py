"""Tests for the agent backend enum in yaml_validator."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mc.infrastructure.agents.yaml_validator import AgentConfig


def _config(**overrides: object) -> AgentConfig:
    base: dict[str, object] = {"name": "a", "role": "Engineer", "prompt": "do it"}
    base.update(overrides)
    return AgentConfig(**base)


def test_backend_codex_accepted() -> None:
    assert _config(backend="codex").backend == "codex"


def test_backend_claude_code_accepted() -> None:
    assert _config(backend="claude-code").backend == "claude-code"


def test_backend_none_accepted() -> None:
    assert _config(backend=None).backend is None


def test_backend_unknown_rejected() -> None:
    with pytest.raises(ValidationError, match="Invalid backend"):
        _config(backend="nope")


def test_backend_hermes_with_profile_accepted() -> None:
    config = _config(backend="hermes", profile="my-profile")
    assert config.backend == "hermes"
    assert config.profile == "my-profile"


def test_backend_hermes_without_profile_rejected() -> None:
    with pytest.raises(ValidationError, match="profile"):
        _config(backend="hermes")


def test_profile_stripped_of_whitespace() -> None:
    config = _config(backend="hermes", profile="  my-profile  ")
    assert config.profile == "my-profile"


def test_profile_blank_becomes_none() -> None:
    with pytest.raises(ValidationError, match="profile"):
        _config(backend="hermes", profile="   ")


def test_hermes_agent_data_has_profile() -> None:
    from mc.infrastructure.agents.yaml_validator import _config_to_agent_data

    config = _config(backend="hermes", profile="research")
    result = _config_to_agent_data(config)
    assert not isinstance(result, list)
    assert result.backend == "hermes"
    assert result.profile == "research"
