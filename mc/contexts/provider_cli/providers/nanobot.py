"""Nanobot runtime-owned provider CLI parser.

Nanobot sessions are owned entirely by Mission Control.  There is no
provider-native resume id — session continuity runs through MC's internal
``session_key``.  This parser therefore declares ``mode="runtime-owned"`` and
``supports_resume=False``.

Interrupt and stop map to POSIX signals sent to the process group.  Resume
is not supported and raises ``NotImplementedError``.
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

    provider_name: str = "nanobot"

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def start_session(
        self,
        mc_session_id: str,
        command: list[str],
        cwd: str,
        env: dict[str, str] | None = None,
    ) -> ProviderProcessHandle:
        """Launch the nanobot CLI process via the supervisor."""
        supervisor = self._get_supervisor()
        return await supervisor.launch(
            mc_session_id=mc_session_id,
            provider=self.provider_name,
            command=command,
            cwd=cwd,
            env=env,
        )

    def __init__(self, *, supervisor: Any | None = None) -> None:
        self._supervisor = supervisor

    def _get_supervisor(self) -> Any:
        if self._supervisor is None:
            from mc.runtime.provider_cli.process_supervisor import ProviderProcessSupervisor

            self._supervisor = ProviderProcessSupervisor()
        return self._supervisor

    # ------------------------------------------------------------------
    # Session discovery
    # ------------------------------------------------------------------

    async def discover_session(
        self,
        handle: ProviderProcessHandle,
    ) -> ProviderSessionSnapshot:
        """Return a runtime-owned snapshot for a Nanobot session."""
        return ProviderSessionSnapshot(
            mc_session_id=handle.mc_session_id,
            mode="runtime-owned",
            supports_resume=False,
            supports_interrupt=True,
            supports_stop=True,
            provider_session_id=None,
        )

    async def inspect_process_tree(self, handle: ProviderProcessHandle) -> dict[str, Any]:
        """Return process tree info."""
        return {"pid": handle.pid, "pgid": handle.pgid}

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    def parse_output(self, chunk: bytes) -> list[ParsedCliEvent]:
        """Parse raw stdout/stderr into normalized ``ParsedCliEvent`` objects.

        Recognises the prefixes emitted by ``NanobotInteractiveSessionRunner``
        and maps them to canonical event kinds.
        """
        if not chunk:
            return []

        raw: str = chunk.decode("utf-8", errors="replace") if isinstance(chunk, bytes) else chunk
        events: list[ParsedCliEvent] = []

        for line in raw.splitlines():
            text = line.strip()
            if not text:
                continue

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

            events.append(ParsedCliEvent(kind=kind, text=text))

        return events

    # ------------------------------------------------------------------
    # Process signals
    # ------------------------------------------------------------------

    async def interrupt(self, handle: ProviderProcessHandle) -> None:
        """Send SIGINT to the nanobot process group."""
        if handle.pgid:
            os.killpg(handle.pgid, signal.SIGINT)
        else:
            os.kill(handle.pid, signal.SIGINT)

    async def stop(self, handle: ProviderProcessHandle) -> None:
        """Send SIGTERM to the nanobot process group."""
        if handle.pgid:
            os.killpg(handle.pgid, signal.SIGTERM)
        else:
            os.kill(handle.pid, signal.SIGTERM)

    async def resume(self, handle: ProviderProcessHandle, message: str) -> None:
        """Resume is not supported for runtime-owned Nanobot sessions."""
        raise NotImplementedError(
            "Nanobot uses runtime-owned session continuity via session_key. "
            "Provider-native resume is not supported."
        )
