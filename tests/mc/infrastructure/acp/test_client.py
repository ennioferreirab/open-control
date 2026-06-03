"""Tests for the ACP transport client."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from acp.schema import (
    AgentMessageChunk,
    AllowedOutcome,
    AvailableCommandsUpdate,
    DeniedOutcome,
    PermissionOption,
    TextContentBlock,
    ToolCallUpdate,
    UsageUpdate,
)

from mc.infrastructure.acp.client import AcpClient, _AcpAdapter, _TurnState, _usage_to_dict
from mc.infrastructure.acp.types import AcpTurnResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_text_chunk(text: str, message_id: str = "msg-1") -> AgentMessageChunk:
    return AgentMessageChunk(
        content=TextContentBlock(type="text", text=text),
        message_id=message_id,
        session_update="agent_message_chunk",
    )


def _make_usage_update(amount: float = 0.001) -> UsageUpdate:
    from acp.schema import Cost

    return UsageUpdate(
        used=10, size=0, cost=Cost(amount=amount, currency="USD"), session_update="usage_update"
    )


def _make_available_commands_update() -> AvailableCommandsUpdate:
    return AvailableCommandsUpdate(
        available_commands=[], session_update="available_commands_update"
    )


def _make_permission_option(kind: str, option_id: str = "opt-1") -> PermissionOption:
    return PermissionOption(kind=kind, name=kind, option_id=option_id)


def _make_tool_call_update() -> ToolCallUpdate:
    return MagicMock(spec=ToolCallUpdate)


def _make_prompt_response(stop_reason: str = "end_turn") -> MagicMock:
    resp = MagicMock()
    resp.stop_reason = stop_reason
    usage = MagicMock()
    usage.input_tokens = 5
    usage.output_tokens = 3
    usage.total_tokens = 8
    usage.cached_read_tokens = None
    usage.cached_write_tokens = None
    usage.thought_tokens = None
    resp.usage = usage
    return resp


def _make_fake_conn(prompt_response: Any | None = None) -> AsyncMock:
    conn = AsyncMock()
    conn.initialize = AsyncMock(return_value=MagicMock())
    new_sess_resp = MagicMock()
    new_sess_resp.session_id = "test-session-id"
    conn.new_session = AsyncMock(return_value=new_sess_resp)
    conn.prompt = AsyncMock(return_value=prompt_response or _make_prompt_response())
    return conn


@asynccontextmanager
async def _fake_spawn(adapter: Any, conn: AsyncMock):
    """Context manager that simulates spawn_agent_process, yielding the given conn."""
    yield conn, MagicMock()


# ---------------------------------------------------------------------------
# _TurnState
# ---------------------------------------------------------------------------


def test_turn_state_assembled_text_concatenates_chunks() -> None:
    turn = _TurnState()
    turn.text_chunks = ["Hello", ", ", "world"]
    assert turn.assembled_text() == "Hello, world"


def test_turn_state_assembled_text_empty_when_no_chunks() -> None:
    assert _TurnState().assembled_text() == ""


# ---------------------------------------------------------------------------
# _AcpAdapter.session_update — chunk assembly
# ---------------------------------------------------------------------------


async def test_adapter_assembles_text_from_agent_message_chunks() -> None:
    adapter = _AcpAdapter()
    adapter._turn = _TurnState()

    await adapter.session_update("s1", _make_text_chunk("Hello"))
    await adapter.session_update("s1", _make_text_chunk(" world"))

    assert adapter._turn.assembled_text() == "Hello world"


async def test_adapter_ignores_empty_first_chunk() -> None:
    """An empty text in the first AgentMessageChunk must not be appended."""
    adapter = _AcpAdapter()
    adapter._turn = _TurnState()

    empty_chunk = _make_text_chunk("")
    await adapter.session_update("s1", empty_chunk)
    await adapter.session_update("s1", _make_text_chunk("Real text"))

    assert adapter._turn.assembled_text() == "Real text"
    assert len(adapter._turn.text_chunks) == 1


async def test_adapter_available_commands_update_not_assembled() -> None:
    """AvailableCommandsUpdate must not produce any text contribution."""
    adapter = _AcpAdapter()
    adapter._turn = _TurnState()

    await adapter.session_update("s1", _make_available_commands_update())
    await adapter.session_update("s1", _make_text_chunk("actual reply"))

    assert adapter._turn.assembled_text() == "actual reply"


async def test_adapter_available_commands_update_forwarded_to_on_update() -> None:
    received: list[Any] = []
    adapter = _AcpAdapter()
    adapter._turn = _TurnState(on_update=received.append)

    update = _make_available_commands_update()
    await adapter.session_update("s1", update)

    assert len(received) == 1
    assert received[0] is update


async def test_adapter_usage_update_sets_cost() -> None:
    adapter = _AcpAdapter()
    adapter._turn = _TurnState()

    await adapter.session_update("s1", _make_usage_update(amount=0.0042))

    assert adapter._turn.cost_usd == pytest.approx(0.0042)


async def test_adapter_usage_update_with_none_cost_does_not_set_cost() -> None:
    from acp.schema import UsageUpdate

    adapter = _AcpAdapter()
    adapter._turn = _TurnState()
    adapter._turn.cost_usd = 0.001

    no_cost_update = UsageUpdate(used=5, size=0, cost=None, session_update="usage_update")
    await adapter.session_update("s1", no_cost_update)

    assert adapter._turn.cost_usd == pytest.approx(0.001)


async def test_adapter_on_update_receives_all_update_types() -> None:
    received: list[Any] = []
    adapter = _AcpAdapter()
    adapter._turn = _TurnState(on_update=received.append)

    chunk = _make_text_chunk("hi")
    usage = _make_usage_update()
    commands = _make_available_commands_update()

    await adapter.session_update("s1", chunk)
    await adapter.session_update("s1", usage)
    await adapter.session_update("s1", commands)

    assert len(received) == 3
    assert received[0] is chunk
    assert received[1] is usage
    assert received[2] is commands


# ---------------------------------------------------------------------------
# _AcpAdapter.request_permission — auto-grant
# ---------------------------------------------------------------------------


async def test_permission_grants_first_allow_once_option() -> None:
    adapter = _AcpAdapter()
    opt = _make_permission_option("allow_once", "opt-allow")
    response = await adapter.request_permission(
        options=[opt],
        session_id="s1",
        tool_call=_make_tool_call_update(),
    )
    assert isinstance(response.outcome, AllowedOutcome)
    assert response.outcome.option_id == "opt-allow"


async def test_permission_grants_allow_always_option() -> None:
    adapter = _AcpAdapter()
    opt = _make_permission_option("allow_always", "opt-always")
    response = await adapter.request_permission(
        options=[opt],
        session_id="s1",
        tool_call=_make_tool_call_update(),
    )
    assert isinstance(response.outcome, AllowedOutcome)
    assert response.outcome.option_id == "opt-always"


async def test_permission_denies_when_no_allow_option() -> None:
    adapter = _AcpAdapter()
    opt = _make_permission_option("reject_once", "opt-reject")
    response = await adapter.request_permission(
        options=[opt],
        session_id="s1",
        tool_call=_make_tool_call_update(),
    )
    assert isinstance(response.outcome, DeniedOutcome)


async def test_permission_prefers_allow_over_reject_in_mixed_list() -> None:
    adapter = _AcpAdapter()
    opts = [
        _make_permission_option("reject_once", "opt-reject"),
        _make_permission_option("allow_once", "opt-allow"),
    ]
    response = await adapter.request_permission(
        options=opts,
        session_id="s1",
        tool_call=_make_tool_call_update(),
    )
    assert isinstance(response.outcome, AllowedOutcome)
    assert response.outcome.option_id == "opt-allow"


# ---------------------------------------------------------------------------
# _usage_to_dict
# ---------------------------------------------------------------------------


def test_usage_to_dict_returns_empty_for_none() -> None:
    assert _usage_to_dict(None) == {}


def test_usage_to_dict_includes_required_fields() -> None:
    usage = MagicMock()
    usage.input_tokens = 10
    usage.output_tokens = 5
    usage.total_tokens = 15
    usage.cached_read_tokens = None
    usage.cached_write_tokens = None
    usage.thought_tokens = None

    result = _usage_to_dict(usage)

    assert result["input_tokens"] == 10
    assert result["output_tokens"] == 5
    assert result["total_tokens"] == 15
    assert "cached_read_tokens" not in result
    assert "cached_write_tokens" not in result


def test_usage_to_dict_includes_optional_fields_when_set() -> None:
    usage = MagicMock()
    usage.input_tokens = 10
    usage.output_tokens = 5
    usage.total_tokens = 15
    usage.cached_read_tokens = 3
    usage.cached_write_tokens = 2
    usage.thought_tokens = 4

    result = _usage_to_dict(usage)

    assert result["cached_read_tokens"] == 3
    assert result["cached_write_tokens"] == 2
    assert result["thought_tokens"] == 4


# ---------------------------------------------------------------------------
# AcpClient — ANTHROPIC_MODEL env injection
# ---------------------------------------------------------------------------


async def test_acp_client_injects_anthropic_model_when_set() -> None:
    captured_env: dict[str, str] = {}
    conn = _make_fake_conn()

    def fake_spawn(adapter: Any, cmd: str, *args: str, env: dict | None = None, **kwargs: Any):
        if env:
            captured_env.update(env)

        @asynccontextmanager
        async def _ctx():
            yield conn, MagicMock()

        return _ctx()

    with patch("mc.infrastructure.acp.client.acp.spawn_agent_process", side_effect=fake_spawn):
        async with AcpClient(
            command=["npx", "-y", "@agentclientprotocol/claude-agent-acp"],
            cwd="/tmp",
            model="haiku",
        ):
            pass

    assert captured_env.get("ANTHROPIC_MODEL") == "haiku"


async def test_acp_client_does_not_inject_anthropic_model_when_none() -> None:
    captured_env: dict[str, str] = {}
    conn = _make_fake_conn()

    # Ensure ANTHROPIC_MODEL is not already in the test environment
    os.environ.pop("ANTHROPIC_MODEL", None)

    def fake_spawn(adapter: Any, cmd: str, *args: str, env: dict | None = None, **kwargs: Any):
        if env:
            captured_env.update(env)

        @asynccontextmanager
        async def _ctx():
            yield conn, MagicMock()

        return _ctx()

    with patch("mc.infrastructure.acp.client.acp.spawn_agent_process", side_effect=fake_spawn):
        async with AcpClient(
            command=["npx", "-y", "@agentclientprotocol/claude-agent-acp"],
            cwd="/tmp",
            model=None,
        ):
            pass

    assert "ANTHROPIC_MODEL" not in captured_env


# ---------------------------------------------------------------------------
# AcpClient.prompt — full turn result
# ---------------------------------------------------------------------------


async def test_prompt_returns_correct_acpturnresult() -> None:
    """Full synthetic turn: empty first chunk, real text, usage update, then response.

    conn.prompt fires updates through the adapter as a side effect before returning,
    matching real SDK behaviour where session/update notifications arrive during the
    prompt call.
    """
    conn = _make_fake_conn()

    captured_adapter: list[_AcpAdapter] = []

    def fake_spawn(adapter: Any, cmd: str, *args: str, env: dict | None = None, **kwargs: Any):
        captured_adapter.append(adapter)

        @asynccontextmanager
        async def _ctx():
            yield conn, MagicMock()

        return _ctx()

    async def fake_conn_prompt(**kwargs: Any) -> MagicMock:
        adapter = captured_adapter[0]
        empty = AgentMessageChunk(
            content=TextContentBlock(type="text", text=""),
            message_id=None,
            session_update="agent_message_chunk",
        )
        await adapter.session_update("test-session-id", empty)
        await adapter.session_update("test-session-id", _make_available_commands_update())
        await adapter.session_update("test-session-id", _make_text_chunk("Part one"))
        await adapter.session_update("test-session-id", _make_text_chunk(" Part two"))
        await adapter.session_update("test-session-id", _make_usage_update(0.007))
        return _make_prompt_response("end_turn")

    conn.prompt = AsyncMock(side_effect=fake_conn_prompt)

    with patch("mc.infrastructure.acp.client.acp.spawn_agent_process", side_effect=fake_spawn):
        async with AcpClient(
            command=["npx", "-y", "@agentclientprotocol/claude-agent-acp"],
            cwd="/tmp",
            model="haiku",
        ) as client:
            result = await client.prompt("Hello")

    assert isinstance(result, AcpTurnResult)
    assert result.text == "Part one Part two"
    assert result.stop_reason == "end_turn"
    assert result.session_id == "test-session-id"
    assert result.usage["input_tokens"] == 5
    assert result.usage["output_tokens"] == 3
    assert result.cost_usd == pytest.approx(0.007)


async def test_prompt_assembles_chunks_accumulated_during_conn_prompt() -> None:
    """Verify chunk accumulation when updates are fired synchronously via the adapter."""
    conn = _make_fake_conn()

    def fake_spawn(adapter: Any, cmd: str, *args: str, env: dict | None = None, **kwargs: Any):
        @asynccontextmanager
        async def _ctx():
            yield conn, MagicMock()

        return _ctx()

    with patch("mc.infrastructure.acp.client.acp.spawn_agent_process", side_effect=fake_spawn):
        async with AcpClient(
            command=["npx"],
            cwd="/tmp",
            model=None,
        ) as client:
            assert client._adapter is not None
            # Prime the adapter's _turn directly to simulate pre-prompt updates
            # (conn.prompt is mocked so it returns without firing session_update;
            # we verify that _TurnState is reset per prompt() call)
            client._adapter._turn.text_chunks = ["stale text"]
            client._adapter._turn.cost_usd = 99.0

            result = await client.prompt("any")

    # _TurnState was reset; stale chunks are gone
    assert result.text == ""
    assert result.cost_usd is None


async def test_prompt_passes_session_id_from_new_session() -> None:
    conn = _make_fake_conn()

    def fake_spawn(adapter: Any, cmd: str, *args: str, env: dict | None = None, **kwargs: Any):
        @asynccontextmanager
        async def _ctx():
            yield conn, MagicMock()

        return _ctx()

    with patch("mc.infrastructure.acp.client.acp.spawn_agent_process", side_effect=fake_spawn):
        async with AcpClient(command=["npx"], cwd="/tmp") as client:
            result = await client.prompt("Hi")

    assert result.session_id == "test-session-id"


async def test_prompt_outside_context_raises_runtime_error() -> None:
    client = AcpClient(command=["npx"], cwd="/tmp")
    with pytest.raises(RuntimeError, match="async context manager"):
        await client.prompt("Hi")


async def test_prompt_on_update_receives_updates() -> None:
    """on_update callback is called for each session/update fired during the turn."""
    conn = _make_fake_conn()
    received: list[Any] = []

    def fake_spawn(adapter: Any, cmd: str, *args: str, env: dict | None = None, **kwargs: Any):
        @asynccontextmanager
        async def _ctx():
            yield conn, MagicMock()

        return _ctx()

    with patch("mc.infrastructure.acp.client.acp.spawn_agent_process", side_effect=fake_spawn):
        async with AcpClient(command=["npx"], cwd="/tmp") as client:
            assert client._adapter is not None
            # Manually fire updates through the adapter to simulate SDK behaviour
            await client._adapter.session_update("test-session-id", _make_text_chunk("chunk one"))
            # Now call prompt; on_update is wired for this turn
            await client.prompt("Hello", on_update=received.append)
            # Fire one more update after prompt() resets the turn state
            await client._adapter.session_update("test-session-id", _make_text_chunk("chunk two"))

    # Only updates fired after prompt() was called reach on_update
    assert len(received) == 1
    assert isinstance(received[0], AgentMessageChunk)


# ---------------------------------------------------------------------------
# AcpClient — mcp_servers / claudeCode kwarg
# ---------------------------------------------------------------------------


async def test_new_session_called_with_mcp_servers_and_claude_code_kwarg() -> None:
    """When mcp_servers and allowed_tools are set, new_session receives claudeCode."""
    conn = _make_fake_conn()
    fake_server = MagicMock()

    def fake_spawn(adapter: Any, cmd: str, *args: str, env: dict | None = None, **kwargs: Any):
        @asynccontextmanager
        async def _ctx():
            yield conn, MagicMock()

        return _ctx()

    with patch("mc.infrastructure.acp.client.acp.spawn_agent_process", side_effect=fake_spawn):
        async with AcpClient(
            command=["npx"],
            cwd="/tmp",
            mcp_servers=[fake_server],
            allowed_tools=["mcp__mc__ask_user"],
        ):
            pass

    conn.new_session.assert_called_once()
    call_kwargs = conn.new_session.call_args.kwargs
    assert call_kwargs["mcp_servers"] == [fake_server]
    assert call_kwargs["claudeCode"] == {
        "options": {
            "strictMcpConfig": True,
            "allowedTools": ["mcp__mc__ask_user"],
        }
    }


async def test_new_session_called_without_claude_code_when_no_mcp() -> None:
    """When no mcp_servers or allowed_tools are set, new_session has no claudeCode kwarg."""
    conn = _make_fake_conn()

    def fake_spawn(adapter: Any, cmd: str, *args: str, env: dict | None = None, **kwargs: Any):
        @asynccontextmanager
        async def _ctx():
            yield conn, MagicMock()

        return _ctx()

    with patch("mc.infrastructure.acp.client.acp.spawn_agent_process", side_effect=fake_spawn):
        async with AcpClient(command=["npx"], cwd="/tmp"):
            pass

    conn.new_session.assert_called_once()
    call_kwargs = conn.new_session.call_args.kwargs
    assert "claudeCode" not in call_kwargs
    assert call_kwargs["mcp_servers"] == []
