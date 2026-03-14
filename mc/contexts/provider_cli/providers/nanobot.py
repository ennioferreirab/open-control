"""Nanobot runtime-owned provider CLI parser.

Nanobot uses a runtime-owned session model — it does NOT have native external
``--resume <session_id>`` semantics.  Session continuity is maintained through
the internal ``session_key`` and loop ownership managed by Mission Control.

This parser:
- declares ``mode="runtime-owned"``
- extracts ``session_key`` from Nanobot subprocess output
- maps interrupt to SIGINT (cancels the active agent loop)
- raises ``NotImplementedError`` for ``resume`` (MC runtime owns continuity)
- delegates process-tree inspection to ``ProviderProcessSupervisor``
"""

from __future__ import annotations

import re
import signal
from typing import Any

from mc.contexts.provider_cli.types import (
    ParsedCliEvent,
    ProviderProcessHandle,
    ProviderSessionSnapshot,
)

# Patterns for parsing Nanobot subprocess stdout/stderr
_SESSION_KEY_RE = re.compile(r"\bMC_INTERACTIVE_SESSION_ID\s*[=:]\s*(\S+)")
_SESSION_READY_RE = re.compile(r"\[nanobot-live\]\s+session\s+ready", re.IGNORECASE)
_TURN_STARTED_RE = re.compile(r"\[nanobot-live\]\s+.*turn\s+started", re.IGNORECASE)
_TURN_COMPLETED_RE = re.compile(r"\[nanobot-live\]\s+.*turn\s+completed", re.IGNORECASE)
_SESSION_STOPPED_RE = re.compile(
    r"\[nanobot-live\]\s+.*(?:session.*(?:stopped|ended)"
    r"|stopped.*session|ended.*session)",
    re.IGNORECASE,
)
_SESSION_FAILED_RE = re.compile(r"\[nanobot-live\]\s+.*(?:failed\b|error:)", re.IGNORECASE)
_PROGRESS_RE = re.compile(r"^\[progress\]\s+(.*)", re.MULTILINE)
_TOOL_RE = re.compile(r"^\[tool\]\s+(.*)", re.MULTILINE)
_SUBAGENT_RE = re.compile(
    r"\b(?:spawning|spawn|launching|started)\s+(?:sub)?agent\b", re.IGNORECASE
)
_ERROR_RE = re.compile(r"\b(?:Error|Exception|Traceback)\b")


class NanobotCLIParser:
    """ProviderCLIParser implementation for the Nanobot runtime-owned model.

    Key constraints:
    - ``supports_resume=False``: no CLI ``--resume`` flag.
    - ``supports_interrupt=True``: SIGINT cancels the active agent loop.
    - ``supports_stop=True``: SIGTERM gracefully stops the process.
    """

    provider_name = "mc"

    def __init__(
        self,
        *,
        supervisor: Any | None = None,
    ) -> None:
        self._supervisor = supervisor
        self._discovered_session_key: str | None = None

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
        """Launch Nanobot as a subprocess under MC process ownership."""
        return await self._get_supervisor().launch(
            mc_session_id=mc_session_id,
            provider=self.provider_name,
            command=command,
            cwd=cwd,
            env=env,
        )

    def parse_output(self, chunk: bytes) -> list[ParsedCliEvent]:
        """Parse a raw stdout/stderr chunk from the Nanobot subprocess."""
        text = chunk.decode("utf-8", errors="replace")
        events: list[ParsedCliEvent] = []

        for line in text.splitlines(keepends=True):
            stripped = line.rstrip("\n\r")
            if not stripped:
                continue

            m = _SESSION_KEY_RE.search(stripped)
            if m:
                self._discovered_session_key = m.group(1)
                events.append(
                    ParsedCliEvent(
                        kind="session_discovered",
                        text=stripped,
                        provider_session_id=self._discovered_session_key,
                        metadata={"session_key": self._discovered_session_key},
                    )
                )
                continue

            if _SESSION_READY_RE.search(stripped):
                events.append(
                    ParsedCliEvent(
                        kind="session_ready",
                        text=stripped,
                        provider_session_id=self._discovered_session_key,
                    )
                )
            elif _TURN_STARTED_RE.search(stripped):
                events.append(
                    ParsedCliEvent(
                        kind="turn_started",
                        text=stripped,
                        provider_session_id=self._discovered_session_key,
                    )
                )
            elif _TURN_COMPLETED_RE.search(stripped):
                events.append(
                    ParsedCliEvent(
                        kind="turn_completed",
                        text=stripped,
                        provider_session_id=self._discovered_session_key,
                    )
                )
            elif _SESSION_STOPPED_RE.search(stripped):
                events.append(
                    ParsedCliEvent(
                        kind="session_stopped",
                        text=stripped,
                        provider_session_id=self._discovered_session_key,
                    )
                )
            elif _SESSION_FAILED_RE.search(stripped):
                events.append(
                    ParsedCliEvent(
                        kind="error",
                        text=stripped,
                        provider_session_id=self._discovered_session_key,
                    )
                )
            elif _PROGRESS_RE.match(stripped):
                m2 = _PROGRESS_RE.match(stripped)
                events.append(
                    ParsedCliEvent(
                        kind="output",
                        text=m2.group(1) if m2 else stripped,
                        provider_session_id=self._discovered_session_key,
                        metadata={"source": "progress"},
                    )
                )
            elif _TOOL_RE.match(stripped):
                m3 = _TOOL_RE.match(stripped)
                events.append(
                    ParsedCliEvent(
                        kind="output",
                        text=m3.group(1) if m3 else stripped,
                        provider_session_id=self._discovered_session_key,
                        metadata={"source": "tool"},
                    )
                )
            elif _SUBAGENT_RE.search(stripped):
                events.append(
                    ParsedCliEvent(
                        kind="subagent_spawned",
                        text=stripped,
                        provider_session_id=self._discovered_session_key,
                    )
                )
            elif _ERROR_RE.search(stripped):
                events.append(
                    ParsedCliEvent(
                        kind="error",
                        text=stripped,
                        provider_session_id=self._discovered_session_key,
                    )
                )
            else:
                events.append(
                    ParsedCliEvent(
                        kind="output",
                        text=stripped,
                        provider_session_id=self._discovered_session_key,
                    )
                )

        return events

    async def discover_session(self, handle: ProviderProcessHandle) -> ProviderSessionSnapshot:
        """Return a runtime-owned session snapshot for the Nanobot process."""
        provider_session_id = self._discovered_session_key or handle.mc_session_id
        return ProviderSessionSnapshot(
            mc_session_id=handle.mc_session_id,
            provider_session_id=provider_session_id,
            mode="runtime-owned",
            supports_resume=False,
            supports_interrupt=True,
            supports_stop=True,
        )

    async def inspect_process_tree(self, handle: ProviderProcessHandle) -> dict[str, Any]:
        """Delegate process-tree inspection to the supervisor."""
        return await self._get_supervisor().inspect_process_tree(handle)

    async def interrupt(self, handle: ProviderProcessHandle) -> None:
        """Send SIGINT to the Nanobot process group."""
        await self._get_supervisor().send_signal(handle, signal.SIGINT)

    async def resume(self, handle: ProviderProcessHandle, message: str) -> None:
        """Not supported for runtime-owned Nanobot sessions.

        Raises:
            NotImplementedError: always.
        """
        raise NotImplementedError(
            "Nanobot uses runtime-owned session continuity via session_key. "
            "Use the MC runtime session management API instead of CLI resume."
        )

    async def stop(self, handle: ProviderProcessHandle) -> None:
        """Send SIGTERM to gracefully stop the Nanobot process."""
        await self._get_supervisor().terminate(handle)
