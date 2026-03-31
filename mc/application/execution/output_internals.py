"""Helpers for classifying runtime-internal files under task output."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_INTERNAL_OUTPUT_PREFIX = ".internal/"
_TASK_INTERNAL_OUTPUT_PREFIX = "output/.internal/"


def _normalize_rel_path(path: str) -> str:
    """Normalize a relative task/output path for prefix checks."""
    return path.replace("\\", "/").lstrip("/")


def is_internal_output_relative_path(path: str) -> bool:
    """Return whether an output-relative path lives under `.internal/`."""
    normalized = _normalize_rel_path(path)
    return normalized == ".internal" or normalized.startswith(_INTERNAL_OUTPUT_PREFIX)


def is_internal_output_task_path(path: str) -> bool:
    """Return whether a task-relative artifact path lives under `output/.internal/`."""
    normalized = _normalize_rel_path(path)
    return normalized == "output/.internal" or normalized.startswith(_TASK_INTERNAL_OUTPUT_PREFIX)


def is_internal_output_file(file_entry: Mapping[str, Any]) -> bool:
    """Return whether a task file manifest entry is a runtime-internal output file."""
    return str(file_entry.get("subfolder") or "") == "output" and is_internal_output_relative_path(
        str(file_entry.get("name") or "")
    )
