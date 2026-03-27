"""
Shared Python types for Mission Control.

These types mirror the Convex schema defined in dashboard/convex/schema.ts.
String values MUST match exactly — any mismatch will cause runtime errors.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

ORCHESTRATOR_AGENT_NAME = "orchestrator-agent"
LOW_AGENT_NAME = "low-agent"
HUMAN_AGENT_NAME = "human"

# Model tier system (Story 11.1)
TIER_PREFIX = "tier:"
VALID_TIER_NAMES: frozenset[str] = frozenset(
    {
        "standard-low",
        "standard-medium",
        "standard-high",
        "reasoning-low",
        "reasoning-medium",
        "reasoning-high",
    }
)


class OrchestratorAgentExecutionError(RuntimeError):
    """Raised when orchestrator-agent execution is attempted."""


def is_orchestrator_agent(agent_name: str | None) -> bool:
    """Return True when the given name is the orchestrator-agent."""
    return agent_name == ORCHESTRATOR_AGENT_NAME


def is_tier_reference(model: str | None) -> bool:
    """Return True if model is a tier reference (starts with 'tier:')."""
    return model is not None and model.startswith(TIER_PREFIX)


def extract_tier_name(model: str) -> str | None:
    """Extract and validate the tier name from a tier reference string.

    Returns the tier name (e.g. 'standard-high') if valid, else None.
    """
    if not model.startswith(TIER_PREFIX):
        return None
    name = model[len(TIER_PREFIX) :]
    return name if name in VALID_TIER_NAMES else None


# CC = Claude Code
# CC-specific types — re-exported from vendor package for backwards compatibility
from claude_code.types import (  # noqa: F401, E402 — intentional re-exports
    CC_AVAILABLE_MODELS,
    CC_MODEL_PREFIX,
    CCTaskResult,
    ClaudeCodeOpts,
    WorkspaceContext,
    extract_cc_model_name,
    is_cc_model,
)


class TaskStatus(StrEnum):
    """Task lifecycle states. Matches Convex tasks.status union type."""

    READY = "ready"
    FAILED = "failed"
    INBOX = "inbox"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    RETRYING = "retrying"
    CRASHED = "crashed"
    DELETED = "deleted"


class ReviewPhase(StrEnum):
    """Semantic discriminator for task.status='review'."""

    PLAN_REVIEW = "plan_review"
    EXECUTION_PAUSE = "execution_pause"
    FINAL_APPROVAL = "final_approval"


class StepStatus(StrEnum):
    """Step lifecycle states. Matches Convex steps.status union type."""

    PLANNED = "planned"
    ASSIGNED = "assigned"
    RUNNING = "running"
    REVIEW = "review"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    CRASHED = "crashed"
    BLOCKED = "blocked"
    WAITING_HUMAN = "waiting_human"
    DELETED = "deleted"


class TrustLevel(StrEnum):
    """Trust levels for task oversight. Matches Convex tasks.trustLevel union type."""

    AUTONOMOUS = "autonomous"
    HUMAN_APPROVED = "human_approved"


class AgentStatus(StrEnum):
    """Agent runtime states. Matches Convex agents.status union type."""

    ACTIVE = "active"
    IDLE = "idle"
    CRASHED = "crashed"


class ActivityEventType(StrEnum):
    """Activity feed event types. Matches Convex activities.eventType union type."""

    TASK_CREATED = "task_created"
    TASK_FAILED = "task_failed"
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
    TASK_DISPATCH_STARTED = "task_dispatch_started"
    STEP_DISPATCHED = "step_dispatched"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_SKIPPED = "step_skipped"
    STEP_RETRYING = "step_retrying"
    SYSTEM_ERROR = "system_error"
    TASK_DELETED = "task_deleted"
    TASK_RESTORED = "task_restored"
    BULK_CLEAR_DONE = "bulk_clear_done"
    MANUAL_TASK_STATUS_CHANGED = "manual_task_status_changed"
    THREAD_MESSAGE_SENT = "thread_message_sent"
    TASK_REASSIGNED = "task_reassigned"
    AGENT_DELETED = "agent_deleted"
    AGENT_RESTORED = "agent_restored"
    FILE_ATTACHED = "file_attached"
    TASK_MERGED = "task_merged"
    AGENT_OUTPUT = "agent_output"
    BOARD_CREATED = "board_created"
    BOARD_UPDATED = "board_updated"
    BOARD_DELETED = "board_deleted"
    STEP_CREATED = "step_created"
    STEP_STATUS_CHANGED = "step_status_changed"
    STEP_UNBLOCKED = "step_unblocked"


class MessageType(StrEnum):
    """Message categories. Matches Convex messages.messageType union type."""

    WORK = "work"
    REVIEW_FEEDBACK = "review_feedback"
    APPROVAL = "approval"
    DENIAL = "denial"
    SYSTEM_EVENT = "system_event"
    USER_MESSAGE = "user_message"
    COMMENT = "comment"


class ThreadMessageType(StrEnum):
    """Unified thread message types. Matches Convex messages.type union type (Story 2.4).

    Distinct from MessageType (legacy messageType field) — this is the new
    architecture-aligned classification used for structured rendering (Story 2.7).
    """

    STEP_COMPLETION = "step_completion"
    USER_MESSAGE = "user_message"
    SYSTEM_ERROR = "system_error"
    ORCHESTRATOR_AGENT_CHAT = "orchestrator_agent_chat"


# Alias for Story 2.5 — same enum, exposed under the name used in the story spec.
StructuredMessageType = ThreadMessageType


class AuthorType(StrEnum):
    """Message author types. Matches Convex messages.authorType union type."""

    AGENT = "agent"
    USER = "user"
    SYSTEM = "system"


class WorkflowStepType(StrEnum):
    """Workflow step types. Matches Convex workflowStepTypeValidator union type."""

    AGENT = "agent"
    HUMAN = "human"
    REVIEW = "review"
    SYSTEM = "system"


@dataclass
class ExecutionPlanStep:
    """A single step in an execution plan (pre-materialization)."""

    temp_id: str
    title: str
    description: str
    assigned_agent: str = "claude-code"
    blocked_by: list[str] = field(default_factory=list)
    parallel_group: int = 1
    order: int = 1
    # Workflow metadata — present when step was compiled from a workflowSpec.
    workflow_step_id: str | None = None
    workflow_step_type: str | None = None  # WorkflowStepType value
    agent_id: str | None = None
    agent_spec_id: str | None = None
    review_spec_id: str | None = None
    on_reject_step_id: str | None = None
    skip: bool = False


def _as_int(value: Any, default: int) -> int:
    """Coerce arbitrary values to a positive integer with a fallback."""
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


@dataclass
class ExecutionPlan:
    """Structured execution plan stored as JSON on a task document."""

    steps: list[ExecutionPlanStep] = field(default_factory=list)
    generated_at: str = ""
    generated_by: str = ORCHESTRATOR_AGENT_NAME

    def __post_init__(self) -> None:
        if not self.generated_at:
            self.generated_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict with snake_case keys; bridge converts to camelCase for Convex."""
        step_dicts = []
        for s in self.steps:
            step: dict[str, Any] = {
                "temp_id": s.temp_id,
                "title": s.title,
                "description": s.description,
                "assigned_agent": s.assigned_agent,
                "blocked_by": s.blocked_by,
                "parallel_group": s.parallel_group,
                "order": s.order,
            }
            if s.workflow_step_id is not None:
                step["workflow_step_id"] = s.workflow_step_id
            if s.workflow_step_type is not None:
                step["workflow_step_type"] = s.workflow_step_type
            if s.agent_id is not None:
                step["agent_id"] = s.agent_id
            if s.agent_spec_id is not None:
                step["agent_spec_id"] = s.agent_spec_id
            if s.review_spec_id is not None:
                step["review_spec_id"] = s.review_spec_id
            if s.on_reject_step_id is not None:
                step["on_reject_step_id"] = s.on_reject_step_id
            step_dicts.append(step)
        return {
            "steps": step_dicts,
            "generated_at": self.generated_at,
            "generated_by": self.generated_by,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionPlan:
        """Deserialize from a snake_case dict (bridge converts camelCase before calling this)."""
        steps: list[ExecutionPlanStep] = []
        for index, raw_step in enumerate(data.get("steps", []), start=1):
            temp_id = raw_step.get("temp_id") or raw_step.get("step_id") or f"step_{index}"
            title = raw_step.get("title") or raw_step.get("description") or temp_id
            description = raw_step.get("description") or title
            assigned_agent = raw_step.get("assigned_agent") or None
            blocked_by = raw_step.get("blocked_by") or raw_step.get("depends_on") or []
            if isinstance(blocked_by, str):
                blocked_by_list = [blocked_by] if blocked_by else []
            elif isinstance(blocked_by, list):
                blocked_by_list = [str(dep) for dep in blocked_by if str(dep).strip()]
            else:
                blocked_by_list = []

            steps.append(
                ExecutionPlanStep(
                    temp_id=temp_id,
                    title=title,
                    description=description,
                    assigned_agent=assigned_agent,
                    blocked_by=blocked_by_list,
                    parallel_group=_as_int(raw_step.get("parallel_group"), 1),
                    order=_as_int(raw_step.get("order"), index),
                    workflow_step_id=raw_step.get("workflow_step_id"),
                    workflow_step_type=raw_step.get("workflow_step_type"),
                    agent_id=raw_step.get("agent_id"),
                    agent_spec_id=raw_step.get("agent_spec_id"),
                    review_spec_id=raw_step.get("review_spec_id"),
                    on_reject_step_id=raw_step.get("on_reject_step_id"),
                )
            )

        return cls(
            steps=steps,
            generated_at=(data.get("generated_at") or data.get("created_at", "")),
            generated_by=(data.get("generated_by") or ORCHESTRATOR_AGENT_NAME),
        )


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
    is_system: bool = False  # System agents cannot be deleted/deactivated
    last_active_at: str | None = None
    id: str | None = None  # Convex _id (populated on read)
    backend: str = "claude-code"
    claude_code_opts: ClaudeCodeOpts | None = None
    interactive_provider: str | None = None


@dataclass
class ArtifactData:
    """An artifact produced by an agent step (e.g., created/modified file).

    Mirrors the Convex schema messages.artifacts array element.
    All string values match the Convex schema union types exactly.
    """

    path: str
    action: str  # "created" | "modified" | "deleted"
    description: str | None = None
    diff: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict for inclusion in bridge mutation args."""
        d: dict[str, Any] = {"path": self.path, "action": self.action}
        if self.description is not None:
            d["description"] = self.description
        if self.diff is not None:
            d["diff"] = self.diff
        return d


# Alias for Story 2.5 — same dataclass, exposed under the name used in the story spec.
StepCompletionArtifact = ArtifactData


@dataclass
class MessageData:
    """Python representation of a Convex message document (snake_case fields)."""

    task_id: str
    author_name: str
    author_type: str  # AuthorType value
    content: str
    message_type: str  # MessageType value (legacy)
    timestamp: str  # ISO 8601
    id: str | None = None  # Convex _id (populated on read)
    # Unified thread fields (Story 2.4)
    type: str | None = None  # ThreadMessageType value
    step_id: str | None = None  # Convex step _id
    artifacts: list[ArtifactData] | None = None


@dataclass
class ActivityData:
    """Python representation of a Convex activity document (snake_case fields)."""

    event_type: str  # ActivityEventType value
    description: str
    timestamp: str  # ISO 8601
    task_id: str | None = None
    agent_name: str | None = None
    id: str | None = None  # Convex _id (populated on read)


def task_safe_id(task_id: str) -> str:
    """Convert a Convex task ID to a filesystem-safe string."""
    return re.sub(r"[^\w\-]", "_", task_id)
