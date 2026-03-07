"""Tests for auto-title generation in the orchestrator (via low-agent delegation)."""

import json
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from mc.runtime.orchestrator import generate_title_via_low_agent


@pytest.mark.asyncio
async def test_generate_title_via_low_agent_calls_llm_with_low_tier():
    """Auto-title uses the model from low-agent (resolved from tier) when configured."""
    mock_bridge = MagicMock()
    mock_bridge.get_agent_by_name.return_value = {"model": "tier:standard-low"}
    mock_bridge.query.return_value = json.dumps({
        "standard-low": "anthropic/claude-haiku-3-5",
        "standard-medium": "anthropic/claude-sonnet-4-6",
        "standard-high": "anthropic/claude-opus-4-6",
    })

    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.finish_reason = "stop"
    mock_response.content = "Fix login validation bug"
    mock_provider.chat = AsyncMock(return_value=mock_response)

    async def _sync_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

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
    call_args = mock_provider.chat.call_args
    assert call_args.kwargs["max_tokens"] == 60


@pytest.mark.asyncio
async def test_generate_title_via_low_agent_falls_back_to_default_on_missing_tier():
    """If tier resolves to null in model_tiers, falls back to default model (model=None)."""
    mock_bridge = MagicMock()
    mock_bridge.get_agent_by_name.return_value = {"model": "tier:standard-low"}
    mock_bridge.query.return_value = json.dumps({
        "standard-low": None,
        "standard-medium": "anthropic/claude-sonnet-4-6",
    })

    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.finish_reason = "stop"
    mock_response.content = "Short description title"
    mock_provider.chat = AsyncMock(return_value=mock_response)

    async def _sync_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    with patch(
        "mc.runtime.orchestrator.create_provider",
        return_value=(mock_provider, "default-model"),
    ) as mock_create:
        with patch("mc.runtime.orchestrator.asyncio.to_thread", side_effect=_sync_to_thread):
            result = await generate_title_via_low_agent(mock_bridge, "Some task description")

    assert result == "Short description title"
    # Falls back to model=None (use provider's default model)
    mock_create.assert_called_once_with(model=None)


@pytest.mark.asyncio
async def test_generate_title_via_low_agent_returns_none_when_agent_not_found():
    """If low-agent is not found, returns None without calling the LLM."""
    mock_bridge = MagicMock()
    mock_bridge.get_agent_by_name.return_value = None

    async def _sync_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    with patch("mc.runtime.orchestrator.asyncio.to_thread", side_effect=_sync_to_thread):
        result = await generate_title_via_low_agent(mock_bridge, "Some task description")

    assert result is None


@pytest.mark.asyncio
async def test_generate_title_via_low_agent_strips_quotes():
    """LLM response with surrounding quotes should be cleaned."""
    mock_bridge = MagicMock()
    mock_bridge.get_agent_by_name.return_value = {"model": "anthropic/claude-haiku-3-5"}

    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.finish_reason = "stop"
    mock_response.content = '"Fix the login bug"'
    mock_provider.chat = AsyncMock(return_value=mock_response)

    async def _sync_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    with patch(
        "mc.runtime.orchestrator.create_provider",
        return_value=(mock_provider, "anthropic/claude-haiku-3-5"),
    ):
        with patch("mc.runtime.orchestrator.asyncio.to_thread", side_effect=_sync_to_thread):
            result = await generate_title_via_low_agent(mock_bridge, "description")

    assert result == "Fix the login bug"
