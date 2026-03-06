"""Tests for AskUserRegistry — global registry of active AskUserHandler instances."""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from mc.ask_user.handler import AskUserHandler
from mc.ask_user.registry import AskUserRegistry


def _handler_with_pending(task_id: str) -> AskUserHandler:
    """Create an AskUserHandler with a fake pending ask for the given task_id."""
    handler = AskUserHandler()
    handler._pending_ask["req-123"] = MagicMock()  # fake future
    handler._task_to_request[task_id] = "req-123"
    return handler


class TestAskUserRegistry:
    def test_register_and_lookup(self):
        registry = AskUserRegistry()
        handler = AskUserHandler()
        registry.register("task-abc", handler)
        assert registry.get("task-abc") is handler

    def test_unregister(self):
        registry = AskUserRegistry()
        handler = AskUserHandler()
        registry.register("task-abc", handler)
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
        handler = _handler_with_pending("task-abc")
        registry.register("task-abc", handler)
        assert registry.has_pending_ask("task-abc") is True

    def test_has_pending_ask_no_pending(self):
        registry = AskUserRegistry()
        handler = AskUserHandler()  # no pending asks
        registry.register("task-abc", handler)
        assert registry.has_pending_ask("task-abc") is False

    def test_has_pending_ask_unregistered(self):
        registry = AskUserRegistry()
        assert registry.has_pending_ask("nonexistent") is False

    def test_active_task_ids(self):
        registry = AskUserRegistry()
        handler_a = _handler_with_pending("task-a")
        handler_b = AskUserHandler()  # no pending asks
        registry.register("task-a", handler_a)
        registry.register("task-b", handler_b)
        assert registry.active_task_ids() == {"task-a"}

    def test_deliver_reply(self):
        registry = AskUserRegistry()
        loop = asyncio.new_event_loop()
        try:
            handler = AskUserHandler()
            future = loop.create_future()
            handler._pending_ask["req-123"] = future
            handler._task_to_request["task-abc"] = "req-123"
            registry.register("task-abc", handler)
            result = registry.deliver_reply("task-abc", "Yes!")
            assert result is True
            assert future.done()
            assert future.result() == "Yes!"
        finally:
            loop.close()

    def test_deliver_reply_no_handler(self):
        registry = AskUserRegistry()
        result = registry.deliver_reply("nonexistent", "answer")
        assert result is False
