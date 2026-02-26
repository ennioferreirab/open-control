"""Tests for _build_thread_context in executor.py."""

import pytest

from nanobot.mc.executor import _build_thread_context
from nanobot.mc.thread_context import ThreadContextBuilder


def _msg(author_name: str, author_type: str, content: str, message_type: str = "work", ts: str = "2026-02-23T10:00:00Z"):
    return {
        "author_name": author_name,
        "author_type": author_type,
        "content": content,
        "message_type": message_type,
        "timestamp": ts,
    }


class TestBuildThreadContextEmpty:
    """Empty/no-op scenarios."""

    def test_empty_list_returns_empty(self):
        assert _build_thread_context([]) == ""

    def test_no_user_messages_returns_empty(self):
        messages = [
            _msg("System", "system", "Agent started work", "system_event"),
            _msg("research-agent", "agent", "Here is my analysis", "work"),
        ]
        assert _build_thread_context(messages) == ""

    def test_none_like_returns_empty(self):
        assert _build_thread_context([]) == ""


class TestBuildThreadContextBasic:
    """Basic formatting."""

    def test_single_user_message(self):
        messages = [
            _msg("User", "user", "Please fix the bug", "user_message", "2026-02-23T10:00:00Z"),
        ]
        result = _build_thread_context(messages)
        # Single user message goes to [Latest Follow-up]; no thread history
        # is rendered because there are no other messages to show.
        assert "[Latest Follow-up]" in result
        assert "User: Please fix the bug" in result

    def test_multi_turn_conversation(self):
        messages = [
            _msg("System", "system", "Agent started", "system_event", "2026-02-23T10:00:00Z"),
            _msg("research-agent", "agent", "Done with analysis", "work", "2026-02-23T10:01:00Z"),
            _msg("User", "user", "Can you also check X?", "user_message", "2026-02-23T10:05:00Z"),
        ]
        result = _build_thread_context(messages)
        assert "[Thread History]" in result
        assert "System [system]" in result
        assert "research-agent [agent]" in result
        assert "[Latest Follow-up]" in result
        assert "User: Can you also check X?" in result

    def test_latest_user_message_separated(self):
        """The latest user message should be in [Latest Follow-up], not [Thread History]."""
        messages = [
            _msg("User", "user", "First instruction", "user_message", "2026-02-23T10:00:00Z"),
            _msg("agent", "agent", "Response", "work", "2026-02-23T10:01:00Z"),
            _msg("User", "user", "Follow-up instruction", "user_message", "2026-02-23T10:05:00Z"),
        ]
        result = _build_thread_context(messages)
        # The latest user message should be in Follow-up section
        assert "User: Follow-up instruction" in result.split("[Latest Follow-up]")[1]
        # The first user message should be in Thread History
        history = result.split("[Latest Follow-up]")[0]
        assert "First instruction" in history

    def test_message_format_includes_author_type_timestamp(self):
        messages = [
            _msg("System", "system", "Task started", "system_event", "2026-02-23T10:00:00Z"),
            _msg("User", "user", "Do something", "user_message", "2026-02-23T10:05:00Z"),
        ]
        result = _build_thread_context(messages)
        assert "System [system] (2026-02-23T10:00:00Z): Task started" in result


class TestBuildThreadContextTruncation:
    """Truncation for >max_messages."""

    def test_truncation_at_default_20(self):
        messages = []
        for i in range(25):
            messages.append(
                _msg("agent", "agent", f"Message {i}", "work", f"2026-02-23T10:{i:02d}:00Z")
            )
        # Add a user message at the end to trigger context injection
        messages.append(
            _msg("User", "user", "Latest follow-up", "user_message", "2026-02-23T10:30:00Z")
        )
        result = _build_thread_context(messages)
        assert "(6 earlier messages omitted)" in result
        assert "[Latest Follow-up]" in result
        assert "User: Latest follow-up" in result

    def test_custom_max_messages(self):
        messages = [
            _msg("agent", "agent", f"Msg {i}", "work", f"2026-02-23T10:{i:02d}:00Z")
            for i in range(10)
        ]
        messages.append(
            _msg("User", "user", "Follow up", "user_message", "2026-02-23T10:15:00Z")
        )
        result = _build_thread_context(messages, max_messages=5)
        assert "(6 earlier messages omitted)" in result

    def test_exactly_max_messages_no_truncation(self):
        messages = [
            _msg("agent", "agent", f"Msg {i}", "work")
            for i in range(19)
        ]
        messages.append(_msg("User", "user", "Follow up", "user_message"))
        result = _build_thread_context(messages, max_messages=20)
        assert "earlier messages omitted" not in result


class TestBuildThreadContextEdgeCases:
    """Edge cases and boundary conditions."""

    def test_user_message_detected_by_author_type(self):
        """User messages can be detected by author_type='user' even with non-user_message type."""
        messages = [
            _msg("User", "user", "Approved", "approval"),
        ]
        result = _build_thread_context(messages)
        assert result != ""  # Should trigger context injection

    def test_user_message_detected_by_message_type(self):
        """User messages can be detected by message_type='user_message'."""
        messages = [
            _msg("SomeUser", "user", "Hello", "user_message"),
        ]
        result = _build_thread_context(messages)
        assert result != ""

    def test_missing_fields_use_defaults(self):
        messages = [
            {"content": "test"},  # Minimal message
            {"author_type": "user", "content": "follow up"},  # Triggers injection
        ]
        result = _build_thread_context(messages)
        assert "Unknown [system]" in result  # defaults


class TestFormatCommentMessage:
    """Tests for comment message formatting (Story 9-2)."""

    def test_format_comment_message(self):
        builder = ThreadContextBuilder()
        msg = {
            "author_name": "Alice",
            "type": "comment",
            "content": "This needs review",
            "timestamp": "2026-01-01T00:00:00Z",
        }
        result = builder._format_message(msg)
        assert result == "Alice [Comment]: This needs review"

    def test_comment_in_thread_context(self):
        """Comments should appear in thread context (not filtered out)."""
        messages = [
            _msg("User", "user", "Fix the bug", "user_message", "2026-02-23T10:00:00Z"),
            {
                "author_name": "Alice",
                "author_type": "user",
                "content": "This needs review",
                "message_type": "comment",
                "type": "comment",
                "timestamp": "2026-02-23T10:01:00Z",
            },
            _msg("User", "user", "Any update?", "user_message", "2026-02-23T10:05:00Z"),
        ]
        result = _build_thread_context(messages)
        assert "Alice [Comment]: This needs review" in result
        assert "[Thread History]" in result
        assert "[Latest Follow-up]" in result
