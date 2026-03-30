"""Unified execution request data model.

Normalizes all execution context into a single dataclass used by tasks,
steps, and CC execution paths. This replaces the ad-hoc dict/string
context building scattered across executor.py and step_dispatcher.py.

Also contains ExecutionResult and supporting enums (RunnerType,
ErrorCategory) introduced by Story 16.2 for the ExecutionEngine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from mc.types import AgentData

# ---------------------------------------------------------------------------
# Story 16.1 — Entity type constants
# ---------------------------------------------------------------------------


class EntityType:
    """Entity type constants for execution requests."""

    TASK = "task"
    STEP = "step"


# ---------------------------------------------------------------------------
# Story 16.2 — Runner type and error category enums
# ---------------------------------------------------------------------------


class RunnerType(StrEnum):
    """Which backend runs the agent work."""

    # DEPRECATED: CLAUDE_CODE is the legacy Python SDK path.  All new execution
    # should use PROVIDER_CLI (headless ``-p`` flag, JSONL output).
    CLAUDE_CODE = "claude-code"
    HUMAN = "human"
    # INTERACTIVE_TUI is the legacy PTY/tmux path — kept as an escape hatch only.
    # The production default is now PROVIDER_CLI (Story 28.7).
    INTERACTIVE_TUI = "interactive-tui"
    PROVIDER_CLI = "provider-cli"


class ErrorCategory(StrEnum):
    """Normalized error categories for centralized handling."""

    TIER = "tier"
    PROVIDER = "provider"
    RUNNER = "runner"
    WORKFLOW = "workflow"


# ---------------------------------------------------------------------------
# Unified ExecutionRequest (16.1 fields + 16.2 additions)
# ---------------------------------------------------------------------------


@dataclass
class ExecutionRequest:
    """Normalized execution context for task or step execution.

    Fields mirror the context that executor.py and step_dispatcher.py
    assemble independently. The unified context pipeline populates this
    dataclass so that all execution paths share the same preparation.

    The engine inspects ``runner_type`` to select the correct strategy.
    """

    # Identity
    entity_type: str  # EntityType.TASK or EntityType.STEP
    entity_id: str  # task_id or step_id
    task_id: str  # always the parent task_id

    # Task metadata
    title: str = ""
    description: str | None = None

    # Agent configuration (resolved from YAML + Convex)
    agent: AgentData | None = None
    agent_name: str = ""
    agent_prompt: str | None = None
    agent_model: str | None = None
    agent_skills: list[str] | None = None
    reasoning_level: str | None = None

    # Board context
    board: dict[str, Any] | None = None
    board_name: str | None = None
    memory_workspace: Path | None = None
    memory_mode: str | None = None

    # Files
    files: list[dict[str, Any]] = field(default_factory=list)
    file_manifest: list[dict[str, Any]] = field(default_factory=list)
    files_dir: str = ""
    output_dir: str = ""

    # Thread context
    thread_context: str = ""
    thread_messages: list[dict[str, Any]] = field(default_factory=list)
    thread_journal_path: str = ""
    compacted_thread_summary: str = ""

    # Predecessor context (steps only)
    predecessor_context: str = ""
    predecessor_step_ids: list[str] = field(default_factory=list)

    # Skills
    skills: list[str] = field(default_factory=list)

    # Prompt (assembled final prompt)
    prompt: str = ""

    # Model (resolved model identifier, after tier resolution)
    model: str | None = None

    # Tags / tag attributes
    tags: list[str] = field(default_factory=list)
    tag_attributes: str = ""

    # Trust level
    trust_level: str = "autonomous"

    # Step-specific fields
    step_title: str = ""
    step_description: str = ""
    blocked_by: list[str] = field(default_factory=list)

    # CC-specific
    is_cc: bool = False

    # Raw task data (for post-execution hooks)
    task_data: dict[str, Any] = field(default_factory=dict)

    # --- Story 16.2 additions ---
    runner_type: RunnerType = RunnerType.PROVIDER_CLI
    step_id: str | None = None
    session_key: str | None = None
    session_boundary_reason: str | None = None

    @property
    def is_task(self) -> bool:
        """Return True if this is a task execution request."""
        return self.entity_type == EntityType.TASK

    @property
    def is_step(self) -> bool:
        """Return True if this is a step execution request."""
        return self.entity_type == EntityType.STEP

    @property
    def safe_task_id(self) -> str:
        """Return filesystem-safe task ID."""
        from mc.types import task_safe_id

        return task_safe_id(self.task_id)


# ---------------------------------------------------------------------------
# Story 16.2 — ExecutionResult
# ---------------------------------------------------------------------------


@dataclass
class ExecutionResult:
    """Outcome of an execution run.

    Carries enough data for post-execution steps (memory consolidation,
    artifact sync, session finalization) without needing the caller to
    know which runner was used.
    """

    success: bool
    output: str = ""

    # Error details (populated on failure)
    error_category: ErrorCategory | None = None
    error_message: str | None = None

    # Runner-specific metadata
    cost_usd: float = 0.0
    session_id: str | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    memory_workspace: Path | None = None
    session_loop: Any | None = None
    error_exception: Exception | None = None

    # For human strategy: the target status transition
    transition_status: str | None = None
