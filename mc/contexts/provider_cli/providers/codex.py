"""Codex-specific implementation of the ProviderCLIParser protocol."""

from __future__ import annotations

import re
import signal
from typing import Any

from mc.contexts.provider_cli.types import (
    ParsedCliEvent,
    ProviderProcessHandle,
    ProviderSessionSnapshot,
)

# Pattern: "Session: <session-id>" in Codex stdout
_SESSION_ID_RE = re.compile(r"(?i)session[:\s]+([a-zA-Z0-9_\-]{4,})")

# Pattern: approval/confirmation requests emitted by Codex CLI
_APPROVAL_RE = re.compile(
    r"(?i)(approval\s+required|awaiting\s+approval"
    r"|requires?\s+approval|confirm|permission\s+requested)",
)

# Pattern: error lines
_ERROR_RE = re.compile(r"(?i)^\s*(error|fatal|exception)[:\s]")


class CodexCLIParser:
    """Codex-specific ProviderCLIParser implementation.

    Adapts the Codex CLI process to the shared provider CLI parser protocol.
    Handles session-id discovery from stdout, normalizes output into
    ParsedCliEvent objects, and delegates process-level controls to the
    provided ProviderProcessSupervisor.
    """

    provider_name: str = "codex"

    def __init__(self, *, supervisor: Any | None = None) -> None:
        self._supervisor = supervisor
        self._discovered_session_id: str | None = None

    def _get_supervisor(self) -> Any:
        if self._supervisor is None:
            from mc.runtime.provider_cli.process_supervisor import (
                ProviderProcessSupervisor,
            )

            self._supervisor = ProviderProcessSupervisor()
        return self._supervisor

    async def start_session(
        self,
        mc_session_id: str,
        command: list[str],
        cwd: str,
        env: dict[str, str] | None = None,
    ) -> ProviderProcessHandle:
        """Launch the Codex CLI and return a process handle."""
        return await self._get_supervisor().launch(
            mc_session_id=mc_session_id,
            provider=self.provider_name,
            command=command,
            cwd=cwd,
            env=env,
        )

    def parse_output(self, chunk: bytes) -> list[ParsedCliEvent]:
        """Parse a raw output chunk from the Codex CLI into normalized events."""
        if not chunk:
            return []

        text = chunk.decode("utf-8", errors="replace")
        events: list[ParsedCliEvent] = []

        for line in text.splitlines(keepends=True):
            stripped = line.strip()
            if not stripped:
                continue

            session_match = _SESSION_ID_RE.search(stripped)
            if session_match:
                session_id = session_match.group(1)
                self._discovered_session_id = session_id
                events.append(
                    ParsedCliEvent(
                        kind="session_discovered",
                        text=stripped,
                        provider_session_id=session_id,
                        metadata={"raw_line": stripped},
                    )
                )
                events.append(ParsedCliEvent(kind="output", text=stripped))
                continue

            if _APPROVAL_RE.search(stripped):
                events.append(
                    ParsedCliEvent(
                        kind="approval_requested",
                        text=stripped,
                        metadata={"raw_line": stripped},
                    )
                )
                events.append(ParsedCliEvent(kind="output", text=stripped))
                continue

            if _ERROR_RE.match(stripped):
                events.append(
                    ParsedCliEvent(
                        kind="error",
                        text=stripped,
                        metadata={"raw_line": stripped},
                    )
                )
                continue

            events.append(ParsedCliEvent(kind="output", text=stripped))

        return events

    async def discover_session(self, handle: ProviderProcessHandle) -> ProviderSessionSnapshot:
        """Return a ProviderSessionSnapshot for the running Codex process."""
        return ProviderSessionSnapshot(
            mc_session_id=handle.mc_session_id,
            provider_session_id=self._discovered_session_id,
            mode="provider-native",
            supports_resume=True,
            supports_interrupt=True,
            supports_stop=True,
        )

    async def inspect_process_tree(self, handle: ProviderProcessHandle) -> dict[str, Any]:
        """Delegate to ProviderProcessSupervisor.inspect_process_tree()."""
        return await self._get_supervisor().inspect_process_tree(handle)

    async def interrupt(self, handle: ProviderProcessHandle) -> None:
        """Send SIGINT to the Codex process group via the supervisor."""
        await self._get_supervisor().send_signal(handle, signal.SIGINT)

    async def resume(self, handle: ProviderProcessHandle, message: str) -> None:
        """Resume a waiting Codex session by sending the approval text to stdin."""
        resume_message = message.rstrip("\n")
        await self._get_supervisor().write_stdin(handle, f"{resume_message}\n")

    async def stop(self, handle: ProviderProcessHandle) -> None:
        """Send SIGTERM to the Codex process group via the supervisor."""
        await self._get_supervisor().terminate(handle)
