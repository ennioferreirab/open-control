"""Tests for PlanNegotiator skipping @mention messages (Story 13.3).

Verifies that start_plan_negotiation_loop skips user messages containing
@mentions (leaving them for MentionWatcher) while still processing
non-mention messages normally.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.plan_negotiator import start_plan_negotiation_loop

# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

SAMPLE_PLAN: dict = {
    "steps": [
        {
            "tempId": "step_1",
            "title": "Extract data",
            "description": "Extract financial data",
            "assignedAgent": "financial-agent",
            "blockedBy": [],
            "parallelGroup": 1,
            "order": 1,
        }
    ],
    "generatedAt": "2026-02-25T00:00:00Z",
    "generatedBy": "lead-agent",
}


@pytest.fixture(autouse=True)
def _mock_known_agents():
    """Patch _known_agent_names so mentions resolve without disk access."""
    with patch(
        "mc.mention_handler._known_agent_names",
        return_value={"researcher", "alice", "bob"},
    ):
        yield


def _make_task_data(
    status: str = "in_progress",
    awaiting_kickoff: bool = False,
    plan: dict | None = None,
) -> dict:
    return {
        "status": status,
        "title": "Test Task",
        "awaiting_kickoff": awaiting_kickoff,
        "execution_plan": plan or SAMPLE_PLAN,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPlanNegotiatorMentionSkip:
    """Verifies PlanNegotiator skips @mention messages."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_skips_mention_message(self):
        """AC3: PlanNegotiator skips messages containing @mentions."""
        task_data = _make_task_data(status="in_progress")

        mention_msg = {
            "_id": "msg_mention",
            "author_type": "user",
            "content": "@researcher help me understand this",
        }

        call_count = 0

        async def _fake_queue_get():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [mention_msg]
            raise asyncio.CancelledError

        bridge = MagicMock()
        bridge.query = MagicMock(return_value=task_data)
        bridge.get_steps_by_task = MagicMock(return_value=[])
        bridge.post_lead_agent_message = MagicMock()
        bridge.update_execution_plan = MagicMock()

        mock_queue = MagicMock()
        mock_queue.get = AsyncMock(side_effect=_fake_queue_get)
        bridge.async_subscribe = MagicMock(return_value=mock_queue)

        with patch(
            "mc.plan_negotiator.asyncio.to_thread",
            new=AsyncMock(
                side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)
            ),
        ), patch(
            "mc.plan_negotiator.handle_plan_negotiation",
            new=AsyncMock(return_value=None),
        ) as mock_handle:
            try:
                self._run(
                    start_plan_negotiation_loop(
                        bridge, "task_mention", poll_interval=0.01
                    )
                )
            except asyncio.CancelledError:
                pass

        # handle_plan_negotiation must NOT be called for @mention messages
        mock_handle.assert_not_called()

    def test_still_processes_non_mention_messages(self):
        """AC4: PlanNegotiator still handles non-mention messages normally."""
        task_data = _make_task_data(status="in_progress")

        normal_msg = {
            "_id": "msg_normal",
            "author_type": "user",
            "content": "Please add a research step to the plan",
        }

        call_count = 0

        async def _fake_queue_get():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [normal_msg]
            raise asyncio.CancelledError

        bridge = MagicMock()
        bridge.query = MagicMock(return_value=task_data)
        bridge.get_steps_by_task = MagicMock(return_value=[])
        bridge.post_lead_agent_message = MagicMock()
        bridge.update_execution_plan = MagicMock()

        mock_queue = MagicMock()
        mock_queue.get = AsyncMock(side_effect=_fake_queue_get)
        bridge.async_subscribe = MagicMock(return_value=mock_queue)

        with patch(
            "mc.plan_negotiator.asyncio.to_thread",
            new=AsyncMock(
                side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)
            ),
        ), patch(
            "mc.plan_negotiator.handle_plan_negotiation",
            new=AsyncMock(return_value=None),
        ) as mock_handle:
            try:
                self._run(
                    start_plan_negotiation_loop(
                        bridge, "task_normal", poll_interval=0.01
                    )
                )
            except asyncio.CancelledError:
                pass

        # handle_plan_negotiation MUST be called for non-mention messages
        mock_handle.assert_called_once()
        call_args = mock_handle.call_args
        assert "Please add a research step" in call_args[0][2]

    def test_skips_mention_but_processes_normal_in_same_batch(self):
        """AC2+AC4: In a batch with both mention and non-mention messages,
        only the non-mention message is routed to plan negotiation."""
        task_data = _make_task_data(status="in_progress")

        mention_msg = {
            "_id": "msg_mention_batch",
            "author_type": "user",
            "content": "@alice check this plan",
        }
        normal_msg = {
            "_id": "msg_normal_batch",
            "author_type": "user",
            "content": "Remove step 2 from the plan",
        }

        call_count = 0

        async def _fake_queue_get():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [mention_msg, normal_msg]
            raise asyncio.CancelledError

        bridge = MagicMock()
        bridge.query = MagicMock(return_value=task_data)
        bridge.get_steps_by_task = MagicMock(return_value=[])
        bridge.post_lead_agent_message = MagicMock()
        bridge.update_execution_plan = MagicMock()

        mock_queue = MagicMock()
        mock_queue.get = AsyncMock(side_effect=_fake_queue_get)
        bridge.async_subscribe = MagicMock(return_value=mock_queue)

        with patch(
            "mc.plan_negotiator.asyncio.to_thread",
            new=AsyncMock(
                side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)
            ),
        ), patch(
            "mc.plan_negotiator.handle_plan_negotiation",
            new=AsyncMock(return_value=None),
        ) as mock_handle:
            try:
                self._run(
                    start_plan_negotiation_loop(
                        bridge, "task_mixed", poll_interval=0.01
                    )
                )
            except asyncio.CancelledError:
                pass

        # Only the normal message should be handled
        mock_handle.assert_called_once()
        assert "Remove step 2" in mock_handle.call_args[0][2]

    def test_skips_mention_on_review_awaiting_kickoff(self):
        """AC3: PlanNegotiator skips @mention on review+awaitingKickoff task."""
        task_data = _make_task_data(
            status="review", awaiting_kickoff=True
        )

        mention_msg = {
            "_id": "msg_rev_mention",
            "author_type": "user",
            "content": "@bob review the steps please",
        }

        call_count = 0

        async def _fake_queue_get():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [mention_msg]
            raise asyncio.CancelledError

        bridge = MagicMock()
        bridge.query = MagicMock(return_value=task_data)
        bridge.get_steps_by_task = MagicMock(return_value=[])
        bridge.post_lead_agent_message = MagicMock()
        bridge.update_execution_plan = MagicMock()

        mock_queue = MagicMock()
        mock_queue.get = AsyncMock(side_effect=_fake_queue_get)
        bridge.async_subscribe = MagicMock(return_value=mock_queue)

        with patch(
            "mc.plan_negotiator.asyncio.to_thread",
            new=AsyncMock(
                side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)
            ),
        ), patch(
            "mc.plan_negotiator.handle_plan_negotiation",
            new=AsyncMock(return_value=None),
        ) as mock_handle:
            try:
                self._run(
                    start_plan_negotiation_loop(
                        bridge, "task_rev", poll_interval=0.01
                    )
                )
            except asyncio.CancelledError:
                pass

        mock_handle.assert_not_called()


class TestNoDoubleProcessing:
    """AC5 / integration-level: verify no double-processing when both
    MentionWatcher and PlanNegotiator poll the same task."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_mention_handled_only_by_watcher_not_negotiator(self):
        """When both systems see a @mention message, only MentionWatcher dispatches it."""
        # Simulate: PlanNegotiator skips the mention
        task_data = _make_task_data(status="in_progress")

        mention_msg = {
            "_id": "msg_double",
            "author_type": "user",
            "content": "@researcher analyze the data",
        }

        # --- PlanNegotiator side: should skip ---
        call_count = 0

        async def _fake_queue_get():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [mention_msg]
            raise asyncio.CancelledError

        bridge = MagicMock()
        bridge.query = MagicMock(return_value=task_data)
        bridge.get_steps_by_task = MagicMock(return_value=[])
        bridge.post_lead_agent_message = MagicMock()
        bridge.update_execution_plan = MagicMock()

        mock_queue = MagicMock()
        mock_queue.get = AsyncMock(side_effect=_fake_queue_get)
        bridge.async_subscribe = MagicMock(return_value=mock_queue)

        with patch(
            "mc.plan_negotiator.asyncio.to_thread",
            new=AsyncMock(
                side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)
            ),
        ), patch(
            "mc.plan_negotiator.handle_plan_negotiation",
            new=AsyncMock(return_value=None),
        ) as mock_handle_negotiation:
            try:
                self._run(
                    start_plan_negotiation_loop(
                        bridge, "task_both", poll_interval=0.01
                    )
                )
            except asyncio.CancelledError:
                pass

        # PlanNegotiator must NOT have processed the mention
        mock_handle_negotiation.assert_not_called()

        # --- MentionWatcher side: should process ---
        from mc.mention_watcher import MentionWatcher

        watcher_bridge = MagicMock()
        watcher_bridge.query = MagicMock(
            side_effect=lambda q, p: [_make_task_data()] if "listByStatus" in q else []
        )

        # Simulate: task with in_progress status returning the mention message
        in_progress_task = {
            "id": "task_both",
            "status": "in_progress",
            "title": "Test Task",
        }

        def _watcher_query(query_name: str, params: dict) -> list:
            if query_name == "tasks:listByStatus" and params.get("status") == "in_progress":
                return [in_progress_task]
            return []

        watcher_bridge.query = _watcher_query
        watcher_bridge.get_task_messages = MagicMock(return_value=[mention_msg])

        watcher = MentionWatcher(watcher_bridge)

        # First poll: seed seen messages
        self._run(watcher._poll_all_tasks())

        # Second poll with a new message
        new_mention = {
            "_id": "msg_double_2",
            "author_type": "user",
            "content": "@researcher new question",
        }
        watcher_bridge.get_task_messages = MagicMock(
            return_value=[mention_msg, new_mention]
        )

        with patch(
            "mc.mention_watcher.asyncio.to_thread",
            new=AsyncMock(
                side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)
            ),
        ), patch(
            "mc.mention_handler.handle_all_mentions",
            new=AsyncMock(return_value=True),
        ) as mock_handle_mention:
            self._run(watcher._poll_all_tasks())

        # MentionWatcher MUST have processed the new mention
        mock_handle_mention.assert_called_once()
        call_kwargs = mock_handle_mention.call_args[1]
        assert call_kwargs["task_id"] == "task_both"
        assert "@researcher" in call_kwargs["content"]
