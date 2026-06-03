"""Tests for mc.memory.service — canonical helpers for memory backends."""

import json
import sqlite3
from unittest.mock import AsyncMock, patch

import pytest

from mc.memory.service import (
    DEFAULT_TASK_CONSOLIDATION_SYSTEM_PROMPT,
    consolidate_task_output,
    create_memory_store,
    quarantine_invalid_memory_files,
)
from mc.memory.store import HybridMemoryStore

# ── create_memory_store ─────────────────────────────────────────────────────


class TestCreateMemoryStore:
    """Tests for create_memory_store()."""

    def test_returns_hybrid_store(self, tmp_path):
        store = create_memory_store(tmp_path)
        assert isinstance(store, HybridMemoryStore)

    def test_does_not_mutate_workspace_when_creating_store(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        rogue = memory_dir / "rogue.txt"
        rogue.write_text("bad", encoding="utf-8")

        store = create_memory_store(tmp_path)

        assert isinstance(store, HybridMemoryStore)
        assert rogue.exists()
        assert not (tmp_path / ".memory-quarantine").exists()

    def test_passes_embedding_model(self, tmp_path):
        store = create_memory_store(tmp_path, embedding_model="test-embed")
        assert isinstance(store, HybridMemoryStore)


# ── quarantine_invalid_memory_files ─────────────────────────────────────────


class TestQuarantineInvalidMemoryFiles:
    """Tests for quarantine_invalid_memory_files()."""

    def test_noop_when_no_memory_dir(self, tmp_path):
        result = quarantine_invalid_memory_files(tmp_path)
        assert result == []

    def test_noop_when_all_valid(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "MEMORY.md").write_text("ok", encoding="utf-8")
        (memory_dir / "HISTORY.md").write_text("ok", encoding="utf-8")

        result = quarantine_invalid_memory_files(tmp_path)
        assert result == []

    def test_moves_invalid_files_to_quarantine(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "MEMORY.md").write_text("ok", encoding="utf-8")
        rogue = memory_dir / "rogue.md"
        rogue.write_text("bad content", encoding="utf-8")

        result = quarantine_invalid_memory_files(tmp_path)

        assert len(result) == 1
        assert not rogue.exists()
        quarantine_dir = tmp_path / ".memory-quarantine"
        assert quarantine_dir.exists()
        moved = result[0]
        assert moved.read_text(encoding="utf-8") == "bad content"

    def test_moves_legacy_snapshot_files_to_quarantine(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        legacy = memory_dir / "HISTORY_2026-03-05_1430.md"
        legacy.write_text("legacy history", encoding="utf-8")

        result = quarantine_invalid_memory_files(tmp_path)

        assert len(result) == 1
        assert result[0].name == "HISTORY_2026-03-05_1430.md"
        assert result[0].read_text(encoding="utf-8") == "legacy history"
        assert not legacy.exists()

    def test_moves_youtube_summarizer_style_files_to_quarantine(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        summary = memory_dir / "kelvincleto_summary_2026-03-05.md"
        listing = memory_dir / "kelvincleto_videos.json"
        summary.write_text("summary", encoding="utf-8")
        listing.write_text("{}", encoding="utf-8")

        result = quarantine_invalid_memory_files(tmp_path)
        names = [path.name for path in result]

        assert names == [
            "kelvincleto_summary_2026-03-05.md",
            "kelvincleto_videos.json",
        ]
        assert not summary.exists()
        assert not listing.exists()

    def test_custom_quarantine_root(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "rogue.txt").write_text("bad", encoding="utf-8")

        custom_q = tmp_path / "custom-quarantine"
        result = quarantine_invalid_memory_files(tmp_path, quarantine_root=custom_q)

        assert len(result) == 1
        assert result[0].parent == custom_q

    def test_quarantines_directories(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        subdir = memory_dir / "subdir"
        subdir.mkdir()
        (subdir / "file.txt").write_text("inner", encoding="utf-8")

        result = quarantine_invalid_memory_files(tmp_path)

        assert len(result) == 1
        assert not subdir.exists()

    def test_handles_name_collisions(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        quarantine_dir = tmp_path / ".memory-quarantine"
        quarantine_dir.mkdir(parents=True, exist_ok=True)

        (quarantine_dir / "rogue.md").write_text("first", encoding="utf-8")

        (memory_dir / "rogue.md").write_text("second", encoding="utf-8")

        result = quarantine_invalid_memory_files(tmp_path)

        assert len(result) == 1
        assert result[0].name == "rogue-2.md"
        assert result[0].read_text(encoding="utf-8") == "second"
        assert (quarantine_dir / "rogue.md").read_text(encoding="utf-8") == "first"

    def test_preserves_valid_memory_files(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        mem = memory_dir / "MEMORY.md"
        hist = memory_dir / "HISTORY.md"
        archive = memory_dir / "HISTORY_ARCHIVE.md"
        sqlite_path = memory_dir / "memory-index.sqlite"
        lock = memory_dir / ".memory.lock"
        mem.write_text("mem", encoding="utf-8")
        hist.write_text("hist", encoding="utf-8")
        archive.write_text("arch", encoding="utf-8")
        conn = sqlite3.connect(str(sqlite_path))
        conn.close()
        lock.write_text("lock", encoding="utf-8")

        (memory_dir / "rogue.json").write_text("{}", encoding="utf-8")

        result = quarantine_invalid_memory_files(tmp_path)

        assert len(result) == 1
        assert mem.exists()
        assert hist.exists()
        assert archive.exists()
        assert sqlite_path.exists()
        assert lock.exists()


# ── consolidate_task_output ─────────────────────────────────────────────────


def _json_text(history_entry: str, memory_update: str) -> str:
    """Return a JSON string as run_utility_turn would return it."""
    return json.dumps({"history_entry": history_entry, "memory_update": memory_update})


class TestConsolidateTaskOutput:
    """Tests for consolidate_task_output()."""

    @pytest.fixture
    def workspace(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        (memory_dir / "MEMORY.md").write_text("# Existing Memory\nFact 1", encoding="utf-8")
        return tmp_path

    @pytest.mark.asyncio
    async def test_successful_consolidation(self, workspace):
        text = _json_text(
            "[2026-03-05 10:00] Task completed successfully",
            "# Updated Memory\nFact 1\nFact 2",
        )

        with patch(
            "mc.infrastructure.acp.utility.run_utility_turn",
            new=AsyncMock(return_value=text),
        ):
            result = await consolidate_task_output(
                workspace,
                task_title="Test Task",
                task_output="Task did things",
                task_status="completed",
                task_id="task-123",
            )

        assert result is True
        history = (workspace / "memory" / "HISTORY.md").read_text(encoding="utf-8")
        assert "Task completed successfully" in history
        memory = (workspace / "memory" / "MEMORY.md").read_text(encoding="utf-8")
        assert "Fact 2" in memory

    @pytest.mark.asyncio
    async def test_llm_call_failure_returns_false(self, workspace):
        from mc.infrastructure.providers.errors import ProviderError

        with patch(
            "mc.infrastructure.acp.utility.run_utility_turn",
            new=AsyncMock(side_effect=ProviderError("API error")),
        ):
            result = await consolidate_task_output(
                workspace,
                task_title="Test Task",
                task_output="output",
                task_status="completed",
                task_id="task-456",
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_no_tool_calls_returns_false(self, workspace):
        """When the LLM returns text with no parseable JSON, returns False."""
        with patch(
            "mc.infrastructure.acp.utility.run_utility_turn",
            new=AsyncMock(return_value="not valid json here"),
        ):
            result = await consolidate_task_output(
                workspace,
                task_title="Test Task",
                task_output="output",
                task_status="completed",
                task_id="task-789",
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_truncates_long_output(self, workspace):
        """Verify truncation is applied to long task output."""
        long_output = "x" * 5000
        text = _json_text("[2026-03-05 10:00] Done", "# Memory")

        captured_prompt: list[str] = []

        async def _capture(prompt, **kwargs):
            captured_prompt.append(prompt)
            return text

        with patch("mc.infrastructure.acp.utility.run_utility_turn", side_effect=_capture):
            await consolidate_task_output(
                workspace,
                task_title="Test Task",
                task_output=long_output,
                task_status="completed",
                task_id="task-trunc",
                max_output_chars=3000,
            )

        assert captured_prompt
        assert "truncated" in captured_prompt[0]
        assert "5000" in captured_prompt[0]

    @pytest.mark.asyncio
    async def test_unchanged_memory_not_rewritten(self, workspace):
        existing_memory = (workspace / "memory" / "MEMORY.md").read_text(encoding="utf-8")
        text = _json_text("[2026-03-05 10:00] Nothing new", existing_memory)

        with patch(
            "mc.infrastructure.acp.utility.run_utility_turn",
            new=AsyncMock(return_value=text),
        ):
            result = await consolidate_task_output(
                workspace,
                task_title="Test Task",
                task_output="output",
                task_status="completed",
                task_id="task-noop",
            )

        assert result is True
        history = (workspace / "memory" / "HISTORY.md").read_text(encoding="utf-8")
        assert "Nothing new" in history
        memory = (workspace / "memory" / "MEMORY.md").read_text(encoding="utf-8")
        assert memory == existing_memory

    @pytest.mark.asyncio
    async def test_empty_workspace_creates_memory_dir(self, tmp_path):
        text = _json_text("[2026-03-05 10:00] First entry", "# First memory")

        with patch(
            "mc.infrastructure.acp.utility.run_utility_turn",
            new=AsyncMock(return_value=text),
        ):
            result = await consolidate_task_output(
                tmp_path,
                task_title="First Task",
                task_output="output",
                task_status="completed",
                task_id="task-new",
            )

        assert result is True


# ── Constants ───────────────────────────────────────────────────────────────


class TestConstants:
    """Verify module-level constants are sensible."""

    def test_system_prompt_is_non_empty_string(self):
        assert isinstance(DEFAULT_TASK_CONSOLIDATION_SYSTEM_PROMPT, str)
        assert len(DEFAULT_TASK_CONSOLIDATION_SYSTEM_PROMPT) > 50

    def test_system_prompt_requests_json_contract(self):
        # The parser reads these keys from the returned JSON, so the prompt must name them.
        assert "history_entry" in DEFAULT_TASK_CONSOLIDATION_SYSTEM_PROMPT
        assert "memory_update" in DEFAULT_TASK_CONSOLIDATION_SYSTEM_PROMPT
