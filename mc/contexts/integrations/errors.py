"""Typed error hierarchy for integration failures."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class IntegrationErrorKind(StrEnum):
    AUTH_EXPIRED = "auth_expired"
    RATE_LIMITED = "rate_limited"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    CAPABILITY_UNSUPPORTED = "capability_unsupported"
    MAPPING_NOT_FOUND = "mapping_not_found"
    VALIDATION_FAILED = "validation_failed"
    PLATFORM_ERROR = "platform_error"


@dataclass(frozen=True)
class IntegrationError(Exception):
    kind: IntegrationErrorKind
    message: str
    platform: str
    retryable: bool
    raw_error: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Exception.__init__ was bypassed by the frozen dataclass constructor.
        # Set Exception.args so str(e) returns a useful message.
        object.__setattr__(self, "args", (self.message,))
