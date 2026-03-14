"""MC-owned provider tool adapter layer.

Transforms the tool list before submission to the LLM provider so that
vendor provider implementations do not need to understand MC-specific
tool semantics (e.g. top-level JSON Schema combinators that Codex rejects).

AC1: ProviderToolAdapter protocol — the explicit adapter contract.
AC2: CodexToolAdapter — strips top-level schema combinators (oneOf / anyOf / allOf).
AC4: AdaptedProvider — wraps an inner provider instance; adaptation happens here.
"""

from __future__ import annotations

import copy
from typing import Any, Protocol, runtime_checkable

# Top-level JSON Schema combinators that Codex rejects.
_COMBINATORS = frozenset({"oneOf", "anyOf", "allOf", "not"})


@runtime_checkable
class ProviderToolAdapter(Protocol):
    """Contract for objects that can adapt a tool list for a specific provider."""

    def adapt_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return a provider-safe version of the tool list.

        Implementations MUST:
        - preserve public tool names unchanged
        - not mutate the input list or its elements
        - return a new list (shallow or deep copy as appropriate)
        """
        ...


class CodexToolAdapter:
    """Adapter that makes tool schemas safe for the OpenAI Codex provider.

    Codex rejects JSON Schema payloads that contain top-level combinators
    (oneOf, anyOf, allOf, not) inside ``parameters``.  This adapter strips
    those keys while preserving all other schema details so the semantic
    requirement is enforced by runtime validation rather than schema
    enforcement.
    """

    def adapt_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return a Codex-safe copy of *tools* with top-level combinators removed.

        Args:
            tools: OpenAI function-calling tool descriptors.

        Returns:
            A new list of tool descriptors safe for the Codex provider.
        """
        result: list[dict[str, Any]] = []
        for tool in tools:
            adapted = self._adapt_tool(tool)
            result.append(adapted)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _adapt_tool(self, tool: dict[str, Any]) -> dict[str, Any]:
        """Return a Codex-safe copy of a single tool descriptor."""
        if tool.get("type") != "function":
            return copy.deepcopy(tool)

        fn = tool.get("function") or {}
        params = fn.get("parameters")
        if not isinstance(params, dict) or not _has_top_level_combinator(params):
            # Nothing to strip — return a deep copy to avoid mutating the original.
            return copy.deepcopy(tool)

        # Strip the combinators from a copy of the parameters dict.
        adapted_params = {k: v for k, v in params.items() if k not in _COMBINATORS}
        adapted_fn = {**fn, "parameters": adapted_params}
        return {"type": "function", "function": adapted_fn}


def _has_top_level_combinator(params: dict[str, Any]) -> bool:
    return any(k in params for k in _COMBINATORS)


class AdaptedProvider:
    """Wraps an inner LLM provider and applies a ProviderToolAdapter before each chat call.

    This is MC factory-owned wrapping (AC4): vendor provider implementations
    are not modified; adaptation is injected here in the MC infrastructure layer.
    """

    def __init__(self, inner: Any, tool_adapter: ProviderToolAdapter) -> None:
        self._inner = inner
        self._tool_adapter = tool_adapter

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Adapt tools, then delegate to the inner provider's chat method."""
        adapted_tools = self._tool_adapter.adapt_tools(tools or []) if tools is not None else None
        return await self._inner.chat(messages=messages, tools=adapted_tools, **kwargs)

    def get_default_model(self) -> str:
        """Delegate to inner provider."""
        return self._inner.get_default_model()

    def list_models(self) -> list[str]:
        """Delegate to inner provider."""
        return self._inner.list_models()
