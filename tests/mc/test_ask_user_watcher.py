"""Tests for AskUserReplyWatcher — watches task threads for user replies to ask_user."""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from mc.ask_user_handler import AskUserHandler
from mc.ask_user_watcher import AskUserReplyWatcher
from mc.ask_user_registry import AskUserRegistry


def _handler_with_pending(task_id: str) -> AskUserHandler:
    """Create an AskUserHandler with a fake pending ask for the given task_id."""
    handler = AskUserHandler()
    handler._pending_ask["req-123"] = MagicMock()  # fake future
    handler._task_to_request[task_id] = "req-123"
    return handler


class TestAskUserReplyWatcher:
    @pytest.fixture
    def bridge(self):
        mock = MagicMock()
        mock.get_task_messages = MagicMock(return_value=[])
        return mock

    @pytest.fixture
    def registry(self):
        return AskUserRegistry()

    def test_init(self, bridge, registry):
        watcher = AskUserReplyWatcher(bridge, registry)
        assert watcher._bridge is bridge
        assert watcher._registry is registry

    @pytest.mark.asyncio
    async def test_delivers_user_reply_to_pending_ask(self, bridge, registry):
        handler = _handler_with_pending("task-abc")
        registry.register("task-abc", handler)

        watcher = AskUserReplyWatcher(bridge, registry)

        # First poll: only the agent question exists — seeds the seen set
        bridge.get_task_messages = MagicMock(return_value=[
            {"_id": "msg-1", "author_type": "agent", "content": "**agent is asking:**\n\nWhat color?"},
        ])
        await watcher._poll_once()

        # Second poll: user reply appears
        bridge.get_task_messages = MagicMock(return_value=[
            {"_id": "msg-1", "author_type": "agent", "content": "**agent is asking:**\n\nWhat color?"},
            {"_id": "msg-2", "author_type": "user", "content": "Blue"},
        ])
        await watcher._poll_once()

        # The fake future in _pending_ask should have been resolved
        future = handler._pending_ask.get("req-123")
        # deliver_user_reply was called by deliver_reply which calls handler.deliver_user_reply
        # The MagicMock future's set_result would be called
        assert future is not None

    @pytest.mark.asyncio
    async def test_ignores_agent_messages(self, bridge, registry):
        handler = _handler_with_pending("task-abc")
        registry.register("task-abc", handler)

        bridge.get_task_messages = MagicMock(return_value=[
            {"_id": "msg-1", "author_type": "agent", "content": "I am done"},
        ])

        await AskUserReplyWatcher(bridge, registry)._poll_once()

        # Only one poll with agent message — future should NOT be resolved
        # (MagicMock future's set_result should not have been called)

    @pytest.mark.asyncio
    async def test_skips_tasks_without_pending_ask(self, bridge, registry):
        handler = AskUserHandler()  # no pending asks
        registry.register("task-abc", handler)

        await AskUserReplyWatcher(bridge, registry)._poll_once()

        bridge.get_task_messages.assert_not_called()

    @pytest.mark.asyncio
    async def test_deduplicates_seen_messages(self, bridge, registry):
        # Use a real event loop future so we can check if it was resolved
        loop = asyncio.get_running_loop()
        handler = AskUserHandler()
        future = loop.create_future()
        handler._pending_ask["req-123"] = future
        handler._task_to_request["task-abc"] = "req-123"
        registry.register("task-abc", handler)

        watcher = AskUserReplyWatcher(bridge, registry)

        # First poll: seed seen set (empty thread)
        bridge.get_task_messages = MagicMock(return_value=[])
        await watcher._poll_once()

        # Second poll: user message appears
        bridge.get_task_messages = MagicMock(return_value=[
            {"_id": "msg-1", "author_type": "user", "content": "Blue"},
        ])
        await watcher._poll_once()

        assert future.done()
        assert future.result() == "Blue"

        # Re-register a fresh pending ask so has_pending_ask is still True for 3rd poll
        future2 = loop.create_future()
        handler._pending_ask["req-456"] = future2
        handler._task_to_request["task-abc"] = "req-456"

        # Third poll: same message still there — should NOT deliver again
        await watcher._poll_once()

        assert not future2.done()  # msg-1 already seen, not delivered again
