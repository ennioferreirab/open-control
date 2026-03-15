"""ProviderCliControlPlane — routes intervention commands to real subprocesses.

Single entry point for interrupt, stop, and resume. Delegates to
HumanInterventionController (state machine) and holds parser/handle
references registered by the strategy during execution.
"""

from __future__ import annotations

import logging
from typing import Any

from mc.contexts.provider_cli.registry import ProviderSessionRegistry
from mc.runtime.provider_cli.intervention import HumanInterventionController

logger = logging.getLogger(__name__)


class ProviderCliControlPlane:
    """Route interrupt/stop/resume to active provider-cli subprocesses."""

    def __init__(
        self,
        *,
        registry: ProviderSessionRegistry,
    ) -> None:
        self._registry = registry
        self._intervention = HumanInterventionController(registry=registry)
        self._parsers: dict[str, dict[str, Any]] = {}

    def register_parser(
        self,
        mc_session_id: str,
        *,
        parser: Any,
        handle: Any,
    ) -> None:
        """Register parser and handle for an active session.

        Called by the strategy after launching a session so that subsequent
        commands can reach the right subprocess.
        """
        self._parsers[mc_session_id] = {"parser": parser, "handle": handle}

    def unregister_parser(self, mc_session_id: str) -> None:
        """Remove parser/handle registration after session ends."""
        self._parsers.pop(mc_session_id, None)

    def get_session_info(self, mc_session_id: str) -> dict[str, Any] | None:
        """Return registry record as dict, or None if not found."""
        record = self._registry.get(mc_session_id)
        if record is None:
            return None
        return {
            "mc_session_id": record.mc_session_id,
            "provider": record.provider,
            "status": record.status.value,
            "provider_session_id": record.provider_session_id,
            "pid": record.pid,
        }

    async def interrupt(self, mc_session_id: str) -> dict[str, Any]:
        """Interrupt the provider-cli subprocess for the given session."""
        error = self._validate(mc_session_id)
        if error is not None:
            return error

        entry = self._parsers[mc_session_id]
        try:
            await self._intervention.interrupt(
                mc_session_id, entry["handle"], entry["parser"]
            )
            return {"mc_session_id": mc_session_id, "action": "interrupt", "outcome": "applied"}
        except Exception as exc:
            return {
                "mc_session_id": mc_session_id,
                "action": "interrupt",
                "outcome": "failed",
                "error": str(exc),
            }

    async def stop(self, mc_session_id: str) -> dict[str, Any]:
        """Stop (terminate) the provider-cli subprocess."""
        error = self._validate(mc_session_id)
        if error is not None:
            return error

        entry = self._parsers[mc_session_id]
        try:
            await self._intervention.stop(
                mc_session_id, entry["handle"], entry["parser"]
            )
            return {"mc_session_id": mc_session_id, "action": "stop", "outcome": "applied"}
        except Exception as exc:
            return {
                "mc_session_id": mc_session_id,
                "action": "stop",
                "outcome": "failed",
                "error": str(exc),
            }

    async def resume(self, mc_session_id: str, *, message: str) -> dict[str, Any]:
        """Resume a paused provider-cli subprocess."""
        error = self._validate(mc_session_id)
        if error is not None:
            return error

        entry = self._parsers[mc_session_id]
        try:
            await self._intervention.resume(
                mc_session_id, entry["handle"], message, entry["parser"]
            )
            return {"mc_session_id": mc_session_id, "action": "resume", "outcome": "applied"}
        except Exception as exc:
            return {
                "mc_session_id": mc_session_id,
                "action": "resume",
                "outcome": "failed",
                "error": str(exc),
            }

    def _validate(self, mc_session_id: str) -> dict[str, Any] | None:
        """Return error dict if session not ready for commands, else None."""
        if self._registry.get(mc_session_id) is None:
            return {"mc_session_id": mc_session_id, "error": "session_not_found"}
        if mc_session_id not in self._parsers:
            return {"mc_session_id": mc_session_id, "error": "parser_not_registered"}
        return None
