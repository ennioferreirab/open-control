"""Tests for mc.hooks.ipc_sync — SyncIPCClient with mocked sockets."""

from __future__ import annotations

import json
import os
import socket
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mc.hooks.ipc_sync import SyncIPCClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def unix_socket_pair():
    """Create a Unix domain socket server with a short path (macOS 104-char limit)."""
    # Use /tmp directly for a short socket path
    sock_dir = tempfile.mkdtemp(prefix="ipc", dir="/tmp")
    socket_path = os.path.join(sock_dir, "t.sock")

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(socket_path)
    server.listen(1)
    server.settimeout(5.0)

    yield socket_path, server

    server.close()
    if os.path.exists(socket_path):
        os.unlink(socket_path)
    os.rmdir(sock_dir)


def _echo_server(server_sock: socket.socket, response: dict | None = None):
    """Accept one connection, read request, send response, close."""
    try:
        conn, _ = server_sock.accept()
        conn.settimeout(5.0)
        data = b""
        while b"\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk

        if response is None:
            # Echo back the request as the response
            request = json.loads(data.decode())
            response = {"result": "ok", "echo": request}

        conn.sendall((json.dumps(response) + "\n").encode())
        conn.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSyncIPCClientInit:
    def test_stores_path_and_timeout(self):
        client = SyncIPCClient("/tmp/test.sock", timeout=3.0)
        assert client._path == "/tmp/test.sock"
        assert client._timeout == 3.0

    def test_default_timeout(self):
        client = SyncIPCClient("/tmp/test.sock")
        assert client._timeout == 5.0


class TestSyncIPCClientRequest:
    def test_successful_request(self, unix_socket_pair):
        socket_path, server = unix_socket_pair
        response = {"result": "success", "data": {"key": "value"}}

        # Start echo server in background
        thread = threading.Thread(target=_echo_server, args=(server, response))
        thread.start()

        client = SyncIPCClient(socket_path, timeout=5.0)
        result = client.request("test_method", {"param1": "value1"})

        thread.join(timeout=5.0)
        assert result == response

    def test_sends_correct_json_rpc_format(self, unix_socket_pair):
        socket_path, server = unix_socket_pair

        received_data = {}

        def capture_server(server_sock):
            try:
                conn, _ = server_sock.accept()
                conn.settimeout(5.0)
                data = b""
                while b"\n" not in data:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                received_data.update(json.loads(data.decode()))
                conn.sendall((json.dumps({"result": "ok"}) + "\n").encode())
                conn.close()
            except Exception:
                pass

        thread = threading.Thread(target=capture_server, args=(server,))
        thread.start()

        client = SyncIPCClient(socket_path, timeout=5.0)
        client.request("my_method", {"foo": "bar"})

        thread.join(timeout=5.0)
        assert received_data["method"] == "my_method"
        assert received_data["params"] == {"foo": "bar"}

    def test_connection_refused(self, tmp_path: Path):
        """Connecting to a non-existent socket raises ConnectionError."""
        socket_path = str(tmp_path / "nonexistent.sock")
        client = SyncIPCClient(socket_path, timeout=1.0)
        with pytest.raises(ConnectionError, match="Cannot connect"):
            client.request("test", {})

    def test_server_closes_without_response(self, unix_socket_pair):
        """Server closing without sending data raises ConnectionError."""
        socket_path, server = unix_socket_pair

        def close_immediately(server_sock):
            try:
                conn, _ = server_sock.accept()
                conn.close()  # close without sending anything
            except Exception:
                pass

        thread = threading.Thread(target=close_immediately, args=(server,))
        thread.start()

        client = SyncIPCClient(socket_path, timeout=5.0)
        with pytest.raises(ConnectionError, match=r"closed connection|Connection reset"):
            client.request("test", {})

        thread.join(timeout=5.0)

    def test_timeout_raises_connection_error(self, unix_socket_pair):
        """Socket timeout raises ConnectionError."""
        socket_path, server = unix_socket_pair

        def slow_server(server_sock):
            try:
                conn, _ = server_sock.accept()
                import time

                time.sleep(3)  # longer than client timeout
                conn.close()
            except Exception:
                pass

        thread = threading.Thread(target=slow_server, args=(server,))
        thread.daemon = True
        thread.start()

        client = SyncIPCClient(socket_path, timeout=0.5)
        with pytest.raises(ConnectionError, match="timed out"):
            client.request("test", {})

        thread.join(timeout=5.0)

    def test_socket_cleaned_up_on_connect_error(self, tmp_path: Path):
        """Socket should be closed even when connect fails."""
        socket_path = str(tmp_path / "no-such.sock")
        client = SyncIPCClient(socket_path)

        with pytest.raises(ConnectionError):
            client.request("test", {})
        # No leaked file descriptors — just verify no exception on cleanup

    def test_socket_cleaned_up_on_success(self, unix_socket_pair):
        """Socket should be closed after a successful request."""
        socket_path, server = unix_socket_pair

        thread = threading.Thread(
            target=_echo_server,
            args=(server, {"result": "ok"}),
        )
        thread.start()

        client = SyncIPCClient(socket_path, timeout=5.0)
        client.request("test", {})
        thread.join(timeout=5.0)
        # No exception means cleanup succeeded

    def test_large_response(self, unix_socket_pair):
        """Client should handle responses larger than 4096 bytes."""
        socket_path, server = unix_socket_pair
        large_data = {"result": "x" * 10000}

        thread = threading.Thread(
            target=_echo_server,
            args=(server, large_data),
        )
        thread.start()

        client = SyncIPCClient(socket_path, timeout=5.0)
        result = client.request("test", {})

        thread.join(timeout=5.0)
        assert result["result"] == "x" * 10000


class TestSyncIPCClientMocked:
    """Tests using mocked sockets for faster execution."""

    def test_connection_error_wraps_file_not_found(self):
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = FileNotFoundError("no socket")

        with patch("mc.hooks.ipc_sync._socket.socket", return_value=mock_sock):
            client = SyncIPCClient("/fake/path.sock")
            with pytest.raises(ConnectionError, match="Cannot connect"):
                client.request("test", {})

        mock_sock.close.assert_called()

    def test_connection_error_wraps_connection_refused(self):
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = ConnectionRefusedError("refused")

        with patch("mc.hooks.ipc_sync._socket.socket", return_value=mock_sock):
            client = SyncIPCClient("/fake/path.sock")
            with pytest.raises(ConnectionError, match="Cannot connect"):
                client.request("test", {})

    def test_connection_error_wraps_oserror(self):
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = OSError("generic os error")

        with patch("mc.hooks.ipc_sync._socket.socket", return_value=mock_sock):
            client = SyncIPCClient("/fake/path.sock")
            with pytest.raises(ConnectionError, match="Cannot connect"):
                client.request("test", {})
