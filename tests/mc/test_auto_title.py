"""Tests for auto-title generation in the orchestrator (heuristic default + LLM opt-in)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.runtime.orchestrator import generate_title_via_low_agent, heuristic_title

_TIERS = {
    "standard-low": "anthropic/claude-haiku-3-5",
    "standard-medium": "anthropic/claude-sonnet-4-6",
    "standard-high": "anthropic/claude-opus-4-6",
}


def _llm_enabled_bridge(*, agent_model, tiers=None):
    """Bridge whose settings report the LLM title toggle ON and the given tier map."""
    bridge = MagicMock()
    bridge.get_agent_by_name.return_value = {"model": agent_model}
    tiers_json = json.dumps(_TIERS if tiers is None else tiers)

    def _query(name, args=None):
        if name == "settings:get" and (args or {}).get("key") == "auto_title_enabled":
            return "true"
        return tiers_json

    bridge.query.side_effect = _query
    return bridge


async def _sync_to_thread(func, *args, **kwargs):
    return func(*args, **kwargs)


@pytest.mark.asyncio
async def test_generate_title_via_low_agent_calls_llm_with_low_tier():
    """With the toggle on, auto-title uses the low-agent model resolved from its tier."""
    mock_bridge = _llm_enabled_bridge(agent_model="tier:standard-low")

    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.finish_reason = "stop"
    mock_response.content = "Fix login validation bug"
    mock_provider.chat = AsyncMock(return_value=mock_response)

    with patch(
        "mc.runtime.orchestrator.create_provider",
        return_value=(mock_provider, "anthropic/claude-haiku-3-5"),
    ) as mock_create:
        with patch("mc.runtime.orchestrator.asyncio.to_thread", side_effect=_sync_to_thread):
            result = await generate_title_via_low_agent(
                mock_bridge,
                "When users try to log in with an email that contains special characters "
                "like + or dots, the validation rejects them even though they are valid "
                "RFC 5322 email addresses. This needs to be fixed in the auth module.",
            )

    assert result == "Fix login validation bug"
    mock_bridge.get_agent_by_name.assert_called_once()
    mock_create.assert_called_once_with(model="anthropic/claude-haiku-3-5")
    mock_provider.chat.assert_called_once()
    assert mock_provider.chat.call_args.kwargs["max_tokens"] == 60


@pytest.mark.asyncio
async def test_generate_title_via_low_agent_falls_back_to_default_on_missing_tier():
    """If the tier resolves to null in model_tiers, falls back to the default model."""
    mock_bridge = _llm_enabled_bridge(
        agent_model="tier:standard-low",
        tiers={"standard-low": None, "standard-medium": "anthropic/claude-sonnet-4-6"},
    )

    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.finish_reason = "stop"
    mock_response.content = "Short description title"
    mock_provider.chat = AsyncMock(return_value=mock_response)

    with patch(
        "mc.runtime.orchestrator.create_provider",
        return_value=(mock_provider, "default-model"),
    ) as mock_create:
        with patch("mc.runtime.orchestrator.asyncio.to_thread", side_effect=_sync_to_thread):
            result = await generate_title_via_low_agent(mock_bridge, "Some task description")

    assert result == "Short description title"
    mock_create.assert_called_once_with(model=None)


@pytest.mark.asyncio
async def test_generate_title_via_low_agent_returns_none_when_agent_not_found():
    """With the toggle on but no low-agent, returns None without calling the LLM."""
    mock_bridge = _llm_enabled_bridge(agent_model=None)
    mock_bridge.get_agent_by_name.return_value = None

    with patch("mc.runtime.orchestrator.asyncio.to_thread", side_effect=_sync_to_thread):
        result = await generate_title_via_low_agent(mock_bridge, "Some task description")

    assert result is None


@pytest.mark.asyncio
async def test_generate_title_via_low_agent_strips_quotes():
    """An LLM response with surrounding quotes is cleaned."""
    mock_bridge = _llm_enabled_bridge(agent_model="anthropic/claude-haiku-3-5")

    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.finish_reason = "stop"
    mock_response.content = '"Fix the login bug"'
    mock_provider.chat = AsyncMock(return_value=mock_response)

    with patch(
        "mc.runtime.orchestrator.create_provider",
        return_value=(mock_provider, "anthropic/claude-haiku-3-5"),
    ):
        with patch("mc.runtime.orchestrator.asyncio.to_thread", side_effect=_sync_to_thread):
            result = await generate_title_via_low_agent(mock_bridge, "description")

    assert result == "Fix the login bug"


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

    with patch("mc.runtime.orchestrator.create_provider") as mock_create:
        with patch("mc.runtime.orchestrator.asyncio.to_thread", side_effect=_sync_to_thread):
            result = await generate_title_via_low_agent(
                mock_bridge, "Fix the login bug. More detail follows."
            )

    assert result == "Fix the login bug."
    mock_create.assert_not_called()
    mock_bridge.get_agent_by_name.assert_not_called()
