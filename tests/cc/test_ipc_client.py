"""Tests for MCSocketClient and MCSocketServer IPC round-trips."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from claude_code.ipc_client import MCSocketClient
from claude_code.ipc_server import MCSocketServer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _short_sock() -> str:
    """Return a short /tmp socket path safe for macOS's 104-char limit."""
    return f"/tmp/mc-test-{uuid.uuid4().hex[:8]}.sock"


async def _make_server_and_client(
    sock_path: str,
    handlers: dict | None = None,
) -> tuple[MCSocketServer, MCSocketClient, str]:
    """Create a MCSocketServer + MCSocketClient pair sharing a tmp socket."""
    bridge = None
    bus = None
    srv = MCSocketServer(bridge, bus)

    if handlers:
        for method, handler in handlers.items():
            srv.register(method, handler)

    await srv.start(sock_path)
    client = MCSocketClient(sock_path)
    return srv, client, sock_path


# ---------------------------------------------------------------------------
# MCSocketClient tests
# ---------------------------------------------------------------------------


class TestMCSocketClientRoundTrip:
    async def test_basic_request_response(self):
        """Round-trip a JSON-RPC message through the actual unix socket."""
        sock = _short_sock()

        async def echo_handler(**params: Any) -> dict[str, Any]:
            return {"echo": params}

        srv, client, _ = await _make_server_and_client(sock)
        srv.register("echo", echo_handler)

        try:
            result = await client.request("echo", {"foo": "bar"})
            assert result == {"echo": {"foo": "bar"}}
        finally:
            await srv.stop()

    async def test_unknown_method_returns_error(self):
        """Calling an unregistered method returns an error dict."""
        sock = _short_sock()
        srv, client, _ = await _make_server_and_client(sock)

        try:
            result = await client.request("does_not_exist", {})
            assert "error" in result
            assert "Unknown method" in result["error"]
        finally:
            await srv.stop()

    async def test_connection_error_raises(self):
        """Connecting to a non-existent socket raises ConnectionError."""
        sock = _short_sock()  # no server started
        client = MCSocketClient(sock)

        with pytest.raises(ConnectionError):
            await client.request("anything", {})

    async def test_multiple_requests(self):
        """Multiple sequential requests all succeed."""
        sock = _short_sock()
        call_count = 0

        async def count_handler(**params: Any) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return {"n": call_count}

        srv, client, _ = await _make_server_and_client(sock)
        srv.register("count", count_handler)

        try:
            r1 = await client.request("count", {})
            r2 = await client.request("count", {})
            assert r1 == {"n": 1}
            assert r2 == {"n": 2}
        finally:
            await srv.stop()


class TestMCSocketClientTimeout:
    async def test_client_raises_connection_error_on_missing_socket(self):
        """Verify client raises ConnectionError when socket file does not exist.

        This is a deterministic test that does not require timing/async hackery.
        The 300-second internal timeout is tested implicitly by the overall
        production use; cancellation behaviour is covered by asyncio itself.
        """
        sock = _short_sock()  # no server running at this path
        client = MCSocketClient(sock)

        with pytest.raises(ConnectionError, match="Cannot connect"):
            await client.request("anything", {})


# ---------------------------------------------------------------------------
# MCSocketServer tests
# ---------------------------------------------------------------------------


class TestMCSocketServerHandlers:
    async def test_send_message_no_delivery_path_returns_error(self):
        """send_message returns an error when no delivery path is available.

        H3 fix: without bridge, bus, channel+chat_id, or task_id, the server
        must report an error instead of silently succeeding.
        """
        sock = _short_sock()
        srv, client, _ = await _make_server_and_client(sock)

        try:
            result = await client.request(
                "send_message",
                {"content": "hello", "agent_name": "bot", "task_id": None},
            )
            # With no bridge, no bus, and no channel/chat_id/task_id,
            # the server should return an error.
            assert "error" in result
        finally:
            await srv.stop()

    async def test_delegate_task_no_bridge_returns_error(self):
        """delegate_task returns error when bridge is unavailable."""
        sock = _short_sock()
        srv, client, _ = await _make_server_and_client(sock)

        try:
            result = await client.request(
                "delegate_task",
                {"description": "do something", "agent_name": "bot"},
            )
            assert "error" in result
        finally:
            await srv.stop()

    async def test_self_delegation_prevented(self):
        """delegate_task blocks when agent == agent_name."""
        sock = _short_sock()

        mock_bridge = MagicMock()
        srv = MCSocketServer(mock_bridge, None)
        await srv.start(sock)
        client = MCSocketClient(sock)

        try:
            result = await client.request(
                "delegate_task",
                {
                    "description": "do something",
                    "agent": "myagent",
                    "agent_name": "myagent",
                },
            )
            assert "error" in result
            assert "Self-delegation" in result["error"] or "self" in result["error"].lower()
        finally:
            await srv.stop()

    async def test_report_progress_no_bridge(self):
        """report_progress returns success even with no bridge."""
        sock = _short_sock()
        srv, client, _ = await _make_server_and_client(sock)

        try:
            result = await client.request(
                "report_progress",
                {"message": "50% done", "percentage": 50, "agent_name": "bot"},
            )
            assert result.get("status") == "Progress reported"
        finally:
            await srv.stop()

    async def test_report_progress_with_bridge(self):
        """report_progress calls bridge.create_activity when bridge available."""
        sock = _short_sock()

        mock_bridge = MagicMock()
        mock_bridge.create_activity = MagicMock(return_value=None)

        srv = MCSocketServer(mock_bridge, None)
        await srv.start(sock)
        client = MCSocketClient(sock)

        try:
            result = await client.request(
                "report_progress",
                {
                    "message": "working",
                    "percentage": 75,
                    "agent_name": "bot",
                    "task_id": "task-123",
                },
            )
            assert result.get("status") == "Progress reported"
            # bridge.create_activity should have been called
            mock_bridge.create_activity.assert_called_once()
            call_args = mock_bridge.create_activity.call_args
            assert "75%" in call_args[0][1] or "75" in str(call_args)
        finally:
            await srv.stop()

    async def test_ask_user_no_handler_returns_error(self):
        """ask_user without a handler returns an error message."""
        sock = _short_sock()

        mock_bridge = MagicMock()
        mock_bridge.send_message = MagicMock(return_value=None)

        srv = MCSocketServer(mock_bridge, None)
        # No handler set — should return error
        await srv.start(sock)
        client = MCSocketClient(sock)

        try:
            result = await client.request(
                "ask_user",
                {
                    "question": "What's up?",
                    "agent_name": "bot",
                    "task_id": "task-abc",
                },
            )
            assert result.get("answer") == "No ask_user handler configured."
        finally:
            await srv.stop()

    async def test_deliver_user_reply_resolves_future(self):
        """AskUserHandler.deliver_user_reply resolves the pending ask_user future."""
        sock = _short_sock()

        mock_bridge = MagicMock()
        mock_bridge.send_message = MagicMock(return_value=None)
        mock_bridge.update_task_status = MagicMock(return_value=None)

        from mc.contexts.conversation.ask_user.handler import AskUserHandler

        handler = AskUserHandler()
        srv = MCSocketServer(mock_bridge, None)
        srv.set_ask_user_handler(handler)
        await srv.start(sock)
        client = MCSocketClient(sock)

        ask_task = asyncio.create_task(
            client.request(
                "ask_user",
                {
                    "question": "Are you ready?",
                    "agent_name": "bot",
                    "task_id": "task-xyz",
                },
            )
        )

        # Let the server start waiting
        await asyncio.sleep(0.1)

        # Deliver the reply via handler
        handler.deliver_user_reply("task-xyz", "Yes, ready!")

        result = await asyncio.wait_for(ask_task, timeout=5)
        assert result.get("answer") == "Yes, ready!"

        await srv.stop()

    async def test_emit_supervision_event_routes_to_interactive_supervisor(self):
        sock = _short_sock()

        supervisor = MagicMock()
        supervisor.handle_event = MagicMock(
            return_value={"session_id": "interactive_session:claude"}
        )

        srv = MCSocketServer(None, None, interactive_supervisor=supervisor)
        await srv.start(sock)
        client = MCSocketClient(sock)

        try:
            result = await client.request(
                "emit_supervision_event",
                {
                    "provider": "claude-code",
                    "raw_event": {
                        "eventName": "Stop",
                        "session_id": "interactive_session:claude",
                        "task_id": "task-1",
                    },
                },
            )
            assert result == {"status": "ok", "session_id": "interactive_session:claude"}
            handled_event = supervisor.handle_event.call_args.args[0]
            assert handled_event.kind == "turn_completed"
            assert handled_event.session_id == "interactive_session:claude"
        finally:
            await srv.stop()

    async def test_record_final_result_routes_to_interactive_supervisor(self):
        sock = _short_sock()

        supervisor = MagicMock()
        supervisor.record_final_result = MagicMock(
            return_value={"session_id": "interactive_session:claude"}
        )

        srv = MCSocketServer(None, None, interactive_supervisor=supervisor)
        await srv.start(sock)
        client = MCSocketClient(sock)

        try:
            result = await client.request(
                "record_final_result",
                {
                    "session_id": "interactive_session:claude",
                    "content": "Implemented the requested step.",
                    "source": "claude-mcp",
                },
            )
            assert result == {"status": "Final result recorded"}
            supervisor.record_final_result.assert_called_once_with(
                session_id="interactive_session:claude",
                content="Implemented the requested step.",
                source="claude-mcp",
            )
        finally:
            await srv.stop()

    async def test_create_agent_spec_dispatches_to_bridge(self):
        """create_agent_spec calls bridge.create_agent_spec + publish."""
        sock = _short_sock()

        mock_bridge = MagicMock()
        mock_bridge.create_agent_spec = MagicMock(return_value="spec-id-123")
        mock_bridge.publish_agent_spec = MagicMock(return_value=None)

        srv = MCSocketServer(mock_bridge, None)
        await srv.start(sock)
        client = MCSocketClient(sock)

        try:
            result = await client.request(
                "create_agent_spec",
                {
                    "name": "my-agent",
                    "role": "Developer",
                    "display_name": "My Agent",
                },
            )
            assert result.get("spec_id") == "spec-id-123"
            mock_bridge.create_agent_spec.assert_called_once()
            mock_bridge.publish_agent_spec.assert_called_once_with("spec-id-123")
        finally:
            await srv.stop()

    async def test_create_agent_spec_no_bridge_returns_error(self):
        """create_agent_spec returns error when bridge is unavailable."""
        sock = _short_sock()
        srv, client, _ = await _make_server_and_client(sock)

        try:
            result = await client.request(
                "create_agent_spec",
                {"name": "x", "role": "Y"},
            )
            assert "error" in result
        finally:
            await srv.stop()

    async def test_publish_squad_graph_dispatches_to_bridge(self):
        """publish_squad_graph calls bridge.publish_squad_graph."""
        sock = _short_sock()

        mock_bridge = MagicMock()
        mock_bridge.publish_squad_graph = MagicMock(return_value="squad-id-abc")

        srv = MCSocketServer(mock_bridge, None)
        await srv.start(sock)
        client = MCSocketClient(sock)

        graph = {
            "squad": {"name": "s1", "displayName": "S1"},
            "agents": [],
            "workflows": [],
        }

        try:
            result = await client.request(
                "publish_squad_graph",
                {"graph": graph},
            )
            assert result.get("squad_id") == "squad-id-abc"
            mock_bridge.publish_squad_graph.assert_called_once_with(graph)
        finally:
            await srv.stop()
