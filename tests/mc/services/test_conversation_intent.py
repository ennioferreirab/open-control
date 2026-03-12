"""Tests for ConversationIntentResolver — Story 17.3, AC1."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mc.contexts.conversation.intent import (
    ConversationIntent,
    ConversationIntentResolver,
)


# All agent names used across tests
_ALL_TEST_AGENTS = {"researcher", "alice", "bob", "nanobot"}


@pytest.fixture(autouse=True)
def _mock_known_agent_names():
    """Patch _known_agent_names so tests do not depend on ~/.nanobot/agents/."""
    with patch(
        "mc.contexts.conversation.mentions.handler._known_agent_names",
        return_value=_ALL_TEST_AGENTS,
    ):
        yield


@pytest.fixture
def bridge() -> MagicMock:
    """Create a mock ConvexBridge."""
    b = MagicMock()
    b.query = MagicMock(return_value=None)
    return b


@pytest.fixture
def resolver(bridge: MagicMock) -> ConversationIntentResolver:
    return ConversationIntentResolver(bridge=bridge)


# ── Intent: comment ──────────────────────────────────────────────────


class TestCommentIntent:
    """Plain comment — no agent action."""

    def test_plain_message_no_task(self, resolver: ConversationIntentResolver) -> None:
        """A plain message on a task with no assigned agent is a comment."""
        task_data: dict = {"status": "inbox", "assigned_agent": None}
        result = resolver.resolve(
            content="This is a plain comment",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.intent == ConversationIntent.COMMENT

    def test_plain_message_done_task(
        self, resolver: ConversationIntentResolver
    ) -> None:
        """A plain message on a done task (no mention) is a comment."""
        task_data: dict = {"status": "done", "assigned_agent": "researcher"}
        result = resolver.resolve(
            content="Thanks, looks good!",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.intent == ConversationIntent.COMMENT

    def test_empty_content_is_comment(
        self, resolver: ConversationIntentResolver
    ) -> None:
        task_data: dict = {"status": "in_progress", "assigned_agent": "researcher"}
        result = resolver.resolve(
            content="   ",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.intent == ConversationIntent.COMMENT


# ── Intent: mention ──────────────────────────────────────────────────


class TestMentionIntent:
    """@mention of an agent."""

    def test_mention_in_inbox(self, resolver: ConversationIntentResolver) -> None:
        """@mention detected regardless of task status."""
        task_data: dict = {"status": "inbox", "assigned_agent": None}
        result = resolver.resolve(
            content="@researcher help me with this",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.intent == ConversationIntent.MENTION
        assert result.mentioned_agents == [("researcher", "help me with this")]

    def test_mention_in_done_task(
        self, resolver: ConversationIntentResolver
    ) -> None:
        """@mention works on done tasks (universal mentions)."""
        task_data: dict = {"status": "done", "assigned_agent": "alice"}
        result = resolver.resolve(
            content="@bob can you review this?",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.intent == ConversationIntent.MENTION
        assert result.mentioned_agents[0][0] == "bob"

    def test_mention_in_crashed_task(
        self, resolver: ConversationIntentResolver
    ) -> None:
        """@mention works on crashed tasks."""
        task_data: dict = {"status": "crashed", "assigned_agent": "alice"}
        result = resolver.resolve(
            content="@researcher debug this crash",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.intent == ConversationIntent.MENTION

    def test_mention_overrides_follow_up(
        self, resolver: ConversationIntentResolver
    ) -> None:
        """A message with @mention is always classified as mention, not follow_up."""
        task_data: dict = {"status": "in_progress", "assigned_agent": "alice"}
        result = resolver.resolve(
            content="@researcher help me with this",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.intent == ConversationIntent.MENTION

    def test_mention_overrides_plan_chat(
        self, resolver: ConversationIntentResolver
    ) -> None:
        """@mention takes priority over plan_chat."""
        task_data: dict = {
            "status": "review",
            "awaiting_kickoff": True,
            "execution_plan": {"steps": [{"title": "Step 1"}]},
            "assigned_agent": "alice",
        }
        result = resolver.resolve(
            content="@bob help with the plan",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.intent == ConversationIntent.MENTION

    def test_mention_overrides_manual_reply(
        self, resolver: ConversationIntentResolver
    ) -> None:
        """@mention takes priority over manual_reply (ask_user pending)."""
        task_data: dict = {"status": "review", "assigned_agent": "alice"}
        result = resolver.resolve(
            content="@bob help me answer",
            task_data=task_data,
            has_pending_ask=True,
        )
        assert result.intent == ConversationIntent.MENTION


# ── Intent: manual_reply ─────────────────────────────────────────────


class TestManualReplyIntent:
    """Human reply in manual/human task (ask_user pending)."""

    def test_manual_reply_when_ask_pending(
        self, resolver: ConversationIntentResolver
    ) -> None:
        """User reply while ask_user is pending => manual_reply."""
        task_data: dict = {"status": "review", "assigned_agent": "alice"}
        result = resolver.resolve(
            content="Yes, proceed with option 2",
            task_data=task_data,
            has_pending_ask=True,
        )
        assert result.intent == ConversationIntent.MANUAL_REPLY

    def test_manual_reply_in_progress(
        self, resolver: ConversationIntentResolver
    ) -> None:
        """manual_reply recognized when ask_user pending, even in_progress."""
        task_data: dict = {"status": "in_progress", "assigned_agent": "alice"}
        result = resolver.resolve(
            content="Go ahead",
            task_data=task_data,
            has_pending_ask=True,
        )
        assert result.intent == ConversationIntent.MANUAL_REPLY


# ── Intent: plan_chat ────────────────────────────────────────────────


class TestPlanChatIntent:
    """Plan discussion/negotiation."""

    def test_plan_chat_review_awaiting_kickoff(
        self, resolver: ConversationIntentResolver
    ) -> None:
        """Review + awaitingKickoff + plan => plan_chat."""
        task_data: dict = {
            "status": "review",
            "awaiting_kickoff": True,
            "execution_plan": {"steps": [{"title": "Step 1"}]},
            "assigned_agent": "alice",
        }
        result = resolver.resolve(
            content="Can we add a testing step?",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.intent == ConversationIntent.PLAN_CHAT

    def test_plan_chat_in_progress_with_plan(
        self, resolver: ConversationIntentResolver
    ) -> None:
        """in_progress with execution plan => plan_chat."""
        task_data: dict = {
            "status": "in_progress",
            "execution_plan": {"steps": [{"title": "Step 1"}]},
            "assigned_agent": "alice",
        }
        result = resolver.resolve(
            content="Change step 2 to use researcher",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.intent == ConversationIntent.PLAN_CHAT

    def test_not_plan_chat_when_review_without_kickoff(
        self, resolver: ConversationIntentResolver
    ) -> None:
        """Review without awaiting_kickoff is NOT plan_chat."""
        task_data: dict = {
            "status": "review",
            "awaiting_kickoff": False,
            "execution_plan": {"steps": [{"title": "Step 1"}]},
            "assigned_agent": "alice",
        }
        result = resolver.resolve(
            content="Change the plan",
            task_data=task_data,
            has_pending_ask=False,
        )
        # Should be follow_up or comment, not plan_chat
        assert result.intent != ConversationIntent.PLAN_CHAT

    def test_not_plan_chat_when_no_plan(
        self, resolver: ConversationIntentResolver
    ) -> None:
        """in_progress without execution plan is NOT plan_chat."""
        task_data: dict = {
            "status": "in_progress",
            "assigned_agent": "alice",
        }
        result = resolver.resolve(
            content="Change the approach",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.intent == ConversationIntent.FOLLOW_UP


# ── Intent: follow_up ────────────────────────────────────────────────


class TestFollowUpIntent:
    """Non-mention follow-up to agent in active task."""

    def test_follow_up_in_progress(
        self, resolver: ConversationIntentResolver
    ) -> None:
        """Non-mention message on in_progress task (no plan) => follow_up."""
        task_data: dict = {"status": "in_progress", "assigned_agent": "alice"}
        result = resolver.resolve(
            content="Can you also check the tests?",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.intent == ConversationIntent.FOLLOW_UP

    def test_follow_up_assigned(
        self, resolver: ConversationIntentResolver
    ) -> None:
        """Non-mention on assigned task => follow_up."""
        task_data: dict = {"status": "assigned", "assigned_agent": "alice"}
        result = resolver.resolve(
            content="Please prioritize this",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.intent == ConversationIntent.FOLLOW_UP

    def test_follow_up_review_non_kickoff(
        self, resolver: ConversationIntentResolver
    ) -> None:
        """Non-mention on review (not awaiting kickoff) => follow_up."""
        task_data: dict = {
            "status": "review",
            "awaiting_kickoff": False,
            "assigned_agent": "alice",
        }
        result = resolver.resolve(
            content="What do you think?",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.intent == ConversationIntent.FOLLOW_UP

    def test_follow_up_retrying(
        self, resolver: ConversationIntentResolver
    ) -> None:
        """Non-mention on retrying task => follow_up."""
        task_data: dict = {"status": "retrying", "assigned_agent": "alice"}
        result = resolver.resolve(
            content="Any progress?",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.intent == ConversationIntent.FOLLOW_UP


# ── ResolveResult fields ─────────────────────────────────────────────


class TestResolveResultFields:
    """Verify that ResolveResult carries correct metadata."""

    def test_mention_result_has_mentioned_agents(
        self, resolver: ConversationIntentResolver
    ) -> None:
        task_data: dict = {"status": "inbox"}
        result = resolver.resolve(
            content="@alice @bob help",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.intent == ConversationIntent.MENTION
        names = [a[0] for a in result.mentioned_agents]
        assert "alice" in names
        assert "bob" in names

    def test_non_mention_result_has_empty_mentioned_agents(
        self, resolver: ConversationIntentResolver
    ) -> None:
        task_data: dict = {"status": "in_progress", "assigned_agent": "alice"}
        result = resolver.resolve(
            content="Hello",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.mentioned_agents == []

    def test_result_carries_content(
        self, resolver: ConversationIntentResolver
    ) -> None:
        task_data: dict = {"status": "inbox"}
        result = resolver.resolve(
            content="some message",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.content == "some message"

    def test_result_carries_task_data(
        self, resolver: ConversationIntentResolver
    ) -> None:
        task_data: dict = {"status": "done", "assigned_agent": "alice"}
        result = resolver.resolve(
            content="thanks",
            task_data=task_data,
            has_pending_ask=False,
        )
        assert result.task_data is task_data
