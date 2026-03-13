"""Stable runtime adapters for execution internals.

These helpers isolate the rest of the runtime from the legacy executor
implementation while preserving the current behavior and test seams.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def snapshot_output_dir(task_id: str) -> dict[str, float]:
    """Capture the output directory snapshot for later artifact detection."""
    from mc.contexts.execution.executor import _snapshot_output_dir

    return _snapshot_output_dir(task_id)


def collect_output_artifacts(
    task_id: str,
    pre_snapshot: dict[str, float] | None,
) -> list[dict[str, Any]]:
    """Collect created/updated artifacts relative to the task output dir."""
    from mc.contexts.execution.executor import _collect_output_artifacts

    return _collect_output_artifacts(task_id, pre_snapshot)


def relocate_invalid_memory_files(task_id: str, workspace: Path) -> list[Path]:
    """Move invalid memory files out of the workspace and into task output."""
    from mc.contexts.execution.executor import _relocate_invalid_memory_files

    return _relocate_invalid_memory_files(task_id, workspace)


def build_thread_context(messages: list[dict[str, Any]], max_messages: int = 20) -> str:
    """Render thread history into execution context text."""
    from mc.contexts.execution.executor import _build_thread_context

    return _build_thread_context(messages, max_messages=max_messages)


def build_tag_attributes_context(
    tags: list[str],
    attr_values: list[dict[str, Any]],
    attr_catalog: list[dict[str, Any]],
) -> str:
    """Render tag attributes into execution context text."""
    from mc.contexts.execution.executor import _build_tag_attributes_context

    return _build_tag_attributes_context(tags, attr_values, attr_catalog)


def provider_error_types() -> tuple[type[Exception], ...]:
    """Return the provider/OAuth exception types used by the runtime."""
    from mc.contexts.execution.executor import _PROVIDER_ERRORS

    return _PROVIDER_ERRORS


async def run_nanobot_task(
    *,
    agent_name: str,
    agent_prompt: str | None,
    agent_model: str | None,
    reasoning_level: str | None = None,
    task_title: str = "",
    task_description: str | None = None,
    agent_skills: list[str] | None = None,
    board_name: str | None = None,
    memory_workspace: Path | None = None,
    cron_service: Any | None = None,
    task_id: str | None = None,
    bridge: Any | None = None,
    ask_user_registry: Any | None = None,
    on_progress: Any | None = None,
) -> tuple[Any, str, Any]:
    """Delegate nanobot execution through the legacy helper during cutover."""
    from mc.contexts.execution.executor import _run_agent_on_task

    return await _run_agent_on_task(
        agent_name=agent_name,
        agent_prompt=agent_prompt,
        agent_model=agent_model,
        reasoning_level=reasoning_level,
        task_title=task_title,
        task_description=task_description,
        agent_skills=agent_skills,
        board_name=board_name,
        memory_workspace=memory_workspace,
        cron_service=cron_service,
        task_id=task_id,
        bridge=bridge,
        ask_user_registry=ask_user_registry,
        on_progress=on_progress,
    )
