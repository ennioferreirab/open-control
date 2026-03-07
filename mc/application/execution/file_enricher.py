"""File manifest and workspace enrichment.

Extracts the duplicated file manifest building logic from executor.py
and step_dispatcher.py into a single shared module.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from mc.types import task_safe_id

logger = logging.getLogger(__name__)


def _human_size(b: int) -> str:
    """Convert a byte count to a human-readable size string."""
    if b < 1024 * 1024:
        return f"{b // 1024} KB"
    return f"{b / (1024 * 1024):.1f} MB"


def build_file_manifest(raw_files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize raw file records into a manifest with consistent keys.

    Args:
        raw_files: Raw file dicts from Convex task data.

    Returns:
        List of normalized file manifest dicts with name, type, size, subfolder.
    """
    return [
        {
            "name": f.get("name", "unknown"),
            "type": f.get("type", "application/octet-stream"),
            "size": f.get("size", 0),
            "subfolder": f.get("subfolder", "attachments"),
        }
        for f in raw_files
    ]


def resolve_task_dirs(task_id: str) -> tuple[str, str]:
    """Resolve the task workspace and output directories.

    Args:
        task_id: The Convex task ID.

    Returns:
        Tuple of (files_dir, output_dir) as absolute path strings.
    """
    safe_id = task_safe_id(task_id)
    base = Path.home() / ".nanobot" / "tasks" / safe_id
    return str(base), str(base / "output")


def build_file_context(
    file_manifest: list[dict[str, Any]],
    files_dir: str,
    output_dir: str,
    *,
    is_step: bool = False,
    step_title: str = "",
    step_description: str = "",
    task_title: str = "",
    raw_files: list[dict[str, Any]] | None = None,
) -> str:
    """Build the file-related context string for agent injection.

    Assembles workspace instructions, file manifest, and file routing
    summary into a single context block.

    Args:
        file_manifest: Normalized file manifest.
        files_dir: Task workspace directory path.
        output_dir: Output directory path.
        is_step: True if building for a step (changes format).
        step_title: Step title (for step context).
        step_description: Step description (for step context).
        task_title: Parent task title (for step context).
        raw_files: Raw file dicts for routing context.

    Returns:
        Assembled file context string.
    """
    parts: list[str] = []

    if is_step:
        # Step format: execution description with step + task context
        desc = (
            f'You are executing step: "{step_title}"\n'
            f"Step description: {step_description}\n\n"
            f'This step is part of task: "{task_title}"\n'
            f"Task workspace: {files_dir}\n"
            f"Save ALL output files to: {output_dir}\n"
            "Do NOT save output files outside this directory."
        )

        # Inject task-level file manifest
        if file_manifest:
            manifest_summary = ", ".join(
                f"{f['name']} ({f['subfolder']}, {_human_size(f['size'])})"
                for f in file_manifest
            )
            desc += (
                f"\n\nTask has {len(file_manifest)} file(s) in its manifest. "
                f"File manifest: {manifest_summary}\n"
                f"Review the file manifest before starting work."
            )

        # Inject file routing context
        if raw_files:
            from mc.contexts.planning.planner import _build_file_summary

            file_routing_summary = _build_file_summary(raw_files)
            if file_routing_summary:
                delegation_summary = file_routing_summary.replace(
                    "Consider file types when selecting the best agent.",
                    f"Files available at: {files_dir}/attachments",
                )
                desc += f"\n\n{delegation_summary}"

        parts.append(desc)
    else:
        # Task format: workspace instructions
        task_instruction = (
            f"Task workspace: {files_dir}\n"
            f"Save ALL output files (reports, summaries, generated content) "
            f"to: {output_dir}\n"
            f"Do NOT save output files outside this directory."
        )
        if file_manifest:
            manifest_summary = ", ".join(
                f"{f['name']} ({f['subfolder']}, {_human_size(f['size'])})"
                for f in file_manifest
            )
            task_instruction += (
                f"\nTask has {len(file_manifest)} attached file(s) "
                f"at {files_dir}/attachments. "
                f"File manifest: {manifest_summary}"
            )
        parts.append(task_instruction)

    return "\n".join(parts)
