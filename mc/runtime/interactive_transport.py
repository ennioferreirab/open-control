"""Runtime-owned socket transport for interactive PTY sessions."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Callable

from websockets.exceptions import ConnectionClosed

from mc.infrastructure.interactive import TerminalSize, resize_terminal


class InteractiveSocketTransport:
    """Bridge browser websocket traffic to a tmux-attached PTY."""

    def __init__(
        self,
        *,
        session_service: Any,
        read_chunk: Callable[[int, int], bytes] = os.read,
        write_chunk: Callable[[int, bytes], int] = os.write,
        resize_handler: Callable[[int, TerminalSize], None] = resize_terminal,
    ) -> None:
        self._session_service = session_service
        self._read_chunk = read_chunk
        self._write_chunk = write_chunk
        self._resize_handler = resize_handler

    async def handle_connection(
        self,
        websocket: Any,
        *,
        session_id: str,
        size: TerminalSize,
        attach_token: str | None = None,
        timestamp_factory: Callable[[], str] | None = None,
    ) -> None:
        now = timestamp_factory or (lambda: datetime.now(timezone.utc).isoformat())
        attached = self._session_service.attach_session(
            session_id,
            size=size,
            attach_token=attach_token,
            timestamp=now(),
        )
        output_task = asyncio.create_task(
            self._relay_output(attached.terminal.master_fd, websocket)
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
                await self._handle_client_message(attached.terminal.master_fd, message)
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
            if not crashed:
                self._session_service.detach_session(session_id, timestamp=now())
            attached.terminal.close()

    async def _relay_output(self, master_fd: int, websocket: Any) -> None:
        while True:
            chunk = await asyncio.to_thread(self._read_chunk, master_fd, 4096)
            if not chunk:
                break
            await websocket.send(chunk)

    async def _handle_client_message(self, master_fd: int, message: str | bytes) -> None:
        if isinstance(message, bytes):
            await asyncio.to_thread(self._write_chunk, master_fd, message)
            return

        payload = json.loads(message)
        event_type = payload.get("type")

        if event_type == "input":
            data = payload.get("data", "")
            await asyncio.to_thread(self._write_chunk, master_fd, data.encode("utf-8"))
            return

        if event_type == "resize":
            size = TerminalSize(columns=payload["columns"], rows=payload["rows"])
            await asyncio.to_thread(self._resize_handler, master_fd, size)
