"""
Task state machine — validates transitions and maps to activity event types.

This mirrors the Convex-side validation in dashboard/convex/tasks.ts.
The Convex side is authoritative; this module is for bridge-side pre-validation.
"""

from __future__ import annotations

from nanobot.mc.types import TaskStatus, ActivityEventType

# Valid transitions: current_status -> [allowed_next_statuses]
VALID_TRANSITIONS: dict[str, list[str]] = {
    TaskStatus.PLANNING: [TaskStatus.FAILED, TaskStatus.REVIEWING_PLAN],
    # reviewing_plan -> in_progress is handled by the approveAndKickOff Convex mutation.
    # reviewing_plan -> failed covers post-kickoff materialization failure.
    TaskStatus.REVIEWING_PLAN: [TaskStatus.IN_PROGRESS, TaskStatus.PLANNING, TaskStatus.FAILED],
    TaskStatus.INBOX: [TaskStatus.ASSIGNED],
    TaskStatus.ASSIGNED: [TaskStatus.IN_PROGRESS],
    TaskStatus.IN_PROGRESS: [TaskStatus.REVIEW, TaskStatus.DONE],
    TaskStatus.REVIEW: [TaskStatus.DONE, TaskStatus.INBOX],
    TaskStatus.RETRYING: [TaskStatus.IN_PROGRESS, TaskStatus.CRASHED],
    TaskStatus.CRASHED: [TaskStatus.INBOX],
}

# These target statuses are allowed from ANY source state
UNIVERSAL_TARGETS: set[str] = {TaskStatus.RETRYING, TaskStatus.CRASHED}

# Map (from, to) -> activity event type
TRANSITION_EVENT_MAP: dict[tuple[str, str], str] = {
    (TaskStatus.PLANNING, TaskStatus.REVIEWING_PLAN): ActivityEventType.TASK_PLANNING,
    (TaskStatus.PLANNING, TaskStatus.FAILED): ActivityEventType.TASK_FAILED,
    (TaskStatus.REVIEWING_PLAN, TaskStatus.PLANNING): ActivityEventType.TASK_PLANNING,
    (TaskStatus.REVIEWING_PLAN, TaskStatus.IN_PROGRESS): ActivityEventType.TASK_STARTED,
    (TaskStatus.REVIEWING_PLAN, TaskStatus.FAILED): ActivityEventType.TASK_FAILED,
    (TaskStatus.INBOX, TaskStatus.ASSIGNED): ActivityEventType.TASK_ASSIGNED,
    (TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS): ActivityEventType.TASK_STARTED,
    (TaskStatus.IN_PROGRESS, TaskStatus.REVIEW): ActivityEventType.REVIEW_REQUESTED,
    (TaskStatus.IN_PROGRESS, TaskStatus.DONE): ActivityEventType.TASK_COMPLETED,
    (TaskStatus.REVIEW, TaskStatus.DONE): ActivityEventType.TASK_COMPLETED,
    (TaskStatus.REVIEW, TaskStatus.INBOX): ActivityEventType.TASK_RETRYING,
    (TaskStatus.RETRYING, TaskStatus.IN_PROGRESS): ActivityEventType.TASK_RETRYING,
    (TaskStatus.RETRYING, TaskStatus.CRASHED): ActivityEventType.TASK_CRASHED,
    (TaskStatus.CRASHED, TaskStatus.INBOX): ActivityEventType.TASK_RETRYING,
}


def is_valid_transition(current_status: str, new_status: str) -> bool:
    """Check if a state transition is valid."""
    if new_status in UNIVERSAL_TARGETS:
        return True
    allowed = VALID_TRANSITIONS.get(current_status, [])
    return new_status in allowed


def validate_transition(current_status: str, new_status: str) -> None:
    """Validate a state transition. Raises ValueError if invalid."""
    if not is_valid_transition(current_status, new_status):
        raise ValueError(
            f"Cannot transition from '{current_status}' to '{new_status}'"
        )


def get_event_type(current_status: str, new_status: str) -> str:
    """Get the activity event type for a transition."""
    if new_status == TaskStatus.RETRYING:
        return ActivityEventType.TASK_RETRYING
    if new_status == TaskStatus.CRASHED:
        return ActivityEventType.TASK_CRASHED
    event_type = TRANSITION_EVENT_MAP.get((current_status, new_status))
    if event_type is None:
        raise ValueError(
            f"No event type mapping for transition '{current_status}' -> '{new_status}'"
        )
    return event_type
