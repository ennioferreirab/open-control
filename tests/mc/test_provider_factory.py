"""Tests for provider_factory — Story 8.5, Task 3 & Task 6."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mc.infrastructure.providers.factory import ProviderError, create_provider

# ---------------------------------------------------------------------------
# 6.3: Test the shared provider factory with each provider type
# ---------------------------------------------------------------------------


class TestCreateProviderAnthropicOAuth:
    """Test create_provider for the anthropic_oauth provider type."""

    def test_returns_anthropic_oauth_provider(self):
        """When provider_name is anthropic_oauth, return AnthropicOAuthProvider."""
        mock_config = MagicMock()
        mock_config.agents.defaults.model = "anthropic-oauth/claude-sonnet-4-6"
        mock_config.get_provider_name.return_value = "anthropic_oauth"
        mock_config.get_provider.return_value = None

        mock_provider_instance = MagicMock()
        mock_cls = MagicMock(return_value=mock_provider_instance)

        with (
            patch("nanobot.config.loader.load_config", return_value=mock_config),
            patch(
                "nanobot.providers.anthropic_oauth_provider.AnthropicOAuthProvider",
                mock_cls,
            ),
        ):
            provider, model = create_provider()
            assert model == "anthropic-oauth/claude-sonnet-4-6"
            assert provider is mock_provider_instance
            mock_cls.assert_called_once_with(default_model="anthropic-oauth/claude-sonnet-4-6")

    def test_raises_provider_error_on_import_failure(self):
        """When the anthropic_oauth provider is not installed, raise ProviderError."""
        import builtins
        import sys

        mock_config = MagicMock()
        mock_config.agents.defaults.model = "anthropic-oauth/claude-sonnet"
        mock_config.get_provider_name.return_value = "anthropic_oauth"
        mock_config.get_provider.return_value = None

        # Remove the cached module so the import is re-attempted
        saved = sys.modules.pop("nanobot.providers.anthropic_oauth_provider", None)

        real_import = builtins.__import__

        def _failing_import(name, *args, **kwargs):
            if name == "nanobot.providers.anthropic_oauth_provider":
                raise ImportError("httpx not installed")
            return real_import(name, *args, **kwargs)

        try:
            with (
                patch("nanobot.config.loader.load_config", return_value=mock_config),
                patch("builtins.__import__", side_effect=_failing_import),
            ):
                with pytest.raises(ProviderError, match="not available"):
                    create_provider()
        finally:
            if saved is not None:
                sys.modules["nanobot.providers.anthropic_oauth_provider"] = saved


class TestCreateProviderOpenAICodex:
    """Test create_provider for the openai_codex provider type."""

    def test_returns_openai_codex_provider(self):
        """When provider_name is openai_codex, return an AdaptedProvider wrapping OpenAICodexProvider."""
        from mc.infrastructure.providers.tool_adapters import AdaptedProvider

        mock_config = MagicMock()
        mock_config.agents.defaults.model = "openai-codex/gpt-4"
        mock_config.get_provider_name.return_value = "openai_codex"
        mock_config.get_provider.return_value = None

        mock_raw_provider = MagicMock()
        mock_cls = MagicMock(return_value=mock_raw_provider)

        with (
            patch("nanobot.config.loader.load_config", return_value=mock_config),
            patch(
                "nanobot.providers.openai_codex_provider.OpenAICodexProvider",
                mock_cls,
            ),
        ):
            provider, model = create_provider()
            assert model == "openai-codex/gpt-4"
            assert isinstance(provider, AdaptedProvider)
            assert provider._inner is mock_raw_provider


class TestCodexProviderWrappedWithAdapter:
    """Codex provider must be wrapped with AdaptedProvider(CodexToolAdapter)."""

    def test_codex_provider_is_adapted(self):
        """create_provider for openai_codex returns an AdaptedProvider."""
        from mc.infrastructure.providers.tool_adapters import AdaptedProvider

        mock_config = MagicMock()
        mock_config.agents.defaults.model = "openai-codex/gpt-5.4"
        mock_config.get_provider_name.return_value = "openai_codex"
        mock_config.get_provider.return_value = None

        mock_raw_provider = MagicMock()
        mock_cls = MagicMock(return_value=mock_raw_provider)

        with (
            patch("nanobot.config.loader.load_config", return_value=mock_config),
            patch(
                "nanobot.providers.openai_codex_provider.OpenAICodexProvider",
                mock_cls,
            ),
        ):
            provider, _model = create_provider()
            assert isinstance(provider, AdaptedProvider), (
                f"Codex provider must be wrapped with AdaptedProvider, got {type(provider)}"
            )

    def test_codex_adapted_provider_strips_one_of(self):
        """The adapted Codex provider strips oneOf from tool schemas."""
        mock_config = MagicMock()
        mock_config.agents.defaults.model = "openai-codex/gpt-5.4"
        mock_config.get_provider_name.return_value = "openai_codex"
        mock_config.get_provider.return_value = None

        mock_raw_provider = MagicMock()
        mock_cls = MagicMock(return_value=mock_raw_provider)

        with (
            patch("nanobot.config.loader.load_config", return_value=mock_config),
            patch(
                "nanobot.providers.openai_codex_provider.OpenAICodexProvider",
                mock_cls,
            ),
        ):
            provider, _ = create_provider()

        tool_with_one_of = {
            "type": "function",
            "function": {
                "name": "ask_user",
                "parameters": {
                    "type": "object",
                    "properties": {"question": {"type": "string"}},
                    "oneOf": [{"required": ["question"]}],
                },
            },
        }
        adapted = provider._tool_adapter.adapt_tools([tool_with_one_of])
        params = adapted[0]["function"]["parameters"]
        assert "oneOf" not in params, "oneOf must be stripped for Codex"


class TestCreateProviderCustom:
    """Test create_provider for the custom provider type."""

    def test_returns_custom_provider(self):
        """When provider_name is custom, return CustomProvider."""
        mock_config = MagicMock()
        mock_config.agents.defaults.model = "my-local-model"
        mock_config.get_provider_name.return_value = "custom"
        p = MagicMock()
        p.api_key = "test-key"
        mock_config.get_provider.return_value = p
        mock_config.get_api_base.return_value = "http://localhost:1234/v1"

        mock_provider = MagicMock()
        mock_cls = MagicMock(return_value=mock_provider)

        with (
            patch("nanobot.config.loader.load_config", return_value=mock_config),
            patch(
                "nanobot.providers.custom_provider.CustomProvider",
                mock_cls,
            ),
        ):
            provider, model = create_provider()
            assert model == "my-local-model"
            assert provider is mock_provider
            mock_cls.assert_called_once_with(
                api_key="test-key",
                api_base="http://localhost:1234/v1",
                default_model="my-local-model",
            )


class TestCreateProviderLiteLLM:
    """Test create_provider for the default LiteLLM provider type."""

    def test_returns_litellm_provider_as_default(self):
        """When provider_name is not a special type, return LiteLLMProvider."""
        mock_config = MagicMock()
        mock_config.agents.defaults.model = "openrouter/meta-llama/llama-3"
        mock_config.get_provider_name.return_value = "openrouter"
        p = MagicMock()
        p.api_key = "or-key"
        p.extra_headers = None
        mock_config.get_provider.return_value = p
        mock_config.get_api_base.return_value = None

        mock_provider = MagicMock()
        mock_cls = MagicMock(return_value=mock_provider)

        with (
            patch("nanobot.config.loader.load_config", return_value=mock_config),
            patch(
                "nanobot.providers.litellm_provider.LiteLLMProvider",
                mock_cls,
            ),
        ):
            provider, model = create_provider()
            assert model == "openrouter/meta-llama/llama-3"
            assert provider is mock_provider
            mock_cls.assert_called_once_with(
                api_key="or-key",
                api_base=None,
                default_model="openrouter/meta-llama/llama-3",
                extra_headers=None,
                provider_name="openrouter",
            )


class TestCreateProviderModelOverride:
    """Test that model parameter overrides config default."""

    def test_model_param_overrides_config(self):
        """When model is explicitly provided, it should override config default."""
        mock_config = MagicMock()
        mock_config.agents.defaults.model = "default-model"
        mock_config.get_provider_name.return_value = "litellm"
        p = MagicMock()
        p.api_key = "key"
        p.extra_headers = None
        mock_config.get_provider.return_value = p
        mock_config.get_api_base.return_value = None

        mock_provider = MagicMock()
        mock_cls = MagicMock(return_value=mock_provider)

        with (
            patch("nanobot.config.loader.load_config", return_value=mock_config),
            patch(
                "nanobot.providers.litellm_provider.LiteLLMProvider",
                mock_cls,
            ),
        ):
            _provider, model = create_provider("override-model")
            assert model == "override-model"
            # Verify the override model was passed to get_provider_name
            mock_config.get_provider_name.assert_called_with("override-model")


class TestProviderErrorAttributes:
    """Test ProviderError has expected attributes."""

    def test_has_action_attribute(self):
        """ProviderError should carry an action string."""
        err = ProviderError("Token expired", action="nanobot provider login anthropic-oauth")
        assert err.action == "nanobot provider login anthropic-oauth"
        assert str(err) == "Token expired"

    def test_defaults_to_empty_action(self):
        """ProviderError action defaults to empty string."""
        err = ProviderError("Generic error")
        assert err.action == ""


class TestOpenAICodexProviderListModels:
    def test_list_models_returns_codex_models(self):
        from nanobot.providers.openai_codex_provider import CODEX_MODELS, OpenAICodexProvider

        provider = OpenAICodexProvider()
        result = provider.list_models()
        assert result == CODEX_MODELS
        assert "openai-codex/gpt-5.4" in result
        assert "openai-codex/gpt-5.3-codex" in result
        assert "openai-codex/gpt-5.2" not in result
        assert "openai-codex/gpt-5.1-codex" not in result


class TestOpenAICodexProviderReasoning:
    @pytest.mark.asyncio
    async def test_reasoning_level_added_to_body(self):
        from nanobot.providers.openai_codex_provider import OpenAICodexProvider

        provider = OpenAICodexProvider()
        captured_body = {}

        async def fake_request_codex(url, headers, body, verify):
            captured_body.update(body)
            return ("hello", [], "stop")

        mock_token = MagicMock()
        mock_token.account_id = "acc123"
        mock_token.access = "tok123"
        with (
            patch(
                "nanobot.providers.openai_codex_provider.get_codex_token", return_value=mock_token
            ),
            patch(
                "nanobot.providers.openai_codex_provider._request_codex",
                side_effect=fake_request_codex,
            ),
        ):
            await provider.chat(
                messages=[{"role": "user", "content": "hi"}], reasoning_level="medium"
            )
        assert captured_body.get("reasoning") == {"effort": "medium"}

    @pytest.mark.asyncio
    async def test_reasoning_max_maps_to_high(self):
        from nanobot.providers.openai_codex_provider import OpenAICodexProvider

        provider = OpenAICodexProvider()
        captured_body = {}

        async def fake_request_codex(url, headers, body, verify):
            captured_body.update(body)
            return ("hello", [], "stop")

        mock_token = MagicMock()
        mock_token.account_id = "acc"
        mock_token.access = "tok"
        with (
            patch(
                "nanobot.providers.openai_codex_provider.get_codex_token", return_value=mock_token
            ),
            patch(
                "nanobot.providers.openai_codex_provider._request_codex",
                side_effect=fake_request_codex,
            ),
        ):
            await provider.chat(messages=[{"role": "user", "content": "hi"}], reasoning_level="max")
        assert captured_body.get("reasoning") == {"effort": "high"}

    @pytest.mark.asyncio
    async def test_no_reasoning_when_not_set(self):
        from nanobot.providers.openai_codex_provider import OpenAICodexProvider

        provider = OpenAICodexProvider()
        captured_body = {}

        async def fake_request_codex(url, headers, body, verify):
            captured_body.update(body)
            return ("hello", [], "stop")

        mock_token = MagicMock()
        mock_token.account_id = "acc"
        mock_token.access = "tok"
        with (
            patch(
                "nanobot.providers.openai_codex_provider.get_codex_token", return_value=mock_token
            ),
            patch(
                "nanobot.providers.openai_codex_provider._request_codex",
                side_effect=fake_request_codex,
            ),
        ):
            await provider.chat(messages=[{"role": "user", "content": "hi"}])
        assert "reasoning" not in captured_body


class TestListAvailableModelsCodexDiscovery:
    """list_available_models() merges Codex models when Codex is authenticated."""

    def _make_config(self, models=None):
        mock_config = MagicMock()
        mock_config.agents.defaults.model = "anthropic-oauth/claude-sonnet-4-6"
        mock_config.agents.models = models or [
            "anthropic-oauth/claude-sonnet-4-6",
            "anthropic-oauth/claude-opus-4-6",
        ]
        return mock_config

    def test_codex_models_added_when_authenticated(self):
        """When get_token() succeeds, Codex models are appended to the list."""
        from nanobot.providers.openai_codex_provider import CODEX_MODELS

        from mc.infrastructure.providers.factory import list_available_models

        mock_token = MagicMock()
        config = self._make_config()
        with (
            patch("nanobot.config.loader.load_config", return_value=config),
            patch("mc.infrastructure.providers.factory._get_codex_token", return_value=mock_token),
        ):
            result = list_available_models()
        for m in CODEX_MODELS:
            assert m in result

    def test_codex_models_not_added_when_not_authenticated(self):
        """When get_token() raises, Codex models are NOT added."""
        from nanobot.providers.openai_codex_provider import CODEX_MODELS

        from mc.infrastructure.providers.factory import list_available_models

        config = self._make_config()
        with (
            patch("nanobot.config.loader.load_config", return_value=config),
            patch(
                "mc.infrastructure.providers.factory._get_codex_token",
                side_effect=Exception("no token"),
            ),
        ):
            result = list_available_models()
        for m in CODEX_MODELS:
            assert m not in result

    def test_codex_models_not_duplicated(self):
        """If a Codex model is already in config.agents.models, it appears only once."""
        from mc.infrastructure.providers.factory import list_available_models

        mock_token = MagicMock()
        config = self._make_config(
            models=["openai-codex/gpt-5.3-codex", "anthropic-oauth/claude-sonnet-4-6"]
        )
        with (
            patch("nanobot.config.loader.load_config", return_value=config),
            patch("mc.infrastructure.providers.factory._get_codex_token", return_value=mock_token),
        ):
            result = list_available_models()
        assert result.count("openai-codex/gpt-5.3-codex") == 1
