"""Output enrichment, artifact handling, and agent execution helpers.

Extracted from executor.py to keep module sizes manageable.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mc.types import (
    task_safe_id,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _human_size(b: int) -> str:
    """Convert a byte count to a human-readable size string."""
    if b < 1024 * 1024:
        return f"{b // 1024} KB"
    return f"{b / (1024 * 1024):.1f} MB"


def _snapshot_output_dir(task_id: str) -> dict[str, float]:
    """Capture {relative_path: mtime} for all files in the task's output dir.

    The relative path is relative to the task base directory (two levels above
    the file), e.g. ``"output/report.pdf"`` for a file stored in
    ``~/.nanobot/tasks/{safe_id}/output/report.pdf``.
    """
    safe_id = task_safe_id(task_id)
    output_dir = Path.home() / ".nanobot" / "tasks" / safe_id / "output"
    snapshot: dict[str, float] = {}
    if output_dir.exists():
        for entry in output_dir.rglob("*"):
            if entry.is_file():
                # relative to task base dir (one level above output/)
                rel = str(entry.relative_to(output_dir.parent))
                snapshot[rel] = entry.stat().st_mtime
    return snapshot


def _collect_output_artifacts(
    task_id: str,
    pre_snapshot: dict[str, float] | None,
) -> list[dict[str, Any]]:
    """Compare post-execution output dir against pre-snapshot to detect artifacts.

    Returns a list of artifact dicts (Convex-compatible) describing files
    that were created or modified during agent execution.

    Each dict has keys: ``path``, ``action``, and optionally ``description``
    (for created files) or ``diff`` (for modified files).

    The ``path`` is relative to the task base directory (e.g., ``"output/report.pdf"``).
    """
    safe_id = task_safe_id(task_id)
    output_dir = Path.home() / ".nanobot" / "tasks" / safe_id / "output"
    artifacts: list[dict[str, Any]] = []
    pre = pre_snapshot or {}

    if not output_dir.exists():
        return artifacts

    for entry in output_dir.rglob("*"):
        if not entry.is_file():
            continue
        # relative to task base dir (parent of output/)
        rel = str(entry.relative_to(output_dir.parent))
        size = entry.stat().st_size

        if rel not in pre:
            # New file — created
            ext = entry.suffix.lstrip(".").upper() or "file"
            artifacts.append(
                {
                    "path": rel,
                    "action": "created",
                    "description": f"{ext}, {_human_size(size)}",
                }
            )
        elif entry.stat().st_mtime > pre[rel]:
            # Existing file with newer mtime — modified
            artifacts.append(
                {
                    "path": rel,
                    "action": "modified",
                    "diff": f"File updated ({_human_size(size)})",
                }
            )

    return artifacts


def _relocate_invalid_memory_files(task_id: str, workspace: Path) -> list[Path]:
    """Move memory contract violations into the task output directory.

    Files are relocated to `output/` with a `memory-relocated-` prefix so they
    show up in the normal artifact pipeline. Directories are archived as zip
    files for the same reason.
    """
    from mc.memory import find_invalid_memory_files
    from mc.memory.index import MemoryIndex

    memory_dir = workspace / "memory"
    invalid_paths = find_invalid_memory_files(memory_dir)
    if not invalid_paths:
        return []

    safe_id = task_safe_id(task_id)
    output_dir = Path.home() / ".nanobot" / "tasks" / safe_id / "output"
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


def _build_thread_context(messages: list[dict[str, Any]], max_messages: int = 20) -> str:
    """Format thread messages as conversation context for the agent.

    Thin shim that delegates to ThreadContextBuilder for backward compatibility.
    Preserves legacy behavior: returns empty string if no user messages exist.

    For step-aware context with predecessor injection, use ThreadContextBuilder
    directly with predecessor_step_ids parameter.
    """
    from mc.application.execution.thread_context import ThreadContextBuilder

    return ThreadContextBuilder().build(messages, max_messages=max_messages)


def _build_tag_attributes_context(
    tags: list[str],
    attr_values: list[dict[str, Any]],
    attr_catalog: list[dict[str, Any]],
) -> str:
    """Build a context section describing tag attribute values for the agent.

    Args:
        tags: List of tag name strings assigned to the task.
        attr_values: List of tagAttributeValue records (snake_case keys from bridge).
        attr_catalog: List of tagAttribute records (snake_case keys from bridge).

    Returns:
        A formatted string section like:
        [Task Tag Attributes]
        client-tag: priority=high, deadline=2026-03-01
        ...
        Returns empty string if no tags have non-empty attribute values.
    """
    if not tags or not attr_values or not attr_catalog:
        return ""

    # Build attribute id -> name lookup
    attr_name_map: dict[str, str] = {}
    for attr in attr_catalog:
        attr_id = attr.get("id") or attr.get("_id") or ""
        attr_name = attr.get("name", "")
        if attr_id and attr_name:
            attr_name_map[attr_id] = attr_name

    # Group values by tag name
    tag_attrs: dict[str, list[str]] = {}
    for val in attr_values:
        tag_name = val.get("tag_name", "")
        value = val.get("value", "")
        attr_id = val.get("attribute_id") or val.get("_attribute_id") or ""

        # Skip empty values
        if not tag_name or not value or tag_name not in tags:
            continue

        attr_name = attr_name_map.get(attr_id, "")
        if not attr_name:
            continue

        if tag_name not in tag_attrs:
            tag_attrs[tag_name] = []
        tag_attrs[tag_name].append(f"{attr_name}={value}")

    if not tag_attrs:
        return ""

    lines = ["[Task Tag Attributes]"]
    for tag_name in tags:
        if tag_name in tag_attrs:
            pairs = ", ".join(tag_attrs[tag_name])
            lines.append(f"{tag_name}: {pairs}")

    return "\n".join(lines)


def _collect_provider_error_types() -> tuple[type[Exception], ...]:
    """Collect provider-specific exception types for targeted catching.

    Returns a tuple of exception classes that represent provider/OAuth
    errors (as opposed to agent runtime errors). These are caught
    separately in _execute_task so they get surfaced with actionable
    instructions instead of being buried in generic crash handling.
    """
    from mc.infrastructure.providers.factory import ProviderError

    types: list[type[Exception]] = [ProviderError]
    try:
        from nanobot.providers.anthropic_oauth import AnthropicOAuthExpired

        types.append(AnthropicOAuthExpired)
    except ImportError:
        pass
    return tuple(types)


_PROVIDER_ERRORS = _collect_provider_error_types()


def _provider_error_action(exc: Exception) -> str:
    """Extract a user-facing action string from a provider error.

    For ProviderError the action is explicit. For AnthropicOAuthExpired
    the message itself contains the command. Falls back to a generic hint.
    """
    from mc.infrastructure.providers.factory import ProviderError

    if isinstance(exc, ProviderError) and exc.action:
        return exc.action
    # AnthropicOAuthExpired messages include "Run: nanobot provider login ..."
    msg = str(exc)
    if "Run:" in msg:
        return msg[msg.index("Run:") :]
    return "Check provider configuration in ~/.nanobot/config.json"


def _make_provider(model: str | None = None):
    """Create the LLM provider from the user's nanobot config.

    Delegates to the shared provider_factory.create_provider() to avoid
    duplication with nanobot/cli/commands.py.
    """
    from mc.infrastructure.providers.factory import create_provider

    return create_provider(model)


def build_task_message(title: str, description: str | None) -> str:
    """Build the task message sent to the agent.

    When a description exists, uses structured XML tags so the agent
    can distinguish title from description. Otherwise, plain title
    for backward compatibility.
    """
    if description and description.strip():
        return f"<title>{title}</title>\n<description>{description}</description>"
    return title


def _get_iana_timezone() -> str | None:
    """Resolve IANA timezone name from system (e.g. 'America/Vancouver')."""
    from mc.infrastructure.orientation_helpers import get_iana_timezone

    return get_iana_timezone()


def build_executor_agent_roster() -> str:
    """Build a roster of available agents for injection into executor orientation.

    Reads ~/.nanobot/agents/*/config.yaml, excludes system agents and lead-agent.
    Returns formatted list for agent orientation interpolation.
    """
    from mc.infrastructure.orientation_helpers import build_agent_roster

    return build_agent_roster()


async def _enrich_nanobot_description(
    bridge: Any,
    task_id: str,
    title: str,
    description: str | None,
    task_data: dict | None,
) -> str:
    """Enrich nanobot task description with file manifest, thread context, and tag attributes.

    Uses local helper functions and execution runtime adapters
    (Story 20.1 cleanup).
    """
    import asyncio

    from mc.application.execution.runtime import (
        build_tag_attributes_context,
        build_thread_context,
    )

    description = description or ""
    safe_id = task_safe_id(task_id)
    files_dir = str(Path.home() / ".nanobot" / "tasks" / safe_id)
    try:
        fresh_task = await asyncio.to_thread(bridge.query, "tasks:getById", {"task_id": task_id})
        raw_files = (fresh_task or {}).get("files") or []
    except Exception:
        logger.warning(
            "[executor] Failed to fetch fresh task data for '%s', using snapshot",
            title,
        )
        raw_files = (task_data or {}).get("files") or []
    file_manifest = [
        {
            "name": f.get("name", "unknown"),
            "type": f.get("type", "application/octet-stream"),
            "size": f.get("size", 0),
            "subfolder": f.get("subfolder", "attachments"),
        }
        for f in raw_files
    ]
    output_dir = str(Path.home() / ".nanobot" / "tasks" / safe_id / "output")
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
            f"\nTask has {len(file_manifest)} attached file(s) at "
            f"{files_dir}/attachments. File manifest: {manifest_summary}"
        )
    description = (description or "") + f"\n\n{task_instruction}"
    try:
        thread_messages = await asyncio.to_thread(bridge.get_task_messages, task_id)
        thread_context = build_thread_context(thread_messages)
        if thread_context:
            description = (description or "") + f"\n{thread_context}"
    except Exception:
        logger.warning(
            "[executor] Failed to fetch thread messages for '%s'",
            title,
            exc_info=True,
        )
    try:
        task_tags = (task_data or {}).get("tags") or []
        if task_tags:
            tag_attr_values = await asyncio.to_thread(
                bridge.query, "tagAttributeValues:getByTask", {"task_id": task_id}
            )
            tag_attr_catalog = await asyncio.to_thread(bridge.query, "tagAttributes:list", {})
            tag_attrs_context = build_tag_attributes_context(
                task_tags,
                tag_attr_values if isinstance(tag_attr_values, list) else [],
                tag_attr_catalog if isinstance(tag_attr_catalog, list) else [],
            )
            if tag_attrs_context:
                description = (description or "") + f"\n\n{tag_attrs_context}"
    except Exception:
        logger.warning(
            "[executor] Failed to fetch tag attributes for '%s'",
            title,
            exc_info=True,
        )
    return description
