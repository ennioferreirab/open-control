"""SHARED: Claude Code hook relay into the interactive supervision sink.

Normalizes Claude Code hook events and forwards them to the supervision
sink.  Used by both headless (provider-cli) and TUI execution paths.
"""

from __future__ import annotations

from typing import Any

from mc.contexts.interactive.supervision import (
    SUPERVISION_METADATA_EXCLUDE_KEYS,
    normalize_provider_event,
)
from mc.contexts.interactive.types import InteractiveSupervisionSink


class ClaudeHookRelay:
    """Translate Claude hook payloads into canonical supervision events."""

    def __init__(self, *, sink: InteractiveSupervisionSink) -> None:
        self._sink = sink

    def handle(
        self,
        payload: dict[str, Any],
        *,
        session_id: str,
        task_id: str,
        step_id: str | None = None,
        agent_name: str | None = None,
    ) -> dict[str, object]:
        raw_event = dict(payload)
        raw_event.setdefault("eventName", payload.get("hook_event_name"))
        raw_event["session_id"] = session_id
        raw_event["task_id"] = task_id
        if step_id is not None:
            raw_event["step_id"] = step_id
        if agent_name is not None:
            raw_event["agent_name"] = agent_name
        raw_event["metadata"] = {
            key: value
            for key, value in payload.items()
            if key not in SUPERVISION_METADATA_EXCLUDE_KEYS
        }
        event = normalize_provider_event(provider="claude-code", raw_event=raw_event)
        return self._sink.handle_event(event)
