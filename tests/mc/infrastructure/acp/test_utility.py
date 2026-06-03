from __future__ import annotations

from unittest.mock import patch

import pytest

from mc.infrastructure.acp.types import AcpTurnResult
from mc.infrastructure.acp.utility import extract_json, run_utility_turn
from mc.infrastructure.providers.errors import ProviderError


def _fake_client_factory(reply: str, captured: dict):
    class _FakeClient:
        def __init__(self, command, cwd, model=None, mcp_servers=None, allowed_tools=None):
            captured["model"] = model
            captured["allowed_tools"] = allowed_tools

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def prompt(self, text, on_update=None):
            return AcpTurnResult(
                text=reply,
                stop_reason="end_turn",
                session_id="s",
                usage={},
                cost_usd=None,
            )

    return _FakeClient


@pytest.mark.asyncio
async def test_returns_stripped_text(tmp_path):
    captured: dict = {}
    with patch(
        "mc.infrastructure.acp.client.AcpClient",
        _fake_client_factory("  hello world  ", captured),
    ):
        result = await run_utility_turn("hi", cwd=str(tmp_path))
    assert result == "hello world"


@pytest.mark.asyncio
async def test_low_tier_resolves_to_haiku_with_no_tools(tmp_path):
    captured: dict = {}
    with patch(
        "mc.infrastructure.acp.client.AcpClient",
        _fake_client_factory("ok", captured),
    ):
        await run_utility_turn("hi", tier="low", cwd=str(tmp_path))
    assert captured["model"] == "haiku"
    assert captured["allowed_tools"] == []


@pytest.mark.asyncio
async def test_empty_text_raises_provider_error(tmp_path):
    captured: dict = {}
    with patch(
        "mc.infrastructure.acp.client.AcpClient",
        _fake_client_factory("   ", captured),
    ):
        with pytest.raises(ProviderError):
            await run_utility_turn("hi", cwd=str(tmp_path))


def test_extract_json_tolerates_preamble():
    text = 'Sure, here you go:\n```json\n{"target_agent": "a", "ok": true}\n```\nDone.'
    assert extract_json(text) == {"target_agent": "a", "ok": True}


def test_extract_json_raises_on_garbage():
    with pytest.raises(ProviderError):
        extract_json("no json here at all")
