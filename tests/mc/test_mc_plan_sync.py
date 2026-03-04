"""Tests for MC plan sync: SyncIPCClient + MCPlanSyncHandler."""
from __future__ import annotations

import json
import os
import socket
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import pytest


def _short_sock_path(name: str) -> str:
    """Return a short Unix socket path under /tmp to stay within the 104-char macOS limit."""
    return str(Path(tempfile.gettempdir()) / name)


# ---------------------------------------------------------------------------
# SyncIPCClient tests
# ---------------------------------------------------------------------------

class TestSyncIPCClient:
    """Tests for the synchronous IPC client."""

    def test_request_sends_json_rpc_and_returns_response(self):
        """Client sends JSON-RPC request and parses response."""
        sock_path = _short_sock_path("mc_ipc_test.sock")
        # Clean up any leftover socket file
        Path(sock_path).unlink(missing_ok=True)

        # Start a mock IPC server
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(sock_path)
        server.listen(1)

        def handle():
            conn, _ = server.accept()
            data = b""
            while b"\n" not in data:
                data += conn.recv(4096)
            request = json.loads(data.decode())
            assert request["method"] == "report_progress"
            assert request["params"]["message"] == "hello"
            response = json.dumps({"status": "Progress reported"}) + "\n"
            conn.sendall(response.encode())
            conn.close()
            server.close()

        t = threading.Thread(target=handle)
        t.start()

        from mc.hooks.ipc_sync import SyncIPCClient
        client = SyncIPCClient(sock_path)
        result = client.request("report_progress", {"message": "hello"})
        assert result == {"status": "Progress reported"}
        t.join(timeout=5)
        Path(sock_path).unlink(missing_ok=True)

    def test_request_raises_connection_error_when_no_socket(self):
        """Client raises ConnectionError when socket doesn't exist."""
        from mc.hooks.ipc_sync import SyncIPCClient
        client = SyncIPCClient(_short_sock_path("mc_ipc_nonexistent.sock"))
        with pytest.raises(ConnectionError):
            client.request("report_progress", {"message": "hello"})

    def test_request_raises_connection_error_on_timeout(self):
        """Client raises ConnectionError when server doesn't respond."""
        sock_path = _short_sock_path("mc_ipc_timeout.sock")
        Path(sock_path).unlink(missing_ok=True)

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(sock_path)
        server.listen(1)

        def handle():
            conn, _ = server.accept()
            import time
            time.sleep(10)  # Don't respond
            conn.close()
            server.close()

        t = threading.Thread(target=handle, daemon=True)
        t.start()

        from mc.hooks.ipc_sync import SyncIPCClient
        client = SyncIPCClient(sock_path, timeout=0.5)
        with pytest.raises(ConnectionError):
            client.request("report_progress", {"message": "hello"})
        Path(sock_path).unlink(missing_ok=True)
