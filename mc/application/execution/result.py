"""Unified execution result data model.

Captures the output of an execution (task or step) including artifacts,
session info, and status. Used by both nanobot and CC execution paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionResult:
    """Normalized execution result from task or step execution.

    Captures all output data that downstream code needs (message posting,
    artifact syncing, status transitions, memory consolidation).
    """

    # The agent's output text
    output: str = ""

    # Whether the execution errored
    is_error: bool = False

    # Artifacts produced during execution
    artifacts: list[dict[str, Any]] = field(default_factory=list)

    # Session tracking (for nanobot memory consolidation)
    session_key: str | None = None

    # CC-specific fields
    session_id: str | None = None
    cost_usd: float = 0.0

    # The entity_type ("task" or "step") that produced this result
    entity_type: str = "task"

    @property
    def has_artifacts(self) -> bool:
        """Return True if execution produced any artifacts."""
        return bool(self.artifacts)
