"""Tests for ConversationService — Story 17.3, AC2/AC3/AC4/AC5/AC6."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.services.conversation import ConversationService
from mc.services.conversation_intent import ConversationIntent


# All agent names used across tests
_ALL_TEST_AGENTS = {"researcher", "alice", "bob", "nanobot"}


@pytest.fixture(autouse=True)
def _mock_known_agent_names():
    """Patch _known_agent_names so tests do not depend on ~/.nanobot/agents/."""
    with patch(
        "mc.mentions.handler._known_agent_names",
        return_value=_ALL_TEST_AGENTS,
    ):
        yield


@pytest.fixture
def bridge() -> MagicMock:
    """Create a mock ConvexBridge."""
    b = MagicMock()
    b.query = MagicMock(return_value=None)
    b.get_task = MagicMock(return_value=None)
    b.get_task_messages = MagicMock(return_value=[])
    b.send_message = MagicMock()
    b.post_lead_agent_message = MagicMock()
    b.create_activity = MagicMock()
    b.update_task_status = MagicMock()
    return b


@pytest.fixture
def ask_user_registry() -> MagicMock:
    """Create a mock AskUserRegistry."""
    reg = MagicMock()
    reg.has_pending_ask = MagicMock(return_value=False)
    return reg


@pytest.fixture
def service(bridge: MagicMock, ask_user_registry: MagicMock) -> ConversationService:
    return ConversationService(bridge=bridge, ask_user_registry=ask_user_registry)


# ── AC2: Unified message classification ──────────────────────────────


class TestClassifyMessage:
    """ConversationService.classify delegates to IntentResolver."""

    def test_classify_mention(self, service: ConversationService) -> None:
        task_data: dict[str, Any] = {"status": "inbox"}
        result = service.classify(
            content="@researcher help",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.MENTION

    def test_classify_comment(self, service: ConversationService) -> None:
        task_data: dict[str, Any] = {"status": "done", "assigned_agent": "alice"}
        result = service.classify(
            content="Just a note",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.COMMENT

    def test_classify_follow_up(self, service: ConversationService) -> None:
        task_data: dict[str, Any] = {"status": "in_progress", "assigned_agent": "alice"}
        result = service.classify(
            content="Check the tests too",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.FOLLOW_UP

    def test_classify_plan_chat(self, service: ConversationService) -> None:
        task_data: dict[str, Any] = {
            "status": "review",
            "awaiting_kickoff": True,
            "execution_plan": {"steps": [{"title": "Step 1"}]},
        }
        result = service.classify(
            content="Add a testing step",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.PLAN_CHAT

    def test_classify_manual_reply_when_ask_pending(
        self,
        bridge: MagicMock,
        ask_user_registry: MagicMock,
    ) -> None:
        ask_user_registry.has_pending_ask.return_value = True
        svc = ConversationService(bridge=bridge, ask_user_registry=ask_user_registry)
        task_data: dict[str, Any] = {"status": "review", "assigned_agent": "alice"}
        result = svc.classify(
            content="Yes, option 2",
            task_data=task_data,
            task_id="task-1",
        )
        assert result.intent == ConversationIntent.MANUAL_REPLY


# ── AC3: Unified context construction ────────────────────────────────


class TestContextAssembly:
    """Shared context assembly for all conversation types."""

    @pytest.mark.asyncio
    async def test_build_context_uses_thread_context_builder(
        self, service: ConversationService, bridge: MagicMock
    ) -> None:
        """build_context calls build_thread_context with messages."""
        bridge.get_task_messages = MagicMock(return_value=[
            {"author_name": "User", "author_type": "user", "content": "hello"},
        ])
        with patch(
            "mc.services.conversation.build_thread_context",
            return_value="[Thread History]\nUser [user]: hello",
        ) as mock_btc:
            ctx = await service.build_context(task_id="task-1")
            mock_btc.assert_called_once()
            assert "[Thread History]" in ctx

    @pytest.mark.asyncio
    async def test_build_context_returns_empty_on_no_messages(
        self, service: ConversationService, bridge: MagicMock
    ) -> None:
        bridge.get_task_messages = MagicMock(return_value=[])
        ctx = await service.build_context(task_id="task-1")
        assert ctx == ""


# ── AC4: Mention behavior preserved ─────────────────────────────────


class TestMentionBehavior:
    """Mentions trigger agent response but do NOT change task status."""

    @pytest.mark.asyncio
    async def test_handle_mention_does_not_change_status(
        self, service: ConversationService, bridge: MagicMock
    ) -> None:
        """Dispatching a mention should NOT call update_task_status."""
        task_data: dict[str, Any] = {
            "status": "in_progress",
            "assigned_agent": "alice",
            "title": "Test Task",
        }
        with patch(
            "mc.services.conversation.handle_all_mentions",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await service.handle_message(
                task_id="task-1",
                content="@researcher help",
                task_data=task_data,
            )
        bridge.update_task_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_mention_dispatches_to_handler(
        self, service: ConversationService, bridge: MagicMock
    ) -> None:
        """Mention intent dispatches to handle_all_mentions."""
        task_data: dict[str, Any] = {
            "status": "in_progress",
            "assigned_agent": "alice",
            "title": "Test Task",
        }
        with patch(
            "mc.services.conversation.handle_all_mentions",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_mentions:
            await service.handle_message(
                task_id="task-1",
                content="@researcher help",
                task_data=task_data,
            )
            mock_mentions.assert_called_once_with(
                bridge=bridge,
                task_id="task-1",
                content="@researcher help",
                task_title="Test Task",
            )

    @pytest.mark.asyncio
    async def test_mention_works_in_done_status(
        self, service: ConversationService, bridge: MagicMock
    ) -> None:
        """Universal mentions work across all statuses including done."""
        task_data: dict[str, Any] = {
            "status": "done",
            "assigned_agent": "alice",
            "title": "Done Task",
        }
        with patch(
            "mc.services.conversation.handle_all_mentions",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_mentions:
            await service.handle_message(
                task_id="task-1",
                content="@bob review this",
                task_data=task_data,
            )
            mock_mentions.assert_called_once()


# ── AC4: Follow-up behavior ─────────────────────────────────────────


class TestFollowUpBehavior:
    """Non-mention follow-ups CAN move status."""

    @pytest.mark.asyncio
    async def test_follow_up_returns_follow_up_intent(
        self, service: ConversationService, bridge: MagicMock
    ) -> None:
        """follow_up intent is returned for handle_message."""
        task_data: dict[str, Any] = {
            "status": "in_progress",
            "assigned_agent": "alice",
            "title": "Active Task",
        }
        result = await service.handle_message(
            task_id="task-1",
            content="Also check the tests",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.FOLLOW_UP


# ── AC5: Direct replies to CC tasks ─────────────────────────────────


class TestDirectReplyToCCTask:
    """Direct thread replies to Claude Code tasks work correctly."""

    @pytest.mark.asyncio
    async def test_follow_up_on_cc_task_detected(
        self, service: ConversationService, bridge: MagicMock
    ) -> None:
        """follow_up on a CC task should be classified and handled correctly."""
        task_data: dict[str, Any] = {
            "status": "done",
            "assigned_agent": "cc-agent",
            "title": "CC Task",
        }
        # Done + no mention => comment (CC thread reply detection is
        # a separate concern handled by the poller/watcher layer that
        # calls ConversationService.handle_message)
        result = await service.handle_message(
            task_id="task-1",
            content="Can you fix the bug?",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.COMMENT

    @pytest.mark.asyncio
    async def test_follow_up_on_cc_task_in_progress(
        self, service: ConversationService, bridge: MagicMock
    ) -> None:
        """follow_up on an in_progress CC task classifies correctly."""
        task_data: dict[str, Any] = {
            "status": "in_progress",
            "assigned_agent": "cc-agent",
            "title": "CC Task",
        }
        result = await service.handle_message(
            task_id="task-1",
            content="Also handle edge cases",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.FOLLOW_UP


# ── AC2: Plan chat routing ───────────────────────────────────────────


class TestPlanChatRouting:
    """Plan-chat messages route through ConversationService."""

    @pytest.mark.asyncio
    async def test_plan_chat_dispatches_to_negotiator(
        self, service: ConversationService, bridge: MagicMock
    ) -> None:
        """plan_chat intent dispatches to handle_plan_negotiation."""
        task_data: dict[str, Any] = {
            "status": "review",
            "awaiting_kickoff": True,
            "execution_plan": {"steps": [{"title": "Step 1"}]},
            "title": "Plan Task",
        }
        with patch(
            "mc.services.conversation.handle_plan_negotiation",
            new_callable=AsyncMock,
        ) as mock_plan:
            await service.handle_message(
                task_id="task-1",
                content="Add a testing step",
                task_data=task_data,
            )
            mock_plan.assert_called_once_with(
                service._bridge,
                "task-1",
                "Add a testing step",
                task_data["execution_plan"],
                task_status="review",
            )


# ── AC2: Manual reply routing ────────────────────────────────────────


class TestManualReplyRouting:
    """manual_reply messages are passed through to the ask_user flow."""

    @pytest.mark.asyncio
    async def test_manual_reply_returns_intent(
        self,
        bridge: MagicMock,
        ask_user_registry: MagicMock,
    ) -> None:
        """manual_reply intent is returned (delivery is caller's responsibility)."""
        ask_user_registry.has_pending_ask.return_value = True
        svc = ConversationService(bridge=bridge, ask_user_registry=ask_user_registry)
        task_data: dict[str, Any] = {
            "status": "review",
            "assigned_agent": "alice",
            "title": "Ask Task",
        }
        result = await svc.handle_message(
            task_id="task-1",
            content="Yes, proceed",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.MANUAL_REPLY


# ── AC2: Comment handling ────────────────────────────────────────────


class TestCommentHandling:
    """Comments are no-ops: no agent action taken."""

    @pytest.mark.asyncio
    async def test_comment_no_side_effects(
        self, service: ConversationService, bridge: MagicMock
    ) -> None:
        task_data: dict[str, Any] = {
            "status": "done",
            "assigned_agent": "alice",
            "title": "Done Task",
        }
        result = await service.handle_message(
            task_id="task-1",
            content="Looks good, thanks!",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.COMMENT
        bridge.update_task_status.assert_not_called()


# ── Edge cases ───────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge case handling."""

    @pytest.mark.asyncio
    async def test_empty_content(
        self, service: ConversationService, bridge: MagicMock
    ) -> None:
        task_data: dict[str, Any] = {"status": "in_progress", "assigned_agent": "alice"}
        result = await service.handle_message(
            task_id="task-1",
            content="   ",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.COMMENT

    @pytest.mark.asyncio
    async def test_no_task_data_defaults_to_comment(
        self, service: ConversationService, bridge: MagicMock
    ) -> None:
        result = await service.handle_message(
            task_id="task-1",
            content="Hello",
            task_data={},
        )
        assert result.intent == ConversationIntent.COMMENT

    @pytest.mark.asyncio
    async def test_handle_message_returns_resolve_result(
        self, service: ConversationService, bridge: MagicMock
    ) -> None:
        """handle_message always returns a ResolveResult."""
        task_data: dict[str, Any] = {"status": "inbox"}
        result = await service.handle_message(
            task_id="task-1",
            content="@researcher help",
            task_data=task_data,
        )
        from mc.services.conversation_intent import ResolveResult
        assert isinstance(result, ResolveResult)
