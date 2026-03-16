"""Tests for the task-scoped thread journal file store."""

from __future__ import annotations

from pathlib import Path

from mc.infrastructure.thread_journal_store import (
    ThreadCompactionState,
    ThreadJournalStore,
)


def test_store_writes_initial_journal_and_reloadable_state(tmp_path: Path) -> None:
    journal_path = tmp_path / "THREAD_JOURNAL.md"
    state_path = tmp_path / "THREAD_COMPACTION_STATE.json"
    store = ThreadJournalStore(journal_path=journal_path, state_path=state_path)

    store.write_journal_header(
        task_title="Investigate thread journal",
        task_id="task-123",
        created_at="2026-03-16T12:00:00Z",
        updated_at="2026-03-16T12:00:00Z",
        status="in_progress",
        assigned_agent="nanobot",
        board_name="default",
        workflow_spec="workflow-1",
        plan_generated_by="workflow",
        execution_plan_markdown="1. Sync thread\n2. Compact context",
    )
    state = ThreadCompactionState(
        compacted_summary="Earlier context summary",
        last_compacted_message_id="msg-5",
        last_compacted_timestamp="2026-03-16T12:05:00Z",
        source_message_ids=["msg-1", "msg-2"],
        message_count_since_compaction=4,
        char_count_since_compaction=128,
        summary_token_budget=20_000,
        recent_window_messages=15,
    )
    store.write_state(state)

    reloaded = ThreadJournalStore(journal_path=journal_path, state_path=state_path)
    loaded_state = reloaded.read_state()
    journal_text = journal_path.read_text(encoding="utf-8")

    assert "# Thread Journal" in journal_text
    assert "Task: Investigate thread journal" in journal_text
    assert "## Task Snapshot" in journal_text
    assert "## Execution Plan" in journal_text
    assert "## Thread Events" in journal_text
    assert loaded_state == state


def test_append_event_keeps_header_sections_and_appends_markdown(tmp_path: Path) -> None:
    journal_path = tmp_path / "THREAD_JOURNAL.md"
    store = ThreadJournalStore(journal_path=journal_path)
    store.write_journal_header(
        task_title="Thread journal",
        task_id="task-123",
        created_at="2026-03-16T12:00:00Z",
        updated_at="2026-03-16T12:00:00Z",
        status="review",
        assigned_agent="lead-agent",
        board_name=None,
        workflow_spec=None,
        plan_generated_by="lead-agent",
        execution_plan_markdown="1. Plan",
    )

    store.append_event(
        timestamp="2026-03-16T12:01:00Z",
        author_name="User",
        author_type="user",
        event_type="user_message",
        content="Please keep the whole workflow history.",
    )
    store.append_event(
        timestamp="2026-03-16T12:02:00Z",
        author_name="dev-agent",
        author_type="agent",
        event_type="step_completion",
        content="Implemented the first draft.",
        step_id="step-1",
        artifacts=[{"path": "output/report.md", "action": "created"}],
    )

    journal_text = journal_path.read_text(encoding="utf-8")

    assert journal_text.count("# Thread Journal") == 1
    assert journal_text.count("## Task Snapshot") == 1
    assert journal_text.count("## Execution Plan") == 1
    assert journal_text.count("## Thread Events") == 1
    assert "### 2026-03-16T12:01:00Z | User | user_message" in journal_text
    assert "Please keep the whole workflow history." in journal_text
    assert "### 2026-03-16T12:02:00Z | dev-agent | step_completion | step=step-1" in journal_text
    assert "- CREATED: output/report.md" in journal_text
