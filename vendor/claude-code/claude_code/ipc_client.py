"""Unix socket IPC client for MCP bridge communication.

The MCP bridge (mcp_bridge.py) runs as a separate stdio subprocess.
It communicates with the MC runtime via this lightweight IPC layer.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

_IPC_STREAM_LIMIT = 1024 * 1024


class MCSocketClient:
    """Async client for communicating with the MC IPC server over a Unix socket."""

    def __init__(self, socket_path: str) -> None:
        self._path = socket_path

    async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC-style request and await the response.

        Args:
            method: The IPC method name (e.g. 'ask_user', 'send_message').
            params: The method parameters dict.

        Returns:
            The response dict parsed from the server reply.

        Raises:
            ConnectionError: If the socket cannot be reached.
            asyncio.TimeoutError: If no response arrives within 300 seconds.
        """
        try:
            reader, writer = await asyncio.open_unix_connection(
                self._path,
                limit=_IPC_STREAM_LIMIT,
            )
        except (FileNotFoundError, ConnectionRefusedError) as exc:
            raise ConnectionError(
                f"Cannot connect to MC IPC socket at {self._path}: {exc}"
            ) from exc

        try:
            payload = json.dumps({"method": method, "params": params}) + "\n"
            writer.write(payload.encode())
            await writer.drain()

            raw = await asyncio.wait_for(reader.readline(), timeout=300)
            if not raw:
                raise ConnectionError("MC IPC server closed connection without response")
            return json.loads(raw)
        finally:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=2)
            except Exception:
                pass
