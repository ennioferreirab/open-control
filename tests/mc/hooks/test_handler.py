"""Tests for mc.hooks.handler — BaseHandler subclassing and method dispatch."""

from __future__ import annotations

from typing import ClassVar

import pytest

from mc.hooks.handler import BaseHandler


class TestBaseHandlerMatching:
    """Test the BaseHandler.matches() classmethod."""

    def test_exact_match(self):
        class H(BaseHandler):
            events: ClassVar[list[tuple[str, str | None]]] = [("PostToolUse", "Write")]

        assert H.matches("PostToolUse", "Write") is True

    def test_exact_mismatch_tool(self):
        class H(BaseHandler):
            events: ClassVar[list[tuple[str, str | None]]] = [("PostToolUse", "Write")]

        assert H.matches("PostToolUse", "Bash") is False

    def test_exact_mismatch_event(self):
        class H(BaseHandler):
            events: ClassVar[list[tuple[str, str | None]]] = [("PostToolUse", "Write")]

        assert H.matches("TaskCompleted", "Write") is False

    def test_wildcard_matcher(self):
        """When matcher_value is None, any tool name should match."""

        class H(BaseHandler):
            events: ClassVar[list[tuple[str, str | None]]] = [("TaskCompleted", None)]

        assert H.matches("TaskCompleted", "") is True
        assert H.matches("TaskCompleted", "anything") is True
        assert H.matches("TaskCompleted", "Write") is True

    def test_wildcard_wrong_event(self):
        class H(BaseHandler):
            events: ClassVar[list[tuple[str, str | None]]] = [("TaskCompleted", None)]

        assert H.matches("PostToolUse", "") is False

    def test_multiple_events(self):
        class H(BaseHandler):
            events: ClassVar[list[tuple[str, str | None]]] = [
                ("PostToolUse", "Write"),
                ("TaskCompleted", None),
            ]

        assert H.matches("PostToolUse", "Write") is True
        assert H.matches("TaskCompleted", "any") is True
        assert H.matches("SubagentStart", "") is False

    def test_empty_events_list(self):
        class H(BaseHandler):
            events: ClassVar[list[tuple[str, str | None]]] = []

        assert H.matches("PostToolUse", "Write") is False

    def test_default_events_is_empty(self):
        assert BaseHandler.matches("PostToolUse", "Write") is False


class TestBaseHandlerInit:
    """Test BaseHandler instantiation and attributes."""

    def test_stores_ctx_and_payload(self):
        ctx = object()
        payload = {"key": "value"}
        handler = BaseHandler(ctx, payload)  # type: ignore[arg-type]
        assert handler.ctx is ctx
        assert handler.payload is payload

    def test_handle_raises_not_implemented(self):
        handler = BaseHandler(None, {})  # type: ignore[arg-type]
        with pytest.raises(NotImplementedError):
            handler.handle()


class TestBaseHandlerSubclass:
    """Test that subclassing works correctly."""

    def test_subclass_can_override_handle(self):
        class Custom(BaseHandler):
            events: ClassVar[list[tuple[str, str | None]]] = [("TestEvent", None)]

            def handle(self) -> str | None:
                return "custom result"

        handler = Custom(None, {})  # type: ignore[arg-type]
        assert handler.handle() == "custom result"

    def test_subclass_inherits_matches(self):
        class Custom(BaseHandler):
            events: ClassVar[list[tuple[str, str | None]]] = [("TestEvent", "ToolA")]

        assert Custom.matches("TestEvent", "ToolA") is True
        assert Custom.matches("TestEvent", "ToolB") is False

    def test_subclass_can_return_none(self):
        class Custom(BaseHandler):
            events: ClassVar[list[tuple[str, str | None]]] = [("TestEvent", None)]

            def handle(self) -> str | None:
                return None

        handler = Custom(None, {})  # type: ignore[arg-type]
        assert handler.handle() is None

    def test_subclass_can_access_payload(self):
        class Custom(BaseHandler):
            events: ClassVar[list[tuple[str, str | None]]] = [("TestEvent", None)]

            def handle(self) -> str | None:
                return self.payload.get("name")

        handler = Custom(None, {"name": "test-value"})  # type: ignore[arg-type]
        assert handler.handle() == "test-value"
