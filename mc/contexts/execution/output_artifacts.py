"""Helpers for task output artifact detection and memory relocation."""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Any

from mc.infrastructure.runtime_home import get_tasks_dir
from mc.types import task_safe_id

logger = logging.getLogger(__name__)


def slugify(text: str, max_len: int = 40) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = re.sub(r"[^\w\-]", "_", text.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug[:max_len] if slug else "unknown"


def _human_size(b: int) -> str:
    """Convert a byte count to a human-readable size string."""
    if b < 1024 * 1024:
        return f"{b // 1024} KB"
    return f"{b / (1024 * 1024):.1f} MB"


def _snapshot_output_dir(task_id: str) -> dict[str, float]:
    """Capture {relative_path: mtime} for all files in the task's output dir."""
    safe_id = task_safe_id(task_id)
    output_dir = get_tasks_dir() / safe_id / "output"
    snapshot: dict[str, float] = {}
    if output_dir.exists():
        for entry in output_dir.rglob("*"):
            if entry.is_file():
                rel = str(entry.relative_to(output_dir.parent))
                snapshot[rel] = entry.stat().st_mtime
    return snapshot


def _collect_output_artifacts(
    task_id: str,
    pre_snapshot: dict[str, float] | None,
) -> list[dict[str, Any]]:
    """Compare post-execution output dir against pre-snapshot to detect artifacts."""
    safe_id = task_safe_id(task_id)
    output_dir = get_tasks_dir() / safe_id / "output"
    artifacts: list[dict[str, Any]] = []
    pre = pre_snapshot or {}

    if not output_dir.exists():
        return artifacts

    for entry in output_dir.rglob("*"):
        if not entry.is_file():
            continue

        # Prompt logs are diagnostic files — show in Files tab only, not as
        # thread artifacts.
        if entry.name.startswith("system_prompt_"):
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


def _relocate_invalid_memory_files(task_id: str, workspace: Path) -> list[Path]:
    """Move memory contract violations into the task output directory."""
    from mc.memory import find_invalid_memory_files
    from mc.memory.index import MemoryIndex

    memory_dir = workspace / "memory"
    invalid_paths = find_invalid_memory_files(memory_dir)
    if not invalid_paths:
        return []

    safe_id = task_safe_id(task_id)
    output_dir = get_tasks_dir() / safe_id / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    moved: list[Path] = []

    def _unique_path(base_name: str) -> Path:
        candidate = output_dir / base_name
        if not candidate.exists():
            return candidate
        stem = candidate.stem
        suffix = candidate.suffix
        idx = 2
        while True:
            candidate = output_dir / f"{stem}-{idx}{suffix}"
            if not candidate.exists():
                return candidate
            idx += 1

    for path in invalid_paths:
        if path.is_dir() and not path.is_symlink():
            archive_base = _unique_path(f"memory-relocated-{path.name}").with_suffix("")
            archive_file = Path(
                shutil.make_archive(
                    str(archive_base),
                    "zip",
                    root_dir=path.parent,
                    base_dir=path.name,
                )
            )
            shutil.rmtree(path)
            moved.append(archive_file)
            logger.warning(
                "[executor] Archived invalid memory directory '%s' to '%s'",
                path,
                archive_file,
            )
            continue

        target = _unique_path(f"memory-relocated-{path.name}")
        shutil.move(str(path), str(target))
        moved.append(target)
        logger.warning(
            "[executor] Relocated invalid memory file '%s' to '%s'",
            path,
            target,
        )

    if memory_dir.exists():
        MemoryIndex(memory_dir).sync()

    return moved


def write_prompt_log(
    task_id: str,
    filename: str,
    content: str,
    *,
    step_id: str | None = None,
) -> None:
    """Write a prompt log file to the task's output directory."""
    from datetime import datetime as _dt

    safe_id = task_safe_id(task_id)
    output_dir = get_tasks_dir() / safe_id / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = _dt.now().strftime("%d:%H:%M:%S")
    final_name = filename.replace("{DDHHMMSS}", ts)
    if step_id:
        stem, dot, ext = final_name.rpartition(".")
        suffix = f"_{step_id[-6:]}"
        final_name = f"{stem}{suffix}{dot}{ext}" if dot else f"{final_name}{suffix}"
    path = output_dir / final_name
    path.write_text(content, encoding="utf-8")
    logger.info("[prompt-log] Wrote %s (%d bytes)", path, len(content))
