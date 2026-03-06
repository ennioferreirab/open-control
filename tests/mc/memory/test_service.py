"""Tests for mc.memory.service — canonical helpers for memory backends."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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

    def test_quarantines_invalid_files_before_returning(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        rogue = memory_dir / "rogue.txt"
        rogue.write_text("bad", encoding="utf-8")

        store = create_memory_store(tmp_path)

        assert isinstance(store, HybridMemoryStore)
        assert not rogue.exists()
        assert (tmp_path / ".memory-quarantine" / "rogue.txt").exists()

    def test_passes_embedding_model(self, tmp_path):
        store = create_memory_store(tmp_path, embedding_model="test-embed")
        # The store should be created successfully with the model parameter
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

        # Pre-populate quarantine with a file of the same name
        (quarantine_dir / "rogue.md").write_text("first", encoding="utf-8")

        (memory_dir / "rogue.md").write_text("second", encoding="utf-8")

        result = quarantine_invalid_memory_files(tmp_path)

        assert len(result) == 1
        # Should use a suffixed name to avoid overwriting
        assert result[0].name == "rogue-2.md"
        assert result[0].read_text(encoding="utf-8") == "second"
        # Original quarantined file is untouched
        assert (quarantine_dir / "rogue.md").read_text(encoding="utf-8") == "first"

    def test_preserves_valid_memory_files(self, tmp_path):
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        mem = memory_dir / "MEMORY.md"
        hist = memory_dir / "HISTORY.md"
        archive = memory_dir / "HISTORY_2026-03-05_1430.md"
        sqlite_path = memory_dir / "memory-index.sqlite"
        lock = memory_dir / ".memory.lock"
        mem.write_text("mem", encoding="utf-8")
        hist.write_text("hist", encoding="utf-8")
        archive.write_text("arch", encoding="utf-8")
        # Create a valid (empty) SQLite database so MemoryIndex.sync() can open it
        conn = sqlite3.connect(str(sqlite_path))
        conn.close()
        lock.write_text("lock", encoding="utf-8")

        # Add a rogue file
        (memory_dir / "rogue.json").write_text("{}", encoding="utf-8")

        result = quarantine_invalid_memory_files(tmp_path)

        assert len(result) == 1
        assert mem.exists()
        assert hist.exists()
        assert archive.exists()
        assert sqlite_path.exists()
        assert lock.exists()


# ── consolidate_task_output ─────────────────────────────────────────────────


def _make_llm_response(history_entry: str, memory_update: str):
    """Build a mock provider response with a save_memory tool call."""
    tool_call = MagicMock()
    tool_call.arguments = json.dumps({
        "history_entry": history_entry,
        "memory_update": memory_update,
    })
    response = MagicMock()
    response.tool_calls = [tool_call]
    return response


def _make_llm_response_no_tool_calls():
    """Build a mock provider response with no tool calls."""
    response = MagicMock()
    response.tool_calls = None
    return response


class TestConsolidateTaskOutput:
    """Tests for consolidate_task_output()."""

    @pytest.fixture
    def workspace(self, tmp_path):
        """Set up a workspace with a memory directory."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        (memory_dir / "MEMORY.md").write_text("# Existing Memory\nFact 1", encoding="utf-8")
        return tmp_path

    async def test_successful_consolidation(self, workspace):
        mock_response = _make_llm_response(
            "[2026-03-05 10:00] Task completed successfully",
            "# Updated Memory\nFact 1\nFact 2",
        )
        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        with patch("mc.memory.service.create_provider", return_value=(provider, "resolved-medium-model")):
            result = await consolidate_task_output(
                workspace,
                task_title="Test Task",
                task_output="Task did things",
                task_status="completed",
                task_id="task-123",
            )

        assert result is True
        # Check history was appended
        history = (workspace / "memory" / "HISTORY.md").read_text(encoding="utf-8")
        assert "Task completed successfully" in history
        # Check memory was updated
        memory = (workspace / "memory" / "MEMORY.md").read_text(encoding="utf-8")
        assert "Fact 2" in memory

    async def test_llm_call_failure_returns_false(self, workspace):
        provider = MagicMock()
        provider.chat = AsyncMock(side_effect=Exception("API error"))

        with patch("mc.memory.service.create_provider", return_value=(provider, "resolved-medium-model")):
            result = await consolidate_task_output(
                workspace,
                task_title="Test Task",
                task_output="output",
                task_status="completed",
                task_id="task-456",
            )

        assert result is False

    async def test_no_tool_calls_returns_false(self, workspace):
        mock_response = _make_llm_response_no_tool_calls()
        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        with patch("mc.memory.service.create_provider", return_value=(provider, "resolved-medium-model")):
            result = await consolidate_task_output(
                workspace,
                task_title="Test Task",
                task_output="output",
                task_status="completed",
                task_id="task-789",
            )

        assert result is False

    async def test_truncates_long_output(self, workspace):
        long_output = "x" * 5000

        mock_response = _make_llm_response(
            "[2026-03-05 10:00] Done",
            "# Memory",
        )
        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        with patch("mc.memory.service.create_provider", return_value=(provider, "resolved-medium-model")):
            await consolidate_task_output(
                workspace,
                task_title="Test Task",
                task_output=long_output,
                task_status="completed",
                task_id="task-trunc",
                max_output_chars=3000,
            )

            call_args = provider.chat.call_args
            messages = call_args.kwargs["messages"]
            user_msg = messages[1]["content"]
            assert "truncated" in user_msg
            assert "5000" in user_msg

    async def test_custom_system_prompt(self, workspace):
        mock_response = _make_llm_response("[2026-03-05] Done", "# Memory")
        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        with patch("mc.memory.service.create_provider", return_value=(provider, "resolved-medium-model")):
            await consolidate_task_output(
                workspace,
                task_title="Test Task",
                task_output="output",
                task_status="completed",
                task_id="task-prompt",
                system_prompt="Custom prompt",
            )

            call_args = provider.chat.call_args
            messages = call_args.kwargs["messages"]
            assert messages[0]["content"] == "Custom prompt"

    async def test_default_system_prompt_used(self, workspace):
        mock_response = _make_llm_response("[2026-03-05] Done", "# Memory")
        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        with patch("mc.memory.service.create_provider", return_value=(provider, "resolved-medium-model")):
            await consolidate_task_output(
                workspace,
                task_title="Test Task",
                task_output="output",
                task_status="completed",
                task_id="task-default",
            )

            call_args = provider.chat.call_args
            messages = call_args.kwargs["messages"]
            assert messages[0]["content"] == DEFAULT_TASK_CONSOLIDATION_SYSTEM_PROMPT

    async def test_unchanged_memory_not_rewritten(self, workspace):
        existing_memory = (workspace / "memory" / "MEMORY.md").read_text(encoding="utf-8")
        mock_response = _make_llm_response(
            "[2026-03-05 10:00] Nothing new",
            existing_memory,  # Same as current
        )
        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        with patch("mc.memory.service.create_provider", return_value=(provider, "resolved-medium-model")):
            result = await consolidate_task_output(
                workspace,
                task_title="Test Task",
                task_output="output",
                task_status="completed",
                task_id="task-noop",
            )

        assert result is True
        # History should still be appended
        history = (workspace / "memory" / "HISTORY.md").read_text(encoding="utf-8")
        assert "Nothing new" in history
        # Memory should remain unchanged
        memory = (workspace / "memory" / "MEMORY.md").read_text(encoding="utf-8")
        assert memory == existing_memory

    async def test_string_args_from_llm(self, workspace):
        """When the LLM returns arguments as a JSON string (not pre-parsed dict)."""
        tool_call = MagicMock()
        tool_call.arguments = json.dumps({
            "history_entry": "[2026-03-05] String args",
            "memory_update": "# New memory",
        })
        response = MagicMock()
        response.tool_calls = [tool_call]

        provider = MagicMock()
        provider.chat = AsyncMock(return_value=response)

        with patch("mc.memory.service.create_provider", return_value=(provider, "resolved-medium-model")):
            result = await consolidate_task_output(
                workspace,
                task_title="Test",
                task_output="out",
                task_status="done",
                task_id="task-str",
            )

        assert result is True

    async def test_non_dict_args_returns_false(self, workspace):
        """When parsed arguments are not a dict, return False."""
        tool_call = MagicMock()
        tool_call.arguments = '"just a string"'
        response = MagicMock()
        response.tool_calls = [tool_call]

        provider = MagicMock()
        provider.chat = AsyncMock(return_value=response)

        with patch("mc.memory.service.create_provider", return_value=(provider, "resolved-medium-model")):
            result = await consolidate_task_output(
                workspace,
                task_title="Test",
                task_output="out",
                task_status="done",
                task_id="task-bad-args",
            )

        assert result is False

    async def test_malformed_tool_call_returns_false(self, workspace):
        """When tool call arguments can't be parsed, return False."""
        tool_call = MagicMock()
        tool_call.arguments = "not valid json {{{"
        response = MagicMock()
        response.tool_calls = [tool_call]

        provider = MagicMock()
        provider.chat = AsyncMock(return_value=response)

        with patch("mc.memory.service.create_provider", return_value=(provider, "resolved-medium-model")):
            result = await consolidate_task_output(
                workspace,
                task_title="Test",
                task_output="out",
                task_status="done",
                task_id="task-malformed",
            )

        assert result is False

    async def test_non_string_entry_converted_to_json(self, workspace):
        """When history_entry is not a string (e.g. dict), it gets JSON-encoded."""
        tool_call = MagicMock()
        tool_call.arguments = {
            "history_entry": {"key": "value"},
            "memory_update": "# Memory",
        }
        response = MagicMock()
        response.tool_calls = [tool_call]

        provider = MagicMock()
        provider.chat = AsyncMock(return_value=response)

        with patch("mc.memory.service.create_provider", return_value=(provider, "resolved-medium-model")):
            result = await consolidate_task_output(
                workspace,
                task_title="Test",
                task_output="out",
                task_status="done",
                task_id="task-nonstr",
            )

        assert result is True
        history = (workspace / "memory" / "HISTORY.md").read_text(encoding="utf-8")
        assert '"key"' in history

    async def test_empty_workspace_creates_memory_dir(self, tmp_path):
        """consolidate_task_output works even when memory dir doesn't exist yet."""
        mock_response = _make_llm_response(
            "[2026-03-05 10:00] First entry",
            "# First memory",
        )
        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        with patch("mc.memory.service.create_provider", return_value=(provider, "resolved-medium-model")):
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

    def test_system_prompt_mentions_save_memory(self):
        assert "save_memory" in DEFAULT_TASK_CONSOLIDATION_SYSTEM_PROMPT
