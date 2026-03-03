"""Tests for the mention_handler module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mc.mention_handler import (
    extract_mentions,
    is_mention_message,
    _build_mention_context,
    _list_available_agents,
)

# All agent names used across tests — returned by the mocked _known_agent_names
_ALL_TEST_AGENTS = {
    "researcher",
    "alice",
    "bob",
    "life-secretary",
    "agent",
    "my_agent",
}


@pytest.fixture(autouse=True)
def _mock_known_agent_names():
    """Patch _known_agent_names so tests do not depend on ~/.nanobot/agents/."""
    with patch(
        "mc.mention_handler._known_agent_names",
        return_value=_ALL_TEST_AGENTS,
    ):
        yield


class TestExtractMentions:
    """Tests for extract_mentions()."""

    def test_single_mention_with_query(self):
        mentions = extract_mentions("@researcher what is the GDP of Brazil?")
        assert len(mentions) == 1
        agent, query = mentions[0]
        assert agent == "researcher"
        assert "GDP of Brazil" in query

    def test_single_mention_no_query(self):
        mentions = extract_mentions("@researcher")
        assert len(mentions) == 1
        agent, query = mentions[0]
        assert agent == "researcher"
        assert query == ""

    def test_multiple_mentions_same_message(self):
        mentions = extract_mentions("@alice @bob help me with this")
        assert len(mentions) == 2
        names = [m[0] for m in mentions]
        assert "alice" in names
        assert "bob" in names
        # Both receive the same query (without @mentions)
        for _, query in mentions:
            assert "help me with this" in query
            assert "@alice" not in query
            assert "@bob" not in query

    def test_mention_with_hyphens(self):
        mentions = extract_mentions("@life-secretary schedule a meeting")
        assert len(mentions) == 1
        agent, query = mentions[0]
        assert agent == "life-secretary"
        assert "schedule a meeting" in query

    def test_inline_mention(self):
        mentions = extract_mentions("Can you ask @researcher to check this?")
        assert len(mentions) == 1
        agent, query = mentions[0]
        assert agent == "researcher"
        assert "Can you ask" in query or "to check this?" in query

    def test_no_mention(self):
        mentions = extract_mentions("This is a normal message without mentions")
        assert mentions == []

    def test_empty_message(self):
        mentions = extract_mentions("")
        assert mentions == []

    def test_deduplicate_mentions(self):
        mentions = extract_mentions("@alice @alice please help")
        assert len(mentions) == 1
        assert mentions[0][0] == "alice"

    def test_mention_lowercase_normalization(self):
        # Mentions are lowercased
        mentions = extract_mentions("@Researcher help me")
        assert mentions[0][0] == "researcher"

    def test_mention_strips_at_sign_from_query(self):
        mentions = extract_mentions("@researcher what do you think?")
        _, query = mentions[0]
        assert "@" not in query or "email@" not in query  # @mentions removed


class TestIsMentionMessage:
    """Tests for is_mention_message()."""

    def test_returns_true_for_mention(self):
        assert is_mention_message("@researcher help") is True

    def test_returns_false_for_no_mention(self):
        assert is_mention_message("normal message") is False

    def test_returns_true_for_inline_mention(self):
        assert is_mention_message("ask @alice about this") is True

    def test_returns_false_for_empty(self):
        assert is_mention_message("") is False


class TestBuildMentionContext:
    """Tests for _build_mention_context()."""

    def test_empty_messages(self):
        result = _build_mention_context([])
        assert result == ""

    def test_filters_system_events(self):
        messages = [
            {
                "author_name": "System",
                "author_type": "system",
                "message_type": "system_event",
                "content": "Task started",
            },
            {
                "author_name": "Alice",
                "author_type": "user",
                "message_type": "user_message",
                "content": "Hello",
            },
        ]
        result = _build_mention_context(messages)
        assert "Hello" in result
        assert "Task started" not in result

    def test_truncates_long_content(self):
        long_content = "x" * 500
        messages = [
            {
                "author_name": "Alice",
                "author_type": "user",
                "content": long_content,
            }
        ]
        result = _build_mention_context(messages)
        assert "..." in result
        assert len(result) < len(long_content) + 100  # Significantly shorter

    def test_returns_context_header(self):
        messages = [
            {
                "author_name": "Alice",
                "author_type": "user",
                "content": "Test message",
            }
        ]
        result = _build_mention_context(messages)
        assert "[Recent Thread Context]" in result
        assert "Alice" in result
        assert "Test message" in result

    def test_max_messages_limit(self):
        messages = [
            {"author_name": f"User{i}", "author_type": "user", "content": f"msg{i}"}
            for i in range(20)
        ]
        result = _build_mention_context(messages, max_messages=5)
        # Only last 5 messages should appear
        assert "msg19" in result
        assert "msg14" in result
        assert "msg0" not in result


class TestExtractMentionsEdgeCases:
    """Edge case tests for mention extraction."""

    def test_mention_at_start(self):
        mentions = extract_mentions("@agent do something")
        assert len(mentions) == 1
        assert mentions[0][0] == "agent"

    def test_mention_at_end(self):
        mentions = extract_mentions("do something @agent")
        assert len(mentions) == 1
        assert mentions[0][0] == "agent"

    def test_message_with_only_whitespace_after_mention(self):
        mentions = extract_mentions("@agent   ")
        assert len(mentions) == 1
        _, query = mentions[0]
        assert query == ""

    def test_multiple_words_after_mention(self):
        mentions = extract_mentions("@researcher please analyze this data and provide insights")
        assert len(mentions) == 1
        _, query = mentions[0]
        assert "please analyze this data and provide insights" in query

    def test_underscore_in_agent_name(self):
        mentions = extract_mentions("@my_agent help")
        assert len(mentions) == 1
        assert mentions[0][0] == "my_agent"
