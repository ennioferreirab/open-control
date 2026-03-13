"""Bridge-backed registry for interactive TUI session metadata."""

from __future__ import annotations

import secrets
from typing import Any

from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.types import ActivityEventType


class InteractiveSessionRegistry:
    """Persist and discover interactive session metadata via Convex bridge."""

    def __init__(self, bridge: Any, *, token_factory: Any | None = None) -> None:
        self._bridge = bridge
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(24))

    def register(
        self,
        identity: InteractiveSessionIdentity,
        *,
        status: str,
        capabilities: list[str],
        timestamp: str,
        last_active_at: str | None = None,
        ended_at: str | None = None,
        rotate_attach_token: bool = False,
    ) -> dict[str, Any]:
        existing = self.get(identity.session_key)
        metadata = identity.to_metadata(
            status=status,
            capabilities=capabilities,
            timestamp=timestamp,
        )
        metadata["attach_token"] = self._resolve_attach_token(
            existing=existing,
            rotate=rotate_attach_token,
        )
        if last_active_at is not None:
            metadata["last_active_at"] = last_active_at
        if ended_at is not None:
            metadata["ended_at"] = ended_at

        self._upsert(metadata)
        self._emit_activity(
            ActivityEventType.AGENT_CONNECTED,
            f"Interactive TUI session created for @{identity.agent_name} on {identity.surface}.",
            agent_name=identity.agent_name,
        )
        return metadata

    def get(self, session_id: str) -> dict[str, Any] | None:
        result = self._bridge.query(
            "interactiveSessions:getForRuntime",
            {"session_id": session_id},
        )
        return result

    def list_sessions(self, *, agent_name: str | None = None) -> list[dict[str, Any]]:
        args = {"agent_name": agent_name} if agent_name else {}
        result = self._bridge.query("interactiveSessions:listForRuntime", args)
        return result or []

    def mark_attached(self, session_id: str, *, timestamp: str) -> dict[str, Any]:
        existing = self._require_session(session_id)
        event_label = "reattached" if existing.get("status") == "detached" else "attached"
        metadata = self._metadata_from_existing(
            existing,
            status="attached",
            timestamp=timestamp,
            last_active_at=timestamp,
        )
        self._upsert(metadata)
        self._emit_activity(
            ActivityEventType.AGENT_CONNECTED,
            f"Interactive TUI session {event_label} for @{existing['agent_name']} on {existing['surface']}.",
            agent_name=existing["agent_name"],
        )
        return metadata

    def mark_detached(self, session_id: str, *, timestamp: str) -> dict[str, Any]:
        existing = self._require_session(session_id)
        metadata = self._metadata_from_existing(
            existing,
            status="detached",
            timestamp=timestamp,
            last_active_at=timestamp,
        )
        self._upsert(metadata)
        self._emit_activity(
            ActivityEventType.AGENT_DISCONNECTED,
            f"Interactive TUI session detached for @{existing['agent_name']} on {existing['surface']}.",
            agent_name=existing["agent_name"],
        )
        return metadata

    def end_session(
        self,
        session_id: str,
        *,
        timestamp: str,
        outcome: str,
    ) -> dict[str, Any]:
        existing = self._require_session(session_id)
        status = "error" if outcome == "crashed" else "ended"
        metadata = self._metadata_from_existing(
            existing,
            status=status,
            timestamp=timestamp,
            last_active_at=timestamp,
            ended_at=timestamp,
        )
        self._upsert(metadata)
        event_type = (
            ActivityEventType.AGENT_CRASHED
            if outcome == "crashed"
            else ActivityEventType.AGENT_DISCONNECTED
        )
        self._emit_activity(
            event_type,
            f"Interactive TUI session {outcome} for @{existing['agent_name']} on {existing['surface']}.",
            agent_name=existing["agent_name"],
        )
        return metadata

    def terminate(
        self,
        identity: InteractiveSessionIdentity,
        *,
        timestamp: str,
    ) -> dict[str, Any]:
        existing = self.get(identity.session_key)
        if existing is not None:
            return self.end_session(identity.session_key, timestamp=timestamp, outcome="terminated")
        metadata = identity.to_metadata(
            status="ended",
            capabilities=[],
            timestamp=timestamp,
        )
        metadata["attach_token"] = self._resolve_attach_token(existing=None, rotate=True)
        metadata["last_active_at"] = timestamp
        metadata["ended_at"] = timestamp
        self._upsert(metadata)
        self._emit_activity(
            ActivityEventType.AGENT_DISCONNECTED,
            f"Interactive TUI session terminated for @{identity.agent_name} on {identity.surface}.",
            agent_name=identity.agent_name,
        )
        return metadata

    def _resolve_attach_token(
        self,
        *,
        existing: dict[str, Any] | None,
        rotate: bool,
    ) -> str:
        if not rotate and existing and existing.get("attach_token"):
            return str(existing["attach_token"])
        return str(self._token_factory())

    def _upsert(self, metadata: dict[str, Any]) -> None:
        self._bridge.mutation("interactiveSessions:upsert", metadata)

    def _require_session(self, session_id: str) -> dict[str, Any]:
        existing = self.get(session_id)
        if existing is None:
            raise ValueError(f"Interactive session metadata not found for {session_id}")
        return existing

    def _metadata_from_existing(
        self,
        existing: dict[str, Any],
        *,
        status: str,
        timestamp: str,
        last_active_at: str | None = None,
        ended_at: str | None = None,
    ) -> dict[str, Any]:
        metadata = {
            "session_id": existing["session_id"],
            "agent_name": existing["agent_name"],
            "provider": existing["provider"],
            "scope_kind": existing["scope_kind"],
            "scope_id": existing.get("scope_id"),
            "surface": existing["surface"],
            "tmux_session": existing["tmux_session"],
            "status": status,
            "capabilities": existing.get("capabilities", []),
            "created_at": existing.get("created_at", timestamp),
            "updated_at": timestamp,
            "attach_token": self._resolve_attach_token(existing=existing, rotate=False),
        }
        if last_active_at is not None:
            metadata["last_active_at"] = last_active_at
        elif existing.get("last_active_at") is not None:
            metadata["last_active_at"] = existing["last_active_at"]
        if ended_at is not None:
            metadata["ended_at"] = ended_at
        elif existing.get("ended_at") is not None:
            metadata["ended_at"] = existing["ended_at"]
        return metadata

    def _emit_activity(
        self,
        event_type: ActivityEventType,
        description: str,
        *,
        agent_name: str,
    ) -> None:
        self._bridge.create_activity(
            event_type,
            description,
            agent_name=agent_name,
        )
