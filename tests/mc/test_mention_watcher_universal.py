"""Tests for MentionWatcher universal coverage across all task statuses (Story 13.3).

Verifies that the MentionWatcher processes @mentions on tasks in ALL statuses,
using the global watcher feed for recent user messages.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.contexts.conversation.mentions.watcher import MentionWatcher


def _make_bridge(
    recent_messages: list[dict] | None = None,
    task_by_id: dict[str, dict] | None = None,
) -> MagicMock:
    """Return a mock ConvexBridge with configurable recent messages and task lookups."""
    bridge = MagicMock()
    bridge.get_recent_user_messages = MagicMock(return_value=recent_messages or [])
    bridge.async_subscribe = MagicMock()
    bridge.mutation = MagicMock(return_value={"granted": True, "claimId": "claim-1"})

    def _query(query_name: str, params: dict) -> dict | list | None:
        if query_name == "tasks:getById":
            tid = params.get("task_id", "")
            return (task_by_id or {}).get(tid)
        return None

    bridge.query = _query
    return bridge


def _make_task(
    task_id: str,
    status: str,
    title: str = "Test Task",
    awaiting_kickoff: bool = False,
) -> dict:
    return {
        "id": task_id,
        "status": status,
        "title": title,
        "awaiting_kickoff": awaiting_kickoff,
    }


def _make_user_message(msg_id: str, content: str, task_id: str = "task-1") -> dict:
    return {
        "_id": msg_id,
        "author_type": "user",
        "content": content,
        "task_id": task_id,
    }


@pytest.fixture(autouse=True)
def _mock_known_agents():
    """Patch _known_agent_names so mentions resolve without disk access."""
    with patch(
        "mc.contexts.conversation.mentions.handler._known_agent_names",
        return_value={"researcher", "alice", "bob"},
    ):
        yield


@pytest.fixture(autouse=True)
def _mock_to_thread():
    """Patch asyncio.to_thread to run synchronously (no real threading in tests)."""
    with patch(
        "mc.contexts.conversation.mentions.watcher.asyncio.to_thread",
        new=AsyncMock(side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)),
    ):
        yield


class TestMentionWatcherUniversalCoverage:
    """Verifies MentionWatcher processes @mentions on ALL task statuses."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_processes_mention_on_in_progress_task(self):
        """AC1: MentionWatcher processes @mention on in_progress task."""
        task = _make_task("task_ip", "in_progress")
        msg = _make_user_message("msg_new", "@researcher help me", task_id="task_ip")

        bridge = _make_bridge(
            recent_messages=[msg],
            task_by_id={"task_ip": task},
        )

        watcher = MentionWatcher(bridge)

        with patch(
            "mc.contexts.conversation.mentions.handler.handle_all_mentions",
            new=AsyncMock(return_value=True),
        ) as mock_handle:
            self._run(watcher._poll_all_tasks())

        mock_handle.assert_called_once()
        call_kwargs = mock_handle.call_args[1]
        assert call_kwargs["task_id"] == "task_ip"
        assert "@researcher" in call_kwargs["content"]

    def test_processes_mention_on_review_awaiting_kickoff_task(self):
        """AC1: MentionWatcher processes @mention on review+awaitingKickoff."""
        task = _make_task("task_rev", "review", awaiting_kickoff=True)
        msg = _make_user_message("msg_rev_1", "@alice check this plan", task_id="task_rev")

        bridge = _make_bridge(
            recent_messages=[msg],
            task_by_id={"task_rev": task},
        )

        watcher = MentionWatcher(bridge)

        with patch(
            "mc.contexts.conversation.mentions.handler.handle_all_mentions",
            new=AsyncMock(return_value=True),
        ) as mock_handle:
            self._run(watcher._poll_all_tasks())

        mock_handle.assert_called_once()
        call_kwargs = mock_handle.call_args[1]
        assert call_kwargs["task_id"] == "task_rev"

    def test_still_processes_mentions_on_done_task(self):
        """AC1: MentionWatcher continues to process mentions on done tasks."""
        task = _make_task("task_done", "done")
        msg = _make_user_message(
            "msg_done_1",
            "@bob summarize results",
            task_id="task_done",
        )

        bridge = _make_bridge(
            recent_messages=[msg],
            task_by_id={"task_done": task},
        )

        watcher = MentionWatcher(bridge)

        with patch(
            "mc.contexts.conversation.mentions.handler.handle_all_mentions",
            new=AsyncMock(return_value=True),
        ) as mock_handle:
            self._run(watcher._poll_all_tasks())

        mock_handle.assert_called_once()

    def test_dedup_prevents_reprocessing(self):
        """AC2: _seen_message_ids prevents re-processing of already-seen messages."""
        task = _make_task("task_dedup", "in_progress")
        msg = _make_user_message("msg_1", "@researcher help", task_id="task_dedup")

        bridge = _make_bridge(
            recent_messages=[msg],
            task_by_id={"task_dedup": task},
        )

        watcher = MentionWatcher(bridge)

        with patch(
            "mc.contexts.conversation.mentions.handler.handle_all_mentions",
            new=AsyncMock(return_value=True),
        ):
            self._run(watcher._poll_all_tasks())

        with patch(
            "mc.contexts.conversation.mentions.handler.handle_all_mentions",
            new=AsyncMock(return_value=True),
        ) as mock_handle:
            self._run(watcher._poll_all_tasks())

        mock_handle.assert_not_called()


@pytest.mark.asyncio
async def test_run_uses_subscription_feed_and_processes_mentions() -> None:
    """MentionWatcher consumes the native Convex subscription feed."""
    task = _make_task("task_sub", "in_progress")
    msg = _make_user_message("msg_sub_1", "@researcher help me", task_id="task_sub")
    queue: asyncio.Queue[list[dict]] = asyncio.Queue()
    await queue.put([msg])

    bridge = _make_bridge(task_by_id={"task_sub": task})
    bridge.async_subscribe.return_value = queue
    watcher = MentionWatcher(bridge)

    with patch(
        "mc.contexts.conversation.mentions.handler.handle_all_mentions",
        new=AsyncMock(return_value=True),
    ) as mock_handle:
        run_task = asyncio.create_task(watcher.run())
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        run_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run_task

    bridge.async_subscribe.assert_called_once_with(
        "messages:listRecentUserMessagesForWatcher",
        {"limit": watcher._feed_limit},
        sleep_controller=watcher._sleep_controller,
    )
    mock_handle.assert_called_once()


@pytest.mark.asyncio
async def test_gap_fill_uses_bounded_recent_query() -> None:
    """Gap fill should request a bounded recent-user query instead of an unbounded collect."""
    bridge = _make_bridge(
        recent_messages=[],
        task_by_id={"task-gap": _make_task("task-gap", "in_progress")},
    )
    watcher = MentionWatcher(bridge)
    watcher._last_processed_at = watcher._startup_at.replace(year=2025)
    watcher._feed_limit = 2

    full_snapshot = [
        {
            "id": "msg-2",
            "task_id": "task-gap",
            "author_type": "user",
            "content": "@researcher latest",
            "timestamp": "2026-03-23T12:00:02Z",
        },
        {
            "id": "msg-3",
            "task_id": "task-gap",
            "author_type": "user",
            "content": "@researcher newest",
            "timestamp": "2026-03-23T12:00:03Z",
        },
    ]

    with patch.object(watcher, "_process_messages", new=AsyncMock(return_value=False)):
        await watcher._process_feed_snapshot(full_snapshot)

    bridge.get_recent_user_messages.assert_called_once_with(
        watcher._last_processed_at.isoformat(),
        limit=watcher._feed_limit,
    )

    def test_first_poll_marks_messages_as_seen(self):
        """Messages seen on first poll are tracked in _seen_message_ids."""
        msg1 = _make_user_message("msg_old_1", "@researcher old question 1")
        msg2 = _make_user_message("msg_old_2", "@researcher old question 2")

        bridge = _make_bridge(recent_messages=[msg1, msg2])
        watcher = MentionWatcher(bridge)

        with patch(
            "mc.contexts.conversation.mentions.handler.handle_all_mentions",
            new=AsyncMock(return_value=True),
        ):
            self._run(watcher._poll_all_tasks())

        assert "msg_old_1" in watcher._seen_message_ids
        assert "msg_old_2" in watcher._seen_message_ids

    def test_non_mention_messages_are_ignored(self):
        """MentionWatcher only processes messages with valid @mentions."""
        msg = _make_user_message("msg_1", "Please update the plan")

        bridge = _make_bridge(recent_messages=[msg])
        watcher = MentionWatcher(bridge)

        with patch(
            "mc.contexts.conversation.mentions.handler.handle_all_mentions",
            new=AsyncMock(return_value=True),
        ) as mock_handle:
            self._run(watcher._poll_all_tasks())

        mock_handle.assert_not_called()

    def test_dedup_tracks_across_polls(self):
        """Messages are tracked across poll cycles regardless of task status changes."""
        msg = _make_user_message(
            "msg_a1",
            "@researcher hello",
            task_id="task_transition",
        )
        task = _make_task("task_transition", "assigned")

        bridge = _make_bridge(
            recent_messages=[msg],
            task_by_id={"task_transition": task},
        )

        watcher = MentionWatcher(bridge)

        with patch(
            "mc.contexts.conversation.mentions.handler.handle_all_mentions",
            new=AsyncMock(return_value=True),
        ):
            self._run(watcher._poll_all_tasks())

        assert "msg_a1" in watcher._seen_message_ids

        with patch(
            "mc.contexts.conversation.mentions.handler.handle_all_mentions",
            new=AsyncMock(return_value=True),
        ) as mock_handle:
            self._run(watcher._poll_all_tasks())

        mock_handle.assert_not_called()
