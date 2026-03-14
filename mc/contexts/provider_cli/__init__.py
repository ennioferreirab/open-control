"""Provider CLI session domain - shared types, parser protocol, and registry."""

from __future__ import annotations

from mc.contexts.provider_cli.parser import ProviderCLIParser
from mc.contexts.provider_cli.registry import ProviderSessionRegistry
from mc.contexts.provider_cli.types import (
    ParsedCliEvent,
    ProviderProcessHandle,
    ProviderSessionSnapshot,
    SessionStatus,
)

__all__ = [
    "ParsedCliEvent",
    "ProviderCLIParser",
    "ProviderProcessHandle",
    "ProviderSessionRegistry",
    "ProviderSessionSnapshot",
    "SessionStatus",
]
