"""Nanobot runtime-owned provider CLI parser.

Nanobot sessions are owned entirely by Mission Control.  There is no
provider-native resume id — session continuity runs through MC's internal
``session_key``.  This parser therefore declares ``mode="runtime-owned"`` and
``supports_resume=False``.

Interrupt and stop map to POSIX signals sent to the process group.  Resume
is not supported and raises ``NotImplementedError``.

Subagent or child-process metadata surfaced by the nanobot runtime can be
passed into ``discover_session`` via ``subagent_metadata`` and will appear in
the resulting ``ProviderSessionSnapshot.metadata``.
"""

from __future__ import annotations

import os
import signal
from typing import Any

from mc.contexts.provider_cli.types import (
    ParsedCliEvent,
    ProviderProcessHandle,
    ProviderSessionSnapshot,
)

# Output line prefixes emitted by NanobotInteractiveSessionRunner
_PREFIX_PROGRESS = "[progress]"
_PREFIX_TOOL = "[tool]"
_PREFIX_NANOBOT_LIVE = "[nanobot-live]"
_SESSION_READY_MARKER = "Session ready"


class NanobotCLIParser:
    """ProviderCLIParser implementation for Nanobot in runtime-owned mode.

    Session continuity is managed by Mission Control via the ``session_key``
    model.  There is no provider-native external resume id.
    """

    # ------------------------------------------------------------------
    # Session discovery
    # ------------------------------------------------------------------

    def discover_session(
        self,
        session_key: str,
        *,
        subagent_metadata: dict[str, Any] | None = None,
    ) -> ProviderSessionSnapshot:
        """Return a runtime-owned snapshot for a Nanobot session.

        Args:
            session_key: The MC-owned session key.
            subagent_metadata: Optional metadata from running nanobot subagents
                or child processes to surface in the snapshot.

        Returns:
            A ``ProviderSessionSnapshot`` with ``mode="runtime-owned"`` and
            ``supports_resume=False``.  ``provider_session_id`` is always
            ``None`` because Nanobot does not expose a provider-native id.
        """
        return ProviderSessionSnapshot(
            session_key=session_key,
            mode="runtime-owned",
            supports_resume=False,
            provider="mc",
            provider_session_id=None,
            metadata=dict(subagent_metadata) if subagent_metadata else {},
        )

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    def parse_output(self, raw: str, *, session_key: str) -> list[ParsedCliEvent]:
        """Parse a raw stdout/stderr line into normalized ``ParsedCliEvent`` objects.

        Recognises the prefixes emitted by ``NanobotInteractiveSessionRunner``
        and maps them to canonical event kinds:

        - ``[progress] …``      → ``"progress"``
        - ``[tool] …``          → ``"tool"``
        - ``[nanobot-live] Session ready…`` → ``"session_ready"``
        - ``[nanobot-live] …``  → ``"session_failed"`` (error lines)
        - any other non-blank   → ``"output"``

        Returns an empty list for blank or whitespace-only input.
        """
        text = raw.strip()
        if not text:
            return []

        kind: str
        if text.startswith(_PREFIX_PROGRESS):
            kind = "progress"
        elif text.startswith(_PREFIX_TOOL):
            kind = "tool"
        elif text.startswith(_PREFIX_NANOBOT_LIVE):
            if _SESSION_READY_MARKER in text:
                kind = "session_ready"
            else:
                kind = "session_failed"
        else:
            kind = "output"

        return [ParsedCliEvent(kind=kind, content=text, session_key=session_key)]

    # ------------------------------------------------------------------
    # Process signals
    # ------------------------------------------------------------------

    def interrupt(self, handle: ProviderProcessHandle) -> None:
        """Send SIGINT to the nanobot process group to cancel the current turn.

        Falls back to signalling the individual PID when ``pgid`` is 0.
        """
        if handle.pgid:
            os.killpg(handle.pgid, signal.SIGINT)
        else:
            os.kill(handle.pid, signal.SIGINT)

    def stop(self, handle: ProviderProcessHandle) -> None:
        """Send SIGTERM to the nanobot process group to terminate the session.

        Falls back to signalling the individual PID when ``pgid`` is 0.
        """
        if handle.pgid:
            os.killpg(handle.pgid, signal.SIGTERM)
        else:
            os.kill(handle.pid, signal.SIGTERM)

    def resume(self, handle: ProviderProcessHandle, *, resume_id: str | None) -> None:
        """Resume is not supported for runtime-owned Nanobot sessions.

        Session continuity for Nanobot is owned by Mission Control through the
        ``session_key`` model.  There is no provider-native resume contract to
        invoke.  Callers should re-launch a new session instead.

        Raises:
            NotImplementedError: Always, because runtime-owned sessions do not
                support provider-native resume.
        """
        raise NotImplementedError(
            "Nanobot uses runtime-owned session continuity via session_key. "
            "Provider-native resume is not supported for runtime-owned sessions."
        )
