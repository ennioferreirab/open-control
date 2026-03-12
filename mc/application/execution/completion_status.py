"""Canonical helpers for task completion status decisions."""

from __future__ import annotations

from typing import Any

from mc.types import TaskStatus


def resolve_completion_status(task_data: dict[str, Any] | None) -> TaskStatus:
    """Cron-triggered runs should finish directly in done."""
    if not isinstance(task_data, dict):
        return TaskStatus.REVIEW
    if task_data.get("active_cron_job_id") or task_data.get("activeCronJobId"):
        return TaskStatus.DONE
    return TaskStatus.REVIEW
