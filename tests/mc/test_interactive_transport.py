from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from websockets.exceptions import ConnectionClosedOK
from websockets.frames import Close

from mc.infrastructure.interactive import TerminalSize
from mc.runtime.interactive_transport import InteractiveSocketTransport


class FakeWebSocket:
    def __init__(self, messages: list[str | bytes]) -> None:
        self._messages = list(messages)
        self.sent: list[str | bytes] = []

    def __aiter__(self) -> "FakeWebSocket":
        return self

    async def __anext__(self) -> str | bytes:
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)

    async def send(self, message: str | bytes) -> None:
        self.sent.append(message)


@pytest.mark.asyncio
async def test_handle_connection_attaches_session_and_relays_bytes() -> None:
    service = MagicMock()
    attached = SimpleNamespace(
        terminal=SimpleNamespace(master_fd=10, close=MagicMock()),
        metadata={
            "session_id": "interactive_session:claude",
            "attach_token": "attach-token-123",
        },
    )
    service.attach_session.return_value = attached
    websocket = FakeWebSocket([])
    read_chunk = MagicMock(side_effect=[b"hello", b""])
    transport = InteractiveSocketTransport(
        session_service=service,
        read_chunk=read_chunk,
        write_chunk=MagicMock(),
        resize_handler=MagicMock(),
    )

    await transport.handle_connection(
        websocket,
        session_id="interactive_session:claude",
        size=TerminalSize(columns=120, rows=40),
        attach_token="attach-token-123",
        timestamp_factory=lambda: "2026-03-12T23:10:00+00:00",
    )

    service.attach_session.assert_called_once_with(
        "interactive_session:claude",
        size=TerminalSize(columns=120, rows=40),
        attach_token="attach-token-123",
        timestamp="2026-03-12T23:10:00+00:00",
    )
    assert websocket.sent[0] == json.dumps(
        {
            "type": "attached",
            "sessionId": "interactive_session:claude",
            "attachToken": "attach-token-123",
        }
    )
    assert websocket.sent[1] == b"hello"
    service.detach_session.assert_called_once_with(
        "interactive_session:claude",
        timestamp="2026-03-12T23:10:00+00:00",
    )
    attached.terminal.close.assert_called_once_with()


@pytest.mark.asyncio
async def test_handle_connection_writes_input_and_applies_resize() -> None:
    service = MagicMock()
    attached = SimpleNamespace(
        terminal=SimpleNamespace(master_fd=10, close=MagicMock()),
        metadata={
            "session_id": "interactive_session:claude",
            "attach_token": "attach-token-123",
        },
    )
    service.attach_session.return_value = attached
    websocket = FakeWebSocket(
        [
            json.dumps({"type": "input", "data": "ls -la\n"}),
            json.dumps({"type": "resize", "columns": 140, "rows": 50}),
        ]
    )
    write_chunk = MagicMock()
    resize_handler = MagicMock()
    transport = InteractiveSocketTransport(
        session_service=service,
        read_chunk=MagicMock(side_effect=[b""]),
        write_chunk=write_chunk,
        resize_handler=resize_handler,
    )

    await transport.handle_connection(
        websocket,
        session_id="interactive_session:claude",
        size=TerminalSize(columns=120, rows=40),
        attach_token="attach-token-123",
        timestamp_factory=lambda: "2026-03-12T23:10:00+00:00",
    )

    write_chunk.assert_called_once_with(10, b"ls -la\n")
    resize_handler.assert_called_once_with(10, TerminalSize(columns=140, rows=50))


@pytest.mark.asyncio
async def test_handle_connection_closes_attached_terminal_on_client_error() -> None:
    service = MagicMock()
    attached = SimpleNamespace(
        terminal=SimpleNamespace(master_fd=10, close=MagicMock()),
        metadata={
            "session_id": "interactive_session:claude",
            "attach_token": "attach-token-123",
        },
    )
    service.attach_session.return_value = attached
    websocket = FakeWebSocket([])
    send = AsyncMock(side_effect=RuntimeError("socket closed"))
    websocket.send = send
    transport = InteractiveSocketTransport(
        session_service=service,
        read_chunk=MagicMock(side_effect=[b"hello"]),
        write_chunk=MagicMock(),
        resize_handler=MagicMock(),
    )

    with pytest.raises(RuntimeError, match="socket closed"):
        await transport.handle_connection(
            websocket,
            session_id="interactive_session:claude",
            size=TerminalSize(columns=120, rows=40),
            attach_token="attach-token-123",
            timestamp_factory=lambda: "2026-03-12T23:10:00+00:00",
        )

    service.mark_session_crashed.assert_called_once_with(
        "interactive_session:claude",
        timestamp="2026-03-12T23:10:00+00:00",
    )
    attached.terminal.close.assert_called_once_with()


@pytest.mark.asyncio
async def test_handle_connection_treats_normal_client_disconnect_as_detach() -> None:
    service = MagicMock()
    attached = SimpleNamespace(
        terminal=SimpleNamespace(master_fd=10, close=MagicMock()),
        metadata={
            "session_id": "interactive_session:claude",
            "attach_token": "attach-token-123",
        },
    )
    service.attach_session.return_value = attached
    websocket = FakeWebSocket([])
    websocket.send = AsyncMock(
        side_effect=[
            None,
            ConnectionClosedOK(
                rcvd=Close(code=1001, reason="going away"),
                sent=Close(code=1001, reason="going away"),
                rcvd_then_sent=True,
            ),
        ]
    )
    transport = InteractiveSocketTransport(
        session_service=service,
        read_chunk=MagicMock(side_effect=[b"hello"]),
        write_chunk=MagicMock(),
        resize_handler=MagicMock(),
    )

    await transport.handle_connection(
        websocket,
        session_id="interactive_session:claude",
        size=TerminalSize(columns=120, rows=40),
        attach_token="attach-token-123",
        timestamp_factory=lambda: "2026-03-12T23:10:00+00:00",
    )

    service.detach_session.assert_called_once_with(
        "interactive_session:claude",
        timestamp="2026-03-12T23:10:00+00:00",
    )
    service.mark_session_crashed.assert_not_called()
    attached.terminal.close.assert_called_once_with()
