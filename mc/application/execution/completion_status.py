"""Canonical helpers for task completion status decisions."""

from __future__ import annotations

from typing import Any

from mc.types import ReviewPhase, TaskStatus


def resolve_completion_status(task_data: dict[str, Any] | None) -> TaskStatus:
    """Cron-triggered runs should finish directly in done."""
    if not isinstance(task_data, dict):
        return TaskStatus.REVIEW
    if task_data.get("active_cron_job_id") or task_data.get("activeCronJobId"):
        return TaskStatus.DONE
    return TaskStatus.REVIEW


def resolve_completion_review_phase(task_data: dict[str, Any] | None) -> ReviewPhase | None:
    """Review completions should enter final approval explicitly."""
    if resolve_completion_status(task_data) != TaskStatus.REVIEW:
        return None
    return ReviewPhase.FINAL_APPROVAL
