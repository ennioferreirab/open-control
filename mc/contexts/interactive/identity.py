"""Identity helpers for interactive TUI sessions."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

_SAFE_SEGMENT_RE = re.compile(r"[^a-zA-Z0-9_-]+")


def _safe_segment(value: str) -> str:
    normalized = _SAFE_SEGMENT_RE.sub("_", value).strip("_")
    return normalized or "unknown"


def build_interactive_session_key(
    *,
    provider: str,
    agent_name: str,
    scope_kind: str,
    scope_id: str,
    surface: str,
) -> str:
    """Build a stable metadata key for an interactive session."""

    return ":".join(
        [
            "interactive_session",
            _safe_segment(provider),
            _safe_segment(agent_name),
            _safe_segment(scope_kind),
            _safe_segment(scope_id),
            _safe_segment(surface),
        ]
    )


def build_tmux_session_name(session_key: str) -> str:
    """Build a short tmux-safe name from the interactive session key."""

    digest = hashlib.sha1(session_key.encode("utf-8")).hexdigest()[:16]
    return f"mc-int-{digest}"


@dataclass(frozen=True)
class InteractiveSessionIdentity:
    """Stable identity for an interactive provider session."""

    provider: str
    agent_name: str
    scope_kind: str
    scope_id: str
    surface: str

    @property
    def session_key(self) -> str:
        return build_interactive_session_key(
            provider=self.provider,
            agent_name=self.agent_name,
            scope_kind=self.scope_kind,
            scope_id=self.scope_id,
            surface=self.surface,
        )

    @property
    def tmux_session_name(self) -> str:
        return build_tmux_session_name(self.session_key)

    def to_metadata(
        self,
        *,
        status: str,
        capabilities: list[str],
        timestamp: str,
    ) -> dict[str, Any]:
        return {
            "session_id": self.session_key,
            "agent_name": self.agent_name,
            "provider": self.provider,
            "scope_kind": self.scope_kind,
            "scope_id": self.scope_id,
            "surface": self.surface,
            "tmux_session": self.tmux_session_name,
            "status": status,
            "capabilities": capabilities,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
