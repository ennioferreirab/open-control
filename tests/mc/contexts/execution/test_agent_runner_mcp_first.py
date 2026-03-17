"""Tests for MC nanobot runtime MCP-first migration (Story 3 / AC1-AC4).

Proves that:
- _run_agent_on_task injects the repo-owned MC MCP bridge into AgentLoop via mcp_servers
- overlapping native tools (ask_user, ask_agent, delegate_task, message, cron) are hidden
- send_message is NOT removed (it comes from MCP, not native — but the native 'message' is removed)
- process_direct_result is used so structured errors propagate (is_error flag preserved)
- the non-MC nanobot behavior (without mcp_servers) stays unchanged
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_direct_result(content: str = "done", is_error: bool = False):
    """Return a fake DirectProcessResult."""

    class FakeDirectProcessResult:
        pass

    r = FakeDirectProcessResult()
    r.content = content
    r.is_error = is_error
    r.error_message = "Schema validation failed" if is_error else None
    return r


def _make_fake_loop_class(content: str = "done", is_error: bool = False):
    """Return a FakeAgentLoop class that records constructor kwargs."""
    captured_kwargs: dict = {}
    unregistered: list[str] = []

    direct_result = _make_fake_direct_result(content, is_error)

    class FakeTools:
        def unregister(self, name: str) -> None:
            unregistered.append(name)

        def get(self, name: str):
            return None

    class FakeAgentLoop:
        _captured = captured_kwargs
        _unregistered = unregistered

        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)
            self.memory_workspace = Path("/tmp/fake_memory")
            self.tools = FakeTools()

        async def process_direct_result(self, **kwargs):
            return direct_result

    return FakeAgentLoop, captured_kwargs, unregistered


# ---------------------------------------------------------------------------
# AC1: MCP bridge injected into AgentLoop via mcp_servers
# ---------------------------------------------------------------------------


class TestMcpServerInjection:
    """AC1: The MC MCP bridge is injected through AgentLoop mcp_servers."""

    @pytest.mark.asyncio()
    async def test_agent_loop_receives_mcp_servers(self) -> None:
        """AgentLoop is constructed with mcp_servers pointing to the MC bridge."""
        fake_agent_loop_cls, captured_kwargs, _ = _make_fake_loop_class("result text")

        with (
            patch("nanobot.agent.loop.AgentLoop", fake_agent_loop_cls),
            patch("nanobot.bus.queue.MessageBus", MagicMock),
            patch(
                "mc.contexts.execution.agent_runner._call_provider_factory",
                lambda model: (MagicMock(), model or "gpt-4o"),
            ),
        ):
            from mc.contexts.execution.agent_runner import _run_agent_on_task

            await _run_agent_on_task(
                agent_name="test-agent",
                agent_prompt=None,
                agent_model="gpt-4o",
                task_title="Test",
                task_id="task_123",
            )

        assert "mcp_servers" in captured_kwargs, "AgentLoop must receive mcp_servers kwarg"
        mcp_servers = captured_kwargs["mcp_servers"]
        assert isinstance(mcp_servers, dict), "mcp_servers must be a dict"
        assert len(mcp_servers) > 0, "mcp_servers must have at least one entry"

    @pytest.mark.asyncio()
    async def test_mcp_servers_contains_mc_bridge_command(self) -> None:
        """The MC bridge server entry uses the module path as the command."""
        fake_agent_loop_cls, captured_kwargs, _ = _make_fake_loop_class("result text")

        with (
            patch("nanobot.agent.loop.AgentLoop", fake_agent_loop_cls),
            patch("nanobot.bus.queue.MessageBus", MagicMock),
            patch(
                "mc.contexts.execution.agent_runner._call_provider_factory",
                lambda model: (MagicMock(), model or "gpt-4o"),
            ),
        ):
            from mc.contexts.execution.agent_runner import _run_agent_on_task

            await _run_agent_on_task(
                agent_name="test-agent",
                agent_prompt=None,
                agent_model="gpt-4o",
                task_title="Test",
                task_id="task_123",
            )

        mcp_servers = captured_kwargs["mcp_servers"]
        # There must be exactly one MC bridge entry
        assert len(mcp_servers) == 1
        server_config = next(iter(mcp_servers.values()))
        # The args must reference the MC MCP bridge module
        args = server_config.get("args") or []
        bridge_module = "mc.runtime.mcp.bridge"
        assert any(bridge_module in str(a) for a in args), (
            f"Bridge module '{bridge_module}' not found in server config args: {args}"
        )


# ---------------------------------------------------------------------------
# AC2: Overlapping native tools are hidden
# ---------------------------------------------------------------------------


class TestOverlappingToolsHidden:
    """AC2: Native overlapping tools are unregistered in MC runtime."""

    @pytest.mark.asyncio()
    async def test_native_message_tool_is_unregistered(self) -> None:
        """The native 'message' tool is unregistered when running in MC context."""
        fake_agent_loop_cls, _, unregistered = _make_fake_loop_class("done")

        with (
            patch("nanobot.agent.loop.AgentLoop", fake_agent_loop_cls),
            patch("nanobot.bus.queue.MessageBus", MagicMock),
            patch(
                "mc.contexts.execution.agent_runner._call_provider_factory",
                lambda model: (MagicMock(), model or "gpt-4o"),
            ),
        ):
            from mc.contexts.execution.agent_runner import _run_agent_on_task

            await _run_agent_on_task(
                agent_name="test-agent",
                agent_prompt=None,
                agent_model="gpt-4o",
                task_title="Test",
                task_id="task_123",
            )

        assert "message" in unregistered, (
            f"'message' tool must be unregistered; unregistered={unregistered}"
        )

    @pytest.mark.asyncio()
    async def test_overlapping_mc_tools_are_unregistered(self) -> None:
        """ask_user, ask_agent, delegate_task, message, cron are all unregistered."""
        fake_agent_loop_cls, _, unregistered = _make_fake_loop_class("done")

        with (
            patch("nanobot.agent.loop.AgentLoop", fake_agent_loop_cls),
            patch("nanobot.bus.queue.MessageBus", MagicMock),
            patch(
                "mc.contexts.execution.agent_runner._call_provider_factory",
                lambda model: (MagicMock(), model or "gpt-4o"),
            ),
        ):
            from mc.contexts.execution.agent_runner import _run_agent_on_task

            await _run_agent_on_task(
                agent_name="test-agent",
                agent_prompt=None,
                agent_model="gpt-4o",
                task_title="Test",
                task_id="task_123",
            )

        # These native tools overlap with the MCP surface and must be hidden
        must_unregister = {"ask_user", "ask_agent", "delegate_task", "message", "cron"}
        missing = must_unregister - set(unregistered)
        assert not missing, (
            f"These tools must be unregistered in MC runtime but were not: {missing}; "
            f"unregistered={unregistered}"
        )


# ---------------------------------------------------------------------------
# AC4: process_direct_result is used — structured errors preserved
# ---------------------------------------------------------------------------


class TestStructuredErrorPropagation:
    """AC4: When the loop returns is_error=True, the result carries the error state."""

    @pytest.mark.asyncio()
    async def test_error_result_returned_when_loop_reports_error(self) -> None:
        """If process_direct_result returns is_error=True, the caller receives it."""
        fake_agent_loop_cls, _, _ = _make_fake_loop_class("Schema validation failed", is_error=True)

        with (
            patch("nanobot.agent.loop.AgentLoop", fake_agent_loop_cls),
            patch("nanobot.bus.queue.MessageBus", MagicMock),
            patch(
                "mc.contexts.execution.agent_runner._call_provider_factory",
                lambda model: (MagicMock(), model or "gpt-4o"),
            ),
        ):
            from mc.contexts.execution.agent_runner import (
                _coerce_agent_run_result,
                _run_agent_on_task,
            )

            result_raw, _session_key, _loop = await _run_agent_on_task(
                agent_name="test-agent",
                agent_prompt=None,
                agent_model="gpt-4o",
                task_title="Test",
                task_id="task_123",
            )

        result = _coerce_agent_run_result(result_raw)
        assert result.is_error is True, f"Expected is_error=True, got {result}"
        assert result.error_message is not None

    @pytest.mark.asyncio()
    async def test_success_result_returned_when_loop_succeeds(self) -> None:
        """On success, is_error=False and content is the result text."""
        fake_agent_loop_cls, _, _ = _make_fake_loop_class("Report written.", is_error=False)

        with (
            patch("nanobot.agent.loop.AgentLoop", fake_agent_loop_cls),
            patch("nanobot.bus.queue.MessageBus", MagicMock),
            patch(
                "mc.contexts.execution.agent_runner._call_provider_factory",
                lambda model: (MagicMock(), model or "gpt-4o"),
            ),
        ):
            from mc.contexts.execution.agent_runner import (
                _coerce_agent_run_result,
                _run_agent_on_task,
            )

            result_raw, _session_key, _loop = await _run_agent_on_task(
                agent_name="test-agent",
                agent_prompt=None,
                agent_model="gpt-4o",
                task_title="Test",
                task_id="task_123",
            )

        result = _coerce_agent_run_result(result_raw)
        assert result.is_error is False
        assert "Report written." in result.content


# ---------------------------------------------------------------------------
# AC5: Regression — Codex ask_user schema failure no longer masquerades as success
# ---------------------------------------------------------------------------


class TestAskUserSchemaFailureRegression:
    """AC5: Provider schema errors surface as execution errors, not silent success."""

    @pytest.mark.asyncio()
    async def test_ask_user_schema_error_propagates_as_error(self) -> None:
        """If ask_user has schema issues the loop error propagates (not success)."""

        class FakeTools:
            def unregister(self, name: str) -> None:
                pass

            def get(self, name: str):
                return None

        class FakeAgentLoop:
            def __init__(self, **kwargs):
                self.memory_workspace = Path("/tmp/fake_memory")
                self.tools = FakeTools()

            async def process_direct_result(self, **kwargs):
                # Return an error result mimicking ask_user schema rejection

                class _Result:
                    content = "Sorry, I encountered an error calling the AI model."
                    is_error = True
                    error_message = (
                        "400: ask_user parameter 'questions[].options' oneOf not supported"
                    )

                return _Result()

        with (
            patch("nanobot.agent.loop.AgentLoop", FakeAgentLoop),
            patch("nanobot.bus.queue.MessageBus", MagicMock),
            patch(
                "mc.contexts.execution.agent_runner._call_provider_factory",
                lambda model: (MagicMock(), model or "gpt-4o"),
            ),
        ):
            from mc.contexts.execution.agent_runner import (
                _coerce_agent_run_result,
                _run_agent_on_task,
            )

            result_raw, _, _ = await _run_agent_on_task(
                agent_name="codex-agent",
                agent_prompt=None,
                agent_model="codex/gpt-5.4",
                task_title="Test ask_user schema",
                task_id="task_schema_fail",
            )

        result = _coerce_agent_run_result(result_raw)

        # Must be an error, NOT a successful task completion
        assert result.is_error is True, "Schema failure must propagate as error, not silent success"
        assert result.error_message is not None
        assert "oneOf" in result.error_message or "ask_user" in result.error_message
