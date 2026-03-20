from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
from websockets.frames import Close

from mc.contexts.interactive.supervision_types import InteractiveSupervisionEvent
from mc.runtime.interactive import (
    InteractiveRuntime,
    InteractiveSocketServer,
    _BenignHandshakeAbortFilter,
    build_interactive_runtime,
)
from mc.types import AgentData


def test_build_interactive_runtime_creates_provider_agnostic_runtime() -> None:
    bridge = MagicMock()

    runtime = build_interactive_runtime(bridge, host="127.0.0.1", port=8877)

    assert isinstance(runtime, InteractiveRuntime)
    assert runtime.server.host == "127.0.0.1"
    assert runtime.server.port == 8877
    assert runtime.service is not None
    assert runtime.transport is not None
    assert "claude-code" in runtime.adapters
    assert "codex" in runtime.adapters
    assert "mc" in runtime.adapters
    assert runtime.adapters["codex"]._supervision_sink is runtime.supervisor


def test_build_interactive_runtime_wires_waiting_human_pause_semantics() -> None:
    bridge = MagicMock()
    bridge.query.return_value = {
        "session_id": "interactive_session:codex",
        "agent_name": "codex-reviewer",
        "task_id": "task-1",
        "step_id": "step-1",
        "provider": "codex",
        "scope_kind": "chat",
        "scope_id": "chat:codex-reviewer",
        "status": "attached",
        "surface": "chat",
        "tmux_session": "tmux:interactive_session:codex",
        "attach_token": "attach-token",
        "created_at": "2026-03-16T00:00:00Z",
    }
    bridge.get_task.return_value = {"id": "task-1", "status": "in_progress", "state_version": 2}

    runtime = build_interactive_runtime(bridge, host="127.0.0.1", port=8877)

    runtime.supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="paused_for_review",
            provider="codex",
            session_id="interactive_session:codex",
            summary="Need user confirmation before continuing.",
        )
    )

    bridge.transition_task_from_snapshot.assert_called_once()
    bridge.update_step_status.assert_called_once_with("step-1", "waiting_human")


def test_benign_handshake_abort_filter_drops_client_cancelled_handshake_errors() -> None:
    filter_ = _BenignHandshakeAbortFilter()
    record = logging.LogRecord(
        name="mc.runtime.interactive.websocket",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="opening handshake failed",
        args=(),
        exc_info=(
            ConnectionClosedError,
            ConnectionClosedError(None, None, None),
            None,
        ),
    )

    assert filter_.filter(record) is False


def test_benign_handshake_abort_filter_keeps_other_websocket_errors() -> None:
    filter_ = _BenignHandshakeAbortFilter()
    record = logging.LogRecord(
        name="mc.runtime.interactive.websocket",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="connection handler failed",
        args=(),
        exc_info=(RuntimeError, RuntimeError("boom"), None),
    )

    assert filter_.filter(record) is True


@pytest.mark.asyncio
async def test_interactive_socket_server_creates_or_reattaches_session_from_query_params() -> None:
    transport = MagicMock()
    transport.handle_connection = AsyncMock()
    coordinator = MagicMock()
    coordinator.create_or_attach = AsyncMock(
        return_value={"session_id": "interactive_session:claude"}
    )
    load_agent = MagicMock(
        return_value=AgentData(
            name="claude-pair",
            display_name="Claude Pair",
            role="Engineer",
            backend="claude-code",
        )
    )
    server = InteractiveSocketServer(
        transport=transport,
        coordinator=coordinator,
        load_agent=load_agent,
        host="127.0.0.1",
        port=8877,
    )
    connection = SimpleNamespace(
        request=SimpleNamespace(
            path=(
                "/interactive?provider=claude-code&agentName=claude-pair"
                "&scopeKind=chat&scopeId=chat:claude-pair&surface=chat&taskId=chat-claude-pair"
                "&columns=120&rows=40"
            )
        )
    )

    await server.handle_connection(connection)

    coordinator.create_or_attach.assert_awaited_once()
    transport.handle_connection.assert_awaited_once()
    call = transport.handle_connection.await_args
    assert call.kwargs["session_id"] == "interactive_session:claude"
    assert call.kwargs["size"].columns == 120
    assert call.kwargs["size"].rows == 40


@pytest.mark.asyncio
async def test_interactive_socket_server_surfaces_runtime_errors_to_client() -> None:
    transport = MagicMock()
    transport.handle_connection = AsyncMock()
    coordinator = MagicMock()
    coordinator.create_or_attach = AsyncMock(side_effect=RuntimeError("Claude binary missing"))
    load_agent = MagicMock(
        return_value=AgentData(
            name="claude-pair",
            display_name="Claude Pair",
            role="Engineer",
            backend="claude-code",
        )
    )
    connection = SimpleNamespace(
        request=SimpleNamespace(
            path=(
                "/interactive?provider=claude-code&agentName=claude-pair"
                "&scopeKind=chat&scopeId=chat:claude-pair&surface=chat&taskId=chat-claude-pair"
                "&columns=120&rows=40"
            )
        ),
        send=AsyncMock(),
        close=AsyncMock(),
    )
    server = InteractiveSocketServer(
        transport=transport,
        coordinator=coordinator,
        load_agent=load_agent,
        host="127.0.0.1",
        port=8877,
    )

    await server.handle_connection(connection)

    connection.send.assert_awaited_once()
    message = connection.send.await_args.args[0]
    assert "Claude binary missing" in message
    connection.close.assert_awaited_once_with()
    transport.handle_connection.assert_not_awaited()


@pytest.mark.asyncio
async def test_interactive_socket_server_parses_request_and_delegates() -> None:
    transport = MagicMock()
    transport.handle_connection = AsyncMock()
    server = InteractiveSocketServer(
        transport=transport,
        coordinator=MagicMock(),
        load_agent=MagicMock(),
        host="127.0.0.1",
        port=8877,
    )
    connection = SimpleNamespace(
        request=SimpleNamespace(
            path="/interactive?sessionId=interactive_session:claude&columns=120&rows=40"
        )
    )

    await server.handle_connection(connection)

    transport.handle_connection.assert_awaited_once()
    call = transport.handle_connection.await_args
    assert call.args[0] is connection
    assert call.kwargs["session_id"] == "interactive_session:claude"
    assert call.kwargs["attach_token"] is None
    assert call.kwargs["size"].columns == 120
    assert call.kwargs["size"].rows == 40


@pytest.mark.asyncio
async def test_interactive_socket_server_passes_attach_token_on_reconnect_requests() -> None:
    transport = MagicMock()
    transport.handle_connection = AsyncMock()
    server = InteractiveSocketServer(
        transport=transport,
        coordinator=MagicMock(),
        load_agent=MagicMock(),
        host="127.0.0.1",
        port=8877,
    )
    connection = SimpleNamespace(
        request=SimpleNamespace(
            path=(
                "/interactive?sessionId=interactive_session:claude"
                "&attachToken=attach-token-123&columns=120&rows=40"
            )
        )
    )

    await server.handle_connection(connection)

    call = transport.handle_connection.await_args
    assert call.kwargs["attach_token"] == "attach-token-123"


@pytest.mark.asyncio
async def test_interactive_socket_server_closes_unauthorized_attach_attempts() -> None:
    transport = MagicMock()
    transport.handle_connection = AsyncMock(side_effect=RuntimeError("not authorized"))
    server = InteractiveSocketServer(
        transport=transport,
        coordinator=MagicMock(),
        load_agent=MagicMock(),
        host="127.0.0.1",
        port=8877,
    )
    connection = SimpleNamespace(
        request=SimpleNamespace(
            path="/interactive?sessionId=interactive_session:claude&columns=120&rows=40"
        ),
        send=AsyncMock(),
        close=AsyncMock(),
    )

    await server.handle_connection(connection)

    connection.send.assert_awaited_once()
    assert "not authorized" in connection.send.await_args.args[0]
    connection.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_interactive_socket_server_ignores_normal_connection_close_during_error_handling() -> (
    None
):
    transport = MagicMock()
    transport.handle_connection = AsyncMock(side_effect=RuntimeError("not authorized"))
    server = InteractiveSocketServer(
        transport=transport,
        coordinator=MagicMock(),
        load_agent=MagicMock(),
        host="127.0.0.1",
        port=8877,
    )
    connection = SimpleNamespace(
        request=SimpleNamespace(
            path="/interactive?sessionId=interactive_session:claude&columns=120&rows=40"
        ),
        send=AsyncMock(
            side_effect=ConnectionClosedOK(
                rcvd=Close(code=1001, reason="going away"),
                sent=Close(code=1001, reason="going away"),
                rcvd_then_sent=True,
            )
        ),
        close=AsyncMock(),
    )

    await server.handle_connection(connection)

    connection.send.assert_awaited_once()
    connection.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_interactive_socket_server_start_and_stop() -> None:
    transport = MagicMock()
    ws_server = MagicMock()
    ws_server.wait_closed = AsyncMock()
    serve_cm = AsyncMock(return_value=ws_server)

    with patch("mc.runtime.interactive.websockets.serve", serve_cm):
        server = InteractiveSocketServer(
            transport=transport,
            coordinator=MagicMock(),
            load_agent=MagicMock(),
            host="127.0.0.1",
            port=8877,
        )
        await server.start()
        await server.stop()

    serve_cm.assert_awaited_once()
    ws_server.close.assert_called_once_with()
    ws_server.wait_closed.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_interactive_socket_server_passes_prompt_to_coordinator() -> None:
    transport = MagicMock()
    transport.handle_connection = AsyncMock()
    coordinator = MagicMock()
    coordinator.create_or_attach = AsyncMock(
        return_value={"session_id": "interactive_session:claude"}
    )
    load_agent = MagicMock(
        return_value=AgentData(
            name="nanobot",
            display_name="Bento",
            role="Assistant",
            backend="claude-code",
        )
    )
    server = InteractiveSocketServer(
        transport=transport,
        coordinator=coordinator,
        load_agent=load_agent,
        host="127.0.0.1",
        port=8877,
    )
    connection = SimpleNamespace(
        request=SimpleNamespace(
            path=(
                "/interactive?provider=claude-code&agentName=nanobot"
                "&scopeKind=chat&scopeId=create-agent:abc&surface=chat&taskId=create-agent:abc"
                "&columns=120&rows=40"
                "&prompt=Use+the+create-agent+skill"
            )
        )
    )

    await server.handle_connection(connection)

    coordinator.create_or_attach.assert_awaited_once()
    call_kwargs = coordinator.create_or_attach.await_args.kwargs
    assert call_kwargs["task_prompt"] == "Use the create-agent skill"
