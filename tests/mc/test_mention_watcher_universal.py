"""Tests for MentionWatcher universal coverage across all task statuses (Story 13.3).

Verifies that the MentionWatcher processes @mentions on tasks in ALL statuses,
including in_progress and review+awaitingKickoff which were previously skipped.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.mentions.watcher import MentionWatcher

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bridge(
    tasks_by_status: dict[str, list[dict]] | None = None,
    messages_by_task: dict[str, list[dict]] | None = None,
) -> MagicMock:
    """Return a mock ConvexBridge with configurable task and message returns."""
    bridge = MagicMock()

    def _query(query_name: str, params: dict) -> list[dict]:
        if query_name == "tasks:listByStatus":
            status = params.get("status", "")
            return (tasks_by_status or {}).get(status, [])
        return []

    def _get_task_messages(task_id: str) -> list[dict]:
        return (messages_by_task or {}).get(task_id, [])

    bridge.query = _query
    bridge.get_task_messages = _get_task_messages
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


def _make_user_message(msg_id: str, content: str) -> dict:
    return {
        "_id": msg_id,
        "author_type": "user",
        "content": content,
    }


@pytest.fixture(autouse=True)
def _mock_known_agents():
    """Patch _known_agent_names so mentions resolve without disk access."""
    with patch(
        "mc.mentions.handler._known_agent_names",
        return_value={"researcher", "alice", "bob"},
    ):
        yield


@pytest.fixture(autouse=True)
def _mock_to_thread():
    """Patch asyncio.to_thread to run synchronously (no real threading in tests)."""
    with patch(
        "mc.mentions.watcher.asyncio.to_thread",
        new=AsyncMock(
            side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)
        ),
    ):
        yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMentionWatcherUniversalCoverage:
    """Verifies MentionWatcher processes @mentions on ALL task statuses."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_processes_mention_on_in_progress_task(self):
        """AC1: MentionWatcher processes @mention on in_progress task (previously skipped)."""
        task = _make_task("task_ip", "in_progress")
        msg = _make_user_message("msg_new", "@researcher help me")

        bridge = _make_bridge(
            tasks_by_status={"in_progress": [task]},
            messages_by_task={"task_ip": [msg]},
        )

        watcher = MentionWatcher(bridge)

        # First poll: marks all existing messages as seen (first encounter)
        self._run(watcher._poll_all_tasks())

        # Add a new message for the second poll
        new_msg = _make_user_message("msg_new_2", "@researcher what is GDP?")

        def _get_msgs(task_id):
            return [msg, new_msg]

        bridge.get_task_messages = _get_msgs

        with patch(
            "mc.mentions.handler.handle_all_mentions",
            new=AsyncMock(return_value=True),
        ) as mock_handle:
            self._run(watcher._poll_all_tasks())

        mock_handle.assert_called_once()
        call_kwargs = mock_handle.call_args[1]
        assert call_kwargs["task_id"] == "task_ip"
        assert "@researcher" in call_kwargs["content"]

    def test_processes_mention_on_review_awaiting_kickoff_task(self):
        """AC1: MentionWatcher processes @mention on review+awaitingKickoff (previously skipped)."""
        task = _make_task("task_rev", "review", awaiting_kickoff=True)
        msg = _make_user_message("msg_rev_1", "@alice check this plan")

        bridge = _make_bridge(
            tasks_by_status={"review": [task]},
            messages_by_task={"task_rev": [msg]},
        )

        watcher = MentionWatcher(bridge)

        # First poll: marks all existing messages as seen
        self._run(watcher._poll_all_tasks())

        # Add a new mention message
        new_msg = _make_user_message("msg_rev_2", "@alice review the steps")

        def _get_msgs(task_id):
            return [msg, new_msg]

        bridge.get_task_messages = _get_msgs

        with patch(
            "mc.mentions.handler.handle_all_mentions",
            new=AsyncMock(return_value=True),
        ) as mock_handle:
            self._run(watcher._poll_all_tasks())

        mock_handle.assert_called_once()
        call_kwargs = mock_handle.call_args[1]
        assert call_kwargs["task_id"] == "task_rev"

    def test_still_processes_mentions_on_done_task(self):
        """AC1: MentionWatcher continues to process mentions on done tasks."""
        task = _make_task("task_done", "done")
        msg = _make_user_message("msg_done_1", "first message")

        bridge = _make_bridge(
            tasks_by_status={"done": [task]},
            messages_by_task={"task_done": [msg]},
        )

        watcher = MentionWatcher(bridge)

        # First poll: seed seen messages
        self._run(watcher._poll_all_tasks())

        new_msg = _make_user_message("msg_done_2", "@bob summarize results")

        def _get_msgs(task_id):
            return [msg, new_msg]

        bridge.get_task_messages = _get_msgs

        with patch(
            "mc.mentions.handler.handle_all_mentions",
            new=AsyncMock(return_value=True),
        ) as mock_handle:
            self._run(watcher._poll_all_tasks())

        mock_handle.assert_called_once()

    def test_dedup_prevents_reprocessing(self):
        """AC2: _per_task_seen prevents re-processing of already-seen messages."""
        task = _make_task("task_dedup", "in_progress")
        msg = _make_user_message("msg_1", "@researcher help")

        bridge = _make_bridge(
            tasks_by_status={"in_progress": [task]},
            messages_by_task={"task_dedup": [msg]},
        )

        watcher = MentionWatcher(bridge)

        # First poll: marks msg as seen (first encounter)
        self._run(watcher._poll_all_tasks())

        # Second poll: same message, should NOT be processed
        with patch(
            "mc.mentions.handler.handle_all_mentions",
            new=AsyncMock(return_value=True),
        ) as mock_handle:
            self._run(watcher._poll_all_tasks())

        # No new messages, so handle_all_mentions should NOT be called
        mock_handle.assert_not_called()

    def test_first_encounter_marks_existing_messages_as_seen(self):
        """Task 3.2: On first encounter, existing messages are marked as seen."""
        task = _make_task("task_first", "in_progress")
        old_msgs = [
            _make_user_message("msg_old_1", "@researcher old question 1"),
            _make_user_message("msg_old_2", "@researcher old question 2"),
        ]

        bridge = _make_bridge(
            tasks_by_status={"in_progress": [task]},
            messages_by_task={"task_first": old_msgs},
        )

        watcher = MentionWatcher(bridge)

        # First poll: should NOT dispatch any mentions (just marks as seen)
        with patch(
            "mc.mentions.handler.handle_all_mentions",
            new=AsyncMock(return_value=True),
        ) as mock_handle:
            self._run(watcher._poll_all_tasks())

        mock_handle.assert_not_called()

        # Verify messages are in _per_task_seen
        assert "msg_old_1" in watcher._per_task_seen["task_first"]
        assert "msg_old_2" in watcher._per_task_seen["task_first"]

    def test_non_mention_messages_are_ignored(self):
        """MentionWatcher only processes messages with valid @mentions."""
        task = _make_task("task_no_mention", "in_progress")
        msg = _make_user_message("msg_0", "first message")

        bridge = _make_bridge(
            tasks_by_status={"in_progress": [task]},
            messages_by_task={"task_no_mention": [msg]},
        )

        watcher = MentionWatcher(bridge)
        self._run(watcher._poll_all_tasks())

        # Add a non-mention message
        new_msg = _make_user_message("msg_1", "Please update the plan")

        def _get_msgs(task_id):
            return [msg, new_msg]

        bridge.get_task_messages = _get_msgs

        with patch(
            "mc.mentions.handler.handle_all_mentions",
            new=AsyncMock(return_value=True),
        ) as mock_handle:
            self._run(watcher._poll_all_tasks())

        mock_handle.assert_not_called()

    def test_negotiation_statuses_constant_removed(self):
        """Task 1.3: _NEGOTIATION_STATUSES constant no longer exists."""
        import mc.mentions.watcher as mw

        assert not hasattr(mw, "_NEGOTIATION_STATUSES")

    def test_per_task_seen_tracks_across_status_changes(self):
        """Task 3.3: _per_task_seen tracks by task_id, not status."""
        task_assigned = _make_task("task_transition", "assigned")
        msg = _make_user_message("msg_a1", "@researcher hello")

        bridge = _make_bridge(
            tasks_by_status={"assigned": [task_assigned]},
            messages_by_task={"task_transition": [msg]},
        )

        watcher = MentionWatcher(bridge)

        # First poll with "assigned" status
        self._run(watcher._poll_all_tasks())
        assert "task_transition" in watcher._per_task_seen

        # Now the task transitions to "in_progress"
        task_in_progress = _make_task("task_transition", "in_progress")
        bridge_2 = _make_bridge(
            tasks_by_status={"in_progress": [task_in_progress]},
            messages_by_task={"task_transition": [msg]},
        )
        watcher._bridge = bridge_2

        # Second poll: same message should still be in _per_task_seen (tracked by task_id)
        with patch(
            "mc.mentions.handler.handle_all_mentions",
            new=AsyncMock(return_value=True),
        ) as mock_handle:
            self._run(watcher._poll_all_tasks())

        # The old message should not trigger another dispatch
        mock_handle.assert_not_called()
        assert "msg_a1" in watcher._per_task_seen["task_transition"]

    def test_concurrent_session_key_uniqueness(self):
        """Task 4.1: session key in handle_mention uses unique UUID per mention.

        Verifies the actual source code in mention_handler.py constructs
        session keys with the expected `mc:mention:{agent}:{task}:{uuid}` format.
        """
        import inspect
        import re

        from mc.mentions.handler import handle_mention

        source = inspect.getsource(handle_mention)
        # The source should contain the session_key pattern
        pattern = re.compile(
            r'session_key\s*=\s*f"mc:mention:\{agent_name\}:\{task_id\}:'
        )
        assert pattern.search(source), (
            "handle_mention does not construct session_key with "
            "'mc:mention:{agent_name}:{task_id}:...' pattern"
        )
        # Verify it uses uuid for uniqueness
        assert "uuid.uuid4()" in source, (
            "handle_mention does not use uuid.uuid4() for session key uniqueness"
        )
