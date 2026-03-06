"""
Workflow contract adapter — loads the canonical workflow spec and exposes helpers.

The single source of truth is ``shared/workflow/workflow_spec.json``.
This module loads that file once at import time and provides Python-friendly
accessor functions used by the rest of the ``mc`` package.

Story 15.1 — Shared Workflow Contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Load spec once at import time
# ---------------------------------------------------------------------------

_SPEC_PATH = Path(__file__).resolve().parents[2] / "shared" / "workflow" / "workflow_spec.json"

with open(_SPEC_PATH, "r") as _f:
    SPEC: dict[str, Any] = json.load(_f)

# ---------------------------------------------------------------------------
# Derived constants
# ---------------------------------------------------------------------------

TASK_STATUSES: list[str] = SPEC["taskStatuses"]
STEP_STATUSES: list[str] = SPEC["stepStatuses"]

_TASK_TRANSITIONS: dict[str, list[str]] = SPEC["taskTransitions"]
_TASK_UNIVERSAL_TARGETS: list[str] = SPEC["taskUniversalTargets"]
_TASK_TRANSITION_EVENTS: dict[str, str] = SPEC["taskTransitionEvents"]
_TASK_UNIVERSAL_TARGET_EVENTS: dict[str, str] = SPEC["taskUniversalTargetEvents"]

_STEP_TRANSITIONS: dict[str, list[str]] = SPEC["stepTransitions"]
_STEP_TRANSITION_EVENTS: dict[str, str] = SPEC["stepTransitionEvents"]

_MENTION_SAFE_STATUSES: set[str] = set(SPEC["mentionSafeTaskStatuses"])

THREAD_MESSAGE_TYPES: list[str] = SPEC["threadMessageTypes"]


# ---------------------------------------------------------------------------
# Task helpers
# ---------------------------------------------------------------------------


def is_valid_task_transition(from_status: str, to_status: str) -> bool:
    """Check if a task state transition is valid.

    Returns True if *to_status* is reachable from *from_status* either via
    the explicit transition map or via universal target statuses.
    """
    if to_status in _TASK_UNIVERSAL_TARGETS:
        return True
    allowed = _TASK_TRANSITIONS.get(from_status, [])
    return to_status in allowed


def get_allowed_transitions(status: str) -> list[str]:
    """Return the list of statuses reachable from *status* (excluding universal targets)."""
    return list(_TASK_TRANSITIONS.get(status, []))


def get_universal_transitions() -> list[str]:
    """Return the list of universal target statuses (reachable from any status)."""
    return list(_TASK_UNIVERSAL_TARGETS)


def get_task_transition_event(from_status: str, to_status: str) -> str | None:
    """Return the activity event type for a task transition, or None if unmapped.

    For universal targets, returns the universal target event.
    """
    if to_status in _TASK_UNIVERSAL_TARGET_EVENTS:
        return _TASK_UNIVERSAL_TARGET_EVENTS[to_status]
    return _TASK_TRANSITION_EVENTS.get(f"{from_status}->{to_status}")


# ---------------------------------------------------------------------------
# Step helpers
# ---------------------------------------------------------------------------


def is_valid_step_transition(from_status: str, to_status: str) -> bool:
    """Check if a step state transition is valid."""
    allowed = _STEP_TRANSITIONS.get(from_status, [])
    return to_status in allowed


def get_step_allowed_transitions(status: str) -> list[str]:
    """Return the list of step statuses reachable from *status*."""
    return list(_STEP_TRANSITIONS.get(status, []))


def get_step_transition_event(from_status: str, to_status: str) -> str | None:
    """Return the activity event type for a step transition, or None if unmapped."""
    return _STEP_TRANSITION_EVENTS.get(f"{from_status}->{to_status}")


# ---------------------------------------------------------------------------
# Mention safety
# ---------------------------------------------------------------------------


def is_mention_safe(status: str) -> bool:
    """Return True if the given task status allows @mention interactions."""
    return status in _MENTION_SAFE_STATUSES
