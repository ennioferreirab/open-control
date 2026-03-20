"""Embedding provider abstractions for memory search."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Protocol

from mc.infrastructure.runtime_home import get_config_path

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    """Interface for text embedding providers."""

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        """Return vector embeddings for input texts, or None if disabled."""


class NullProvider:
    """No-op provider used when embeddings are disabled."""

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        return None


class LiteLLMProvider:
    """Embedding provider backed by ``litellm.embedding``.

    Resolves the API key from the nanobot provider registry + config.json,
    independent of which LLM model the agent uses for chat.
    """

    def __init__(self, model: str) -> None:
        self.model = model
        self._api_key: str | None = self._resolve_api_key(model)

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        import litellm

        kwargs: dict[str, Any] = {"model": self.model, "input": texts}
        if self._api_key:
            kwargs["api_key"] = self._api_key

        try:
            response = litellm.embedding(**kwargs)
        except Exception:
            return None
        data: Any = getattr(response, "data", None)
        if data is None and isinstance(response, dict):
            data = response.get("data")

        if not isinstance(data, list):
            return None

        vectors: list[list[float]] = []
        for item in data:
            if isinstance(item, dict):
                embedding = item.get("embedding")
            else:
                embedding = getattr(item, "embedding", None)
            if isinstance(embedding, list):
                vectors.append([float(v) for v in embedding])

        return vectors

    @staticmethod
    def _resolve_api_key(model: str) -> str | None:
        """Resolve the API key for the embedding model's provider.

        Uses the nanobot provider registry to find the env var name,
        then checks: env var → nanobot config.json providers section.
        """
        try:
            from nanobot.providers.registry import find_by_model, find_by_name
        except ImportError:
            return None

        # Extract provider prefix (e.g. "openrouter" from "openrouter/openai/text-embedding-3-small")
        prefix = model.split("/", 1)[0] if "/" in model else ""
        spec = find_by_name(prefix) if prefix else find_by_model(model)
        if not spec or not spec.env_key:
            return None

        # 1. Check env var (already set by gateway or provider init)
        from_env = os.environ.get(spec.env_key)
        if from_env:
            return from_env

        # 2. Read from nanobot config.json providers section
        try:
            config_path = get_config_path()
            if not config_path.exists():
                return None
            config = json.loads(config_path.read_text(encoding="utf-8"))
            api_key = config.get("providers", {}).get(spec.name, {}).get("apiKey", "")
            return api_key if api_key else None
        except Exception:
            return None


def get_provider(model: str | None) -> EmbeddingProvider:
    """Return embedding provider for the configured model."""

    if model is None:
        return NullProvider()
    return LiteLLMProvider(model)
