from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from claude_code.memory_consolidator import CCMemoryConsolidator

from mc.memory import create_memory_store


def _make_llm_response(history_entry: str, memory_update: str) -> MagicMock:
    response = MagicMock()
    tool_call = MagicMock()
    tool_call.arguments = json.dumps(
        {
            "history_entry": history_entry,
            "memory_update": memory_update,
        }
    )
    response.tool_calls = [tool_call]
    return response


def _mock_provider(response: object | Exception):
    provider = MagicMock()
    if isinstance(response, Exception):
        provider.chat = AsyncMock(side_effect=response)
    else:
        provider.chat = AsyncMock(return_value=response)
    return patch(
        "mc.memory.service.create_provider",
        return_value=(provider, "resolved-model"),
    )


@pytest.mark.asyncio
async def test_consolidate_writes_history(tmp_path):
    consolidator = CCMemoryConsolidator(tmp_path)
    response = _make_llm_response(
        "[2026-03-05 12:00] Completed parser fix and updated tests.",
        "Known facts.",
    )

    with _mock_provider(response):
        ok = await consolidator.consolidate(
            task_title="Fix parser",
            task_output="Patched parser and tests",
            task_status="completed",
            task_id="task-1",
            model="claude-haiku",
        )

    assert ok is True
    history = (tmp_path / "memory" / "HISTORY.md").read_text(encoding="utf-8")
    assert "Completed parser fix and updated tests." in history


@pytest.mark.asyncio
async def test_consolidate_updates_memory(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    memory_path = memory_dir / "MEMORY.md"
    memory_path.write_text("Old memory", encoding="utf-8")

    consolidator = CCMemoryConsolidator(tmp_path)
    response = _make_llm_response(
        "[2026-03-05 12:01] Added deployment note.",
        "New memory content",
    )

    with _mock_provider(response):
        ok = await consolidator.consolidate(
            task_title="Deploy",
            task_output="Deployment finished",
            task_status="completed",
            task_id="task-2",
            model="claude-haiku",
        )

    assert ok is True
    assert memory_path.read_text(encoding="utf-8") == "New memory content"


@pytest.mark.asyncio
async def test_consolidate_skips_memory_if_unchanged(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    memory_path = memory_dir / "MEMORY.md"
    memory_path.write_text("Same memory", encoding="utf-8")

    consolidator = CCMemoryConsolidator(tmp_path)
    response = _make_llm_response(
        "[2026-03-05 12:02] No new facts.",
        "Same memory",
    )

    with _mock_provider(response):
        ok = await consolidator.consolidate(
            task_title="No-op task",
            task_output="No changes",
            task_status="completed",
            task_id="task-3",
            model="claude-haiku",
        )

    assert ok is True
    assert memory_path.read_text(encoding="utf-8") == "Same memory"


@pytest.mark.asyncio
async def test_consolidate_returns_false_on_llm_failure(tmp_path):
    consolidator = CCMemoryConsolidator(tmp_path)

    with _mock_provider(RuntimeError("boom")):
        ok = await consolidator.consolidate(
            task_title="Crashy task",
            task_output="whatever",
            task_status="completed",
            task_id="task-4",
            model="claude-haiku",
        )

    assert ok is False


@pytest.mark.asyncio
async def test_consolidate_returns_false_on_no_tool_call(tmp_path):
    consolidator = CCMemoryConsolidator(tmp_path)
    response = MagicMock()
    response.tool_calls = []

    with _mock_provider(response):
        ok = await consolidator.consolidate(
            task_title="Bad response",
            task_output="none",
            task_status="completed",
            task_id="task-5",
            model="claude-haiku",
        )

    assert ok is False


@pytest.mark.asyncio
async def test_consolidate_error_status_task(tmp_path):
    consolidator = CCMemoryConsolidator(tmp_path)
    response = _make_llm_response(
        "[2026-03-05 12:03] Task failed; captured stack trace cause.",
        "Captured: parser crash when input empty.",
    )

    with _mock_provider(response):
        ok = await consolidator.consolidate(
            task_title="Failing task",
            task_output="Traceback ...",
            task_status="error",
            task_id="task-6",
            model="claude-haiku",
        )

    assert ok is True
    history = (tmp_path / "memory" / "HISTORY.md").read_text(encoding="utf-8")
    assert "Task failed; captured stack trace cause." in history


@pytest.mark.asyncio
async def test_consolidate_skips_memory_if_unchanged_with_trailing_whitespace(tmp_path):
    """LLM often returns content with trailing newline; strip() prevents spurious writes."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    memory_path = memory_dir / "MEMORY.md"
    memory_path.write_text("Same memory", encoding="utf-8")

    consolidator = CCMemoryConsolidator(tmp_path)
    # LLM returns the same content but with a trailing newline (common LLM behaviour)
    response = _make_llm_response(
        "[2026-03-05 12:05] No new facts.",
        "Same memory\n",
    )

    with _mock_provider(response):
        ok = await consolidator.consolidate(
            task_title="No-op trailing-ws task",
            task_output="No changes",
            task_status="completed",
            task_id="task-3b",
            model="claude-haiku",
        )

    assert ok is True
    assert memory_path.read_text(encoding="utf-8") == "Same memory"


@pytest.mark.asyncio
async def test_consolidate_creates_memory_dir(tmp_path):
    consolidator = CCMemoryConsolidator(tmp_path)
    response = _make_llm_response(
        "[2026-03-05 12:04] Created memory folder and stored summary.",
        "Initial memory facts.",
    )

    with _mock_provider(response):
        ok = await consolidator.consolidate(
            task_title="First task",
            task_output="output",
            task_status="completed",
            task_id="task-7",
            model="claude-haiku",
        )

    assert ok is True
    assert (tmp_path / "memory").exists()


@pytest.mark.asyncio
async def test_consolidate_syncs_index_for_search(tmp_path):
    consolidator = CCMemoryConsolidator(tmp_path)
    response = _make_llm_response(
        "[2026-03-05 12:06] Captured canary rollout preference for deploys.",
        "Deployment policy: prefer canary rollout before broad release.",
    )

    with _mock_provider(response):
        ok = await consolidator.consolidate(
            task_title="Deploy API",
            task_output="Used canary rollout and verified health checks",
            task_status="completed",
            task_id="task-8",
            model="claude-haiku",
        )

    assert ok is True
    store = create_memory_store(tmp_path)
    results = store.search("canary rollout", top_k=3)
    assert "canary rollout" in results.lower()
