"""Tests for file-based memory consolidation."""

from __future__ import annotations

import tempfile as _tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mc.infrastructure.providers.errors import ProviderError
from mc.memory.consolidation import (
    HISTORY_CONSOLIDATION_THRESHOLD_CHARS,
    consolidate_history_and_memory,
    is_history_above_threshold,
)

_REAL_NAMED_TEMPFILE = _tempfile.NamedTemporaryFile


def test_is_history_above_threshold_no_file(tmp_path):
    assert is_history_above_threshold(tmp_path) is False


def test_is_history_above_threshold_small_file(tmp_path):
    (tmp_path / "HISTORY.md").write_text("small", encoding="utf-8")
    assert is_history_above_threshold(tmp_path) is False


def test_is_history_above_threshold_large_file(tmp_path):
    (tmp_path / "HISTORY.md").write_text(
        "x" * (HISTORY_CONSOLIDATION_THRESHOLD_CHARS + 1), encoding="utf-8"
    )
    assert is_history_above_threshold(tmp_path) is True


def test_is_history_above_threshold_custom(tmp_path):
    (tmp_path / "HISTORY.md").write_text("x" * 100, encoding="utf-8")
    assert is_history_above_threshold(tmp_path, threshold_chars=50) is True
    assert is_history_above_threshold(tmp_path, threshold_chars=200) is False


def _capture_named_tempfile_factory(created_paths: list[Path]):
    def _factory(*args, **kwargs):
        handle = _REAL_NAMED_TEMPFILE(*args, **kwargs)
        created_paths.append(Path(handle.name))
        return handle

    return _factory


def _force_small_threshold():
    return patch("mc.memory.consolidation.HISTORY_CONSOLIDATION_THRESHOLD_CHARS", 1)


@pytest.mark.asyncio
async def test_consolidate_archives_and_clears(tmp_path):
    """Full consolidation cycle: archive old files, write new memory, clear history."""
    (tmp_path / "HISTORY.md").write_text("[2026-03-05] Built memory system.", encoding="utf-8")
    (tmp_path / "MEMORY.md").write_text("Old facts.", encoding="utf-8")

    new_memory = "# Consolidated Memory\n\nBuilt memory system. Old facts preserved."
    temp_paths: list[Path] = []

    with (
        _force_small_threshold(),
        patch(
            "mc.infrastructure.acp.utility.run_utility_turn",
            new=AsyncMock(return_value=new_memory),
        ),
        patch("mc.memory.index.MemoryIndex"),
        patch(
            "tempfile.NamedTemporaryFile", side_effect=_capture_named_tempfile_factory(temp_paths)
        ),
    ):
        ok = await consolidate_history_and_memory(tmp_path)

    assert ok is True

    assert "Consolidated Memory" in (tmp_path / "MEMORY.md").read_text(encoding="utf-8")
    assert (tmp_path / "HISTORY.md").read_text(encoding="utf-8") == ""

    archive_history = tmp_path / "HISTORY_ARCHIVE.md"
    assert archive_history.exists()
    archive_text = archive_history.read_text(encoding="utf-8")
    assert "## Archived Snapshot [" in archive_text
    assert "Source: HISTORY.md" in archive_text
    assert "Chars: 33" in archive_text
    assert "Built memory system" in archive_text
    assert list(tmp_path.glob("HISTORY_????-??-??_*.md")) == []

    memory_archives = list(tmp_path.glob("MEMORY_*.md"))
    assert len(memory_archives) == 1
    assert "Old facts" in memory_archives[0].read_text(encoding="utf-8")
    assert all(not path.exists() for path in temp_paths)


@pytest.mark.asyncio
async def test_consolidate_no_history(tmp_path):
    """No-op when HISTORY.md is empty or missing."""
    ok = await consolidate_history_and_memory(tmp_path)
    assert ok is True


@pytest.mark.asyncio
async def test_consolidate_below_threshold_is_noop(tmp_path):
    history_file = tmp_path / "HISTORY.md"
    history_file.write_text("small history", encoding="utf-8")

    with patch(
        "mc.infrastructure.acp.utility.run_utility_turn",
        side_effect=AssertionError("should not call utility turn"),
    ):
        ok = await consolidate_history_and_memory(tmp_path)

    assert ok is True
    assert history_file.read_text(encoding="utf-8") == "small history"
    assert not (tmp_path / "HISTORY_ARCHIVE.md").exists()


@pytest.mark.asyncio
async def test_consolidate_llm_failure(tmp_path):
    (tmp_path / "HISTORY.md").write_text("some content", encoding="utf-8")

    with (
        _force_small_threshold(),
        patch(
            "mc.infrastructure.acp.utility.run_utility_turn",
            new=AsyncMock(side_effect=ProviderError("boom")),
        ),
    ):
        ok = await consolidate_history_and_memory(tmp_path)

    assert ok is False
    assert "some content" in (tmp_path / "HISTORY.md").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_consolidate_empty_memory_returned(tmp_path):
    (tmp_path / "HISTORY.md").write_text("some content", encoding="utf-8")

    with (
        _force_small_threshold(),
        patch(
            "mc.infrastructure.acp.utility.run_utility_turn",
            new=AsyncMock(side_effect=ProviderError("ACP utility turn returned empty text")),
        ),
    ):
        ok = await consolidate_history_and_memory(tmp_path)

    assert ok is False


@pytest.mark.asyncio
async def test_consolidate_preserves_tail_arriving_during_llm(tmp_path):
    history_file = tmp_path / "HISTORY.md"
    history_file.write_text("[2026-03-05] Initial event.\n\n", encoding="utf-8")
    (tmp_path / "MEMORY.md").write_text("Old facts.", encoding="utf-8")

    async def _utility_turn(prompt, **kwargs):
        with open(history_file, "a", encoding="utf-8") as handle:
            handle.write("[2026-03-05 12:01] Tail event.\n\n")
        return "# Consolidated Memory\n\nInitial event preserved."

    with (
        _force_small_threshold(),
        patch("mc.infrastructure.acp.utility.run_utility_turn", side_effect=_utility_turn),
    ):
        ok = await consolidate_history_and_memory(tmp_path)

    assert ok is True
    assert history_file.read_text(encoding="utf-8") == "[2026-03-05 12:01] Tail event.\n\n"
    archive_text = (tmp_path / "HISTORY_ARCHIVE.md").read_text(encoding="utf-8")
    assert "Initial event." in archive_text
    assert "Tail event." not in archive_text
    assert "Initial event preserved." in (tmp_path / "MEMORY.md").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_consolidate_aborts_on_non_append_conflict(tmp_path):
    history_file = tmp_path / "HISTORY.md"
    history_file.write_text("[2026-03-05] Initial event.\n\n", encoding="utf-8")
    (tmp_path / "MEMORY.md").write_text("Old facts.", encoding="utf-8")
    temp_paths: list[Path] = []

    async def _utility_turn(prompt, **kwargs):
        history_file.write_text("[2026-03-05 12:01] Rewritten history.\n\n", encoding="utf-8")
        return "# Consolidated Memory\n\nShould not commit."

    with (
        _force_small_threshold(),
        patch("mc.infrastructure.acp.utility.run_utility_turn", side_effect=_utility_turn),
        patch(
            "tempfile.NamedTemporaryFile", side_effect=_capture_named_tempfile_factory(temp_paths)
        ),
    ):
        ok = await consolidate_history_and_memory(tmp_path)

    assert ok is False
    assert history_file.read_text(encoding="utf-8") == "[2026-03-05 12:01] Rewritten history.\n\n"
    assert (tmp_path / "MEMORY.md").read_text(encoding="utf-8") == "Old facts."
    assert not (tmp_path / "HISTORY_ARCHIVE.md").exists()
    assert list(tmp_path.glob("MEMORY_*.md")) == []
    assert all(not path.exists() for path in temp_paths)
