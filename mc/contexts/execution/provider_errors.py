"""Provider error policy helpers for task execution."""

from __future__ import annotations


def _collect_provider_error_types() -> tuple[type[Exception], ...]:
    """Collect provider-specific exception types for targeted catching."""
    from mc.infrastructure.providers.errors import ProviderError

    return (ProviderError,)


PROVIDER_ERRORS = _collect_provider_error_types()


def _provider_error_action(exc: Exception) -> str:
    """Extract the best user-facing recovery command for a provider error."""
    from mc.infrastructure.providers.errors import ProviderError

    if isinstance(exc, ProviderError) and exc.action:
        return exc.action

    msg = str(exc)
    if "Run:" in msg:
        return msg[msg.index("Run:") :]
    return "Check provider configuration in ~/.open-control/config.json"
