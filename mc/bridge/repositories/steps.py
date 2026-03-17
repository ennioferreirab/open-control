"""Step repository -- CRUD and queries for step entities."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.bridge.client import BridgeClient

logger = logging.getLogger(__name__)


def _coerce_state_version(step_data: dict[str, Any]) -> int:
    raw_value = step_data.get("state_version", step_data.get("stateVersion", 0))
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return 0


def _default_transition_idempotency_key(
    *,
    step_id: str,
    expected_state_version: int,
    from_status: str,
    to_status: str,
) -> str:
    return f"py:{step_id}:v{expected_state_version}:{from_status}:{to_status}"


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
        """Update a step's lifecycle status via the canonical CAS transition path."""
        step_data = self.get_step(step_id)
        if not isinstance(step_data, dict):
            logger.warning("[bridge] skipping step transition for missing step %s", step_id)
            return None
        result = self.transition_step_from_snapshot(
            step_data,
            status,
            reason=f"Compatibility transition via update_step_status ({status})",
            error_message=error_message,
        )
        self._log_state_transition("step", f"Step {step_id} status changed to {status}")
        return result

    def transition_step(
        self,
        step_id: str,
        *,
        from_status: str,
        to_status: str,
        expected_state_version: int,
        reason: str,
        idempotency_key: str,
        error_message: str | None = None,
    ) -> Any:
        """Apply a canonical step transition through Convex."""
        mutation_args: dict[str, Any] = {
            "step_id": step_id,
            "from_status": from_status,
            "expected_state_version": expected_state_version,
            "to_status": to_status,
            "reason": reason,
            "idempotency_key": idempotency_key,
        }
        if error_message is not None:
            mutation_args["error_message"] = error_message
        result = self._client.mutation("steps:transition", mutation_args)
        logger.debug(
            "[bridge] step transition %s -> %s for %s returned %s",
            from_status,
            to_status,
            step_id,
            result.get("kind") if isinstance(result, dict) else type(result).__name__,
        )
        return result

    def transition_step_from_snapshot(
        self,
        step_data: dict[str, Any],
        to_status: str,
        *,
        reason: str,
        error_message: str | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        """Transition a step using status/version from an in-memory snapshot."""
        step_id = str(step_data.get("id") or step_data.get("_id") or "").strip()
        if not step_id:
            raise ValueError("Step snapshot is missing an id")
        from_status = str(step_data.get("status") or "").strip()
        if not from_status:
            raise ValueError(f"Step snapshot {step_id} is missing a status")
        expected_state_version = _coerce_state_version(step_data)
        resolved_idempotency_key = idempotency_key or _default_transition_idempotency_key(
            step_id=step_id,
            expected_state_version=expected_state_version,
            from_status=from_status,
            to_status=to_status,
        )
        return self.transition_step(
            step_id,
            from_status=from_status,
            to_status=to_status,
            expected_state_version=expected_state_version,
            reason=reason,
            error_message=error_message,
            idempotency_key=resolved_idempotency_key,
        )

    def get_step(self, step_id: str) -> dict[str, Any] | None:
        """Fetch a single step by id."""
        return self._client.query("steps:getById", {"step_id": step_id})

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
