"""
Shared provider factory — creates LLM providers from user config.

Extracted from executor.py and cli/commands.py to eliminate duplication.
Both the gateway executor and CLI commands import from this module.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _get_codex_token():
    """Try to get the Codex OAuth token. Raises if not authenticated."""
    from oauth_cli_kit import get_token

    return get_token()


def _merge_codex_models(models: list[str]) -> list[str]:
    """Append Codex models if the user is authenticated, without duplicates."""
    try:
        _get_codex_token()
    except Exception:
        return models
    from nanobot.providers.openai_codex_provider import CODEX_MODELS

    existing = set(models)
    return models + [m for m in CODEX_MODELS if m not in existing]


def _to_cc_prefix(models: list[str]) -> list[str]:
    """Replace anthropic-oauth/ prefix with cc/ so models route through Claude Code backend."""
    result: list[str] = []
    for m in models:
        if m.startswith("anthropic-oauth/") or m.startswith("anthropic_oauth/"):
            result.append("cc/" + m.split("/", 1)[1])
        else:
            result.append(m)
    return result


def list_available_models() -> list[str]:
    """Return model identifiers available from the configured provider.

    Priority:
      1. agents.models in config — explicit user-defined list (base).
      2. Authenticated OAuth providers — Codex models merged in if token exists.
      3. Provider API query — e.g. GET /v1/models for OpenRouter, Anthropic, etc.
      4. Fallback — just the default model if everything else fails.

    Anthropic OAuth models are exposed with the cc/ prefix so they route
    through the Claude Code backend instead of the direct OAuth provider.
    """
    from nanobot.config.loader import load_config

    config = load_config()
    default_model = config.agents.defaults.model

    # 1. Explicit user-defined list as base
    if config.agents.models:
        models: list[str] = list(config.agents.models)
        # 2. Merge Codex models if authenticated
        return _to_cc_prefix(_merge_codex_models(models))

    # 2. Query the active provider's models endpoint
    try:
        provider, _ = create_provider(model=None)
        models_from_api = provider.list_models()
        if models_from_api:
            return _to_cc_prefix(_merge_codex_models(models_from_api))
    except Exception as e:
        logger.warning("list_available_models: provider query failed: %s", e)

    # 4. Fallback
    base = [default_model] if default_model else []
    return _to_cc_prefix(_merge_codex_models(base))


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

    # cc/ prefix means "Claude Code backend model" (e.g. "cc/claude-sonnet-4-6").
    # The cc/ prefix is only valid for the Claude Code executor; for regular LLM
    # calls strip the prefix so the bare model name can be resolved normally.
    if resolved_model.startswith("cc/"):
        resolved_model = resolved_model[len("cc/") :]

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

    # If the model uses a "plain" provider prefix (e.g. "anthropic/claude-haiku-3-5")
    # but the user configured an OAuth/custom variant (e.g. "anthropic-oauth/..."),
    # inherit the default provider's prefix for the same model family.
    # E.g. standard-low="anthropic/claude-haiku-3-5" + default="anthropic-oauth/claude-sonnet-4-6"
    #   → resolved as "anthropic-oauth/claude-haiku-3-5" so OAuth auth is used.
    if provider_name is None and model and "/" in model:
        _model_prefix = model.split("/", 1)[0]
        _model_base = model.split("/", 1)[1]
        if "/" in default_model:
            _default_prefix = default_model.rsplit("/", 1)[0]
            if _default_prefix.startswith(_model_prefix):
                _candidate = f"{_default_prefix}/{_model_base}"
                _candidate_pn = config.get_provider_name(_candidate)
                if _candidate_pn is not None:
                    logger.debug(
                        "create_provider: remapped %s → %s (inherit default provider prefix)",
                        resolved_model,
                        _candidate,
                    )
                    resolved_model = _candidate
                    provider_name = _candidate_pn

    p = config.get_provider(resolved_model)

    # Anthropic OAuth
    if provider_name == "anthropic_oauth" or resolved_model.startswith("anthropic-oauth/"):
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

            from mc.infrastructure.providers.tool_adapters import (
                AdaptedProvider,
                CodexToolAdapter,
            )

            raw_provider = OpenAICodexProvider(default_model=resolved_model)
            return AdaptedProvider(
                inner=raw_provider, tool_adapter=CodexToolAdapter()
            ), resolved_model
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
                api_base=config.get_api_base(resolved_model) or "http://localhost:8000/v1",
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
