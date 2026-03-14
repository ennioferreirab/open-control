"""HumanInterventionController - coordinates interrupt, resume, and stop."""

from __future__ import annotations

from mc.contexts.provider_cli.parser import ProviderCLIParser
from mc.contexts.provider_cli.registry import ProviderSessionRegistry
from mc.contexts.provider_cli.types import ProviderProcessHandle, SessionStatus


class HumanInterventionController:
    """Orchestrates the human intervention lifecycle for provider CLI sessions.

    The controller coordinates state transitions in the registry and delegates
    signal/resume operations to the parser.  It does NOT own the registry —
    it reads and updates it as a coordinator.

    State machines enforced by the registry:
        interrupt: RUNNING -> INTERRUPTING -> HUMAN_INTERVENING
        resume:    HUMAN_INTERVENING -> RESUMING -> RUNNING
        stop:      <any active state> -> STOPPED
    """

    def __init__(
        self,
        *,
        registry: ProviderSessionRegistry,
    ) -> None:
        self._registry = registry

    async def interrupt(
        self,
        mc_session_id: str,
        handle: ProviderProcessHandle,
        parser: ProviderCLIParser,
    ) -> None:
        """Interrupt a running session and enter human-intervention state.

        Transitions: RUNNING -> INTERRUPTING -> HUMAN_INTERVENING.

        If the parser raises during interrupt, the session is transitioned to
        CRASHED and the exception is re-raised.
        """
        self._registry.update_status(mc_session_id, SessionStatus.INTERRUPTING)

        try:
            await parser.interrupt(handle)
        except Exception:
            self._registry.update_status(mc_session_id, SessionStatus.CRASHED)
            raise

        self._registry.update_status(mc_session_id, SessionStatus.HUMAN_INTERVENING)

    async def resume(
        self,
        mc_session_id: str,
        handle: ProviderProcessHandle,
        message: str,
        parser: ProviderCLIParser,
    ) -> None:
        """Resume a session from human-intervention state.

        Transitions: HUMAN_INTERVENING -> RESUMING -> RUNNING.

        If the parser raises, the session is transitioned to CRASHED.
        """
        self._registry.update_status(mc_session_id, SessionStatus.RESUMING)

        try:
            await parser.resume(handle, message)
        except Exception:
            self._registry.update_status(mc_session_id, SessionStatus.CRASHED)
            raise

        self._registry.update_status(mc_session_id, SessionStatus.RUNNING)

    async def stop(
        self,
        mc_session_id: str,
        handle: ProviderProcessHandle,
        parser: ProviderCLIParser,
    ) -> None:
        """Terminate the provider session explicitly.

        If parser.stop raises, the session is transitioned to CRASHED.
        """
        try:
            await parser.stop(handle)
        except Exception:
            self._registry.update_status(mc_session_id, SessionStatus.CRASHED)
            raise

        self._registry.update_status(mc_session_id, SessionStatus.STOPPED)

    def get_intervention_state(self, mc_session_id: str) -> SessionStatus:
        """Return the current lifecycle status for the given session."""
        record = self._registry.require(mc_session_id)
        return record.status
