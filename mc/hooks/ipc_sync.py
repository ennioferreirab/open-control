"""Synchronous IPC client for hook-to-MC communication.

Hooks run as blocking shell commands (not async), so they need a synchronous
client. This uses stdlib socket module — same JSON-RPC protocol as the async
MCSocketClient in vendor/claude-code/claude_code/ipc_client.py.
"""

from __future__ import annotations

import json
import socket as _socket
from typing import Any


class SyncIPCClient:
    """Synchronous client for the MC IPC server over a Unix socket."""

    def __init__(self, socket_path: str, timeout: float = 5.0) -> None:
        self._path = socket_path
        self._timeout = timeout

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC-style request and return the response.

        Raises:
            ConnectionError: If the socket cannot be reached or times out.
        """
        sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        sock.settimeout(self._timeout)
        try:
            sock.connect(self._path)
        except (FileNotFoundError, ConnectionRefusedError, OSError) as exc:
            sock.close()
            raise ConnectionError(
                f"Cannot connect to MC IPC socket at {self._path}: {exc}"
            ) from exc

        try:
            payload = json.dumps({"method": method, "params": params}) + "\n"
            sock.sendall(payload.encode())

            data = b""
            while b"\n" not in data:
                try:
                    chunk = sock.recv(4096)
                except _socket.timeout as exc:
                    raise ConnectionError(
                        f"MC IPC socket timed out after {self._timeout}s"
                    ) from exc
                if not chunk:
                    raise ConnectionError("MC IPC server closed connection without response")
                data += chunk

            return json.loads(data.decode())
        finally:
            sock.close()
