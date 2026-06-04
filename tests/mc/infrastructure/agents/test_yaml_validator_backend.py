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
        _config(backend="hermes")
