"""Provider error types — independent of any specific provider implementation."""

from __future__ import annotations


class ProviderError(Exception):
    """Raised when a provider operation fails with an actionable message."""

    def __init__(self, message: str, action: str | None = None) -> None:
        self.action = action or ""
        super().__init__(message)
