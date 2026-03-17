"""Runtime-owned socket transport for interactive PTY sessions.

.. deprecated::
    Superseded by the provider CLI process supervisor (Stories 28.1-28.6).
    The provider CLI live-share model streams output directly through the MC
    gateway instead of a dedicated PTY/WebSocket server. Retained while
    ``build_interactive_runtime()`` is still wired. Do NOT add new callers.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import time
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from websockets.exceptions import ConnectionClosed

from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.infrastructure.interactive import TerminalSize, resize_terminal

logger = logging.getLogger(__name__)
_ACTIVE_SESSION_CONNECTIONS: Counter[str] = Counter()


def _resolve_transport_log_level(env_var: str = "MC_INTERACTIVE_TRANSPORT_LOG_LEVEL") -> int | None:
    """Resolve an optional per-module log level override for interactive transport."""

    level_name = os.environ.get(env_var, "").strip().upper()
    if not level_name:
        return None
    level = getattr(logging, level_name, None)
    return level if isinstance(level, int) else None


class InteractiveSocketTransport:
    """Bridge browser websocket traffic to a tmux-attached PTY."""

    def __init__(
        self,
        *,
        session_service: Any,
        read_chunk: Callable[[int, int], bytes] = os.read,
        write_chunk: Callable[[int, bytes], int] = os.write,
        resize_handler: Callable[[int, TerminalSize], None] = resize_terminal,
        monotonic_time: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._session_service = session_service
        self._read_chunk = read_chunk
        self._write_chunk = write_chunk
        self._resize_handler = resize_handler
        self._monotonic_time = monotonic_time
        self._active_websockets: dict[str, Any] = {}
        self._pending_terminations: set[str] = set()
        self._session_locks: dict[str, asyncio.Lock] = {}
        module_log_level = _resolve_transport_log_level()
        if module_log_level is not None:
            logger.setLevel(module_log_level)

    async def handle_connection(
        self,
        websocket: Any,
        *,
        session_id: str,
        size: TerminalSize,
        attach_token: str | None = None,
        timestamp_factory: Callable[[], str] | None = None,
    ) -> None:
        now = timestamp_factory or (lambda: datetime.now(UTC).isoformat())
        input_batch: dict[str, dict[str, float | int] | None] = {"pending": None}
        connection_id = hex(id(websocket))
        attached = self._session_service.attach_session(
            session_id,
            size=size,
            attach_token=attach_token,
            timestamp=now(),
        )
        await self._activate_connection(session_id, websocket, connection_id)
        _ACTIVE_SESSION_CONNECTIONS[session_id] += 1
        logger.debug(
            "[interactive] connection attached connection_id=%s session=%s master_fd=%s active_connections=%d",
            connection_id,
            session_id,
            attached.terminal.master_fd,
            _ACTIVE_SESSION_CONNECTIONS[session_id],
        )
        output_task = asyncio.create_task(
            self._relay_output(
                attached.terminal.master_fd,
                websocket,
                session_id=session_id,
                input_batch=input_batch,
            )
        )
        crashed = False

        try:
            await websocket.send(
                json.dumps(
                    {
                        "type": "attached",
                        "sessionId": session_id,
                        "attachToken": attached.metadata.get("attach_token"),
                    }
                )
            )
            async for message in websocket:
                await self._handle_client_message(
                    attached.terminal.master_fd,
                    message,
                    session_id=session_id,
                    input_batch=input_batch,
                )
            await output_task
        except ConnectionClosed:
            pass
        except Exception:
            crashed = True
            self._session_service.mark_session_crashed(session_id, timestamp=now())
            raise
        finally:
            output_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, ConnectionClosed):
                await output_task
            await self._deactivate_connection(session_id, websocket)
            _ACTIVE_SESSION_CONNECTIONS[session_id] -= 1
            active_connections = _ACTIVE_SESSION_CONNECTIONS[session_id]
            if active_connections <= 0:
                _ACTIVE_SESSION_CONNECTIONS.pop(session_id, None)
                active_connections = 0
            if not crashed:
                should_terminate = session_id in self._pending_terminations
                if should_terminate:
                    self._pending_terminations.discard(session_id)
                if active_connections == 0 and should_terminate:
                    with contextlib.suppress(Exception):
                        await self._session_service.terminate_session(
                            self._resolve_identity(session_id),
                            timestamp=now(),
                        )
                    logger.debug(
                        "[interactive] session terminated connection_id=%s session=%s",
                        connection_id,
                        session_id,
                    )
                elif active_connections == 0:
                    self._session_service.detach_session(session_id, timestamp=now())
                logger.debug(
                    "[interactive] connection detached connection_id=%s session=%s active_connections=%d",
                    connection_id,
                    session_id,
                    active_connections,
                )
            else:
                logger.debug(
                    "[interactive] connection crashed connection_id=%s session=%s active_connections=%d",
                    connection_id,
                    session_id,
                    active_connections,
                )
            attached.terminal.close()

    async def _relay_output(
        self,
        master_fd: int,
        websocket: Any,
        *,
        session_id: str,
        input_batch: dict[str, dict[str, float | int] | None],
    ) -> None:
        while True:
            chunk = await asyncio.to_thread(self._read_chunk, master_fd, 4096)
            if not chunk:
                break
            pending_input = input_batch.get("pending")
            if pending_input is not None:
                wait_ms = (self._monotonic_time() - float(pending_input["started_at"])) * 1000.0
                logger.debug(
                    "[interactive] first output after input session=%s wait_ms=%.1f input_messages=%d input_bytes=%d first_output_bytes=%d",
                    session_id,
                    wait_ms,
                    int(pending_input["messages"]),
                    int(pending_input["bytes"]),
                    len(chunk),
                )
                input_batch["pending"] = None
            await websocket.send(chunk)

    async def _handle_client_message(
        self,
        master_fd: int,
        message: str | bytes,
        *,
        session_id: str,
        input_batch: dict[str, dict[str, float | int] | None],
    ) -> None:
        if isinstance(message, bytes):
            await asyncio.to_thread(self._write_chunk, master_fd, message)
            return

        payload = json.loads(message)
        event_type = payload.get("type")

        if event_type == "input":
            data = payload.get("data", "")
            encoded = data.encode("utf-8")
            pending_input = input_batch.get("pending")
            if pending_input is None:
                input_batch["pending"] = {
                    "started_at": self._monotonic_time(),
                    "bytes": len(encoded),
                    "messages": 1,
                }
                logger.debug(
                    "[interactive] input batch started session=%s input_messages=%d input_bytes=%d",
                    session_id,
                    1,
                    len(encoded),
                )
            else:
                pending_input["bytes"] = int(pending_input["bytes"]) + len(encoded)
                pending_input["messages"] = int(pending_input["messages"]) + 1
            await asyncio.to_thread(self._write_chunk, master_fd, encoded)
            return

        if event_type == "resize":
            size = TerminalSize(columns=payload["columns"], rows=payload["rows"])
            await asyncio.to_thread(self._resize_handler, master_fd, size)
            return

        if event_type == "terminate":
            self._pending_terminations.add(session_id)

    async def _activate_connection(
        self, session_id: str, websocket: Any, connection_id: str
    ) -> None:
        lock = self._session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            existing = self._active_websockets.get(session_id)
            if existing is websocket:
                return
            if existing is not None:
                logger.debug(
                    "[interactive] superseding connection session=%s old_connection_id=%s new_connection_id=%s",
                    session_id,
                    hex(id(existing)),
                    connection_id,
                )
                with contextlib.suppress(Exception):
                    await existing.close(code=1012, reason="Superseded by a newer connection")
                wait_closed = getattr(existing, "wait_closed", None)
                if callable(wait_closed):
                    with contextlib.suppress(Exception):
                        await asyncio.wait_for(wait_closed(), timeout=1)  # type: ignore[arg-type]
                await asyncio.sleep(0)
            self._active_websockets[session_id] = websocket

    async def _deactivate_connection(self, session_id: str, websocket: Any) -> None:
        lock = self._session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            if self._active_websockets.get(session_id) is websocket:
                self._active_websockets.pop(session_id, None)
            if session_id not in self._active_websockets:
                self._session_locks.pop(session_id, None)

    def _resolve_identity(self, session_id: str) -> InteractiveSessionIdentity:
        """Reconstruct session identity from registry metadata."""
        metadata = self._session_service._registry.get(session_id) or {}
        return InteractiveSessionIdentity(
            provider=metadata.get("provider", "claude-code"),
            agent_name=metadata.get("agent_name", "unknown"),
            scope_kind=metadata.get("scope_kind", "chat"),
            scope_id=metadata.get("scope_id", session_id),
            surface=metadata.get("surface", "chat"),
        )
