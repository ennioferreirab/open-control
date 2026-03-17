"""Tests for MC provider tool adapters — AC1-AC5."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Fixture: ask_user tool with top-level oneOf combinator
# ---------------------------------------------------------------------------

ASK_USER_TOOL_WITH_ONE_OF = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": "Ask the human user a question.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "questions": {"type": "array", "items": {"type": "object"}},
            },
            "oneOf": [{"required": ["question"]}, {"required": ["questions"]}],
        },
    },
}

OTHER_TOOL = {
    "type": "function",
    "function": {
        "name": "record_final_result",
        "description": "Record the final result.",
        "parameters": {
            "type": "object",
            "properties": {
                "result": {"type": "string"},
            },
            "required": ["result"],
        },
    },
}


class TestProviderToolAdapterContract:
    """AC1: An explicit provider tool-adapter contract exists in mc."""

    def test_adapter_protocol_importable(self) -> None:
        """ProviderToolAdapter protocol can be imported from mc.infrastructure.providers."""
        from mc.infrastructure.providers.tool_adapters import ProviderToolAdapter  # noqa: F401

    def test_codex_adapter_importable(self) -> None:
        """CodexToolAdapter can be imported from mc.infrastructure.providers."""
        from mc.infrastructure.providers.tool_adapters import CodexToolAdapter  # noqa: F401

    def test_adapted_provider_importable(self) -> None:
        """AdaptedProvider can be imported from mc.infrastructure.providers."""
        from mc.infrastructure.providers.tool_adapters import AdaptedProvider  # noqa: F401

    def test_adapter_protocol_has_adapt_tools_method(self) -> None:
        """ProviderToolAdapter protocol exposes adapt_tools(tools) -> list."""
        from mc.infrastructure.providers.tool_adapters import CodexToolAdapter

        adapter = CodexToolAdapter()
        result = adapter.adapt_tools([OTHER_TOOL])
        assert isinstance(result, list)


class TestCodexToolAdapter:
    """AC2: Codex-safe adaptation removes top-level schema combinators."""

    def test_codex_adapter_removes_top_level_one_of(self) -> None:
        """CodexToolAdapter strips top-level 'oneOf' from function parameters."""
        from mc.infrastructure.providers.tool_adapters import CodexToolAdapter

        adapter = CodexToolAdapter()
        adapted = adapter.adapt_tools([ASK_USER_TOOL_WITH_ONE_OF])
        assert len(adapted) == 1
        params = adapted[0]["function"]["parameters"]
        assert "oneOf" not in params, "top-level oneOf must be stripped for Codex"

    def test_codex_adapter_preserves_properties(self) -> None:
        """Properties are preserved after adaptation."""
        from mc.infrastructure.providers.tool_adapters import CodexToolAdapter

        adapter = CodexToolAdapter()
        adapted = adapter.adapt_tools([ASK_USER_TOOL_WITH_ONE_OF])
        params = adapted[0]["function"]["parameters"]
        assert "properties" in params
        assert "question" in params["properties"]
        assert "questions" in params["properties"]

    def test_codex_adapter_passes_through_tools_without_one_of(self) -> None:
        """Tools without top-level combinators are passed through unchanged."""
        from mc.infrastructure.providers.tool_adapters import CodexToolAdapter

        adapter = CodexToolAdapter()
        adapted = adapter.adapt_tools([OTHER_TOOL])
        assert adapted[0]["function"]["parameters"] == OTHER_TOOL["function"]["parameters"]

    def test_codex_adapter_handles_empty_tool_list(self) -> None:
        """Empty tool list returns empty list."""
        from mc.infrastructure.providers.tool_adapters import CodexToolAdapter

        adapter = CodexToolAdapter()
        assert adapter.adapt_tools([]) == []

    def test_codex_adapter_also_strips_any_of_and_all_of(self) -> None:
        """anyOf and allOf at the top level of parameters are also stripped."""
        from mc.infrastructure.providers.tool_adapters import CodexToolAdapter

        tool_with_any_of = {
            "type": "function",
            "function": {
                "name": "some_tool",
                "description": "A tool.",
                "parameters": {
                    "type": "object",
                    "properties": {"x": {"type": "string"}},
                    "anyOf": [{"required": ["x"]}],
                    "allOf": [{"required": ["x"]}],
                },
            },
        }
        adapter = CodexToolAdapter()
        adapted = adapter.adapt_tools([tool_with_any_of])
        params = adapted[0]["function"]["parameters"]
        assert "anyOf" not in params
        assert "allOf" not in params


class TestPublicToolNamesStable:
    """AC3: Public tool names remain unchanged after adaptation."""

    def test_ask_user_name_unchanged(self) -> None:
        """ask_user tool name is stable after Codex adaptation."""
        from mc.infrastructure.providers.tool_adapters import CodexToolAdapter

        adapter = CodexToolAdapter()
        adapted = adapter.adapt_tools([ASK_USER_TOOL_WITH_ONE_OF])
        assert adapted[0]["function"]["name"] == "ask_user"

    def test_public_tool_names_unchanged(self) -> None:
        """All public tool names survive adaptation unchanged."""
        from mc.infrastructure.providers.tool_adapters import CodexToolAdapter

        tools = [
            {"type": "function", "function": {"name": n, "description": "d", "parameters": {}}}
            for n in [
                "ask_user",
                "ask_agent",
                "delegate_task",
                "send_message",
                "cron",
                "report_progress",
                "record_final_result",
            ]
        ]
        adapter = CodexToolAdapter()
        adapted = adapter.adapt_tools(tools)
        names = [t["function"]["name"] for t in adapted]
        assert names == [
            "ask_user",
            "ask_agent",
            "delegate_task",
            "send_message",
            "cron",
            "report_progress",
            "record_final_result",
        ]


class TestAdaptedProvider:
    """AC4: AdaptedProvider wraps an inner provider and applies adaptation."""

    @pytest.mark.asyncio
    async def test_adapted_provider_calls_adapt_tools_before_chat(self) -> None:
        """AdaptedProvider.chat() adapts tools before delegating to inner provider."""
        from unittest.mock import AsyncMock, MagicMock

        from mc.infrastructure.providers.tool_adapters import AdaptedProvider, CodexToolAdapter

        mock_inner = MagicMock()
        mock_inner.chat = AsyncMock(return_value="response")

        adapter = CodexToolAdapter()
        wrapped = AdaptedProvider(inner=mock_inner, tool_adapter=adapter)

        await wrapped.chat(
            messages=[{"role": "user", "content": "hi"}], tools=[ASK_USER_TOOL_WITH_ONE_OF]
        )

        # Inner chat was called
        mock_inner.chat.assert_called_once()
        call_kwargs = mock_inner.chat.call_args
        # Get tools from kwargs or positional args
        passed_tools = call_kwargs.kwargs.get("tools") or (
            call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
        )
        assert passed_tools is not None
        # oneOf must be stripped
        params = passed_tools[0]["function"]["parameters"]
        assert "oneOf" not in params

    @pytest.mark.asyncio
    async def test_adapted_provider_passes_none_tools_unchanged(self) -> None:
        """AdaptedProvider passes None tools as empty list or None to inner."""
        from unittest.mock import AsyncMock, MagicMock

        from mc.infrastructure.providers.tool_adapters import AdaptedProvider, CodexToolAdapter

        mock_inner = MagicMock()
        mock_inner.chat = AsyncMock(return_value="response")

        adapter = CodexToolAdapter()
        wrapped = AdaptedProvider(inner=mock_inner, tool_adapter=adapter)

        await wrapped.chat(messages=[{"role": "user", "content": "hi"}])
        mock_inner.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_adapted_provider_delegates_non_chat_to_inner(self) -> None:
        """AdaptedProvider delegates get_default_model and list_models to inner."""
        from unittest.mock import MagicMock

        from mc.infrastructure.providers.tool_adapters import AdaptedProvider, CodexToolAdapter

        mock_inner = MagicMock()
        mock_inner.get_default_model.return_value = "openai-codex/gpt-5.4"
        mock_inner.list_models.return_value = ["openai-codex/gpt-5.4"]

        adapter = CodexToolAdapter()
        wrapped = AdaptedProvider(inner=mock_inner, tool_adapter=adapter)

        assert wrapped.get_default_model() == "openai-codex/gpt-5.4"
        assert wrapped.list_models() == ["openai-codex/gpt-5.4"]


class TestCodexRegressionOneOfNotReachedCodex:
    """AC5: Regression — ask_user oneOf does not reach Codex unchanged."""

    @pytest.mark.asyncio
    async def test_one_of_stripped_before_codex_receives_tools(self) -> None:
        """The top-level oneOf on ask_user is stripped before Codex sees the tool payload."""
        from unittest.mock import AsyncMock, MagicMock

        from mc.infrastructure.providers.tool_adapters import AdaptedProvider, CodexToolAdapter

        # Simulate OpenAICodexProvider as the inner provider
        mock_codex_provider = MagicMock()
        captured_tools: list[list] = []

        async def fake_chat(messages, tools=None, **kwargs):
            if tools:
                captured_tools.append(tools)
            return MagicMock(content="ok", tool_calls=[], finish_reason="stop")

        mock_codex_provider.chat = AsyncMock(side_effect=fake_chat)

        adapter = CodexToolAdapter()
        wrapped = AdaptedProvider(inner=mock_codex_provider, tool_adapter=adapter)

        await wrapped.chat(
            messages=[{"role": "user", "content": "hi"}],
            tools=[ASK_USER_TOOL_WITH_ONE_OF],
        )

        assert len(captured_tools) == 1, "tools should have been captured"
        received = captured_tools[0]
        assert len(received) == 1
        params = received[0]["function"]["parameters"]
        assert "oneOf" not in params, (
            "ask_user top-level oneOf must be stripped before Codex receives the tool payload"
        )
