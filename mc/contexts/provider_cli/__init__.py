"""Provider CLI session abstraction for Mission Control.

This package provides the provider-agnostic contract for owning provider CLI
sessions from the runtime — without depending on PTY, xterm, or tmux transport.

Public API:
- ``ProviderCLIParser`` — structural Protocol all parsers must satisfy
- ``ParsedCliEvent`` — normalized output event from a provider process
- ``ProviderProcessHandle`` — process metadata (pid, pgid, session_key)
- ``ProviderSessionSnapshot`` — canonical session metadata after discovery
"""

from mc.contexts.provider_cli.parser import ProviderCLIParser
from mc.contexts.provider_cli.types import (
    ParsedCliEvent,
    ProviderProcessHandle,
    ProviderSessionSnapshot,
)

__all__ = [
    "ParsedCliEvent",
    "ProviderCLIParser",
    "ProviderProcessHandle",
    "ProviderSessionSnapshot",
]
