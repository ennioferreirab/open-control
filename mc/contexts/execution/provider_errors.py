"""Provider error policy helpers for task execution."""

from __future__ import annotations


def _collect_provider_error_types() -> tuple[type[Exception], ...]:
    """Collect provider-specific exception types for targeted catching."""
    from mc.infrastructure.providers.factory import ProviderError

    types: list[type[Exception]] = [ProviderError]
    try:
        from nanobot.providers.anthropic_oauth import AnthropicOAuthExpired

        types.append(AnthropicOAuthExpired)
    except ImportError:
        pass
    return tuple(types)


PROVIDER_ERRORS = _collect_provider_error_types()


def _provider_error_action(exc: Exception) -> str:
    """Extract the best user-facing recovery command for a provider error."""
    from mc.infrastructure.providers.factory import ProviderError

    if isinstance(exc, ProviderError) and exc.action:
        return exc.action

    msg = str(exc)
    if "Run:" in msg:
        return msg[msg.index("Run:") :]
    return "Check provider configuration in ~/.nanobot/config.json"
