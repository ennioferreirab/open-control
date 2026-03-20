"""Tests for Story 12.1 — Board Agent Memory Mode (board_utils.py).

Covers:
- resolve_board_workspace() in clean mode (directory creation, memory bootstrap)
- resolve_board_workspace() in with_history mode (symlink creation, global file creation)
- Mode switching: clean replaces symlinks, with_history replaces regular files
- get_agent_memory_mode() defaults and configured modes
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from unittest.mock import patch


@contextlib.contextmanager
def _patch_runtime_home(tmp_path: Path):
    """Patch runtime home helpers to use tmp_path as the nanobot home root.

    Sets up the following layout under tmp_path:
        tmp_path/.nanobot/         ← runtime home
        tmp_path/.nanobot/boards/  ← boards dir
        tmp_path/.nanobot/agents/  ← agents dir
    """
    nanobot_home = tmp_path / ".nanobot"
    boards_dir = nanobot_home / "boards"
    agents_dir = nanobot_home / "agents"
    with (
        patch("mc.infrastructure.boards.get_agents_dir", return_value=agents_dir),
        patch("mc.infrastructure.boards.get_boards_dir", return_value=boards_dir),
        patch("mc.artifacts.service.get_runtime_home", return_value=nanobot_home),
    ):
        yield


# ---------------------------------------------------------------------------
# resolve_board_workspace -- clean mode
# ---------------------------------------------------------------------------


class TestResolveBoardWorkspaceClean:
    def test_creates_dirs(self, tmp_path: Path) -> None:
        from mc.infrastructure.boards import resolve_board_workspace

        with _patch_runtime_home(tmp_path):
            ws = resolve_board_workspace("my-board", "worker", mode="clean")

        assert (ws / "memory").is_dir()
        assert (ws / "sessions").is_dir()

    def test_returns_correct_path(self, tmp_path: Path) -> None:
        from mc.infrastructure.boards import resolve_board_workspace

        with _patch_runtime_home(tmp_path):
            ws = resolve_board_workspace("project-alpha", "dev-agent", mode="clean")

        expected = tmp_path / ".nanobot" / "boards" / "project-alpha" / "agents" / "dev-agent"
        assert ws == expected

    def test_bootstraps_from_global(self, tmp_path: Path) -> None:
        from mc.infrastructure.boards import resolve_board_workspace

        # Create global MEMORY.md
        global_mem_dir = tmp_path / ".nanobot" / "agents" / "dev-agent" / "memory"
        global_mem_dir.mkdir(parents=True)
        (global_mem_dir / "MEMORY.md").write_text("# Global memories", encoding="utf-8")

        with _patch_runtime_home(tmp_path):
            ws = resolve_board_workspace("sprint-1", "dev-agent", mode="clean")

        board_mem = ws / "memory" / "MEMORY.md"
        assert board_mem.exists()
        assert not board_mem.is_symlink()
        assert board_mem.read_text() == "# Global memories"

    def test_creates_empty_memory_when_no_global(self, tmp_path: Path) -> None:
        from mc.infrastructure.boards import resolve_board_workspace

        with _patch_runtime_home(tmp_path):
            ws = resolve_board_workspace("my-board", "worker", mode="clean")

        memory_md = ws / "memory" / "MEMORY.md"
        assert memory_md.exists()
        assert not memory_md.is_symlink()
        assert memory_md.read_text() == ""

    def test_creates_empty_history(self, tmp_path: Path) -> None:
        from mc.infrastructure.boards import resolve_board_workspace

        with _patch_runtime_home(tmp_path):
            ws = resolve_board_workspace("my-board", "worker", mode="clean")

        history_md = ws / "memory" / "HISTORY.md"
        assert history_md.exists()
        assert not history_md.is_symlink()
        assert history_md.read_text() == ""

    def test_does_not_overwrite_existing_board_memory(self, tmp_path: Path) -> None:
        from mc.infrastructure.boards import resolve_board_workspace

        # Pre-create board memory
        board_mem_dir = (
            tmp_path / ".nanobot" / "boards" / "sprint-1" / "agents" / "dev-agent" / "memory"
        )
        board_mem_dir.mkdir(parents=True)
        (board_mem_dir / "MEMORY.md").write_text("board-specific", encoding="utf-8")

        # Also create global with different content
        global_mem_dir = tmp_path / ".nanobot" / "agents" / "dev-agent" / "memory"
        global_mem_dir.mkdir(parents=True)
        (global_mem_dir / "MEMORY.md").write_text("global", encoding="utf-8")

        with _patch_runtime_home(tmp_path):
            ws = resolve_board_workspace("sprint-1", "dev-agent", mode="clean")

        assert (ws / "memory" / "MEMORY.md").read_text() == "board-specific"

    def test_replaces_symlinks_with_regular_files(self, tmp_path: Path) -> None:
        """Switching from with_history to clean should replace symlinks."""
        from mc.infrastructure.boards import resolve_board_workspace

        # Create global files
        global_mem_dir = tmp_path / ".nanobot" / "agents" / "dev-agent" / "memory"
        global_mem_dir.mkdir(parents=True)
        (global_mem_dir / "MEMORY.md").write_text("# Global", encoding="utf-8")
        (global_mem_dir / "HISTORY.md").write_text("# History", encoding="utf-8")

        # First set up with_history (creates symlinks)
        with _patch_runtime_home(tmp_path):
            ws = resolve_board_workspace("my-board", "dev-agent", mode="with_history")

        assert (ws / "memory" / "MEMORY.md").is_symlink()
        assert (ws / "memory" / "HISTORY.md").is_symlink()

        # Now switch to clean
        with _patch_runtime_home(tmp_path):
            ws = resolve_board_workspace("my-board", "dev-agent", mode="clean")

        memory_md = ws / "memory" / "MEMORY.md"
        history_md = ws / "memory" / "HISTORY.md"
        assert not memory_md.is_symlink()
        assert not history_md.is_symlink()
        assert memory_md.exists()
        assert history_md.exists()
        # After unlinking symlink, clean mode bootstraps from global
        assert memory_md.read_text() == "# Global"
        # HISTORY.md starts empty in clean mode
        assert history_md.read_text() == ""


# ---------------------------------------------------------------------------
# resolve_board_workspace -- with_history mode
# ---------------------------------------------------------------------------


class TestResolveBoardWorkspaceWithHistory:
    def test_creates_symlinks(self, tmp_path: Path) -> None:
        from mc.infrastructure.boards import resolve_board_workspace

        # Create global files
        global_mem_dir = tmp_path / ".nanobot" / "agents" / "dev-agent" / "memory"
        global_mem_dir.mkdir(parents=True)
        (global_mem_dir / "MEMORY.md").write_text("# Global", encoding="utf-8")
        (global_mem_dir / "HISTORY.md").write_text("# History", encoding="utf-8")

        with _patch_runtime_home(tmp_path):
            ws = resolve_board_workspace("my-board", "dev-agent", mode="with_history")

        memory_md = ws / "memory" / "MEMORY.md"
        history_md = ws / "memory" / "HISTORY.md"
        assert memory_md.is_symlink()
        assert history_md.is_symlink()
        assert memory_md.resolve() == (global_mem_dir / "MEMORY.md").resolve()
        assert history_md.resolve() == (global_mem_dir / "HISTORY.md").resolve()

    def test_creates_global_if_missing(self, tmp_path: Path) -> None:
        from mc.infrastructure.boards import resolve_board_workspace

        with _patch_runtime_home(tmp_path):
            ws = resolve_board_workspace("my-board", "dev-agent", mode="with_history")

        # Global files should have been created
        global_memory = tmp_path / ".nanobot" / "agents" / "dev-agent" / "memory" / "MEMORY.md"
        global_history = tmp_path / ".nanobot" / "agents" / "dev-agent" / "memory" / "HISTORY.md"
        assert global_memory.exists()
        assert global_history.exists()
        assert global_memory.read_text() == ""
        assert global_history.read_text() == ""

        # Board files should be symlinks pointing to them
        assert (ws / "memory" / "MEMORY.md").is_symlink()
        assert (ws / "memory" / "HISTORY.md").is_symlink()

    def test_replaces_regular_files_with_symlinks(self, tmp_path: Path) -> None:
        """Switching from clean to with_history should replace regular files with symlinks."""
        from mc.infrastructure.boards import resolve_board_workspace

        # First set up clean mode (creates regular files)
        with _patch_runtime_home(tmp_path):
            ws = resolve_board_workspace("my-board", "dev-agent", mode="clean")

        assert not (ws / "memory" / "MEMORY.md").is_symlink()
        assert not (ws / "memory" / "HISTORY.md").is_symlink()
        assert (ws / "memory" / "MEMORY.md").exists()
        assert (ws / "memory" / "HISTORY.md").exists()

        # Now switch to with_history
        with _patch_runtime_home(tmp_path):
            ws = resolve_board_workspace("my-board", "dev-agent", mode="with_history")

        memory_md = ws / "memory" / "MEMORY.md"
        history_md = ws / "memory" / "HISTORY.md"
        assert memory_md.is_symlink()
        assert history_md.is_symlink()

    def test_symlinks_propagate_writes(self, tmp_path: Path) -> None:
        """Writes to symlinked board files should propagate to global originals."""
        from mc.infrastructure.boards import resolve_board_workspace

        with _patch_runtime_home(tmp_path):
            ws = resolve_board_workspace("my-board", "dev-agent", mode="with_history")

        board_memory = ws / "memory" / "MEMORY.md"
        global_memory = tmp_path / ".nanobot" / "agents" / "dev-agent" / "memory" / "MEMORY.md"

        board_memory.write_text("# Updated via board", encoding="utf-8")
        assert global_memory.read_text() == "# Updated via board"

    def test_idempotent_second_call(self, tmp_path: Path) -> None:
        from mc.infrastructure.boards import resolve_board_workspace

        with _patch_runtime_home(tmp_path):
            ws1 = resolve_board_workspace("my-board", "dev-agent", mode="with_history")
            ws2 = resolve_board_workspace("my-board", "dev-agent", mode="with_history")

        assert ws1 == ws2
        assert (ws1 / "memory" / "MEMORY.md").is_symlink()

    def test_creates_dirs(self, tmp_path: Path) -> None:
        from mc.infrastructure.boards import resolve_board_workspace

        with _patch_runtime_home(tmp_path):
            ws = resolve_board_workspace("my-board", "worker", mode="with_history")

        assert (ws / "memory").is_dir()
        assert (ws / "sessions").is_dir()


class TestResolveMemoryWorkspace:
    def test_with_history_uses_shared_agent_workspace(self, tmp_path: Path) -> None:
        from mc.infrastructure.boards import resolve_memory_workspace

        with _patch_runtime_home(tmp_path):
            resolved = resolve_memory_workspace(
                "dev-agent",
                board_name="default",
                mode="with_history",
            )

        expected_root = tmp_path / ".nanobot" / "agents" / "dev-agent"
        assert resolved.workspace == expected_root
        assert resolved.effective_memory_scope == "shared-agent"
        assert resolved.memory_file == expected_root / "memory" / "MEMORY.md"
        assert resolved.history_file == expected_root / "memory" / "HISTORY.md"
        assert resolved.index_file == expected_root / "memory" / "memory-index.sqlite"

    def test_clean_uses_board_scoped_workspace(self, tmp_path: Path) -> None:
        from mc.infrastructure.boards import resolve_memory_workspace

        with _patch_runtime_home(tmp_path):
            resolved = resolve_memory_workspace(
                "dev-agent",
                board_name="default",
                mode="clean",
            )

        expected_root = tmp_path / ".nanobot" / "boards" / "default" / "agents" / "dev-agent"
        assert resolved.workspace == expected_root
        assert resolved.effective_memory_scope == "board"
        assert resolved.memory_file == expected_root / "memory" / "MEMORY.md"
        assert resolved.history_file == expected_root / "memory" / "HISTORY.md"
        assert resolved.index_file == expected_root / "memory" / "memory-index.sqlite"


# ---------------------------------------------------------------------------
# get_agent_memory_mode
# ---------------------------------------------------------------------------


class TestGetAgentMemoryMode:
    def test_defaults_to_clean_when_no_board_data(self) -> None:
        from mc.infrastructure.boards import get_agent_memory_mode

        assert get_agent_memory_mode(None, "dev-agent") == "clean"

    def test_defaults_to_clean_when_no_modes(self) -> None:
        from mc.infrastructure.boards import get_agent_memory_mode

        board_data = {"name": "my-board"}
        assert get_agent_memory_mode(board_data, "dev-agent") == "clean"

    def test_defaults_to_clean_when_empty_modes(self) -> None:
        from mc.infrastructure.boards import get_agent_memory_mode

        board_data = {"name": "my-board", "agent_memory_modes": []}
        assert get_agent_memory_mode(board_data, "dev-agent") == "clean"

    def test_defaults_to_clean_when_agent_not_listed(self) -> None:
        from mc.infrastructure.boards import get_agent_memory_mode

        board_data = {
            "name": "my-board",
            "agent_memory_modes": [
                {"agent_name": "other-agent", "mode": "with_history"},
            ],
        }
        assert get_agent_memory_mode(board_data, "dev-agent") == "clean"

    def test_returns_configured_mode(self) -> None:
        from mc.infrastructure.boards import get_agent_memory_mode

        board_data = {
            "name": "my-board",
            "agent_memory_modes": [
                {"agent_name": "dev-agent", "mode": "with_history"},
                {"agent_name": "research-agent", "mode": "clean"},
            ],
        }
        assert get_agent_memory_mode(board_data, "dev-agent") == "with_history"
        assert get_agent_memory_mode(board_data, "research-agent") == "clean"

    def test_defaults_to_clean_when_mode_missing_in_entry(self) -> None:
        from mc.infrastructure.boards import get_agent_memory_mode

        board_data = {
            "name": "my-board",
            "agent_memory_modes": [
                {"agent_name": "dev-agent"},  # mode key missing
            ],
        }
        assert get_agent_memory_mode(board_data, "dev-agent") == "clean"


class TestResolveBoardArtifactsWorkspace:
    def test_returns_board_scoped_artifacts_dir(self, tmp_path: Path) -> None:
        from mc.artifacts import resolve_board_artifacts_workspace

        with _patch_runtime_home(tmp_path):
            artifacts_dir = resolve_board_artifacts_workspace("default")

        expected = tmp_path / ".nanobot" / "boards" / "default" / "artifacts"
        assert artifacts_dir == expected
        assert artifacts_dir.is_dir()
