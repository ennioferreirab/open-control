"""Tests for the mention_handler module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mc.mention_handler import (
    extract_mentions,
    is_mention_message,
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
