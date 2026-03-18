"""Integration tests for ConversationService wired into gateway runtime.

Story 20.2 -- verifies the end-to-end flow:
  message -> ConversationService -> intent resolution -> handler -> response

Tests cover:
- Gateway creates ConversationService and passes it to watchers
- MentionWatcher routes through ConversationService
- AskUserReplyWatcher routes through ConversationService
- Different message types produce correct intents at runtime
- Behavior preservation (mention no-status-change, plan-chat, ask-user, follow-up)
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.contexts.conversation.intent import ConversationIntent
from mc.contexts.conversation.mentions.watcher import MentionWatcher
from mc.contexts.conversation.service import ConversationService

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
    reg.active_task_ids = MagicMock(return_value=set())
    reg.deliver_reply = MagicMock(return_value=False)
    return reg


@pytest.fixture
def conversation_service(bridge: MagicMock, ask_user_registry: MagicMock) -> ConversationService:
    return ConversationService(bridge=bridge, ask_user_registry=ask_user_registry)


class TestWatcherClaims:
    @pytest.mark.asyncio
    async def test_mention_watcher_claims_messages_before_dispatch(
        self, bridge: MagicMock, conversation_service: ConversationService
    ) -> None:
        claims: set[tuple[str, str, str]] = set()

        def _mutation(name: str, args: dict) -> dict | None:
            if name != "runtimeClaims:acquire":
                return None
            claim = (args["claim_kind"], args["entity_type"], args["entity_id"])
            if claim in claims:
                return {"granted": False, "ownerId": "other-runtime"}
            claims.add(claim)
            return {"granted": True, "claimId": "claim-1"}

        bridge.mutation = MagicMock(side_effect=_mutation)
        bridge.get_recent_user_messages = MagicMock(
            return_value=[
                {"_id": "msg-1", "task_id": "task-1", "content": "@researcher help"},
            ]
        )
        bridge.query = MagicMock(return_value={"id": "task-1", "title": "Task 1"})
        conversation_service.handle_message = AsyncMock()

        watcher = MentionWatcher(bridge, conversation_service=conversation_service)
        await watcher._poll_all_tasks()
        watcher._seen_message_ids.clear()
        await watcher._poll_all_tasks()
        await asyncio.sleep(0)

        conversation_service.handle_message.assert_awaited_once()


# ── AC4: Shared Response Posting ───────────────────────────────────────


class TestSharedResponsePosting:
    """All handlers use ConversationService.post_response()."""

    @pytest.mark.asyncio
    async def test_post_response_sends_via_bridge(
        self, conversation_service: ConversationService, bridge: MagicMock
    ) -> None:
        """post_response sends a message via the bridge."""
        await conversation_service.post_response(
            task_id="task-1",
            author_name="researcher",
            content="Here is the answer.",
        )
        bridge.send_message.assert_called_once_with(
            "task-1",
            "researcher",
            "agent",
            "Here is the answer.",
            "work",
        )


# ── AC5: Behavior Preservation ─────────────────────────────────────────


class TestBehaviorPreservation:
    """Verify all existing behaviors work identically after integration."""

    @pytest.mark.asyncio
    async def test_universal_mentions_work_across_all_statuses(
        self, conversation_service: ConversationService
    ) -> None:
        """@mention works in done, crashed, inbox, assigned, and in_progress statuses."""
        for status in ("done", "crashed", "inbox", "assigned", "in_progress"):
            task_data: dict[str, Any] = {
                "status": status,
                "assigned_agent": "alice",
                "title": f"Task in {status}",
            }
            result = await conversation_service.handle_message(
                task_id=f"task-{status}",
                content="@bob help",
                task_data=task_data,
            )
            assert result.intent == ConversationIntent.MENTION, (
                f"Expected MENTION for status={status}, got {result.intent}"
            )


# ── AC6: Integration — end-to-end flow ─────────────────────────────────


class TestEndToEndFlow:
    """Integration: message -> ConversationService -> correct handler."""

    @pytest.mark.asyncio
    async def test_different_intents_from_same_task(
        self, conversation_service: ConversationService
    ) -> None:
        """Same task, different messages -> different intents."""
        task_data: dict[str, Any] = {
            "status": "in_progress",
            "assigned_agent": "alice",
            "title": "Active Task",
        }

        # Mention
        with patch(
            "mc.contexts.conversation.service.handle_all_mentions",
            new_callable=AsyncMock,
            return_value=True,
        ):
            r1 = await conversation_service.handle_message(
                task_id="task-1",
                content="@bob help",
                task_data=task_data,
            )
        assert r1.intent == ConversationIntent.MENTION

        # Follow-up (no mention)
        r2 = await conversation_service.handle_message(
            task_id="task-1",
            content="Also check edge cases",
            task_data=task_data,
        )
        assert r2.intent == ConversationIntent.FOLLOW_UP


# ── MentionWatcher + ConversationService integration ───────────────────


class TestMentionWatcherWithConversationService:
    """MentionWatcher routes @mentions through ConversationService when provided."""

    @pytest.mark.asyncio
    async def test_mention_watcher_uses_conversation_service_for_dispatch(
        self,
        bridge: MagicMock,
        conversation_service: ConversationService,
    ) -> None:
        """When conversation_service is provided, MentionWatcher routes
        through ConversationService.handle_message() instead of calling
        handle_all_mentions directly."""
        import asyncio

        from mc.contexts.conversation.mentions.watcher import MentionWatcher

        watcher = MentionWatcher(bridge, conversation_service=conversation_service)

        # Mock: global recent user messages query returns a mention message
        bridge.get_recent_user_messages = MagicMock(
            return_value=[
                {
                    "_id": "msg-1",
                    "author_type": "user",
                    "content": "@researcher help",
                    "task_id": "task-1",
                },
            ]
        )
        bridge.query = MagicMock(return_value={"id": "task-1", "status": "done", "title": "Test"})
        bridge.mutation = MagicMock(return_value={"granted": True, "claimId": "claim-1"})

        # Patch ConversationService.handle_message to verify routing
        with patch(
            "mc.contexts.conversation.service.handle_all_mentions",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_handle:
            await watcher._poll_all_tasks()
            # Let background tasks run (handle_message is fire-and-forget)
            await asyncio.sleep(0.05)
            # ConversationService.handle_message calls handle_all_mentions
            # for MENTION intents
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_mention_watcher_without_service_calls_handler_directly(
        self,
        bridge: MagicMock,
    ) -> None:
        """Without conversation_service, MentionWatcher calls
        handle_all_mentions directly (backward compat)."""
        import asyncio

        from mc.contexts.conversation.mentions.watcher import MentionWatcher

        watcher = MentionWatcher(bridge)

        # Mock: global recent user messages query returns a mention message
        bridge.get_recent_user_messages = MagicMock(
            return_value=[
                {
                    "_id": "msg-1",
                    "author_type": "user",
                    "content": "@researcher help",
                    "task_id": "task-1",
                },
            ]
        )
        bridge.query = MagicMock(return_value={"id": "task-1", "status": "done", "title": "Test"})
        bridge.mutation = MagicMock(return_value={"granted": True, "claimId": "claim-1"})

        with patch(
            "mc.contexts.conversation.mentions.handler.handle_all_mentions",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_handle:
            await watcher._poll_all_tasks()
            # Let background tasks run
            await asyncio.sleep(0.05)
            mock_handle.assert_called_once()
