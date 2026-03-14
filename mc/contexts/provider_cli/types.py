"""Shared types for the provider CLI session abstraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParsedCliEvent:
    """A normalized event produced by parsing raw provider CLI output."""

    kind: str
    """Event kind: 'output', 'progress', 'tool', 'session_ready', 'session_failed', etc."""

    content: str
    """Raw text content associated with the event."""

    session_key: str
    """The MC-owned session key this event belongs to."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Optional supplemental metadata for the event."""


@dataclass(frozen=True)
class ProviderProcessHandle:
    """Runtime process metadata for a launched provider CLI session."""

    pid: int
    """Process ID of the launched provider CLI."""

    pgid: int
    """Process group ID for signalling the full process tree. 0 if unknown."""

    session_key: str
    """The MC-owned session key associated with this process."""

    child_pids: tuple[int, ...] = field(default_factory=tuple)
    """Known child PIDs (e.g. subagent processes)."""


@dataclass(frozen=True)
class ProviderSessionSnapshot:
    """Canonical snapshot of a provider session after discovery.

    Distinguishes between:
    - ``"provider-native"``: the provider owns a native resume id (e.g. Claude Code)
    - ``"runtime-owned"``: MC owns session continuity via ``session_key`` (e.g. Nanobot)
    """

    session_key: str
    """The MC-owned key that identifies this session."""

    mode: str
    """Session mode: 'runtime-owned' or 'provider-native'."""

    supports_resume: bool
    """Whether the provider supports native session resume."""

    provider: str
    """Provider identifier (e.g. 'mc', 'claude-code', 'codex')."""

    provider_session_id: str | None = None
    """Provider-native session id, if available. None for runtime-owned sessions."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Supplemental metadata surfaced from subagents or child processes."""
