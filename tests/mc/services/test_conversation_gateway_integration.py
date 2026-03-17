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


# ── AC1: Gateway creates ConversationService ──────────────────────────


class TestGatewayCreatesConversationService:
    """Verify that gateway composition creates ConversationService."""

    def test_conversation_service_accepts_bridge_and_registry(
        self, bridge: MagicMock, ask_user_registry: MagicMock
    ) -> None:
        """ConversationService can be constructed with bridge + registry."""
        svc = ConversationService(bridge=bridge, ask_user_registry=ask_user_registry)
        assert svc._bridge is bridge
        assert svc._ask_user_registry is ask_user_registry

    def test_mention_watcher_accepts_conversation_service(
        self, bridge: MagicMock, conversation_service: ConversationService
    ) -> None:
        """MentionWatcher can be constructed with a conversation_service parameter."""
        from mc.contexts.conversation.mentions.watcher import MentionWatcher

        watcher = MentionWatcher(bridge, conversation_service=conversation_service)
        assert watcher._conversation_service is conversation_service

    def test_mention_watcher_works_without_conversation_service(self, bridge: MagicMock) -> None:
        """MentionWatcher still works without conversation_service (backward compat)."""
        from mc.contexts.conversation.mentions.watcher import MentionWatcher

        watcher = MentionWatcher(bridge)
        assert watcher._conversation_service is None

    def test_ask_user_watcher_accepts_conversation_service(
        self,
        bridge: MagicMock,
        ask_user_registry: MagicMock,
        conversation_service: ConversationService,
    ) -> None:
        """AskUserReplyWatcher can be constructed with a conversation_service."""
        from mc.contexts.conversation.ask_user.watcher import AskUserReplyWatcher

        watcher = AskUserReplyWatcher(
            bridge, ask_user_registry, conversation_service=conversation_service
        )
        assert watcher._conversation_service is conversation_service

    def test_ask_user_watcher_works_without_conversation_service(
        self, bridge: MagicMock, ask_user_registry: MagicMock
    ) -> None:
        """AskUserReplyWatcher still works without conversation_service."""
        from mc.contexts.conversation.ask_user.watcher import AskUserReplyWatcher

        watcher = AskUserReplyWatcher(bridge, ask_user_registry)
        assert watcher._conversation_service is None


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


# ── AC2: Intent Classification at Runtime ──────────────────────────────


class TestRuntimeIntentClassification:
    """Messages arriving at runtime are classified by ConversationIntentResolver."""

    @pytest.mark.asyncio
    async def test_mention_message_classified_as_mention(
        self, conversation_service: ConversationService
    ) -> None:
        """@mention in task thread is classified as MENTION intent."""
        task_data: dict[str, Any] = {"status": "inbox"}
        result = await conversation_service.handle_message(
            task_id="task-1",
            content="@researcher help",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.MENTION

    @pytest.mark.asyncio
    async def test_plan_chat_classified_correctly(
        self, conversation_service: ConversationService
    ) -> None:
        """Plan chat message is classified as PLAN_CHAT intent."""
        task_data: dict[str, Any] = {
            "status": "review",
            "awaiting_kickoff": True,
            "execution_plan": {"steps": [{"title": "Step 1"}]},
        }
        result = await conversation_service.handle_message(
            task_id="task-1",
            content="Add a test step",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.PLAN_CHAT

    @pytest.mark.asyncio
    async def test_ask_user_reply_classified_as_manual_reply(
        self, bridge: MagicMock, ask_user_registry: MagicMock
    ) -> None:
        """When ask_user is pending, message is classified as MANUAL_REPLY."""
        ask_user_registry.has_pending_ask.return_value = True
        svc = ConversationService(bridge=bridge, ask_user_registry=ask_user_registry)
        task_data: dict[str, Any] = {
            "status": "in_progress",
            "assigned_agent": "alice",
        }
        result = await svc.handle_message(
            task_id="task-1",
            content="Yes, proceed",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.MANUAL_REPLY

    @pytest.mark.asyncio
    async def test_follow_up_classified_correctly(
        self, conversation_service: ConversationService
    ) -> None:
        """Non-mention on active task is classified as FOLLOW_UP."""
        task_data: dict[str, Any] = {
            "status": "in_progress",
            "assigned_agent": "alice",
        }
        result = await conversation_service.handle_message(
            task_id="task-1",
            content="Also check tests",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.FOLLOW_UP

    @pytest.mark.asyncio
    async def test_comment_classified_correctly(
        self, conversation_service: ConversationService
    ) -> None:
        """Plain message on done task (no mention) is classified as COMMENT."""
        task_data: dict[str, Any] = {
            "status": "done",
            "assigned_agent": "alice",
        }
        result = await conversation_service.handle_message(
            task_id="task-1",
            content="Thanks for completing this",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.COMMENT


# ── AC3: Shared Context Assembly ───────────────────────────────────────


class TestSharedContextAssembly:
    """All conversation types use ThreadContextBuilder via ConversationService."""

    @pytest.mark.asyncio
    async def test_build_context_delegates_to_thread_context_builder(
        self, conversation_service: ConversationService, bridge: MagicMock
    ) -> None:
        """build_context delegates to the shared ThreadContextBuilder."""
        bridge.get_task_messages = MagicMock(
            return_value=[
                {"author_name": "User", "author_type": "user", "content": "hello"},
            ]
        )
        with patch(
            "mc.contexts.conversation.service.build_thread_context",
            return_value="[Thread History]\nUser [user]: hello",
        ) as mock_btc:
            ctx = await conversation_service.build_context(task_id="task-1")
            mock_btc.assert_called_once()
            assert "[Thread History]" in ctx


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
    async def test_mention_does_not_change_task_status(
        self, conversation_service: ConversationService, bridge: MagicMock
    ) -> None:
        """@mention triggers agent response WITHOUT changing task status."""
        task_data: dict[str, Any] = {
            "status": "in_progress",
            "assigned_agent": "alice",
            "title": "Test Task",
        }
        with patch(
            "mc.contexts.conversation.service.handle_all_mentions",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await conversation_service.handle_message(
                task_id="task-1",
                content="@researcher help",
                task_data=task_data,
            )
        bridge.update_task_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_plan_chat_routes_to_plan_negotiation(
        self, conversation_service: ConversationService, bridge: MagicMock
    ) -> None:
        """Plan-chat routes to handle_plan_negotiation."""
        task_data: dict[str, Any] = {
            "status": "review",
            "awaiting_kickoff": True,
            "execution_plan": {"steps": [{"title": "Step 1"}]},
            "title": "Plan Task",
        }
        with patch(
            "mc.contexts.conversation.service.handle_plan_negotiation",
            new_callable=AsyncMock,
        ) as mock_plan:
            await conversation_service.handle_message(
                task_id="task-1",
                content="Add a testing step",
                task_data=task_data,
            )
            mock_plan.assert_called_once()

    @pytest.mark.asyncio
    async def test_ask_user_reply_returns_manual_reply_intent(
        self, bridge: MagicMock, ask_user_registry: MagicMock
    ) -> None:
        """Ask-user replies deliver MANUAL_REPLY intent for caller handling."""
        ask_user_registry.has_pending_ask.return_value = True
        svc = ConversationService(bridge=bridge, ask_user_registry=ask_user_registry)
        task_data: dict[str, Any] = {
            "status": "in_progress",
            "assigned_agent": "alice",
        }
        result = await svc.handle_message(
            task_id="task-1",
            content="Yes, go ahead",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.MANUAL_REPLY

    @pytest.mark.asyncio
    async def test_follow_up_triggers_follow_up_intent(
        self, conversation_service: ConversationService
    ) -> None:
        """Direct follow-ups trigger FOLLOW_UP intent."""
        task_data: dict[str, Any] = {
            "status": "in_progress",
            "assigned_agent": "alice",
        }
        result = await conversation_service.handle_message(
            task_id="task-1",
            content="Check tests too",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.FOLLOW_UP

    @pytest.mark.asyncio
    async def test_universal_mentions_work_across_all_statuses(
        self, conversation_service: ConversationService
    ) -> None:
        """@mention works in done, crashed, inbox, and other statuses."""
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
    async def test_mention_message_end_to_end(
        self, conversation_service: ConversationService
    ) -> None:
        """End-to-end: mention message -> MENTION intent -> dispatch."""
        task_data: dict[str, Any] = {
            "status": "done",
            "title": "Done Task",
        }
        with patch(
            "mc.contexts.conversation.service.handle_all_mentions",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_handle:
            result = await conversation_service.handle_message(
                task_id="task-1",
                content="@researcher analyze this",
                task_data=task_data,
            )
            assert result.intent == ConversationIntent.MENTION
            mock_handle.assert_called_once_with(
                bridge=conversation_service._bridge,
                task_id="task-1",
                content="@researcher analyze this",
                task_title="Done Task",
            )

    @pytest.mark.asyncio
    async def test_plan_chat_message_end_to_end(
        self, conversation_service: ConversationService
    ) -> None:
        """End-to-end: plan chat -> PLAN_CHAT intent -> handle_plan_negotiation."""
        task_data: dict[str, Any] = {
            "status": "review",
            "awaiting_kickoff": True,
            "execution_plan": {"steps": [{"title": "Step 1"}]},
            "title": "Plan Task",
        }
        with patch(
            "mc.contexts.conversation.service.handle_plan_negotiation",
            new_callable=AsyncMock,
        ) as mock_plan:
            result = await conversation_service.handle_message(
                task_id="task-1",
                content="Modify step 1",
                task_data=task_data,
            )
            assert result.intent == ConversationIntent.PLAN_CHAT
            mock_plan.assert_called_once()

    @pytest.mark.asyncio
    async def test_comment_message_end_to_end(
        self, conversation_service: ConversationService, bridge: MagicMock
    ) -> None:
        """End-to-end: comment -> COMMENT intent -> no side effects."""
        task_data: dict[str, Any] = {
            "status": "done",
            "assigned_agent": "alice",
        }
        result = await conversation_service.handle_message(
            task_id="task-1",
            content="Nice work",
            task_data=task_data,
        )
        assert result.intent == ConversationIntent.COMMENT
        bridge.update_task_status.assert_not_called()

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

        with patch(
            "mc.contexts.conversation.mentions.handler.handle_all_mentions",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_handle:
            await watcher._poll_all_tasks()
            # Let background tasks run
            await asyncio.sleep(0.05)
            mock_handle.assert_called_once()
