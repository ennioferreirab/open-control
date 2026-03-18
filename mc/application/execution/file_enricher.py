"""File manifest and workspace enrichment.

Extracts the duplicated file manifest building logic from executor.py
and step_dispatcher.py into a single shared module.
"""

from __future__ import annotations

import asyncio
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


def _build_file_summary(files: list[dict]) -> str:
    """Build a human-readable file summary for agent context."""
    if not files:
        return ""
    total = sum(f.get("size", 0) for f in files)
    names = ", ".join(
        f"{f['name']} ({f.get('type', 'application/octet-stream')}, {_human_size(f.get('size', 0))})"
        for f in files
    )
    return (
        f"Task has {len(files)} attached file(s) (total {_human_size(total)}): {names}. "
        f"Consider file types when selecting the best agent."
    )


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


def resolve_thread_journal_paths(task_id: str) -> tuple[str, str]:
    """Resolve task-scoped thread journal and compaction-state file paths."""
    _, output_dir = resolve_task_dirs(task_id)
    output_path = Path(output_dir)
    return (
        str(output_path / "THREAD_JOURNAL.md"),
        str(output_path / "THREAD_COMPACTION_STATE.json"),
    )


def build_file_context(
    file_manifest: list[dict[str, Any]],
    files_dir: str,
    output_dir: str,
    *,
    memory_dir: str | None = None,
    artifacts_dir: str | None = None,
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
                f"{f['name']} ({f['subfolder']}, {_human_size(f['size'])})" for f in file_manifest
            )
            desc += (
                f"\n\nTask has {len(file_manifest)} file(s) in its manifest. "
                f"File manifest: {manifest_summary}\n"
                f"Review the file manifest before starting work."
            )

        # Inject file routing context
        if raw_files:
            file_routing_summary = _build_file_summary(raw_files)
            if file_routing_summary:
                delegation_summary = file_routing_summary.replace(
                    "Consider file types when selecting the best agent.",
                    f"Files available at: {files_dir}/attachments",
                )
                desc += f"\n\n{delegation_summary}"

        guidance_lines: list[str] = []
        if memory_dir:
            guidance_lines.append(
                f"Store long-term facts and consolidated history in: {memory_dir}"
            )
        if artifacts_dir:
            guidance_lines.append(f"Store reusable board artifacts in: {artifacts_dir}")
        guidance_lines.append(f"Save task deliverables to: {output_dir}")
        desc += "\n\n[Persistence Rules]\n" + "\n".join(guidance_lines)

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
                f"{f['name']} ({f['subfolder']}, {_human_size(f['size'])})" for f in file_manifest
            )
            task_instruction += (
                f"\nTask has {len(file_manifest)} attached file(s) "
                f"at {files_dir}/attachments. "
                f"File manifest: {manifest_summary}"
            )
        guidance_lines: list[str] = []
        if memory_dir:
            guidance_lines.append(
                f"Store long-term facts and consolidated history in: {memory_dir}"
            )
        if artifacts_dir:
            guidance_lines.append(f"Store reusable board artifacts in: {artifacts_dir}")
        guidance_lines.append(f"Save task deliverables to: {output_dir}")
        task_instruction += "\n\n[Persistence Rules]\n" + "\n".join(guidance_lines)
        parts.append(task_instruction)

    return "\n".join(parts)


def build_absolute_file_path(task_id: str, subfolder: str, name: str) -> str:
    """Return absolute path for a task file entry."""
    safe_id = task_safe_id(task_id)
    return str(Path.home() / ".nanobot" / "tasks" / safe_id / subfolder / name)


def absolutize_artifact_path(task_id: str, path: str) -> str:
    """Resolve a task-relative artifact path into an absolute filesystem path."""
    safe_id = task_safe_id(task_id)
    normalized = path.lstrip("/")
    return str(Path.home() / ".nanobot" / "tasks" / safe_id / normalized)


def _read_merge_field(task_data: dict[str, Any], snake_case: str, camel_case: str) -> Any:
    """Read a merge-related field from either snake_case or camelCase task data."""
    return task_data.get(snake_case, task_data.get(camel_case))


def _default_merge_label(index: int) -> str:
    """Return spreadsheet-style labels: A, B, ..., Z, AA, AB, ..."""
    value = index
    label = ""
    while True:
        label = chr(ord("A") + (value % 26)) + label
        value = value // 26 - 1
        if value < 0:
            return label


async def load_merged_source_payloads(
    bridge: Any,
    task_data: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Fetch source task payloads for a merged task."""
    if not task_data:
        return []

    is_merge_task = _read_merge_field(task_data, "is_merge_task", "isMergeTask") is True
    source_task_ids = (
        _read_merge_field(
            task_data,
            "merge_source_task_ids",
            "mergeSourceTaskIds",
        )
        or []
    )
    source_labels = (
        _read_merge_field(
            task_data,
            "merge_source_labels",
            "mergeSourceLabels",
        )
        or []
    )

    if not is_merge_task or not isinstance(source_task_ids, list) or not source_task_ids:
        return []

    async def _load_source(
        index: int,
        task_id: str,
        seen: set[str],
        labels: list[str],
        parent_label: str | None = None,
    ) -> list[dict[str, Any]]:
        if task_id in seen:
            return []

        source_task = await asyncio.to_thread(
            bridge.query,
            "tasks:getById",
            {"task_id": task_id},
        )
        if not isinstance(source_task, dict):
            return []

        seen.add(task_id)
        base_label = labels[index] if index < len(labels) else _default_merge_label(index)
        label = f"{parent_label}.{base_label}" if parent_label else base_label

        source_messages = await asyncio.to_thread(bridge.get_task_messages, task_id)
        payload = {
            "label": label,
            "task_id": task_id,
            "task_data": source_task,
            "messages": source_messages if isinstance(source_messages, list) else [],
        }

        resolved = [payload]
        nested_source_ids = (
            _read_merge_field(
                source_task,
                "merge_source_task_ids",
                "mergeSourceTaskIds",
            )
            or []
        )
        nested_source_labels = (
            _read_merge_field(
                source_task,
                "merge_source_labels",
                "mergeSourceLabels",
            )
            or []
        )
        nested_is_merge = (
            _read_merge_field(
                source_task,
                "is_merge_task",
                "isMergeTask",
            )
            is True
        )

        if nested_is_merge and isinstance(nested_source_ids, list) and nested_source_ids:
            for nested_index, nested_task_id in enumerate(nested_source_ids):
                resolved.extend(
                    await _load_source(
                        nested_index,
                        nested_task_id,
                        seen,
                        nested_source_labels,
                        label,
                    )
                )

        return resolved

    seen: set[str] = set()
    payloads: list[dict[str, Any]] = []
    for index, task_id in enumerate(source_task_ids):
        payloads.extend(await _load_source(index, task_id, seen, source_labels))
    return payloads


def build_merged_source_context(source_payloads: list[dict[str, Any]]) -> str:
    """Build source-task metadata, file refs, and source thread sections."""
    if not source_payloads:
        return ""

    from mc.application.execution.thread_context import ThreadContextBuilder

    builder = ThreadContextBuilder()
    sections: list[str] = ["[Merged Task Origins]"]

    for source in source_payloads:
        label = source.get("label", "?")
        task_id = source.get("task_id", "unknown")
        task_data = source.get("task_data") or {}
        title = task_data.get("title", f"Task {label}")
        status = task_data.get("status", "unknown")
        description = task_data.get("description")
        line = f"{label}: {title} [{status}]"
        if description:
            line += f" — {description}"
        sections.append(line)

        files = task_data.get("files") or []
        if files:
            file_lines = [f"[Source Task {label} Files]"]
            for file_data in files:
                name = file_data.get("name", "unknown")
                subfolder = file_data.get("subfolder", "attachments")
                absolute_path = build_absolute_file_path(task_id, subfolder, name)
                file_lines.append(f"- {name} ({subfolder}) — {absolute_path}")
            sections.append("\n".join(file_lines))

        messages = source.get("messages") or []
        if messages:
            thread_lines = [f"[Source Thread {label}]"]
            for message in messages[-10:]:
                normalized_message = dict(message)
                normalized_message["artifacts"] = [
                    {
                        **artifact,
                        "path": absolutize_artifact_path(task_id, artifact.get("path", "")),
                    }
                    for artifact in (message.get("artifacts") or [])
                ]
                thread_lines.append(builder._format_message(normalized_message))
            sections.append("\n".join(thread_lines))

    return "\n\n".join(sections)
