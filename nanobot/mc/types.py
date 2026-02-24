"""
Shared Python types for Mission Control.

These types mirror the Convex schema defined in dashboard/convex/schema.ts.
String values MUST match exactly — any mismatch will cause runtime errors.
"""

from __future__ import annotations

import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        """Backport of StrEnum for Python < 3.11."""
        pass


LEAD_AGENT_NAME = "lead-agent"


class TaskStatus(StrEnum):
    """Task lifecycle states. Matches Convex tasks.status union type."""
    INBOX = "inbox"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    RETRYING = "retrying"
    CRASHED = "crashed"


class TrustLevel(StrEnum):
    """Trust levels for task oversight. Matches Convex tasks.trustLevel union type."""
    AUTONOMOUS = "autonomous"
    AGENT_REVIEWED = "agent_reviewed"
    HUMAN_APPROVED = "human_approved"


class AgentStatus(StrEnum):
    """Agent runtime states. Matches Convex agents.status union type."""
    ACTIVE = "active"
    IDLE = "idle"
    CRASHED = "crashed"


class ActivityEventType(StrEnum):
    """Activity feed event types. Matches Convex activities.eventType union type."""
    TASK_CREATED = "task_created"
    TASK_ASSIGNED = "task_assigned"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_CRASHED = "task_crashed"
    TASK_RETRYING = "task_retrying"
    REVIEW_REQUESTED = "review_requested"
    REVIEW_FEEDBACK = "review_feedback"
    REVIEW_APPROVED = "review_approved"
    HITL_REQUESTED = "hitl_requested"
    HITL_APPROVED = "hitl_approved"
    HITL_DENIED = "hitl_denied"
    AGENT_CONNECTED = "agent_connected"
    AGENT_DISCONNECTED = "agent_disconnected"
    AGENT_CRASHED = "agent_crashed"
    AGENT_CONFIG_UPDATED = "agent_config_updated"
    AGENT_ACTIVATED = "agent_activated"
    AGENT_DEACTIVATED = "agent_deactivated"
    SYSTEM_ERROR = "system_error"
    TASK_DELETED = "task_deleted"
    TASK_RESTORED = "task_restored"
    BULK_CLEAR_DONE = "bulk_clear_done"
    MANUAL_TASK_STATUS_CHANGED = "manual_task_status_changed"
    THREAD_MESSAGE_SENT = "thread_message_sent"


class MessageType(StrEnum):
    """Message categories. Matches Convex messages.messageType union type."""
    WORK = "work"
    REVIEW_FEEDBACK = "review_feedback"
    APPROVAL = "approval"
    DENIAL = "denial"
    SYSTEM_EVENT = "system_event"
    USER_MESSAGE = "user_message"


class AuthorType(StrEnum):
    """Message author types. Matches Convex messages.authorType union type."""
    AGENT = "agent"
    USER = "user"
    SYSTEM = "system"


@dataclass
class ExecutionPlanStep:
    """A single step in an execution plan."""
    step_id: str
    description: str
    assigned_agent: str | None = None
    depends_on: list[str] = field(default_factory=list)
    parallel_group: str | None = None
    status: str = "pending"  # "pending" | "in_progress" | "completed" | "failed"


@dataclass
class ExecutionPlan:
    """Structured execution plan stored as JSON on a task document."""
    steps: list[ExecutionPlanStep] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict with camelCase keys for Convex storage."""
        return {
            "steps": [
                {
                    "stepId": s.step_id,
                    "description": s.description,
                    "assignedAgent": s.assigned_agent,
                    "dependsOn": s.depends_on,
                    "parallelGroup": s.parallel_group,
                    "status": s.status,
                }
                for s in self.steps
            ],
            "createdAt": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionPlan:
        """Deserialize from a Convex JSON dict (handles both snake and camel keys)."""
        steps = [
            ExecutionPlanStep(
                step_id=s.get("step_id") or s.get("stepId", ""),
                description=s["description"],
                assigned_agent=s.get("assigned_agent") or s.get("assignedAgent"),
                depends_on=s.get("depends_on") or s.get("dependsOn", []),
                parallel_group=s.get("parallel_group") or s.get("parallelGroup"),
                status=s.get("status", "pending"),
            )
            for s in data.get("steps", [])
        ]
        return cls(steps=steps, created_at=data.get("createdAt", data.get("created_at", "")))


@dataclass
class TaskData:
    """Python representation of a Convex task document (snake_case fields)."""
    title: str
    status: str  # TaskStatus value
    trust_level: str  # TrustLevel value
    created_at: str  # ISO 8601
    updated_at: str  # ISO 8601
    description: str | None = None
    assigned_agent: str | None = None
    reviewers: list[str] | None = None
    tags: list[str] | None = None
    task_timeout: float | None = None
    inter_agent_timeout: float | None = None
    id: str | None = None  # Convex _id (populated on read)


@dataclass
class AgentData:
    """Python representation of a Convex agent document (snake_case fields)."""
    name: str
    display_name: str
    role: str
    prompt: str | None = None  # System prompt (synced to Convex)
    soul: str | None = None  # SOUL.md content (synced to Convex)
    skills: list[str] = field(default_factory=list)
    status: str = "idle"  # AgentStatus value
    enabled: bool = True  # User-controlled activation flag
    model: str | None = None
    last_active_at: str | None = None
    id: str | None = None  # Convex _id (populated on read)


@dataclass
class MessageData:
    """Python representation of a Convex message document (snake_case fields)."""
    task_id: str
    author_name: str
    author_type: str  # AuthorType value
    content: str
    message_type: str  # MessageType value
    timestamp: str  # ISO 8601
    id: str | None = None  # Convex _id (populated on read)


@dataclass
class ActivityData:
    """Python representation of a Convex activity document (snake_case fields)."""
    event_type: str  # ActivityEventType value
    description: str
    timestamp: str  # ISO 8601
    task_id: str | None = None
    agent_name: str | None = None
    id: str | None = None  # Convex _id (populated on read)
