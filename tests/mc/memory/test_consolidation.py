"""Tests for file-based memory consolidation."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.memory.consolidation import (
    HISTORY_CONSOLIDATION_THRESHOLD_CHARS,
    is_history_above_threshold,
    consolidate_history_and_memory,
)


def test_is_history_above_threshold_no_file(tmp_path):
    assert is_history_above_threshold(tmp_path) is False


def test_is_history_above_threshold_small_file(tmp_path):
    (tmp_path / "HISTORY.md").write_text("small", encoding="utf-8")
    assert is_history_above_threshold(tmp_path) is False


def test_is_history_above_threshold_large_file(tmp_path):
    (tmp_path / "HISTORY.md").write_text("x" * (HISTORY_CONSOLIDATION_THRESHOLD_CHARS + 1), encoding="utf-8")
    assert is_history_above_threshold(tmp_path) is True


def test_is_history_above_threshold_custom(tmp_path):
    (tmp_path / "HISTORY.md").write_text("x" * 100, encoding="utf-8")
    assert is_history_above_threshold(tmp_path, threshold_chars=50) is True
    assert is_history_above_threshold(tmp_path, threshold_chars=200) is False


def _make_llm_response(memory_content: str) -> MagicMock:
    tool_call = MagicMock()
    tool_call.function.arguments = json.dumps({"memory": memory_content})
    msg = MagicMock()
    msg.tool_calls = [tool_call]
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.mark.asyncio
async def test_consolidate_archives_and_clears(tmp_path):
    """Full consolidation cycle: archive old files, write new memory, clear history."""
    (tmp_path / "HISTORY.md").write_text("[2026-03-05] Built memory system.", encoding="utf-8")
    (tmp_path / "MEMORY.md").write_text("Old facts.", encoding="utf-8")

    response = _make_llm_response("# Consolidated Memory\n\nBuilt memory system. Old facts preserved.")

    with patch("litellm.acompletion", new=AsyncMock(return_value=response)), \
         patch("mc.memory.index.MemoryIndex"):
        ok = await consolidate_history_and_memory(tmp_path, "test-model")

    assert ok is True

    # New MEMORY.md has consolidated content
    assert "Consolidated Memory" in (tmp_path / "MEMORY.md").read_text(encoding="utf-8")

    # HISTORY.md is cleared
    assert (tmp_path / "HISTORY.md").read_text(encoding="utf-8") == ""

    # Archived files exist
    archives = list(tmp_path.glob("HISTORY_*.md"))
    assert len(archives) == 1
    assert "Built memory system" in archives[0].read_text(encoding="utf-8")

    memory_archives = list(tmp_path.glob("MEMORY_*.md"))
    assert len(memory_archives) == 1
    assert "Old facts" in memory_archives[0].read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_consolidate_no_history(tmp_path):
    """No-op when HISTORY.md is empty or missing."""
    ok = await consolidate_history_and_memory(tmp_path, "test-model")
    assert ok is True


@pytest.mark.asyncio
async def test_consolidate_llm_failure(tmp_path):
    (tmp_path / "HISTORY.md").write_text("some content", encoding="utf-8")

    with patch("litellm.acompletion", new=AsyncMock(side_effect=RuntimeError("boom"))):
        ok = await consolidate_history_and_memory(tmp_path, "test-model")

    assert ok is False
    # Original files untouched
    assert "some content" in (tmp_path / "HISTORY.md").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_consolidate_no_tool_call(tmp_path):
    (tmp_path / "HISTORY.md").write_text("some content", encoding="utf-8")
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(tool_calls=[]))]

    with patch("litellm.acompletion", new=AsyncMock(return_value=response)):
        ok = await consolidate_history_and_memory(tmp_path, "test-model")

    assert ok is False


@pytest.mark.asyncio
async def test_consolidate_empty_memory_returned(tmp_path):
    (tmp_path / "HISTORY.md").write_text("some content", encoding="utf-8")
    response = _make_llm_response("")

    with patch("litellm.acompletion", new=AsyncMock(return_value=response)):
        ok = await consolidate_history_and_memory(tmp_path, "test-model")

    assert ok is False
