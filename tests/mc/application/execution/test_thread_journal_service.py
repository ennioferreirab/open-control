"""Tests for the thread journal sync and rolling compaction service."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from mc.application.execution.thread_journal_service import ThreadJournalService
from mc.infrastructure.thread_journal_store import ThreadCompactionState


def _user_message(message_id: str, content: str) -> dict[str, Any]:
    return {
        "_id": message_id,
        "author_name": "User",
        "author_type": "user",
        "message_type": "user_message",
        "type": "user_message",
        "timestamp": f"2026-03-16T12:00:{message_id[-1]}Z",
        "content": content,
    }


def _plan_message(message_id: str, content: str) -> dict[str, Any]:
    return {
        "_id": message_id,
        "author_name": "lead-agent",
        "author_type": "system",
        "message_type": "system_event",
        "type": "lead_agent_chat",
        "timestamp": f"2026-03-16T12:01:{message_id[-1]}Z",
        "content": content,
    }


def _step_completion(message_id: str, content: str, step_id: str = "step-1") -> dict[str, Any]:
    return {
        "_id": message_id,
        "author_name": "dev-agent",
        "author_type": "agent",
        "message_type": "work",
        "type": "step_completion",
        "step_id": step_id,
        "timestamp": f"2026-03-16T12:02:{message_id[-1]}Z",
        "content": content,
        "artifacts": [{"path": "output/report.md", "action": "created"}],
    }


def test_sync_task_thread_reconciles_unseen_messages_into_journal(tmp_path: Path) -> None:
    service = ThreadJournalService(base_tasks_dir=tmp_path)
    task_data = {
        "status": "in_progress",
        "assigned_agent": "dev-agent",
        "board_id": None,
        "workflow_spec_id": "workflow-1",
        "execution_plan": {"generated_by": "workflow", "steps": [{"title": "Step A"}]},
    }
    messages = [
        _user_message("msg-1", "Please keep full context."),
        _plan_message("msg-2", "Plan updated with a review step."),
        _step_completion("msg-3", "Initial implementation complete."),
    ]

    snapshot = service.sync_task_thread(
        task_id="task-123",
        task_title="Thread journal rollout",
        task_data=task_data,
        messages=messages,
    )

    journal_text = Path(snapshot.journal_path).read_text(encoding="utf-8")

    assert "Thread journal rollout" in journal_text
    assert "Please keep full context." in journal_text
    assert "Plan updated with a review step." in journal_text
    assert "Initial implementation complete." in journal_text
    assert snapshot.state.last_journal_message_id == "msg-3"


def test_context_snapshot_keeps_last_recent_messages_raw(tmp_path: Path) -> None:
    service = ThreadJournalService(
        base_tasks_dir=tmp_path,
        recent_window_messages=3,
    )
    task_data = {"status": "review", "execution_plan": {}}
    messages = [_user_message(f"msg-{index}", f"message {index}") for index in range(1, 7)]

    snapshot = service.sync_task_thread(
        task_id="task-123",
        task_title="Recent window",
        task_data=task_data,
        messages=messages,
    )

    assert [msg["_id"] for msg in snapshot.recent_messages] == ["msg-4", "msg-5", "msg-6"]


def test_compact_thread_reuses_previous_summary_and_only_compacts_older_batch(
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def summarizer(
        *, previous_summary: str, messages: list[dict[str, Any]], max_tokens: int
    ) -> str:
        captured["previous_summary"] = previous_summary
        captured["message_ids"] = [msg["_id"] for msg in messages]
        captured["types"] = [msg.get("type") for msg in messages]
        captured["max_tokens"] = max_tokens
        return "rolled summary v2"

    service = ThreadJournalService(
        base_tasks_dir=tmp_path,
        recent_window_messages=2,
        compaction_batch_messages=2,
        compaction_trigger_messages=2,
        summarizer=summarizer,
    )
    task_data = {"status": "in_progress", "execution_plan": {}}
    messages = [
        _user_message("msg-1", "old 1"),
        _plan_message("msg-2", "old 2 plan"),
        _step_completion("msg-3", "older completion"),
        _user_message("msg-4", "older 4"),
        _user_message("msg-5", "recent 5"),
        _user_message("msg-6", "recent 6"),
    ]

    snapshot = service.sync_task_thread(
        task_id="task-123",
        task_title="Compaction",
        task_data=task_data,
        messages=messages,
    )
    state = ThreadCompactionState(
        compacted_summary="rolled summary v1",
        last_compacted_message_id="msg-2",
        last_compacted_timestamp="2026-03-16T12:02:00Z",
        source_message_ids=["msg-1", "msg-2"],
        message_count_since_compaction=0,
        char_count_since_compaction=0,
        summary_token_budget=20_000,
        recent_window_messages=2,
        last_journal_message_id="msg-6",
    )
    snapshot.store.write_state(state)

    compacted = service.compact_thread(
        task_id="task-123",
        task_title="Compaction",
        task_data=task_data,
        messages=messages,
    )

    assert captured["previous_summary"] == "rolled summary v1"
    assert captured["message_ids"] == ["msg-3", "msg-4"]
    assert captured["types"] == ["step_completion", "user_message"]
    assert captured["max_tokens"] == 20_000
    assert compacted.compacted_summary == "rolled summary v2"
    assert compacted.last_compacted_message_id == "msg-4"
    assert compacted.source_message_ids == ["msg-1", "msg-2", "msg-3", "msg-4"]


@pytest.mark.asyncio
async def test_background_compaction_is_deduplicated_per_task(tmp_path: Path) -> None:
    service = ThreadJournalService(
        base_tasks_dir=tmp_path,
        recent_window_messages=1,
        compaction_batch_messages=1,
        compaction_trigger_messages=1,
        summarizer=lambda **_: "done",
        bridge=MagicMock(),
    )
    task_data = {"status": "in_progress", "execution_plan": {}}
    messages = [
        _user_message("msg-1", "older"),
        _user_message("msg-2", "recent"),
    ]

    first = service.schedule_background_compaction(
        task_id="task-123",
        task_title="Compaction",
        task_data=task_data,
        messages=messages,
    )
    second = service.schedule_background_compaction(
        task_id="task-123",
        task_title="Compaction",
        task_data=task_data,
        messages=messages,
    )

    assert first is second
    await first


@pytest.mark.asyncio
async def test_compaction_failure_crashes_the_task(tmp_path: Path) -> None:
    bridge = MagicMock()

    def failing_summarizer(
        *, previous_summary: str, messages: list[dict[str, Any]], max_tokens: int
    ) -> str:
        raise RuntimeError("compaction exploded")

    service = ThreadJournalService(
        base_tasks_dir=tmp_path,
        recent_window_messages=1,
        compaction_batch_messages=1,
        compaction_trigger_messages=1,
        summarizer=failing_summarizer,
        bridge=bridge,
    )
    task_data = {"status": "in_progress", "execution_plan": {}}
    messages = [
        _user_message("msg-1", "older"),
        _user_message("msg-2", "recent"),
    ]

    task = service.schedule_background_compaction(
        task_id="task-123",
        task_title="Compaction",
        task_data=task_data,
        messages=messages,
    )
    await task

    bridge.update_task_status.assert_called_once()
    args = bridge.update_task_status.call_args[0]
    assert args[0] == "task-123"
    assert args[1] == "crashed"
