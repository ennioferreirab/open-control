from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claude_code.memory_consolidator import CCMemoryConsolidator


def _make_llm_response(history_entry: str, memory_update: str) -> MagicMock:
    tool_call = MagicMock()
    tool_call.function.arguments = json.dumps(
        {
            "history_entry": history_entry,
            "memory_update": memory_update,
        }
    )
    msg = MagicMock()
    msg.tool_calls = [tool_call]
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.mark.asyncio
async def test_consolidate_writes_history(tmp_path):
    consolidator = CCMemoryConsolidator(tmp_path)
    response = _make_llm_response(
        "[2026-03-05 12:00] Completed parser fix and updated tests.",
        "Known facts.",
    )

    with patch("mc.memory.service.litellm.acompletion", new=AsyncMock(return_value=response)):
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

    with patch("mc.memory.service.litellm.acompletion", new=AsyncMock(return_value=response)):
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

    with patch("mc.memory.service.litellm.acompletion", new=AsyncMock(return_value=response)):
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

    with patch("mc.memory.service.litellm.acompletion", new=AsyncMock(side_effect=RuntimeError("boom"))):
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
    response.choices = [MagicMock(message=MagicMock(tool_calls=[]))]

    with patch("mc.memory.service.litellm.acompletion", new=AsyncMock(return_value=response)):
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

    with patch("mc.memory.service.litellm.acompletion", new=AsyncMock(return_value=response)):
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

    with patch("mc.memory.service.litellm.acompletion", new=AsyncMock(return_value=response)):
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

    with patch("mc.memory.service.litellm.acompletion", new=AsyncMock(return_value=response)):
        ok = await consolidator.consolidate(
            task_title="First task",
            task_output="output",
            task_status="completed",
            task_id="task-7",
            model="claude-haiku",
        )

    assert ok is True
    assert (tmp_path / "memory").exists()
