"""Board workspace utilities.

Canonical implementation of board-scoped memory workspace resolution,
extracted from executor.py and step_dispatcher.py to eliminate duplication.

Supports two memory modes:
- "clean" (default): board gets its own copy of MEMORY.md (seeded from global)
  and an empty HISTORY.md per board.
- "with_history": board MEMORY.md and HISTORY.md are symlinks to the agent's
  global memory files, so all boards share the same memory.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def get_agent_memory_mode(
    board_data: dict[str, Any] | None,
    agent_name: str,
) -> str:
    """Return 'clean' or 'with_history' for the given agent on a board.

    The bridge auto-converts camelCase (agentMemoryModes) to snake_case
    (agent_memory_modes), so we use snake_case keys here.
    """
    if not board_data:
        return "clean"
    modes = board_data.get("agent_memory_modes") or []
    for entry in modes:
        if entry.get("agent_name") == agent_name:
            return entry.get("mode", "clean")
    return "clean"


def resolve_board_workspace(
    board_name: str,
    agent_name: str,
    mode: str = "clean",
) -> Path:
    """Resolve and initialize the board-scoped memory workspace for an agent.

    Creates the directory structure idempotently and sets up memory files
    according to the requested mode.

    Args:
        board_name: The board's slug name.
        agent_name: The agent's name.
        mode: "clean" (default) or "with_history".

    Returns:
        Path to ~/.nanobot/boards/{board_name}/agents/{agent_name}/
    """
    board_workspace = (
        Path.home() / ".nanobot" / "boards" / board_name / "agents" / agent_name
    )
    memory_dir = board_workspace / "memory"
    sessions_dir = board_workspace / "sessions"
    memory_dir.mkdir(parents=True, exist_ok=True)
    sessions_dir.mkdir(parents=True, exist_ok=True)

    if mode == "with_history":
        _setup_with_history(memory_dir, agent_name, board_name)
    else:
        _setup_clean(memory_dir, agent_name, board_name)

    return board_workspace


def _setup_with_history(memory_dir: Path, agent_name: str, board_name: str) -> None:
    """Set up with_history mode: symlink board files to global agent memory."""
    global_memory_dir = Path.home() / ".nanobot" / "agents" / agent_name / "memory"
    global_memory_dir.mkdir(parents=True, exist_ok=True)

    for fname in ("MEMORY.md", "HISTORY.md"):
        global_file = global_memory_dir / fname
        board_file = memory_dir / fname

        # Ensure global file exists
        if not global_file.exists():
            global_file.write_text("", encoding="utf-8")

        # Replace regular file or stale symlink with correct symlink
        if board_file.is_symlink():
            try:
                if board_file.resolve() == global_file.resolve():
                    continue  # Already correct
            except OSError:
                pass  # Broken symlink -- remove and recreate
            board_file.unlink()
        elif board_file.exists():
            board_file.unlink()

        try:
            os.symlink(global_file, board_file)
        except FileExistsError:
            # Race condition: another task created the symlink concurrently
            pass

    logger.info(
        "[board_utils] Set up with_history symlinks for agent '%s' on board '%s'",
        agent_name, board_name,
    )


def _setup_clean(memory_dir: Path, agent_name: str, board_name: str) -> None:
    """Set up clean mode: board gets its own copy of memory files."""
    memory_md = memory_dir / "MEMORY.md"

    # If a symlink exists from a previous with_history run, remove it
    if memory_md.is_symlink():
        memory_md.unlink()

    if not memory_md.exists():
        global_memory = (
            Path.home() / ".nanobot" / "agents" / agent_name / "memory" / "MEMORY.md"
        )
        if global_memory.exists() and not global_memory.is_symlink():
            shutil.copy2(global_memory, memory_md)
            logger.info(
                "[board_utils] Bootstrapped board-scoped MEMORY.md for agent '%s' on board '%s'",
                agent_name, board_name,
            )
        elif global_memory.is_symlink() and global_memory.exists():
            # Global is itself a symlink but resolves -- read and write content
            shutil.copy2(global_memory, memory_md)
            logger.info(
                "[board_utils] Bootstrapped board-scoped MEMORY.md for agent '%s' on board '%s'",
                agent_name, board_name,
            )
        else:
            memory_md.write_text("", encoding="utf-8")
            logger.info(
                "[board_utils] Created empty board-scoped MEMORY.md for agent '%s' on board '%s'",
                agent_name, board_name,
            )

    history_md = memory_dir / "HISTORY.md"

    # If a symlink exists from a previous with_history run, remove it
    if history_md.is_symlink():
        history_md.unlink()

    # HISTORY.md always starts empty per board in clean mode
    if not history_md.exists():
        history_md.write_text("", encoding="utf-8")
