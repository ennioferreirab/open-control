"""Filesystem helpers for persistent board-scoped artifacts."""

from __future__ import annotations

from pathlib import Path

from mc.infrastructure.runtime_home import get_runtime_home


def resolve_board_artifacts_workspace(
    board_name: str,
    *,
    root: Path | None = None,
) -> Path:
    """Return the canonical persistent artifact directory for a board."""
    base_root = root if root is not None else get_runtime_home()
    artifacts_dir = base_root / "boards" / board_name / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir
