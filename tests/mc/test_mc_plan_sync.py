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


# ---------------------------------------------------------------------------
# MC context discovery tests
# ---------------------------------------------------------------------------

class TestMCContextDiscovery:
    """Tests for _discover_mc_context in MCPlanSyncHandler."""

    def _make_handler(self, payload):
        from mc.hooks.handlers.mc_plan_sync import MCPlanSyncHandler
        from mc.hooks.context import HookContext
        ctx = HookContext("test-session")
        return MCPlanSyncHandler(ctx, payload)

    def test_returns_none_when_no_mcp_json_and_no_env(self, tmp_path):
        """No MC context available — should return None."""
        handler = self._make_handler({"cwd": str(tmp_path)})
        assert handler._discover_mc_context() is None

    def test_reads_mcp_json_from_cwd(self, tmp_path):
        """Discovers MC context from .mcp.json in cwd."""
        sock_path = str(tmp_path / "mc.sock")
        Path(sock_path).touch()

        mcp_config = {
            "mcpServers": {
                "nanobot": {
                    "command": "uv",
                    "args": ["run", "python", "-m", "claude_code.mcp_bridge"],
                    "env": {
                        "MC_SOCKET_PATH": sock_path,
                        "AGENT_NAME": "test-agent",
                        "TASK_ID": "task-123",
                    },
                }
            }
        }
        (tmp_path / ".mcp.json").write_text(json.dumps(mcp_config))

        handler = self._make_handler({"cwd": str(tmp_path)})
        mc_ctx = handler._discover_mc_context()
        assert mc_ctx is not None
        assert mc_ctx["socket_path"] == sock_path
        assert mc_ctx["agent_name"] == "test-agent"
        assert mc_ctx["task_id"] == "task-123"

    def test_env_var_takes_precedence(self, tmp_path):
        """MC_SOCKET_PATH env var is preferred over .mcp.json."""
        sock_path = str(tmp_path / "env.sock")
        Path(sock_path).touch()

        with patch.dict(os.environ, {
            "MC_SOCKET_PATH": sock_path,
            "AGENT_NAME": "env-agent",
            "TASK_ID": "env-task",
        }):
            handler = self._make_handler({"cwd": str(tmp_path)})
            mc_ctx = handler._discover_mc_context()
            assert mc_ctx is not None
            assert mc_ctx["socket_path"] == sock_path
            assert mc_ctx["agent_name"] == "env-agent"

    def test_returns_none_when_socket_file_missing(self, tmp_path):
        """Socket path in .mcp.json but file doesn't exist — no MC."""
        mcp_config = {
            "mcpServers": {
                "nanobot": {
                    "env": {
                        "MC_SOCKET_PATH": "/tmp/nonexistent-mc-test.sock",
                        "AGENT_NAME": "agent",
                        "TASK_ID": "task",
                    },
                }
            }
        }
        (tmp_path / ".mcp.json").write_text(json.dumps(mcp_config))

        handler = self._make_handler({"cwd": str(tmp_path)})
        assert handler._discover_mc_context() is None
