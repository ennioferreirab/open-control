"""
Task and step state machines — validates transitions and maps to activity event types.

This module is a thin backward-compatible wrapper around the canonical workflow
contract defined in ``shared/workflow/workflow_spec.json`` and loaded by
``mc.domain.workflow_contract``.

All hardcoded transition maps have been replaced by delegations to the contract.
Existing callers that import ``VALID_TRANSITIONS``, ``UNIVERSAL_TARGETS``, etc.
continue to work unchanged.

Story 15.1 — Shared Workflow Contract.
"""

from __future__ import annotations

from mc.domain.workflow_contract import (
    SPEC as _SPEC,
)
from mc.domain.workflow_contract import (
    get_step_transition_event as _get_step_transition_event,
)
from mc.domain.workflow_contract import (
    get_task_transition_event as _get_task_transition_event,
)
from mc.domain.workflow_contract import (
    is_valid_step_transition as _is_valid_step_transition,
)
from mc.domain.workflow_contract import (
    is_valid_task_transition as _is_valid_task_transition,
)

# ---------------------------------------------------------------------------
# Backward-compatible module-level constants — derived from the contract spec
# ---------------------------------------------------------------------------

# Task transitions: current_status -> [allowed_next_statuses]
VALID_TRANSITIONS: dict[str, list[str]] = dict(_SPEC["taskTransitions"])

# Universal targets: allowed from ANY source state
UNIVERSAL_TARGETS: set[str] = set(_SPEC["taskUniversalTargets"])

def _parse_transition_key(k: str) -> tuple[str, str]:
    parts = k.split("->")
    if len(parts) != 2:
        raise ValueError(f"Invalid transition key: {k}")
    return (parts[0].strip(), parts[1].strip())


# Map (from, to) -> activity event type
TRANSITION_EVENT_MAP: dict[tuple[str, str], str] = {
    _parse_transition_key(k): v
    for k, v in _SPEC["taskTransitionEvents"].items()
}

# Step transitions: current_status -> [allowed_next_statuses]
STEP_VALID_TRANSITIONS: dict[str, list[str]] = dict(_SPEC["stepTransitions"])

# Map (from, to) -> activity event type for step transitions
STEP_TRANSITION_EVENT_MAP: dict[tuple[str, str], str] = {
    _parse_transition_key(k): v
    for k, v in _SPEC["stepTransitionEvents"].items()
}


# ---------------------------------------------------------------------------
# Task-level functions — delegate to contract
# ---------------------------------------------------------------------------


def is_valid_transition(current_status: str, new_status: str) -> bool:
    """Check if a state transition is valid."""
    return _is_valid_task_transition(current_status, new_status)


def validate_transition(current_status: str, new_status: str) -> None:
    """Validate a state transition. Raises ValueError if invalid."""
    if not is_valid_transition(current_status, new_status):
        raise ValueError(f"Cannot transition from '{current_status}' to '{new_status}'")


def get_event_type(current_status: str, new_status: str) -> str:
    """Get the activity event type for a transition."""
    event = _get_task_transition_event(current_status, new_status)
    if event is None:
        raise ValueError(
            f"No event type mapping for transition '{current_status}' -> '{new_status}'"
        )
    return event


# ---------------------------------------------------------------------------
# Step-level functions — delegate to contract
# ---------------------------------------------------------------------------


def is_valid_step_transition(current_status: str, new_status: str) -> bool:
    """Check if a step state transition is valid."""
    return _is_valid_step_transition(current_status, new_status)


def validate_step_transition(current_status: str, new_status: str) -> None:
    """Validate a step state transition. Raises ValueError if invalid."""
    if not is_valid_step_transition(current_status, new_status):
        raise ValueError(f"Cannot transition step from '{current_status}' to '{new_status}'")


def get_step_event_type(current_status: str, new_status: str) -> str:
    """Get the activity event type for a step transition."""
    event = _get_step_transition_event(current_status, new_status)
    if event is None:
        raise ValueError(
            f"No event type mapping for step transition '{current_status}' -> '{new_status}'"
        )
    return event
