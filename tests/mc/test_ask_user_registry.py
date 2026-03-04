"""Tests for AskUserRegistry — global registry of active MCSocketServer instances."""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from mc.ask_user_registry import AskUserRegistry


class TestAskUserRegistry:
    def test_register_and_lookup(self):
        registry = AskUserRegistry()
        mock_server = MagicMock()
        registry.register("task-abc", mock_server)
        assert registry.get("task-abc") is mock_server

    def test_unregister(self):
        registry = AskUserRegistry()
        mock_server = MagicMock()
        registry.register("task-abc", mock_server)
        registry.unregister("task-abc")
        assert registry.get("task-abc") is None

    def test_unregister_idempotent(self):
        registry = AskUserRegistry()
        registry.unregister("nonexistent")

    def test_get_missing_returns_none(self):
        registry = AskUserRegistry()
        assert registry.get("nonexistent") is None

    def test_has_pending_ask(self):
        registry = AskUserRegistry()
        mock_server = MagicMock()
        mock_server._task_to_request = {"task-abc": "req-123"}
        mock_server._pending_ask = {"req-123": MagicMock()}
        registry.register("task-abc", mock_server)
        assert registry.has_pending_ask("task-abc") is True

    def test_has_pending_ask_no_pending(self):
        registry = AskUserRegistry()
        mock_server = MagicMock()
        mock_server._task_to_request = {}
        mock_server._pending_ask = {}
        registry.register("task-abc", mock_server)
        assert registry.has_pending_ask("task-abc") is False

    def test_has_pending_ask_unregistered(self):
        registry = AskUserRegistry()
        assert registry.has_pending_ask("nonexistent") is False

    def test_active_task_ids(self):
        registry = AskUserRegistry()
        server_a = MagicMock()
        server_a._task_to_request = {"task-a": "req-1"}
        server_a._pending_ask = {"req-1": MagicMock()}
        server_b = MagicMock()
        server_b._task_to_request = {}
        server_b._pending_ask = {}
        registry.register("task-a", server_a)
        registry.register("task-b", server_b)
        assert registry.active_task_ids() == {"task-a"}

    def test_deliver_reply(self):
        registry = AskUserRegistry()
        mock_server = MagicMock()
        mock_server._task_to_request = {"task-abc": "req-123"}
        mock_server._pending_ask = {"req-123": MagicMock()}
        registry.register("task-abc", mock_server)
        result = registry.deliver_reply("task-abc", "Yes!")
        mock_server.deliver_user_reply.assert_called_once_with("task-abc", "Yes!")
        assert result is True

    def test_deliver_reply_no_server(self):
        registry = AskUserRegistry()
        result = registry.deliver_reply("nonexistent", "answer")
        assert result is False
