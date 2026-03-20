"""Artifact preparation and collection.

Extracts the output artifact snapshot/collection logic from executor.py
into a shared module used by both task and step execution paths.
"""

from __future__ import annotations

import logging
from typing import Any

from mc.infrastructure.runtime_home import get_tasks_dir
from mc.types import task_safe_id

logger = logging.getLogger(__name__)


def _human_size(b: int) -> str:
    """Convert a byte count to a human-readable size string."""
    if b < 1024 * 1024:
        return f"{b // 1024} KB"
    return f"{b / (1024 * 1024):.1f} MB"


def snapshot_output_dir(task_id: str) -> dict[str, float]:
    """Capture {relative_path: mtime} for all files in the task's output dir.

    The relative path is relative to the task base directory (two levels
    above the file), e.g. ``"output/report.pdf"``.

    Args:
        task_id: Convex task ID.

    Returns:
        Dict mapping relative paths to modification times.
    """
    safe_id = task_safe_id(task_id)
    output_dir = get_tasks_dir() / safe_id / "output"
    snapshot: dict[str, float] = {}
    if output_dir.exists():
        for entry in output_dir.rglob("*"):
            if entry.is_file():
                rel = str(entry.relative_to(output_dir.parent))
                snapshot[rel] = entry.stat().st_mtime
    return snapshot


def collect_output_artifacts(
    task_id: str,
    pre_snapshot: dict[str, float] | None,
) -> list[dict[str, Any]]:
    """Compare post-execution output dir against pre-snapshot to detect artifacts.

    Returns a list of artifact dicts describing files that were created
    or modified during agent execution.

    Args:
        task_id: Convex task ID.
        pre_snapshot: Output from snapshot_output_dir() before execution.

    Returns:
        List of artifact dicts with path, action, and description/diff.
    """
    safe_id = task_safe_id(task_id)
    output_dir = get_tasks_dir() / safe_id / "output"
    artifacts: list[dict[str, Any]] = []
    pre = pre_snapshot or {}

    if not output_dir.exists():
        return artifacts

    for entry in output_dir.rglob("*"):
        if not entry.is_file():
            continue
        rel = str(entry.relative_to(output_dir.parent))
        size = entry.stat().st_size

        if rel not in pre:
            ext = entry.suffix.lstrip(".").upper() or "file"
            artifacts.append(
                {
                    "path": rel,
                    "action": "created",
                    "description": f"{ext}, {_human_size(size)}",
                }
            )
        elif entry.stat().st_mtime > pre[rel]:
            artifacts.append(
                {
                    "path": rel,
                    "action": "modified",
                    "diff": f"File updated ({_human_size(size)})",
                }
            )

    return artifacts
