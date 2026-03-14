"""Step repository -- CRUD and queries for step entities."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.bridge.client import BridgeClient

logger = logging.getLogger(__name__)


class StepRepository:
    """Data access methods for step entities in Convex."""

    def __init__(self, client: "BridgeClient"):
        self._client = client

    def create_step(self, step_data: dict[str, Any]) -> str:
        """Create a single step record in Convex.

        Args:
            step_data: Step payload using snake_case keys.

        Returns:
            Convex step _id.
        """
        result = self._client.mutation("steps:create", step_data)
        if not isinstance(result, str):
            raise RuntimeError("steps:create did not return a step id")
        return result

    def batch_create_steps(
        self,
        task_id: str,
        steps: list[dict[str, Any]],
    ) -> list[str]:
        """Create multiple step records atomically via Convex.

        Args:
            task_id: Parent task _id.
            steps: Step payload list using snake_case keys.

        Returns:
            List of created step _id values in insertion order.
        """
        result = self._client.mutation(
            "steps:batchCreate",
            {"task_id": task_id, "steps": steps},
        )
        if result is None:
            return []
        if not isinstance(result, list):
            raise RuntimeError("steps:batchCreate did not return a list of step ids")
        return [str(step_id) for step_id in result]

    def update_step_status(
        self,
        step_id: str,
        status: str,
        error_message: str | None = None,
    ) -> Any:
        """Update a step's lifecycle status via steps:updateStatus."""
        args: dict[str, Any] = {"step_id": step_id, "status": status}
        if error_message is not None:
            args["error_message"] = error_message

        result = self._client.mutation("steps:updateStatus", args)
        self._log_state_transition("step", f"Step {step_id} status changed to {status}")
        return result

    def get_steps_by_task(self, task_id: str) -> list[dict[str, Any]]:
        """Fetch all steps for a task ordered by step.order."""
        result = self._client.query("steps:getByTask", {"task_id": task_id})
        return result if isinstance(result, list) else []

    def check_and_unblock_dependents(self, step_id: str) -> list[str]:
        """Unblock dependents for a completed step.

        Returns:
            List of newly unblocked step IDs.
        """
        result = self._client.mutation(
            "steps:checkAndUnblockDependents",
            {"step_id": step_id},
        )
        if not isinstance(result, list):
            return []
        return [str(unblocked_id) for unblocked_id in result]

    @staticmethod
    def _log_state_transition(entity_type: str, description: str) -> None:
        """Log a state transition to local stdout via logging."""
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info("[MC] %s %s: %s", timestamp, entity_type, description)
