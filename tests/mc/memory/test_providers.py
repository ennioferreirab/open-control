from mc.memory.providers import LiteLLMProvider, NullProvider, get_provider


def test_null_provider_returns_none():
    provider = NullProvider()
    assert provider.embed(["hello"]) is None


def test_get_provider_none_returns_null_provider():
    provider = get_provider(None)
    assert isinstance(provider, NullProvider)


def test_get_provider_model_returns_litellm_provider():
    provider = get_provider("ollama/nomic-embed-text")
    assert isinstance(provider, LiteLLMProvider)


def test_litellm_provider_returns_none_on_exception():
    from unittest.mock import patch
    from mc.memory.providers import LiteLLMProvider

    provider = LiteLLMProvider("some-model")
    with patch("litellm.embedding", side_effect=RuntimeError("API error")):
        result = provider.embed(["hello"])
    assert result is None
