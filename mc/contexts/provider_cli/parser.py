"""ProviderCLIParser Protocol — the generic contract for provider CLI parsers."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from mc.contexts.provider_cli.types import (
    ParsedCliEvent,
    ProviderProcessHandle,
    ProviderSessionSnapshot,
)


@runtime_checkable
class ProviderCLIParser(Protocol):
    """Structural protocol for provider-owned CLI session parsers.

    Implementations cover provider-native parsers (e.g. Claude Code, Codex) and
    runtime-owned parsers (e.g. Nanobot / MC).  The session mode is surfaced in
    the ``ProviderSessionSnapshot`` returned by ``discover_session``.
    """

    def discover_session(
        self,
        session_key: str,
        *,
        subagent_metadata: dict[str, Any] | None = None,
    ) -> ProviderSessionSnapshot:
        """Return a canonical session snapshot for the given MC session key.

        Args:
            session_key: The MC-owned session key.
            subagent_metadata: Optional child-process or subagent metadata to
                surface in the snapshot.  Runtime-owned parsers may enrich the
                snapshot with available process tree information here.

        Returns:
            A ``ProviderSessionSnapshot`` describing the session mode and
            available provider-side metadata.
        """
        ...

    def parse_output(self, raw: str, *, session_key: str) -> list[ParsedCliEvent]:
        """Parse a raw stdout/stderr line into zero or more normalized events.

        Returns an empty list when ``raw`` is blank or not parseable.
        """
        ...

    def interrupt(self, handle: ProviderProcessHandle) -> None:
        """Interrupt the running session (e.g. SIGINT to the process group)."""
        ...

    def resume(self, handle: ProviderProcessHandle, *, resume_id: str | None) -> None:
        """Resume a previously interrupted session.

        For runtime-owned sessions this is not supported and should raise
        ``NotImplementedError``.
        """
        ...

    def stop(self, handle: ProviderProcessHandle) -> None:
        """Terminate the session cleanly (e.g. SIGTERM to the process group)."""
        ...
