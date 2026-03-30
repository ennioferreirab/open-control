"""SHARED: Unified service for persisting session state and activity events.

Provides a single API for all runner strategies (provider-cli, interactive, future
runners) to communicate with the dashboard Live tab infrastructure.

Both ``interactiveSessions`` and ``sessionActivityLog`` Convex tables are
written through this service, eliminating duplicated payload-building logic
across strategies.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mc.bridge.overflow import safe_string_for_convex
from mc.infrastructure.runtime_home import get_tasks_dir

logger = logging.getLogger(__name__)


def _resolve_overflow_dir(session_id: str) -> Path | None:
    """Return the overflow directory for large content, or None."""
    try:
        task_id = session_id.split("-")[0] if "-" in session_id else session_id
        return get_tasks_dir() / task_id / "output" / "_overflow"
    except Exception:
        return None


BATCH_SIZE_THRESHOLD = 20
BATCH_TIME_THRESHOLD_SECONDS = 0.3


class SessionActivityService:
    """Unified service for session metadata and activity log persistence.

    All runner strategies should use this service instead of calling
    ``bridge.mutation`` directly for session and activity log writes.

    Activity log events are buffered and flushed in batches to reduce
    Convex mutation calls. Flush triggers: buffer reaches 20 events OR
    300ms since last flush on the next append_event call.
    """

    def __init__(self, bridge: Any | None = None) -> None:
        self._bridge = bridge
        self._event_buffer: list[dict[str, Any]] = []
        self._last_flush_time: float = time.monotonic()

    @property
    def has_bridge(self) -> bool:
        """Whether a bridge is available for persistence."""
        return self._bridge is not None

    # ------------------------------------------------------------------
    # Session lifecycle (interactiveSessions:upsert)
    # ------------------------------------------------------------------

    def upsert_session(
        self,
        session_id: str,
        *,
        agent_name: str,
        provider: str,
        surface: str,
        task_id: str | None,
        step_id: str | None = None,
        status: str = "ready",
        final_result: str | None = None,
        last_error: str | None = None,
        **extra: Any,
    ) -> None:
        """Create or update an interactive session record.

        Core fields are explicit parameters.  Provider-specific fields
        (``bootstrap_prompt``, ``provider_session_id``, etc.) pass through
        via ``**extra``.
        """
        if self._bridge is None:
            return
        timestamp = datetime.now(UTC).isoformat()
        metadata: dict[str, Any] = {
            "session_id": session_id,
            "agent_name": agent_name,
            "provider": provider,
            "scope_kind": "task",
            "scope_id": task_id,
            "surface": surface,
            "tmux_session": session_id,
            "status": status,
            "capabilities": [],
            "updated_at": timestamp,
            "task_id": task_id,
        }
        if step_id is not None:
            metadata["step_id"] = step_id
        if final_result is not None:
            metadata["final_result"] = final_result
            metadata["final_result_source"] = provider
            metadata["final_result_at"] = timestamp
        if last_error is not None:
            metadata["last_error"] = last_error
        if status in ("ended", "error"):
            metadata["ended_at"] = timestamp
            # Flush any buffered activity events before session ends
            self.flush()
        # Provider-specific extras (bootstrap_prompt, provider_session_id, …)
        for key, value in extra.items():
            if value is not None:
                metadata[key] = value
        try:
            self._bridge.mutation("interactiveSessions:upsert", metadata)
        except Exception:
            logger.debug("[activity-service] Failed to upsert session %s", session_id)

    # ------------------------------------------------------------------
    # Activity log events (sessionActivityLog:append)
    # ------------------------------------------------------------------

    def append_event(
        self,
        session_id: str,
        *,
        kind: str,
        agent_name: str,
        provider: str,
        ts: str | None = None,
        step_id: str | None = None,
        summary: str | None = None,
        raw_text: str | None = None,
        raw_json: str | None = None,
        tool_name: str | None = None,
        tool_input: str | None = None,
        error: str | None = None,
        source_type: str | None = None,
        source_subtype: str | None = None,
        group_key: str | None = None,
        **extra: Any,
    ) -> None:
        """Append a single activity event to the session log.

        Handles overflow protection for ``raw_text`` and ``raw_json``.
        Extra keyword arguments are included in the payload as-is.
        ``ts`` overrides the event timestamp; defaults to now (UTC).
        """
        if self._bridge is None:
            return
        overflow_dir = _resolve_overflow_dir(session_id)
        payload: dict[str, Any] = {
            "session_id": session_id,
            "kind": kind,
            "ts": ts or datetime.now(UTC).isoformat(),
            "agent_name": agent_name,
            "provider": provider,
        }
        if step_id is not None:
            payload["step_id"] = step_id
        if summary is not None:
            payload["summary"] = summary[:1000]
        if tool_name is not None:
            payload["tool_name"] = tool_name
        if tool_input is not None:
            payload["tool_input"] = tool_input
        if error is not None:
            payload["error"] = error
        if source_type is not None:
            payload["source_type"] = source_type
        if source_subtype is not None:
            payload["source_subtype"] = source_subtype
        if group_key is not None:
            payload["group_key"] = group_key

        # Overflow-protected content fields
        if raw_text is not None:
            payload["raw_text"] = safe_string_for_convex(
                raw_text,
                field_name="raw_text",
                task_id=session_id,
                overflow_dir=overflow_dir,
            )
        if raw_json is not None:
            payload["raw_json"] = safe_string_for_convex(
                raw_json,
                field_name="raw_json",
                task_id=session_id,
                overflow_dir=overflow_dir,
            )

        for key, value in extra.items():
            if value is not None:
                payload[key] = value

        self._event_buffer.append(payload)

        # Flush if buffer is full or time threshold exceeded
        now = time.monotonic()
        if (
            len(self._event_buffer) >= BATCH_SIZE_THRESHOLD
            or now - self._last_flush_time > BATCH_TIME_THRESHOLD_SECONDS
        ):
            self._flush_buffer()

    def flush(self) -> None:
        """Flush any buffered events to Convex.

        Should be called at session boundaries and error paths to avoid
        losing buffered events.
        """
        if self._event_buffer:
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        """Send buffered events to Convex as a batch and reset buffer."""
        if not self._event_buffer or self._bridge is None:
            return

        events = self._event_buffer
        self._event_buffer = []
        self._last_flush_time = time.monotonic()

        try:
            if len(events) == 1:
                self._bridge.mutation("sessionActivityLog:append", events[0])
            else:
                self._bridge.mutation("sessionActivityLog:appendBatch", {"events": events})
        except Exception:
            logger.warning("[activity-service] Failed to flush %d event(s)", len(events))

    def append_result(
        self,
        session_id: str,
        *,
        agent_name: str,
        provider: str,
        success: bool,
        content: str,
        step_id: str | None = None,
    ) -> None:
        """Append a result event marking execution completion."""
        self.append_event(
            session_id,
            kind="result",
            agent_name=agent_name,
            provider=provider,
            step_id=step_id,
            source_type="result",
            source_subtype="success" if success else "error",
            summary=content[:1000],
            raw_text=content,
        )
        # Result marks end of execution -- flush remaining events
        self.flush()

    def append_parsed_cli_event(
        self,
        session_id: str,
        *,
        event_kind: str,
        event_text: str | None,
        event_metadata: dict[str, Any] | None,
        timestamp: str,
        agent_name: str,
        provider: str,
        step_id: str | None = None,
    ) -> None:
        """Append an event originating from a CLI parser (provider-cli path).

        Translates ``ParsedCliEvent``-shaped data into the unified activity
        log format.  This preserves the rich metadata that CLI parsers
        produce (tool_input, turn_id, source_type, etc.).
        """
        if self._bridge is None:
            return

        metadata = event_metadata or {}

        # Base fields
        summary: str | None = None
        tool_name: str | None = None
        tool_input_str: str | None = None
        error_str: str | None = None

        if event_kind == "tool_use":
            tool_name = metadata.get("tool_name") or event_text or "tool_use"
            summary = tool_name
            raw_tool_input = metadata.get("tool_input")
            if raw_tool_input is not None:
                if isinstance(raw_tool_input, str):
                    tool_input_str = raw_tool_input
                else:
                    tool_input_str = json.dumps(raw_tool_input, ensure_ascii=True, sort_keys=True)
        elif event_kind == "tool_result":
            summary = event_text
        elif event_kind == "error":
            error_str = event_text or "Provider CLI error"
        else:
            if event_text:
                summary = event_text

        # Raw content
        raw_text = event_text
        raw_json_data = metadata.get("tool_input") or metadata.get("raw_json")
        raw_json: str | None = None
        if raw_json_data is not None:
            raw_json = (
                raw_json_data
                if isinstance(raw_json_data, str)
                else json.dumps(raw_json_data, ensure_ascii=True)
            )

        self.append_event(
            session_id,
            kind=event_kind,
            agent_name=agent_name,
            provider=provider,
            ts=timestamp,
            step_id=step_id,
            summary=summary,
            raw_text=raw_text,
            raw_json=raw_json,
            tool_name=tool_name,
            tool_input=tool_input_str,
            error=error_str,
            source_type=metadata.get("source_type"),
            source_subtype=metadata.get("source_subtype"),
            group_key=metadata.get("turn_id"),
        )
