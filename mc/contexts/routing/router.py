"""Direct-delegation router — selects a target agent from the active registry."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """Result of lead-agent direct delegation routing."""

    target_agent: str
    reason: str
    reason_code: str
    registry_snapshot: list[dict[str, Any]] = field(default_factory=list)
    routed_at: str = ""


class DirectDelegationRouter:
    """Selects a target agent for direct-delegate tasks.

    Uses the active registry view to pick the best agent based on:
    - Board-scoped agent filtering (if boardId present)
    - Explicit assignedAgent override
    - Least-loaded agent (lowest tasksExecuted)
    """

    def __init__(self, bridge: ConvexBridge) -> None:
        self._bridge = bridge

    def route(
        self,
        task_data: dict[str, Any],
    ) -> RoutingDecision | None:
        """Select a target agent for a direct-delegate task.

        Returns None if no suitable agent is found.
        """
        from datetime import datetime

        registry = self._bridge.list_active_registry_view()
        if not registry:
            logger.warning("[router] No active agents in registry")
            return None

        candidates = list(registry)

        # Filter by board if present
        board_id = task_data.get("board_id") or task_data.get("boardId")
        if board_id:
            try:
                board = self._bridge.get_board_by_id(board_id)
                if board:
                    enabled = board.get("enabled_agents") or board.get("enabledAgents") or []
                    if enabled:
                        candidates = [a for a in candidates if a.get("name") in enabled]
            except Exception:
                logger.warning("[router] Failed to fetch board for filtering", exc_info=True)

        # Explicit assignedAgent override
        assigned = task_data.get("assigned_agent") or task_data.get("assignedAgent")
        if assigned:
            match = next((a for a in candidates if a.get("name") == assigned), None)
            if match:
                return RoutingDecision(
                    target_agent=assigned,
                    reason=f"Explicitly assigned to {assigned}",
                    reason_code="explicit_assignment",
                    registry_snapshot=[
                        {"name": a.get("name"), "role": a.get("role")} for a in registry
                    ],
                    routed_at=datetime.now(UTC).isoformat(),
                )

        if not candidates:
            logger.warning("[router] No candidates after board filtering")
            return None

        # Pick least-loaded agent
        candidates.sort(key=lambda a: a.get("tasksExecuted", 0))
        best = candidates[0]

        return RoutingDecision(
            target_agent=best["name"],
            reason=(
                f"Least-loaded agent in registry ({best.get('tasksExecuted', 0)} tasks executed)"
            ),
            reason_code="least_loaded",
            registry_snapshot=[{"name": a.get("name"), "role": a.get("role")} for a in registry],
            routed_at=datetime.now(UTC).isoformat(),
        )
