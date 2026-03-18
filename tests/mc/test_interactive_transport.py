from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from websockets.exceptions import ConnectionClosedOK
from websockets.frames import Close

from mc.infrastructure.interactive import TerminalSize
from mc.runtime.interactive_transport import (
    InteractiveSocketTransport,
    _resolve_transport_log_level,
)


class FakeWebSocket:
    def __init__(self, messages: list[str | bytes]) -> None:
        self._messages = list(messages)
        self.sent: list[str | bytes] = []
        self.closed = False
        self.close_calls: list[tuple[int, str]] = []
        self._closed_event: asyncio.Event = asyncio.Event()

    def __aiter__(self) -> FakeWebSocket:
        return self

    async def __anext__(self) -> str | bytes:
        if self.closed or not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)

    async def send(self, message: str | bytes) -> None:
        self.sent.append(message)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True
        self.close_calls.append((code, reason))
        self._closed_event.set()

    async def wait_closed(self) -> None:
        await self._closed_event.wait()


class BlockingWebSocket(FakeWebSocket):
    def __init__(self) -> None:
        super().__init__([])

    async def __anext__(self) -> str | bytes:
        await self._closed_event.wait()
        raise StopAsyncIteration


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


@pytest.mark.asyncio
async def test_handle_connection_logs_debug_latency_from_input_to_first_output(caplog) -> None:
    service = MagicMock()
    attached = SimpleNamespace(
        terminal=SimpleNamespace(master_fd=10, close=MagicMock()),
        metadata={
            "session_id": "interactive_session:claude",
            "attach_token": "attach-token-123",
        },
    )
    service.attach_session.return_value = attached
    websocket = FakeWebSocket([json.dumps({"type": "input", "data": "h"})])
    transport = InteractiveSocketTransport(
        session_service=service,
        read_chunk=MagicMock(side_effect=[b"hello", b""]),
        write_chunk=MagicMock(),
        resize_handler=MagicMock(),
        monotonic_time=MagicMock(side_effect=[10.0, 10.25]),
    )

    with caplog.at_level(logging.DEBUG, logger="mc.runtime.interactive_transport"):
        await transport.handle_connection(
            websocket,
            session_id="interactive_session:claude",
            size=TerminalSize(columns=120, rows=40),
            attach_token="attach-token-123",
            timestamp_factory=lambda: "2026-03-12T23:10:00+00:00",
        )

    assert "first output after input" in caplog.text
    assert "interactive_session:claude" in caplog.text
    assert "wait_ms=250.0" in caplog.text


@pytest.mark.asyncio
async def test_handle_connection_logs_attach_and_detach_lifecycle(caplog) -> None:
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
    transport = InteractiveSocketTransport(
        session_service=service,
        read_chunk=MagicMock(side_effect=[b""]),
        write_chunk=MagicMock(),
        resize_handler=MagicMock(),
    )

    with caplog.at_level(logging.DEBUG, logger="mc.runtime.interactive_transport"):
        await transport.handle_connection(
            websocket,
            session_id="interactive_session:claude",
            size=TerminalSize(columns=120, rows=40),
            attach_token="attach-token-123",
            timestamp_factory=lambda: "2026-03-12T23:10:00+00:00",
        )

    assert "connection attached" in caplog.text
    assert "active_connections=1" in caplog.text
    assert "connection detached" in caplog.text
    assert "active_connections=0" in caplog.text
    assert "interactive_session:claude" in caplog.text


@pytest.mark.asyncio
async def test_handle_connection_supersedes_existing_session_connection(caplog) -> None:
    service = MagicMock()
    first_attached = SimpleNamespace(
        terminal=SimpleNamespace(master_fd=10, close=MagicMock()),
        metadata={
            "session_id": "interactive_session:claude",
            "attach_token": "attach-token-123",
        },
    )
    second_attached = SimpleNamespace(
        terminal=SimpleNamespace(master_fd=11, close=MagicMock()),
        metadata={
            "session_id": "interactive_session:claude",
            "attach_token": "attach-token-123",
        },
    )
    service.attach_session.side_effect = [first_attached, second_attached]
    first_websocket = BlockingWebSocket()
    second_websocket = BlockingWebSocket()
    transport = InteractiveSocketTransport(
        session_service=service,
        read_chunk=MagicMock(side_effect=[b"", b""]),
        write_chunk=MagicMock(),
        resize_handler=MagicMock(),
    )

    with caplog.at_level(logging.DEBUG, logger="mc.runtime.interactive_transport"):
        first_task = asyncio.create_task(
            transport.handle_connection(
                first_websocket,
                session_id="interactive_session:claude",
                size=TerminalSize(columns=120, rows=40),
                attach_token="attach-token-123",
                timestamp_factory=lambda: "2026-03-12T23:10:00+00:00",
            )
        )
        await asyncio.sleep(0)

        second_task = asyncio.create_task(
            transport.handle_connection(
                second_websocket,
                session_id="interactive_session:claude",
                size=TerminalSize(columns=120, rows=40),
                attach_token="attach-token-123",
                timestamp_factory=lambda: "2026-03-12T23:10:01+00:00",
            )
        )
        await asyncio.sleep(0)
        await second_websocket.close()
        await asyncio.gather(first_task, second_task)

    assert first_websocket.close_calls == [(1012, "Superseded by a newer connection")]
    service.detach_session.assert_called_once_with(
        "interactive_session:claude",
        timestamp="2026-03-12T23:10:01+00:00",
    )
    assert "superseding connection" in caplog.text
    assert "active_connections=1" in caplog.text


def test_resolve_transport_log_level_defaults_to_none(monkeypatch) -> None:
    monkeypatch.delenv("MC_INTERACTIVE_TRANSPORT_LOG_LEVEL", raising=False)
    assert _resolve_transport_log_level() is None


def test_resolve_transport_log_level_reads_debug(monkeypatch) -> None:
    monkeypatch.setenv("MC_INTERACTIVE_TRANSPORT_LOG_LEVEL", "DEBUG")
    assert _resolve_transport_log_level() == logging.DEBUG
