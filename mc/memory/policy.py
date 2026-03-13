"""File contract for agent memory directories."""

from __future__ import annotations

from pathlib import Path

_PRIMARY_MARKDOWN = {"MEMORY.md", "HISTORY.md", "HISTORY_ARCHIVE.md"}
_SQLITE_FILES = {
    "memory-index.sqlite",
    "memory-index.sqlite-shm",
    "memory-index.sqlite-wal",
}
_LOCK_FILES = {
    ".memory.lock",
    ".consolidation.lock",
    "MEMORY.md.lock",
    "HISTORY.md.lock",
}


def is_memory_markdown_file(path: Path) -> bool:
    """Return True if the file is part of the supported markdown memory contract."""
    return path.name in _PRIMARY_MARKDOWN


def is_allowed_memory_file(path: Path) -> bool:
    """Return True if the file is expected inside the memory directory."""
    name = path.name
    if path.is_dir():
        return False
    if is_memory_markdown_file(path):
        return True
    return name in _SQLITE_FILES or name in _LOCK_FILES


def iter_memory_markdown_files(memory_dir: Path) -> list[Path]:
    """List markdown files that belong to the memory contract."""
    if not memory_dir.exists():
        return []
    return [path for path in sorted(memory_dir.glob("*.md")) if is_memory_markdown_file(path)]


def find_invalid_memory_files(memory_dir: Path) -> list[Path]:
    """List files present in the memory dir that are outside the allowed contract."""
    if not memory_dir.exists():
        return []
    invalid: list[Path] = []
    for path in sorted(memory_dir.iterdir()):
        if path.is_dir():
            invalid.append(path)
            continue
        if not is_allowed_memory_file(path):
            invalid.append(path)
    return invalid
