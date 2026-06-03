"""Tests for auto-title generation in the orchestrator (heuristic default + LLM opt-in)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.runtime.orchestrator import generate_title_via_low_agent, heuristic_title


def _llm_enabled_bridge(*, agent_model):
    """Bridge whose settings report the LLM title toggle ON."""
    bridge = MagicMock()
    bridge.get_agent_by_name.return_value = {"model": agent_model}

    def _query(name, args=None):
        if name == "settings:get" and (args or {}).get("key") == "auto_title_enabled":
            return "true"
        return None

    bridge.query.side_effect = _query
    return bridge


async def _sync_to_thread(func, *args, **kwargs):
    return func(*args, **kwargs)


@pytest.mark.asyncio
async def test_generate_title_returns_llm_text():
    """With the toggle on, auto-title returns the text the utility turn produces."""
    mock_bridge = _llm_enabled_bridge(agent_model="anthropic/claude-haiku-3-5")

    with (
        patch(
            "mc.infrastructure.acp.utility.run_utility_turn",
            new=AsyncMock(return_value="Fix login validation bug"),
        ),
        patch("mc.runtime.orchestrator.asyncio.to_thread", side_effect=_sync_to_thread),
    ):
        result = await generate_title_via_low_agent(
            mock_bridge,
            "When users try to log in with an email that contains special characters "
            "like + or dots, the validation rejects them even though they are valid "
            "RFC 5322 email addresses. This needs to be fixed in the auth module.",
        )

    assert result == "Fix login validation bug"
    mock_bridge.get_agent_by_name.assert_called_once()


@pytest.mark.asyncio
async def test_generate_title_strips_quotes():
    """An LLM response with surrounding quotes is cleaned."""
    mock_bridge = _llm_enabled_bridge(agent_model="anthropic/claude-haiku-3-5")

    with (
        patch(
            "mc.infrastructure.acp.utility.run_utility_turn",
            new=AsyncMock(return_value='"Fix the login bug"'),
        ),
        patch("mc.runtime.orchestrator.asyncio.to_thread", side_effect=_sync_to_thread),
    ):
        result = await generate_title_via_low_agent(mock_bridge, "description")

    assert result == "Fix the login bug"


@pytest.mark.asyncio
async def test_generate_title_returns_none_when_agent_not_found():
    """With the toggle on but no low-agent, returns None without calling the LLM."""
    bridge = MagicMock()
    bridge.get_agent_by_name.return_value = None

    def _query(name, args=None):
        if name == "settings:get" and (args or {}).get("key") == "auto_title_enabled":
            return "true"
        return None

    bridge.query.side_effect = _query

    with patch("mc.runtime.orchestrator.asyncio.to_thread", side_effect=_sync_to_thread):
        result = await generate_title_via_low_agent(bridge, "Some task description")

    assert result is None


@pytest.mark.asyncio
async def test_generate_title_returns_none_on_llm_error():
    """When run_utility_turn raises, returns None (the function catches and returns None)."""
    from mc.infrastructure.providers.errors import ProviderError

    mock_bridge = _llm_enabled_bridge(agent_model="anthropic/claude-haiku-3-5")

    with (
        patch(
            "mc.infrastructure.acp.utility.run_utility_turn",
            new=AsyncMock(side_effect=ProviderError("timeout")),
        ),
        patch("mc.runtime.orchestrator.asyncio.to_thread", side_effect=_sync_to_thread),
    ):
        result = await generate_title_via_low_agent(mock_bridge, "Some task description")

    assert result is None


@pytest.mark.asyncio
async def test_generate_title_returns_none_on_empty_text():
    """When run_utility_turn returns empty string, returns None."""
    from mc.infrastructure.providers.errors import ProviderError

    mock_bridge = _llm_enabled_bridge(agent_model="anthropic/claude-haiku-3-5")

    with (
        patch(
            "mc.infrastructure.acp.utility.run_utility_turn",
            new=AsyncMock(side_effect=ProviderError("ACP utility turn returned empty text")),
        ),
        patch("mc.runtime.orchestrator.asyncio.to_thread", side_effect=_sync_to_thread),
    ):
        result = await generate_title_via_low_agent(mock_bridge, "Some task description")

    assert result is None


@pytest.mark.parametrize(
    "description,expected",
    [
        ("Fix the login bug", "Fix the login bug"),
        ("Fix the login bug. Then redeploy.", "Fix the login bug."),
        ("Can you add a dark mode toggle? It is requested.", "Can you add a dark mode toggle?"),
        ("# Add dark mode\n\nDetails here", "Add dark mode"),
        ("> quoted task line", "quoted task line"),
        ('"Refactor the parser"', "Refactor the parser"),
        ("\n\n  Indented first real line", "Indented first real line"),
        ("Implementar suporte a múltiplos idiomas", "Implementar suporte a múltiplos idiomas"),
        ("", None),
        ("   \n  \n", None),
    ],
)
def test_heuristic_title(description, expected):
    assert heuristic_title(description) == expected


def test_heuristic_title_caps_long_first_line():
    result = heuristic_title("x" * 200)
    assert result is not None
    assert len(result) <= 60
    assert result.endswith("...")


@pytest.mark.asyncio
async def test_generate_title_uses_heuristic_when_llm_disabled():
    """Default (auto_title_enabled unset) returns the heuristic and never calls the LLM."""
    mock_bridge = MagicMock()
    mock_bridge.query.side_effect = lambda name, args=None: None

    with (
        patch("mc.infrastructure.acp.utility.run_utility_turn") as mock_utility,
        patch("mc.runtime.orchestrator.asyncio.to_thread", side_effect=_sync_to_thread),
    ):
        result = await generate_title_via_low_agent(
            mock_bridge, "Fix the login bug. More detail follows."
        )

    assert result == "Fix the login bug."
    mock_utility.assert_not_called()
    mock_bridge.get_agent_by_name.assert_not_called()
