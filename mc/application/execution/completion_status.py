"""Canonical helpers for task completion status decisions."""

from __future__ import annotations

from mc.types import TaskStatus


def resolve_completion_status() -> TaskStatus:
    """All completed tasks go directly to done.

    Review is driven by workflow-level review steps (workflowStepType="review"),
    not forced on every task at completion time.
    """
    return TaskStatus.DONE
