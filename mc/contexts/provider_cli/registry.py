"""In-memory registry for provider CLI session records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mc.contexts.provider_cli.types import SessionStatus

# Valid state transitions for provider CLI sessions
_VALID_TRANSITIONS: dict[SessionStatus, set[SessionStatus]] = {
    SessionStatus.STARTING: {SessionStatus.RUNNING, SessionStatus.CRASHED},
    SessionStatus.RUNNING: {
        SessionStatus.WAITING_FOR_INPUT,
        SessionStatus.INTERRUPTING,
        SessionStatus.COMPLETED,
        SessionStatus.CRASHED,
        SessionStatus.STOPPED,
    },
    SessionStatus.WAITING_FOR_INPUT: {
        SessionStatus.RUNNING,
        SessionStatus.RESUMING,
        SessionStatus.INTERRUPTING,
        SessionStatus.STOPPED,
        SessionStatus.CRASHED,
    },
    SessionStatus.INTERRUPTING: {
        SessionStatus.HUMAN_INTERVENING,
        SessionStatus.RUNNING,
        SessionStatus.STOPPED,
        SessionStatus.CRASHED,
    },
    SessionStatus.HUMAN_INTERVENING: {
        SessionStatus.RESUMING,
        SessionStatus.STOPPED,
        SessionStatus.CRASHED,
    },
    SessionStatus.RESUMING: {
        SessionStatus.RUNNING,
        SessionStatus.CRASHED,
    },
    SessionStatus.COMPLETED: set(),
    SessionStatus.STOPPED: set(),
    SessionStatus.CRASHED: set(),
}


@dataclass
class ProviderSessionRecord:
    """Canonical MC session record for a running provider CLI session."""

    mc_session_id: str
    provider: str
    provider_session_id: str | None
    pid: int
    pgid: int | None
    child_pids: list[int]
    mode: str
    status: SessionStatus
    supports_resume: bool
    supports_interrupt: bool
    supports_stop: bool
    extra: dict[str, Any] = field(default_factory=dict)


class ProviderSessionRegistry:
    """In-memory registry for provider CLI session records.

    Stores session records keyed by mc_session_id.  State transitions are
    validated against a strict state machine.  This implementation is
    intentionally Convex-free; a later story will wire it to the bridge.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, ProviderSessionRecord] = {}

    def create(
        self,
        *,
        mc_session_id: str,
        provider: str,
        pid: int,
        pgid: int | None,
        mode: str,
        supports_resume: bool,
        supports_interrupt: bool,
        supports_stop: bool,
        provider_session_id: str | None = None,
        child_pids: list[int] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ProviderSessionRecord:
        """Register a new session record.  Raises if mc_session_id already exists."""
        if mc_session_id in self._sessions:
            raise ValueError(f"Session already registered: {mc_session_id}")
        record = ProviderSessionRecord(
            mc_session_id=mc_session_id,
            provider=provider,
            provider_session_id=provider_session_id,
            pid=pid,
            pgid=pgid,
            child_pids=list(child_pids or []),
            mode=mode,
            status=SessionStatus.STARTING,
            supports_resume=supports_resume,
            supports_interrupt=supports_interrupt,
            supports_stop=supports_stop,
            extra=dict(extra or {}),
        )
        self._sessions[mc_session_id] = record
        return record

    def get(self, mc_session_id: str) -> ProviderSessionRecord | None:
        """Return the session record for *mc_session_id*, or None if not found."""
        return self._sessions.get(mc_session_id)

    def require(self, mc_session_id: str) -> ProviderSessionRecord:
        """Return the session record or raise ValueError."""
        record = self.get(mc_session_id)
        if record is None:
            raise ValueError(f"Session not found: {mc_session_id}")
        return record

    def update_status(self, mc_session_id: str, new_status: SessionStatus) -> ProviderSessionRecord:
        """Transition *mc_session_id* to *new_status*.

        Raises ValueError if the transition is not permitted by the state machine.
        """
        record = self.require(mc_session_id)
        allowed = _VALID_TRANSITIONS.get(record.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid status transition for {mc_session_id}: "
                f"{record.status.value} -> {new_status.value}"
            )
        record.status = new_status
        return record

    def update_provider_session_id(
        self, mc_session_id: str, provider_session_id: str
    ) -> ProviderSessionRecord:
        """Set or update the provider-side session id."""
        record = self.require(mc_session_id)
        record.provider_session_id = provider_session_id
        return record

    def update_child_pids(self, mc_session_id: str, child_pids: list[int]) -> ProviderSessionRecord:
        """Replace the child_pids list for the session."""
        record = self.require(mc_session_id)
        record.child_pids = list(child_pids)
        return record

    def list_sessions(self) -> list[ProviderSessionRecord]:
        """Return all registered session records."""
        return list(self._sessions.values())

    def remove(self, mc_session_id: str) -> None:
        """Remove a session record from the registry."""
        self._sessions.pop(mc_session_id, None)
