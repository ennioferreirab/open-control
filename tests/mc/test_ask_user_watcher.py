"""Tests for AskUserReplyWatcher — watches task threads for user replies to ask_user."""

import asyncio
from unittest.mock import MagicMock

import pytest

from mc.contexts.conversation.ask_user.handler import AskUserHandler
from mc.contexts.conversation.ask_user.registry import AskUserRegistry
from mc.contexts.conversation.ask_user.watcher import AskUserReplyWatcher


def _handler_with_pending(task_id: str) -> AskUserHandler:
    """Create an AskUserHandler with a fake pending ask for the given task_id."""
    handler = AskUserHandler()
    handler._pending_ask["req-123"] = MagicMock()  # fake future
    handler._task_to_request[task_id] = "req-123"
    return handler


class TestAskUserReplyWatcher:
    @pytest.fixture
    def bridge(self):
        mock = MagicMock()
        mock.get_task_messages = MagicMock(return_value=[])
        # Return a granted claim so acquire_runtime_claim delivers replies.
        mock.mutation = MagicMock(return_value={"granted": True, "claimId": "claim-1"})
        return mock

    @pytest.fixture
    def registry(self):
        return AskUserRegistry()

    @pytest.mark.asyncio
    async def test_skips_tasks_without_pending_ask(self, bridge, registry):
        handler = AskUserHandler()  # no pending asks
        registry.register("task-abc", handler)

        await AskUserReplyWatcher(bridge, registry)._poll_once()

        bridge.get_task_messages.assert_not_called()

    @pytest.mark.asyncio
    async def test_deduplicates_seen_messages(self, bridge, registry):
        # Use a real event loop future so we can check if it was resolved
        loop = asyncio.get_running_loop()
        handler = AskUserHandler()
        future = loop.create_future()
        handler._pending_ask["req-123"] = future
        handler._task_to_request["task-abc"] = "req-123"
        registry.register("task-abc", handler)

        watcher = AskUserReplyWatcher(bridge, registry)

        # First poll: seed seen set (empty thread)
        bridge.get_task_messages = MagicMock(return_value=[])
        await watcher._poll_once()

        # Second poll: user message appears
        bridge.get_task_messages = MagicMock(
            return_value=[
                {"_id": "msg-1", "author_type": "user", "content": "Blue"},
            ]
        )
        await watcher._poll_once()

        assert future.done()
        assert future.result() == "Blue"

        # Re-register a fresh pending ask so has_pending_ask is still True for 3rd poll
        future2 = loop.create_future()
        handler._pending_ask["req-456"] = future2
        handler._task_to_request["task-abc"] = "req-456"

        # Third poll: same message still there — should NOT deliver again
        await watcher._poll_once()

        assert not future2.done()  # msg-1 already seen, not delivered again

    @pytest.mark.asyncio
    async def test_claim_prevents_duplicate_delivery_when_seen_cache_is_cleared(
        self, bridge, registry
    ):
        loop = asyncio.get_running_loop()
        handler = AskUserHandler()
        future = loop.create_future()
        handler._pending_ask["req-123"] = future
        handler._task_to_request["task-abc"] = "req-123"
        registry.register("task-abc", handler)

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
        bridge.get_task_messages = MagicMock(
            return_value=[
                {"_id": "msg-1", "author_type": "user", "content": "Blue"},
            ]
        )

        watcher = AskUserReplyWatcher(bridge, registry)
        watcher._seen_messages["task-abc"] = set()

        await watcher._poll_once()
        assert future.done()
        assert future.result() == "Blue"

        future2 = loop.create_future()
        handler._pending_ask["req-456"] = future2
        handler._task_to_request["task-abc"] = "req-456"
        watcher._seen_messages["task-abc"] = set()

        await watcher._poll_once()

        assert not future2.done()

    @pytest.mark.asyncio
    async def test_run_subscribes_to_active_task_threads(self, bridge, registry):
        loop = asyncio.get_running_loop()
        handler = AskUserHandler()
        future = loop.create_future()
        handler._pending_ask["req-123"] = future
        handler._task_to_request["task-abc"] = "req-123"
        registry.register("task-abc", handler)

        queue: asyncio.Queue[object] = asyncio.Queue()
        queue.put_nowait(
            [
                {"_id": "msg-0", "author_type": "user", "content": "Old reply"},
            ]
        )
        queue.put_nowait(
            [
                {"_id": "msg-0", "author_type": "user", "content": "Old reply"},
                {"_id": "msg-1", "author_type": "user", "content": "Blue"},
            ]
        )
        bridge.async_subscribe = MagicMock(return_value=queue)

        watcher = AskUserReplyWatcher(bridge, registry)
        task = asyncio.create_task(watcher.run())
        await asyncio.wait_for(asyncio.shield(future), timeout=5.0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        bridge.async_subscribe.assert_called_once_with(
            "messages:listRecentByTaskForAskUser",
            {"task_id": "task-abc", "limit": watcher._feed_limit},
        )
        assert future.result() == "Blue"
