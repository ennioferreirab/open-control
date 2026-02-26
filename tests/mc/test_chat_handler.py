"""Tests for the ChatHandler (Story 10.2)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bridge() -> MagicMock:
    """Create a mock ConvexBridge with chat helper methods."""
    bridge = MagicMock()
    bridge.get_pending_chat_messages = MagicMock(return_value=[])
    bridge.send_chat_response = MagicMock()
    bridge.mark_chat_processing = MagicMock()
    bridge.mark_chat_done = MagicMock()
    bridge.query = MagicMock(return_value=None)
    bridge.mutation = MagicMock()
    return bridge


def _make_pending_msg(
    chat_id: str = "chat123",
    agent_name: str = "test-agent",
    content: str = "Hello!",
) -> dict:
    """Create a mock pending chat message dict (snake_case keys)."""
    return {
        "id": chat_id,
        "agent_name": agent_name,
        "author_name": "User",
        "author_type": "user",
        "content": content,
        "status": "pending",
        "timestamp": "2026-02-26T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# Test: ChatHandler._process_chat_message — happy path
# ---------------------------------------------------------------------------


class TestProcessChatMessage:
    """Test the core message processing logic."""

    @pytest.mark.asyncio
    async def test_happy_path_sends_response_and_marks_done(self, tmp_path):
        """Process a pending message: mark processing, run agent, send response, mark done."""
        from nanobot.mc.chat_handler import ChatHandler

        bridge = _make_bridge()
        handler = ChatHandler(bridge)
        msg = _make_pending_msg()

        mock_agent_loop = MagicMock()
        mock_agent_loop.process_direct = AsyncMock(
            return_value="Agent response here"
        )

        # Set up agents dir
        agents_dir = tmp_path / "agents"
        config_dir = agents_dir / "test-agent"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text("name: test-agent")

        # Patch lazy imports inside _process_chat_message
        with (
            patch(
                "importlib.util.spec_from_file_location"
            ) as mock_spec_from,
            patch("importlib.util.module_from_spec") as mock_mod_from,
            patch(
                "nanobot.mc.provider_factory.create_provider",
                return_value=(MagicMock(), "test-model"),
            ),
            patch(
                "nanobot.mc.yaml_validator.validate_agent_file",
                return_value=MagicMock(
                    prompt="Test prompt", model=None, skills=[]
                ),
            ),
            patch(
                "nanobot.mc.gateway.AGENTS_DIR",
                agents_dir,
            ),
        ):
            # Set up the spec/module mocks to return our mock AgentLoop
            mock_spec = MagicMock()
            mock_spec_from.return_value = mock_spec

            mock_loop_module = MagicMock()
            mock_loop_module.AgentLoop = MagicMock(
                return_value=mock_agent_loop
            )
            mock_bus_module = MagicMock()
            mock_bus_module.MessageBus = MagicMock

            # First call is for loop.py, second for queue.py
            mock_mod_from.side_effect = [mock_loop_module, mock_bus_module]
            mock_spec.loader = MagicMock()

            await handler._process_chat_message(msg)

        # Assertions: mark_chat_processing called with chat_id
        bridge.mark_chat_processing.assert_called_once_with("chat123")
        # mark_chat_done called
        bridge.mark_chat_done.assert_called_once_with("chat123")
        # send_chat_response called with agent name, result, and display name
        bridge.send_chat_response.assert_called_once()
        call_args = bridge.send_chat_response.call_args[0]
        assert call_args[0] == "test-agent"
        assert call_args[1] == "Agent response here"

    @pytest.mark.asyncio
    async def test_skips_message_without_id(self):
        """Messages without an id are skipped silently."""
        from nanobot.mc.chat_handler import ChatHandler

        bridge = _make_bridge()
        handler = ChatHandler(bridge)
        msg = {"agent_name": "test-agent", "content": "Hello"}

        await handler._process_chat_message(msg)

        bridge.mark_chat_processing.assert_not_called()
        bridge.send_chat_response.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_message_without_agent_name(self):
        """Messages without an agent_name are skipped."""
        from nanobot.mc.chat_handler import ChatHandler

        bridge = _make_bridge()
        handler = ChatHandler(bridge)
        msg = {"id": "chat123", "content": "Hello", "agent_name": ""}

        await handler._process_chat_message(msg)

        bridge.mark_chat_processing.assert_not_called()


# ---------------------------------------------------------------------------
# Test: Error handling
# ---------------------------------------------------------------------------


class TestProcessChatMessageErrors:
    """Test error handling during message processing."""

    @pytest.mark.asyncio
    async def test_error_marks_done_and_sends_error_response(self):
        """On processing error, mark original done and send error response."""
        from nanobot.mc.chat_handler import ChatHandler

        bridge = _make_bridge()
        handler = ChatHandler(bridge)
        msg = _make_pending_msg()

        # Force an error during processing by making mark_chat_processing
        # succeed but the lazy import fail
        with patch(
            "importlib.util.spec_from_file_location",
            side_effect=RuntimeError("import failed"),
        ):
            await handler._process_chat_message(msg)

        # Original should still be marked done (error recovery)
        bridge.mark_chat_done.assert_called_once_with("chat123")
        # Error response should be sent
        bridge.send_chat_response.assert_called_once()
        call_args = bridge.send_chat_response.call_args
        assert call_args[0][0] == "test-agent"
        assert "RuntimeError" in call_args[0][1]


# ---------------------------------------------------------------------------
# Test: Polling loop
# ---------------------------------------------------------------------------


class TestChatHandlerPollingLoop:
    """Test the polling loop behavior."""

    @pytest.mark.asyncio
    async def test_run_polls_and_dispatches(self):
        """The run() loop polls for pending messages and processes them."""
        from nanobot.mc.chat_handler import ChatHandler

        bridge = _make_bridge()
        handler = ChatHandler(bridge)

        msg = _make_pending_msg()
        call_count = 0
        processed = asyncio.Event()

        def fake_get_pending():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [msg]
            return []

        bridge.get_pending_chat_messages = fake_get_pending

        # Mock _process_chat_message to avoid the full agent processing
        original_process = handler._process_chat_message

        async def mock_process(m):
            processed.set()

        handler._process_chat_message = mock_process

        # Patch POLL_INTERVAL_SECONDS to 0 so the loop iterates fast
        with patch("nanobot.mc.chat_handler.POLL_INTERVAL_SECONDS", 0):
            task = asyncio.create_task(handler.run())
            # Wait for processing to happen (with timeout)
            try:
                await asyncio.wait_for(processed.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pass
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        assert processed.is_set()

    @pytest.mark.asyncio
    async def test_run_handles_poll_error_gracefully(self):
        """Errors during polling don't crash the loop."""
        from nanobot.mc.chat_handler import ChatHandler

        bridge = _make_bridge()
        handler = ChatHandler(bridge)

        call_count = 0
        second_poll_done = asyncio.Event()

        def failing_get_pending():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Convex down")
            # Second call succeeds -- proves loop survived the error
            second_poll_done.set()
            return []

        bridge.get_pending_chat_messages = failing_get_pending

        with patch("nanobot.mc.chat_handler.POLL_INTERVAL_SECONDS", 0):
            task = asyncio.create_task(handler.run())
            try:
                await asyncio.wait_for(second_poll_done.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pass
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # The loop survived the error and polled again
        assert call_count >= 2


# ---------------------------------------------------------------------------
# Test: Bridge chat helpers
# ---------------------------------------------------------------------------


class TestBridgeChatHelpers:
    """Test that the bridge chat methods call the right Convex functions."""

    def test_get_pending_chat_messages_calls_query(self):
        """get_pending_chat_messages calls chats:listPending query."""
        from nanobot.mc.bridge import ConvexBridge

        bridge = MagicMock(spec=ConvexBridge)
        bridge.query = MagicMock(return_value=[])

        # Call the actual method on the class, passing bridge as self
        result = ConvexBridge.get_pending_chat_messages(bridge)

        bridge.query.assert_called_once_with("chats:listPending")
        assert result == []

    def test_get_pending_returns_list_or_empty(self):
        """get_pending_chat_messages returns empty list for None."""
        from nanobot.mc.bridge import ConvexBridge

        bridge = MagicMock(spec=ConvexBridge)
        bridge.query = MagicMock(return_value=None)

        result = ConvexBridge.get_pending_chat_messages(bridge)
        assert result == []

    def test_send_chat_response_calls_mutation(self):
        """send_chat_response calls chats:send mutation."""
        from nanobot.mc.bridge import ConvexBridge

        bridge = MagicMock(spec=ConvexBridge)
        bridge._mutation_with_retry = MagicMock()

        ConvexBridge.send_chat_response(bridge, "my-agent", "Hello back!")

        bridge._mutation_with_retry.assert_called_once()
        call_args = bridge._mutation_with_retry.call_args
        assert call_args[0][0] == "chats:send"
        payload = call_args[0][1]
        assert payload["agent_name"] == "my-agent"
        assert payload["author_name"] == "my-agent"
        assert payload["author_type"] == "agent"
        assert payload["content"] == "Hello back!"
        assert payload["status"] == "done"

    def test_mark_chat_processing_calls_mutation(self):
        """mark_chat_processing calls chats:updateStatus with processing."""
        from nanobot.mc.bridge import ConvexBridge

        bridge = MagicMock(spec=ConvexBridge)
        bridge._mutation_with_retry = MagicMock()

        ConvexBridge.mark_chat_processing(bridge, "chat456")

        bridge._mutation_with_retry.assert_called_once_with(
            "chats:updateStatus",
            {"chat_id": "chat456", "status": "processing"},
        )

    def test_mark_chat_done_calls_mutation(self):
        """mark_chat_done calls chats:updateStatus with done."""
        from nanobot.mc.bridge import ConvexBridge

        bridge = MagicMock(spec=ConvexBridge)
        bridge._mutation_with_retry = MagicMock()

        ConvexBridge.mark_chat_done(bridge, "chat789")

        bridge._mutation_with_retry.assert_called_once_with(
            "chats:updateStatus",
            {"chat_id": "chat789", "status": "done"},
        )
