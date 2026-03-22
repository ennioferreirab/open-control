"""End-to-end integration tests: Codex provider + ask_user tool pipeline.

Traces the full call chain that a nanobot MC task follows:
  tool_specs (MC_TOOLS) → MCPToolWrapper.to_schema() →
  AdaptedProvider.adapt_tools() → OpenAICodexProvider.chat() →
  _convert_tools() → _request_codex(body)

Proves that `oneOf` in ask_user's inputSchema is stripped before it reaches
the Codex Responses API, and that the tool is otherwise usable.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mc.infrastructure.providers.factory import create_provider
from mc.infrastructure.providers.tool_adapters import (
    AdaptedProvider,
    CodexToolAdapter,
)
from mc.runtime.mcp.tool_specs import MC_TOOLS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ask_user_input_schema() -> dict[str, Any]:
    """Return the canonical ask_user inputSchema from tool_specs."""
    for tool in MC_TOOLS:
        if tool.name == "ask_user":
            return dict(tool.inputSchema)
    raise AssertionError("ask_user not found in MC_TOOLS")


def _as_openai_tool(name: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """Build an OpenAI function-calling tool descriptor (same as Tool.to_schema)."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": "Ask the user a question.",
            "parameters": parameters,
        },
    }


def _make_codex_config() -> MagicMock:
    """Mock nanobot config that resolves to the Codex provider."""
    cfg = MagicMock()
    cfg.agents.defaults.model = "openai-codex/gpt-5.4"
    cfg.get_provider_name.return_value = "openai_codex"
    cfg.get_provider.return_value = None
    return cfg


# ---------------------------------------------------------------------------
# Test 1: Canonical ask_user schema has oneOf (precondition)
# ---------------------------------------------------------------------------


class TestPrecondition:
    def test_ask_user_schema_contains_one_of(self) -> None:
        """The canonical ask_user inputSchema must have both question and questions properties."""
        schema = _ask_user_input_schema()
        assert "properties" in schema, (
            "Precondition failed: ask_user schema should have properties "
            "so we can verify question/questions are present"
        )
        assert "question" in schema["properties"], (
            "Precondition failed: ask_user schema should have 'question' property"
        )
        assert "questions" in schema["properties"], (
            "Precondition failed: ask_user schema should have 'questions' property"
        )


# ---------------------------------------------------------------------------
# Test 2: CodexToolAdapter strips oneOf from MCP-style tool schema
# ---------------------------------------------------------------------------


class TestAdapterStripsOneOf:
    def test_adapter_strips_one_of_from_ask_user(self) -> None:
        """CodexToolAdapter removes oneOf from ask_user before provider submission."""
        schema = _ask_user_input_schema()
        tool = _as_openai_tool("ask_user", schema)

        adapter = CodexToolAdapter()
        adapted = adapter.adapt_tools([tool])

        params = adapted[0]["function"]["parameters"]
        assert "oneOf" not in params, "oneOf must be stripped for Codex"
        # Properties must survive
        assert "question" in params["properties"]
        assert "questions" in params["properties"]
        # Tool name must be stable
        assert adapted[0]["function"]["name"] == "ask_user"

    def test_adapter_strips_one_of_from_mcp_prefixed_name(self) -> None:
        """MCPToolWrapper prefixes names as mcp_mc_<name>; adapter still strips oneOf."""
        schema = _ask_user_input_schema()
        tool = _as_openai_tool("mcp_mc_ask_user", schema)

        adapter = CodexToolAdapter()
        adapted = adapter.adapt_tools([tool])

        params = adapted[0]["function"]["parameters"]
        assert "oneOf" not in params
        assert adapted[0]["function"]["name"] == "mcp_mc_ask_user"


# ---------------------------------------------------------------------------
# Test 3: Full factory → provider chain (create_provider for Codex)
# ---------------------------------------------------------------------------


class TestFactoryProducesAdaptedCodexProvider:
    def test_create_provider_returns_adapted_provider(self) -> None:
        """create_provider for Codex wraps with AdaptedProvider(CodexToolAdapter)."""
        cfg = _make_codex_config()
        with (
            patch("nanobot.config.loader.load_config", return_value=cfg),
            patch(
                "nanobot.providers.openai_codex_provider.OpenAICodexProvider",
                MagicMock(),
            ),
        ):
            provider, _model = create_provider()

        assert isinstance(provider, AdaptedProvider)
        assert isinstance(provider._tool_adapter, CodexToolAdapter)


# ---------------------------------------------------------------------------
# Test 4: End-to-end — ask_user oneOf never reaches _request_codex body
# ---------------------------------------------------------------------------


class TestEndToEndCodexAskUser:
    """Simulate the full provider.chat() call and capture the HTTP body."""

    @pytest.mark.asyncio()
    async def test_one_of_stripped_before_codex_api(self) -> None:
        """oneOf does NOT appear in the tool params sent to the Codex Responses API."""
        captured_body: dict[str, Any] = {}

        async def fake_request_codex(
            url: str,
            headers: dict[str, str],
            body: dict[str, Any],
            verify: bool,
        ) -> tuple[str, list, str]:
            captured_body.update(body)
            return ("ok", [], "stop")

        mock_token = MagicMock()
        mock_token.account_id = "acc"
        mock_token.access = "tok"

        cfg = _make_codex_config()
        with (
            patch("nanobot.config.loader.load_config", return_value=cfg),
            patch(
                "nanobot.providers.openai_codex_provider.get_codex_token",
                return_value=mock_token,
            ),
            patch(
                "nanobot.providers.openai_codex_provider._request_codex",
                side_effect=fake_request_codex,
            ),
        ):
            provider, _ = create_provider()

        # Build the ask_user tool in OpenAI format (as nanobot's ToolRegistry would)
        schema = _ask_user_input_schema()
        ask_user_tool = _as_openai_tool("mcp_mc_ask_user", schema)

        # Precondition: the raw tool has the expected properties
        assert "properties" in ask_user_tool["function"]["parameters"]

        # Call chat() — AdaptedProvider should pass valid schema to OpenAICodexProvider
        with (
            patch(
                "nanobot.providers.openai_codex_provider.get_codex_token",
                return_value=mock_token,
            ),
            patch(
                "nanobot.providers.openai_codex_provider._request_codex",
                side_effect=fake_request_codex,
            ),
        ):
            await provider.chat(
                messages=[{"role": "user", "content": "hello"}],
                tools=[ask_user_tool],
            )

        # The body must have been captured
        assert "tools" in captured_body, "Codex body must include tools"

        # Find the ask_user tool in the submitted body
        codex_tools = captured_body["tools"]
        ask_user_submitted = None
        for t in codex_tools:
            if t.get("name") == "mcp_mc_ask_user":
                ask_user_submitted = t
                break

        assert ask_user_submitted is not None, (
            f"mcp_mc_ask_user not found in submitted tools: {[t.get('name') for t in codex_tools]}"
        )

        # THE KEY ASSERTION: oneOf must NOT be in the parameters
        params = ask_user_submitted.get("parameters", {})
        assert "oneOf" not in params, (
            f"oneOf must be stripped before reaching Codex API! "
            f"Got parameters: {json.dumps(params, indent=2)}"
        )

        # Properties must still be present
        assert "question" in params.get("properties", {}), "question property must survive"
        assert "questions" in params.get("properties", {}), "questions property must survive"

    @pytest.mark.asyncio()
    async def test_all_phase1_tools_submittable_to_codex(self) -> None:
        """All 7 Phase 1 tools can be submitted to Codex without schema errors."""
        captured_body: dict[str, Any] = {}

        async def fake_request_codex(
            url: str,
            headers: dict[str, str],
            body: dict[str, Any],
            verify: bool,
        ) -> tuple[str, list, str]:
            captured_body.update(body)
            return ("ok", [], "stop")

        mock_token = MagicMock()
        mock_token.account_id = "acc"
        mock_token.access = "tok"

        cfg = _make_codex_config()
        with (
            patch("nanobot.config.loader.load_config", return_value=cfg),
            patch(
                "nanobot.providers.openai_codex_provider.get_codex_token",
                return_value=mock_token,
            ),
            patch(
                "nanobot.providers.openai_codex_provider._request_codex",
                side_effect=fake_request_codex,
            ),
        ):
            provider, _ = create_provider()

        # Build all Phase 1 tools as nanobot MCPToolWrapper would
        tools = []
        for spec in MC_TOOLS:
            tools.append(
                _as_openai_tool(
                    f"mcp_mc_{spec.name}",
                    dict(spec.inputSchema),
                )
            )

        with (
            patch(
                "nanobot.providers.openai_codex_provider.get_codex_token",
                return_value=mock_token,
            ),
            patch(
                "nanobot.providers.openai_codex_provider._request_codex",
                side_effect=fake_request_codex,
            ),
        ):
            await provider.chat(
                messages=[{"role": "user", "content": "hello"}],
                tools=tools,
            )

        codex_tools = captured_body.get("tools", [])
        assert len(codex_tools) == len(MC_TOOLS), (
            f"Expected {len(MC_TOOLS)} tools, got {len(codex_tools)}"
        )

        # No tool should have top-level combinators
        combinators = {"oneOf", "anyOf", "allOf", "not"}
        for t in codex_tools:
            params = t.get("parameters", {})
            found = combinators & set(params.keys())
            assert not found, f"Tool '{t.get('name')}' still has top-level combinators: {found}"

    @pytest.mark.asyncio()
    async def test_codex_response_with_ask_user_tool_call(self) -> None:
        """Codex can respond with a tool call to ask_user and get the result back."""
        from nanobot.providers.base import ToolCallRequest

        call_count = 0

        async def fake_request_codex(
            url: str,
            headers: dict[str, str],
            body: dict[str, Any],
            verify: bool,
        ) -> tuple[str, list[ToolCallRequest], str]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: model decides to call ask_user
                return (
                    "",
                    [
                        ToolCallRequest(
                            id="call_1|fc_1",
                            name="mcp_mc_ask_user",
                            arguments={"question": "What color?"},
                        )
                    ],
                    "stop",
                )
            # Second call: model gets the answer and responds
            return ("The user said blue.", [], "stop")

        mock_token = MagicMock()
        mock_token.account_id = "acc"
        mock_token.access = "tok"

        cfg = _make_codex_config()
        with (
            patch("nanobot.config.loader.load_config", return_value=cfg),
            patch(
                "nanobot.providers.openai_codex_provider.get_codex_token",
                return_value=mock_token,
            ),
            patch(
                "nanobot.providers.openai_codex_provider._request_codex",
                side_effect=fake_request_codex,
            ),
        ):
            provider, _ = create_provider()

        schema = _ask_user_input_schema()
        ask_user_tool = _as_openai_tool("mcp_mc_ask_user", schema)

        # First provider call: model calls ask_user
        with (
            patch(
                "nanobot.providers.openai_codex_provider.get_codex_token",
                return_value=mock_token,
            ),
            patch(
                "nanobot.providers.openai_codex_provider._request_codex",
                side_effect=fake_request_codex,
            ),
        ):
            response = await provider.chat(
                messages=[{"role": "user", "content": "Pick a color for me"}],
                tools=[ask_user_tool],
            )

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "mcp_mc_ask_user"
        assert response.tool_calls[0].arguments == {"question": "What color?"}
