"""Tests for the file-backed Live session store."""

from __future__ import annotations

from pathlib import Path

import pytest

from mc.contexts.interactive.live_store import LiveSessionStore


@pytest.fixture()
def live_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LiveSessionStore:
    monkeypatch.setenv("OPEN_CONTROL_LIVE_HOME", str(tmp_path / "live"))
    import mc.infrastructure.runtime_home as runtime_home

    runtime_home._resolved_live = None
    runtime_home._resolved_live_from_env = None
    return LiveSessionStore()


def test_upsert_session_writes_meta(live_store: LiveSessionStore) -> None:
    meta = live_store.upsert_session(
        {
            "session_id": "session-1",
            "task_id": "task-1",
            "step_id": "step-1",
            "agent_name": "agent",
            "provider": "provider",
            "status": "ready",
            "updated_at": "2026-03-30T10:00:00.000Z",
        }
    )

    assert meta["sessionId"] == "session-1"
    assert meta["taskId"] == "task-1"
    assert meta["stepId"] == "step-1"
    assert meta["eventCount"] == 0

    paths = live_store.session_paths("session-1", task_id="task-1", step_id="step-1")
    meta_path = paths.meta_path
    assert meta_path.exists()
    assert paths.index_path.exists()


def test_append_event_increments_seq(live_store: LiveSessionStore) -> None:
    live_store.upsert_session(
        {
            "session_id": "session-1",
            "task_id": "task-1",
            "agent_name": "agent",
            "provider": "provider",
            "status": "ready",
        }
    )

    first = live_store.append_event(
        {
            "session_id": "session-1",
            "task_id": "task-1",
            "kind": "tool_use",
            "ts": "2026-03-30T10:00:00.000Z",
            "agent_name": "agent",
            "provider": "provider",
            "summary": "Run tests",
        }
    )
    second = live_store.append_event(
        {
            "session_id": "session-1",
            "task_id": "task-1",
            "kind": "tool_result",
            "ts": "2026-03-30T10:00:01.000Z",
            "agent_name": "agent",
            "provider": "provider",
            "summary": "Done",
        }
    )

    assert first["seq"] == 1
    assert second["seq"] == 2
    events = live_store.read_events("session-1", task_id="task-1")
    assert [event["seq"] for event in events] == [1, 2]


def test_session_paths_sanitize_punctuated_session_ids(live_store: LiveSessionStore) -> None:
    paths = live_store.session_paths(
        "interactive_session:claude",
        task_id="task-1",
        step_id="step-1",
    )

    assert paths.index_path.name == "interactive_session_claude.json"
    assert paths.session_dir.name == "interactive_session_claude"
