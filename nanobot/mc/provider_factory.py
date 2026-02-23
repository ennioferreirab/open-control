"""
Shared provider factory — creates LLM providers from user config.

Extracted from executor.py and cli/commands.py to eliminate duplication.
Both the gateway executor and CLI commands import from this module.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    """Raised when provider creation fails with an actionable message."""

    def __init__(self, message: str, action: str | None = None) -> None:
        self.action = action or ""
        super().__init__(message)


def create_provider(model: str | None = None) -> tuple[Any, str]:
    """Create the LLM provider from the user's nanobot config.

    Resolves the provider type from config and returns the appropriate
    provider instance along with the resolved model string.

    Args:
        model: Optional model override. If None, uses config default.

    Returns:
        Tuple of (provider_instance, resolved_model_string).

    Raises:
        ProviderError: If the provider cannot be created (OAuth expired,
            missing dependency, invalid config, etc.) with an actionable
            message and ``action`` attribute.
    """
    from nanobot.config.loader import load_config

    config = load_config()
    default_model = config.agents.defaults.model
    resolved_model = model or default_model

    # If the caller supplied a bare model name (e.g. "claude-sonnet-4-6")
    # that doesn't resolve to a provider, check if the config default model
    # is the same base model with a provider prefix (e.g.
    # "anthropic-oauth/claude-sonnet-4-6").  If so, use the config default
    # so the correct provider is selected.
    provider_name = config.get_provider_name(resolved_model)
    if provider_name is None and model and "/" not in model:
        if default_model.endswith("/" + model):
            resolved_model = default_model
            provider_name = config.get_provider_name(resolved_model)

    p = config.get_provider(resolved_model)

    # Anthropic OAuth
    if provider_name == "anthropic_oauth" or resolved_model.startswith(
        "anthropic-oauth/"
    ):
        try:
            from nanobot.providers.anthropic_oauth_provider import (
                AnthropicOAuthProvider,
            )

            return AnthropicOAuthProvider(default_model=resolved_model), resolved_model
        except ImportError as exc:
            raise ProviderError(
                f"Anthropic OAuth provider not available: {exc}",
                action="pip install httpx  # required for Anthropic OAuth",
            ) from exc

    # OpenAI Codex (OAuth)
    if provider_name == "openai_codex" or resolved_model.startswith("openai-codex/"):
        try:
            from nanobot.providers.openai_codex_provider import OpenAICodexProvider

            return OpenAICodexProvider(default_model=resolved_model), resolved_model
        except ImportError as exc:
            raise ProviderError(
                f"OpenAI Codex provider not available: {exc}",
                action="pip install oauth-cli-kit  # required for OpenAI Codex",
            ) from exc

    # Custom provider
    if provider_name == "custom":
        from nanobot.providers.custom_provider import CustomProvider

        return (
            CustomProvider(
                api_key=p.api_key if p else "no-key",
                api_base=config.get_api_base(resolved_model)
                or "http://localhost:8000/v1",
                default_model=resolved_model,
            ),
            resolved_model,
        )

    # Default: LiteLLM
    from nanobot.providers.litellm_provider import LiteLLMProvider

    return (
        LiteLLMProvider(
            api_key=p.api_key if p else None,
            api_base=config.get_api_base(resolved_model),
            default_model=resolved_model,
            extra_headers=p.extra_headers if p else None,
            provider_name=provider_name,
        ),
        resolved_model,
    )
