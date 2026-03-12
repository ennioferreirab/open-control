"""Tests for the mention_handler module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mc.contexts.conversation.mentions.handler import (
    _build_execution_plan_summary,
    _build_task_context,
    _build_task_files_section,
    extract_mentions,
    is_mention_message,
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
        "mc.contexts.conversation.mentions.handler._known_agent_names",
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


class TestBuildTaskContext:
    """Tests for _build_task_context()."""

    def test_none_task_data(self):
        assert _build_task_context(None) == ""

    def test_empty_task_data(self):
        assert _build_task_context({}) == ""

    def test_full_task_context(self):
        task = {
            "title": "Fix the bug",
            "description": "A critical bug in auth",
            "status": "in_progress",
            "assigned_agent": "researcher",
            "tags": ["urgent", "backend"],
            "board_id": "board_sprint5",
        }
        result = _build_task_context(task)
        assert "[Task Context]" in result
        assert "Title: Fix the bug" in result
        assert "Description: A critical bug in auth" in result
        assert "Status: in_progress" in result
        assert "Assigned Agent: researcher" in result
        assert "Tags: urgent, backend" in result
        assert "Board ID: board_sprint5" in result

    def test_omits_empty_fields(self):
        task = {"title": "Only title", "description": ""}
        result = _build_task_context(task)
        assert "Title: Only title" in result
        assert "Description" not in result


class TestBuildExecutionPlanSummary:
    """Tests for _build_execution_plan_summary()."""

    def test_none_task_data(self):
        assert _build_execution_plan_summary(None) == ""

    def test_no_plan(self):
        assert _build_execution_plan_summary({"title": "Test"}) == ""

    def test_plan_with_steps(self):
        task = {
            "execution_plan": {
                "steps": [
                    {"title": "Research", "status": "completed"},
                    {"title": "Implement", "status": "in_progress"},
                    {"title": "Test", "status": "pending"},
                ]
            }
        }
        result = _build_execution_plan_summary(task)
        assert "[Execution Plan]" in result
        assert "1. Research — completed" in result
        assert "2. Implement — in_progress" in result
        assert "3. Test — pending" in result

    def test_empty_steps_list(self):
        task = {"execution_plan": {"steps": []}}
        assert _build_execution_plan_summary(task) == ""


class TestBuildTaskFilesSection:
    """Tests for _build_task_files_section()."""

    def test_none_task_data(self):
        assert _build_task_files_section(None) == ""

    def test_no_files(self):
        assert _build_task_files_section({"title": "Test"}) == ""

    def test_with_files(self):
        task = {
            "files": [
                {"name": "report.pdf", "description": "Q4 report", "subfolder": "output"},
                {"name": "data.csv", "subfolder": "attachments"},
            ]
        }
        result = _build_task_files_section(task)
        assert "[Task Files]" in result
        assert "report.pdf (output) — Q4 report" in result
        assert "data.csv (attachments)" in result

    def test_empty_files_list(self):
        task = {"files": []}
        assert _build_task_files_section(task) == ""


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
