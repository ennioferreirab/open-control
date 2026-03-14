"""ProviderCLIParser protocol definition."""

from __future__ import annotations

from typing import Any, Protocol

from mc.contexts.provider_cli.types import ParsedCliEvent, ProviderProcessHandle, ProviderSessionSnapshot


class ProviderCLIParser(Protocol):
    """Protocol for provider-specific CLI adapters."""

    provider_name: str

    async def start_session(
        self,
        mc_session_id: str,
        command: list[str],
        cwd: str,
        env: dict[str, str] | None = None,
    ) -> ProviderProcessHandle:
        """Launch the provider CLI and return a process handle."""
        ...

    def parse_output(self, chunk: bytes) -> list[ParsedCliEvent]:
        """Parse a raw output chunk into normalized CLI events."""
        ...

    async def discover_session(self, handle: ProviderProcessHandle) -> ProviderSessionSnapshot:
        """Inspect the running process to discover its provider session identity."""
        ...

    async def inspect_process_tree(self, handle: ProviderProcessHandle) -> dict[str, Any]:
        """Return a snapshot of the process tree rooted at the handle's pgid."""
        ...

    async def interrupt(self, handle: ProviderProcessHandle) -> None:
        """Send an interrupt signal to the provider process tree."""
        ...

    async def resume(self, handle: ProviderProcessHandle, message: str) -> None:
        """Resume a waiting provider session with the given message."""
        ...

    async def stop(self, handle: ProviderProcessHandle) -> None:
        """Terminate the provider process tree."""
        ...
