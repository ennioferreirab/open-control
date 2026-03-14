"""Runtime-owned supervision sink for provider-backed interactive execution."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from mc.contexts.interactive.metrics import increment_interactive_metric
from mc.contexts.interactive.registry import InteractiveSessionRegistry
from mc.contexts.interactive.supervision_types import InteractiveSupervisionEvent
from mc.types import ActivityEventType

logger = logging.getLogger(__name__)


class InteractiveExecutionSupervisor:
    """Consume normalized supervision events and project them into MC state."""

    def __init__(self, *, bridge: Any, registry: InteractiveSessionRegistry) -> None:
        self._bridge = bridge
        self._registry = registry

    def handle_event(self, event: InteractiveSupervisionEvent) -> dict[str, Any]:
        if not event.session_id:
            raise ValueError("Interactive supervision events require a session_id")

        timestamp = event.occurred_at or datetime.now(timezone.utc).isoformat()
        metadata = self._registry.get(event.session_id) or {}
        merged_event = self._merge_event_context(event, metadata)
        event_payload: dict[str, Any] = {"kind": merged_event.kind}
        if merged_event.task_id is not None:
            event_payload["task_id"] = merged_event.task_id
        if merged_event.step_id is not None:
            event_payload["step_id"] = merged_event.step_id
        if merged_event.turn_id is not None:
            event_payload["turn_id"] = merged_event.turn_id
        if merged_event.item_id is not None:
            event_payload["item_id"] = merged_event.item_id
        if merged_event.summary is not None:
            event_payload["summary"] = merged_event.summary
        if merged_event.final_output is not None:
            event_payload["final_output"] = merged_event.final_output
        if merged_event.provider is not None:
            event_payload["final_result_source"] = merged_event.provider
        if merged_event.error is not None:
            event_payload["error"] = merged_event.error
        if merged_event.status is not None:
            event_payload["status"] = merged_event.status
        if merged_event.agent_name is not None:
            event_payload["agent_name"] = merged_event.agent_name
        updated_metadata = self._registry.record_supervision(
            merged_event.session_id,
            event=event_payload,
            timestamp=timestamp,
        )
        if _string_or_none(metadata.get("control_mode")) == "human":
            return updated_metadata
        current_control_mode = _string_or_none(updated_metadata.get("control_mode"))
        if current_control_mode == "human":
            return updated_metadata
        self._apply_lifecycle_side_effects(merged_event)
        return updated_metadata

    def record_final_result(
        self,
        *,
        session_id: str,
        content: str,
        source: str,
    ) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        metadata = self._registry.record_final_result(
            session_id,
            content=content,
            source=source,
            timestamp=timestamp,
        )
        return {"session_id": session_id, "recorded_at": timestamp, "metadata": metadata}

    def _merge_event_context(
        self,
        event: InteractiveSupervisionEvent,
        metadata: dict[str, Any],
    ) -> InteractiveSupervisionEvent:
        return InteractiveSupervisionEvent(
            kind=event.kind,
            session_id=event.session_id,
            provider=event.provider or _string_or_none(metadata.get("provider")),
            task_id=event.task_id or _string_or_none(metadata.get("task_id")),
            step_id=event.step_id or _string_or_none(metadata.get("step_id")),
            turn_id=event.turn_id,
            item_id=event.item_id,
            status=event.status,
            summary=event.summary,
            error=event.error,
            metadata=event.metadata,
            occurred_at=event.occurred_at,
            agent_name=event.agent_name or _string_or_none(metadata.get("agent_name")),
        )

    def _apply_lifecycle_side_effects(self, event: InteractiveSupervisionEvent) -> None:
        if event.kind in {"turn_started", "item_started"}:
            self._mark_running(event)
            return
        if event.kind in {"paused_for_review", "user_input_requested", "ask_user_requested"}:
            self._pause_for_review(event, activity_type=ActivityEventType.REVIEW_REQUESTED)
            return
        if event.kind == "approval_requested":
            self._pause_for_review(event, activity_type=ActivityEventType.HITL_REQUESTED)
            return
        if event.kind == "session_ready":
            self._mark_supervision_ready(event)
            return
        if event.kind == "session_failed":
            self._mark_crashed(event)

    def _mark_running(self, event: InteractiveSupervisionEvent) -> None:
        if event.task_id:
            description = (
                f"Interactive turn started for step {event.step_id}"
                if event.step_id
                else "Interactive turn started"
            )
            try:
                self._bridge.update_task_status(
                    event.task_id,
                    "in_progress",
                    agent_name=event.agent_name,
                    description=description,
                )
            except Exception as exc:
                if _is_same_status_error(exc, "in_progress"):
                    logger.debug(
                        "Task %s already in_progress — idempotent, skipping", event.task_id
                    )
                else:
                    raise
        if event.step_id:
            try:
                self._bridge.update_step_status(event.step_id, "running")
            except Exception as exc:
                if _is_same_status_error(exc, "running"):
                    logger.debug("Step %s already running — idempotent, skipping", event.step_id)
                else:
                    raise
        if event.task_id and event.agent_name:
            self._bridge.create_activity(
                ActivityEventType.STEP_STARTED,
                f"Interactive step started for @{event.agent_name}.",
                task_id=event.task_id,
                agent_name=event.agent_name,
            )

    def _pause_for_review(
        self,
        event: InteractiveSupervisionEvent,
        *,
        activity_type: ActivityEventType,
    ) -> None:
        description = event.summary or "Interactive session is waiting for user input."
        if event.task_id:
            self._bridge.update_task_status(
                event.task_id,
                "review",
                agent_name=event.agent_name,
                description=description,
            )
        if event.step_id:
            self._bridge.update_step_status(event.step_id, "review")
        if event.task_id and event.agent_name:
            action = (
                "paused for review"
                if activity_type == ActivityEventType.REVIEW_REQUESTED
                else "requested approval"
            )
            self._bridge.create_activity(
                activity_type,
                f"Interactive session {action} for @{event.agent_name}.",
                task_id=event.task_id,
                agent_name=event.agent_name,
            )

    def _mark_crashed(self, event: InteractiveSupervisionEvent) -> None:
        description = event.error or "Interactive session failed."
        increment_interactive_metric("interactive_session_crash_total")
        if event.task_id:
            self._bridge.update_task_status(
                event.task_id,
                "crashed",
                agent_name=event.agent_name,
                description=description,
            )
        if event.step_id:
            self._bridge.update_step_status(event.step_id, "crashed", description)
        if event.task_id and event.agent_name:
            self._bridge.create_activity(
                ActivityEventType.AGENT_CRASHED,
                f"Interactive session failed for @{event.agent_name}.",
                task_id=event.task_id,
                agent_name=event.agent_name,
            )

    def _mark_supervision_ready(self, event: InteractiveSupervisionEvent) -> None:
        if event.task_id and event.agent_name:
            self._bridge.create_activity(
                ActivityEventType.AGENT_CONNECTED,
                f"Interactive supervision ready for @{event.agent_name}.",
                task_id=event.task_id,
                agent_name=event.agent_name,
            )


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_same_status_error(exc: Exception, status: str) -> bool:
    """Return True if *exc* represents a no-op same-status transition for *status*.

    Convex validators raise when the current status equals the requested status.
    The message contains a pattern like "<status> -> <status>".
    """
    msg = str(exc)
    return f"{status} -> {status}" in msg
