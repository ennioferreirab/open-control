"""File-backed persistence for Live session metadata and transcript events."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mc.infrastructure.runtime_home import get_live_home

logger = logging.getLogger(__name__)

SAFE_COMPONENT_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _snake_to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(piece[:1].upper() + piece[1:] for piece in parts[1:])


def _camelize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        (_snake_to_camel(key) if "_" in key else key): value
        for key, value in payload.items()
        if value is not None
    }


def _safe_component(value: str) -> str:
    if not value:
        raise ValueError(f"Invalid live session path component: {value!r}")
    if SAFE_COMPONENT_RE.match(value):
        return value
    sanitized = re.sub(r"[^A-Za-z0-9_-]", "_", value)
    if not sanitized:
        raise ValueError(f"Invalid live session path component: {value!r}")
    return sanitized


@dataclass(frozen=True)
class LiveSessionPaths:
    root: Path
    session_dir: Path
    meta_path: Path
    events_path: Path
    index_path: Path


class LiveSessionStore:
    """Append-only filesystem store for Live transcript data."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or get_live_home()

    def session_paths(
        self,
        session_id: str,
        *,
        task_id: str,
        step_id: str | None = None,
    ) -> LiveSessionPaths:
        safe_task_id = _safe_component(task_id)
        safe_session_id = _safe_component(session_id)
        scope_component = _safe_component(step_id) if step_id else "task"
        session_dir = self._root / "sessions" / safe_task_id / scope_component / safe_session_id
        return LiveSessionPaths(
            root=self._root,
            session_dir=session_dir,
            meta_path=session_dir / "meta.json",
            events_path=session_dir / "events.jsonl",
            index_path=self._root / "session-index" / f"{safe_session_id}.json",
        )

    def read_meta(
        self, session_id: str, *, task_id: str, step_id: str | None = None
    ) -> dict[str, Any] | None:
        paths = self.session_paths(session_id, task_id=task_id, step_id=step_id)
        try:
            return json.loads(paths.meta_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def upsert_session(self, metadata: dict[str, Any]) -> dict[str, Any]:
        session_id = str(metadata["session_id"])
        task_id = str(metadata["task_id"])
        step_id = metadata.get("step_id")
        paths = self.session_paths(
            session_id, task_id=task_id, step_id=str(step_id) if step_id else None
        )
        paths.session_dir.mkdir(parents=True, exist_ok=True)

        existing = (
            self.read_meta(session_id, task_id=task_id, step_id=str(step_id) if step_id else None)
            or {}
        )
        event_count = int(existing.get("eventCount", 0))
        if "event_count" in metadata and metadata["event_count"] is not None:
            event_count = int(metadata["event_count"])

        meta_payload = _camelize_payload(
            {
                "session_id": session_id,
                "task_id": task_id,
                "step_id": step_id,
                "agent_name": metadata.get("agent_name"),
                "provider": metadata.get("provider"),
                "status": metadata.get("status"),
                "created_at": metadata.get("created_at") or existing.get("createdAt") or _now(),
                "updated_at": metadata.get("updated_at") or _now(),
                "last_event_at": metadata.get("last_event_at") or existing.get("lastEventAt"),
                "last_event_kind": metadata.get("last_event_kind") or existing.get("lastEventKind"),
                "event_count": event_count,
                "has_live_transcript": metadata.get("has_live_transcript", True),
                "live_storage_mode": metadata.get("live_storage_mode", "file"),
                "live_event_count": metadata.get("live_event_count", event_count),
                "last_error": metadata.get("last_error"),
                "final_result": metadata.get("final_result"),
                "final_result_source": metadata.get("final_result_source"),
                "final_result_at": metadata.get("final_result_at"),
            }
        )

        tmp_path = paths.meta_path.with_suffix(".json.tmp")
        tmp_path.write_text(
            json.dumps(meta_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        tmp_path.replace(paths.meta_path)
        paths.index_path.parent.mkdir(parents=True, exist_ok=True)
        index_tmp = paths.index_path.with_suffix(".json.tmp")
        index_tmp.write_text(
            json.dumps(
                {
                    "sessionId": session_id,
                    "taskId": task_id,
                    "stepId": step_id,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        index_tmp.replace(paths.index_path)
        return meta_payload

    def append_event(self, metadata: dict[str, Any]) -> dict[str, Any]:
        session_id = str(metadata["session_id"])
        task_id = str(metadata["task_id"])
        step_id = metadata.get("step_id")
        paths = self.session_paths(
            session_id, task_id=task_id, step_id=str(step_id) if step_id else None
        )
        paths.session_dir.mkdir(parents=True, exist_ok=True)

        current_meta = (
            self.read_meta(session_id, task_id=task_id, step_id=str(step_id) if step_id else None)
            or {}
        )
        seq = int(current_meta.get("eventCount", 0)) + 1

        event_payload = _camelize_payload({"seq": seq, **metadata})
        with paths.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event_payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")

        self.upsert_session(
            {
                "session_id": session_id,
                "task_id": task_id,
                "step_id": step_id,
                "agent_name": metadata.get("agent_name"),
                "provider": metadata.get("provider"),
                "status": metadata.get("status") or current_meta.get("status"),
                "updated_at": metadata.get("updated_at") or _now(),
                "last_event_at": metadata.get("ts") or metadata.get("last_event_at"),
                "last_event_kind": metadata.get("kind"),
                "event_count": seq,
                "has_live_transcript": True,
                "live_storage_mode": metadata.get(
                    "live_storage_mode", current_meta.get("liveStorageMode", "file")
                ),
                "live_event_count": seq,
            }
        )
        return event_payload

    def read_events(
        self,
        session_id: str,
        *,
        task_id: str,
        step_id: str | None = None,
        after_seq: int = 0,
    ) -> list[dict[str, Any]]:
        paths = self.session_paths(session_id, task_id=task_id, step_id=step_id)
        try:
            contents = paths.events_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []

        events: list[dict[str, Any]] = []
        for line in contents.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError:
                logger.warning("Skipping invalid live event line for session %s", session_id)
                continue
            if int(event.get("seq", 0)) <= after_seq:
                continue
            events.append(event)
        return events
