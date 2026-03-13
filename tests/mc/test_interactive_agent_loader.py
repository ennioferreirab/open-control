from __future__ import annotations

from unittest.mock import MagicMock, patch

from mc.contexts.interactive.agent_loader import load_interactive_agent


def test_load_interactive_agent_reuses_local_agent_data_and_convex_overrides() -> None:
    local_agent = MagicMock(
        name="claude-pair",
        display_name="Claude Pair",
        role="Engineer",
        prompt="Local prompt",
        model="cc/claude-haiku-4-5",
        skills=["local-skill"],
        backend="claude-code",
    )
    bridge = MagicMock()
    bridge.get_agent_by_name.return_value = {
        "prompt": "Convex prompt",
        "model": "cc/claude-sonnet-4-6",
        "skills": ["convex-skill"],
    }

    with patch(
        "mc.contexts.interactive.agent_loader.load_agent_data",
        return_value=local_agent,
    ):
        result = load_interactive_agent("claude-pair", provider="claude-code", bridge=bridge)

    assert result is local_agent
    assert result.prompt == "Convex prompt"
    assert result.model == "cc/claude-sonnet-4-6"
    assert result.skills == ["convex-skill"]
    assert result.backend == "claude-code"


def test_load_interactive_agent_builds_synthetic_provider_agent_when_yaml_missing() -> None:
    bridge = MagicMock()
    bridge.get_agent_by_name.return_value = {
        "display_name": "Claude Pair",
        "role": "Engineer",
        "model": "cc/claude-sonnet-4-6",
        "prompt": "Convex prompt",
        "skills": ["convex-skill"],
    }

    with patch(
        "mc.contexts.interactive.agent_loader.load_agent_data",
        return_value=None,
    ):
        result = load_interactive_agent("claude-pair", provider="claude-code", bridge=bridge)

    assert result is not None
    assert result.name == "claude-pair"
    assert result.display_name == "Claude Pair"
    assert result.role == "Engineer"
    assert result.model == "cc/claude-sonnet-4-6"
    assert result.prompt == "Convex prompt"
    assert result.skills == ["convex-skill"]
    assert result.backend == "claude-code"
