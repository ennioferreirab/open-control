"""Tests for mc.memory.policy — file contract for agent memory directories."""

from pathlib import Path

import pytest

from mc.memory.policy import (
    find_invalid_memory_files,
    is_allowed_memory_file,
    is_memory_markdown_file,
    iter_memory_markdown_files,
)

# ── is_memory_markdown_file ─────────────────────────────────────────────────


class TestIsMemoryMarkdownFile:
    """Tests for is_memory_markdown_file()."""

    @pytest.mark.parametrize(
        "name",
        [
            "MEMORY.md",
            "HISTORY.md",
            "HISTORY_ARCHIVE.md",
        ],
    )
    def test_primary_markdown_files_accepted(self, name):
        assert is_memory_markdown_file(Path(name)) is True

    @pytest.mark.parametrize(
        "name",
        [
            "rogue.md",
            "notes.md",
            "MEMORY.txt",
            "HISTORY.txt",
            "memory.md",  # lowercase
            "history.md",
            "MEMORY_baddate.md",
            "MEMORY_2026-03-05_1430.md",
            "MEMORY_2026-01-01_0000.md",
            "MEMORY_2026-03-05.md",  # no time component
            "HISTORY_2025-12-31_2359.md",
            "HISTORY_2026-03-05_143000.md",
            "RANDOM_2026-03-05_1430.md",  # wrong prefix
            "memory-index.sqlite",
        ],
    )
    def test_non_memory_markdown_rejected(self, name):
        assert is_memory_markdown_file(Path(name)) is False


# ── is_allowed_memory_file ──────────────────────────────────────────────────


class TestIsAllowedMemoryFile:
    """Tests for is_allowed_memory_file()."""

    @pytest.mark.parametrize(
        "name",
        [
            "MEMORY.md",
            "HISTORY.md",
            "HISTORY_ARCHIVE.md",
            "memory-index.sqlite",
            "memory-index.sqlite-shm",
            "memory-index.sqlite-wal",
            ".memory.lock",
            ".consolidation.lock",
            "MEMORY.md.lock",
            "HISTORY.md.lock",
        ],
    )
    def test_allowed_files(self, tmp_path, name):
        path = tmp_path / name
        path.write_text("", encoding="utf-8")
        assert is_allowed_memory_file(path) is True

    @pytest.mark.parametrize(
        "name",
        [
            "rogue.md",
            "notes.txt",
            "data.json",
            ".hidden_file",
        ],
    )
    def test_disallowed_files(self, tmp_path, name):
        path = tmp_path / name
        path.write_text("", encoding="utf-8")
        assert is_allowed_memory_file(path) is False

    def test_directories_are_not_allowed(self, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        assert is_allowed_memory_file(subdir) is False


# ── iter_memory_markdown_files ──────────────────────────────────────────────


class TestIterMemoryMarkdownFiles:
    """Tests for iter_memory_markdown_files()."""

    def test_returns_empty_for_nonexistent_dir(self, tmp_path):
        result = iter_memory_markdown_files(tmp_path / "nonexistent")
        assert result == []

    def test_returns_empty_for_empty_dir(self, tmp_path):
        result = iter_memory_markdown_files(tmp_path)
        assert result == []

    def test_returns_only_memory_markdown_files(self, tmp_path):
        (tmp_path / "MEMORY.md").write_text("mem", encoding="utf-8")
        (tmp_path / "HISTORY.md").write_text("hist", encoding="utf-8")
        (tmp_path / "rogue.md").write_text("nope", encoding="utf-8")
        (tmp_path / "data.json").write_text("{}", encoding="utf-8")

        result = iter_memory_markdown_files(tmp_path)
        names = [p.name for p in result]
        assert "MEMORY.md" in names
        assert "HISTORY.md" in names
        assert "rogue.md" not in names
        assert "data.json" not in names

    def test_includes_archive_files(self, tmp_path):
        (tmp_path / "HISTORY_ARCHIVE.md").write_text("arch", encoding="utf-8")

        result = iter_memory_markdown_files(tmp_path)
        names = [p.name for p in result]
        assert "HISTORY_ARCHIVE.md" in names

    def test_excludes_youtube_summarizer_style_files(self, tmp_path):
        (tmp_path / "MEMORY.md").write_text("facts", encoding="utf-8")
        (tmp_path / "kelvincleto_summary_2026-03-05.md").write_text("rogue", encoding="utf-8")
        (tmp_path / "kelvincleto_videos.json").write_text("{}", encoding="utf-8")

        result = iter_memory_markdown_files(tmp_path)
        names = [p.name for p in result]

        assert names == ["MEMORY.md"]

    def test_results_are_sorted(self, tmp_path):
        (tmp_path / "MEMORY.md").write_text("", encoding="utf-8")
        (tmp_path / "HISTORY.md").write_text("", encoding="utf-8")
        (tmp_path / "HISTORY_ARCHIVE.md").write_text("", encoding="utf-8")

        result = iter_memory_markdown_files(tmp_path)
        names = [p.name for p in result]
        assert names == sorted(names)


# ── find_invalid_memory_files ───────────────────────────────────────────────


class TestFindInvalidMemoryFiles:
    """Tests for find_invalid_memory_files()."""

    def test_returns_empty_for_nonexistent_dir(self, tmp_path):
        result = find_invalid_memory_files(tmp_path / "nonexistent")
        assert result == []

    def test_returns_empty_when_all_valid(self, tmp_path):
        (tmp_path / "MEMORY.md").write_text("", encoding="utf-8")
        (tmp_path / "HISTORY.md").write_text("", encoding="utf-8")
        (tmp_path / "memory-index.sqlite").write_text("", encoding="utf-8")
        (tmp_path / ".memory.lock").write_text("", encoding="utf-8")

        result = find_invalid_memory_files(tmp_path)
        assert result == []

    def test_detects_rogue_files(self, tmp_path):
        (tmp_path / "MEMORY.md").write_text("", encoding="utf-8")
        (tmp_path / "rogue.md").write_text("bad", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("bad", encoding="utf-8")
        (tmp_path / "HISTORY_2026-03-05_1430.md").write_text("legacy", encoding="utf-8")

        result = find_invalid_memory_files(tmp_path)
        names = [p.name for p in result]
        assert "HISTORY_2026-03-05_1430.md" in names
        assert "rogue.md" in names
        assert "notes.txt" in names
        assert "MEMORY.md" not in names

    def test_detects_youtube_summarizer_style_files(self, tmp_path):
        (tmp_path / "kelvincleto_summary_2026-03-05.md").write_text("summary", encoding="utf-8")
        (tmp_path / "kelvincleto_videos.json").write_text("{}", encoding="utf-8")

        result = find_invalid_memory_files(tmp_path)
        names = [p.name for p in result]

        assert names == [
            "kelvincleto_summary_2026-03-05.md",
            "kelvincleto_videos.json",
        ]

    def test_detects_directories_as_invalid(self, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        result = find_invalid_memory_files(tmp_path)
        names = [p.name for p in result]
        assert "subdir" in names

    def test_results_are_sorted(self, tmp_path):
        (tmp_path / "z_file.txt").write_text("", encoding="utf-8")
        (tmp_path / "a_file.txt").write_text("", encoding="utf-8")

        result = find_invalid_memory_files(tmp_path)
        names = [p.name for p in result]
        assert names == sorted(names)

    def test_empty_dir_returns_empty(self, tmp_path):
        result = find_invalid_memory_files(tmp_path)
        assert result == []
