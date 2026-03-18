"""Tests for NanobotRunnerStrategy MCP-first migration (Story 3 / AC4, AC5).

Proves that:
- When the agent loop returns is_error=True, ExecutionResult.success is False
- Provider/schema errors are categorized as RUNNER (not silently successful)
- The Codex ask_user schema failure scenario produces a failed ExecutionResult
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mc.application.execution.request import (
    EntityType,
    ErrorCategory,
    ExecutionRequest,
    RunnerType,
)
from mc.application.execution.strategies.nanobot import NanobotRunnerStrategy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(title: str = "Test Task", agent_model: str = "gpt-4o") -> ExecutionRequest:
    return ExecutionRequest(
        entity_type=EntityType.TASK,
        entity_id="task_mcp_1",
        task_id="task_mcp_1",
        title=title,
        agent_name="test-agent",
        runner_type=RunnerType.NANOBOT,
        agent_model=agent_model,
        description="Test description",
    )


def _make_fake_loop_result(content: str, is_error: bool = False):
    """Return an object resembling AgentRunResult / DirectProcessResult."""
    from mc.contexts.execution.agent_runner import AgentRunResult

    return AgentRunResult(
        content=content,
        is_error=is_error,
        error_message="Schema error" if is_error else None,
    )


# ---------------------------------------------------------------------------
# AC4: Provider/schema failures propagate as execution errors
# ---------------------------------------------------------------------------


class TestNanobotStrategyErrorPropagation:
    """AC4: is_error=True from the loop must produce ExecutionResult(success=False)."""

    @pytest.mark.asyncio()
    async def test_loop_error_produces_failed_execution_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When AgentRunResult.is_error=True, ExecutionResult.success must be False."""
        from mc.application.execution.strategies import nanobot as nanobot_mod

        fake_loop_obj = object()
        error_result = _make_fake_loop_result("Sorry, I encountered an error.", is_error=True)

        async def fake_run_agent_loop(request, mc_session_id):
            return (error_result, "session_key_err", fake_loop_obj)

        monkeypatch.setattr(nanobot_mod, "_PROVIDER_ERRORS", ())
        strategy = NanobotRunnerStrategy()
        monkeypatch.setattr(strategy, "_run_agent_loop", fake_run_agent_loop)

        result = await strategy.execute(_make_request())

        assert result.success is False, (
            "ExecutionResult.success must be False when loop reports is_error=True"
        )
        assert result.error_category is not None
        assert result.error_message is not None

    @pytest.mark.asyncio()
    async def test_loop_error_is_categorized_as_runner(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """is_error=True from the loop should be categorized as a RUNNER error."""
        from mc.application.execution.strategies import nanobot as nanobot_mod

        error_result = _make_fake_loop_result("Error content", is_error=True)

        async def fake_run_agent_loop(request, mc_session_id):
            return (error_result, "session_key_err", object())

        monkeypatch.setattr(nanobot_mod, "_PROVIDER_ERRORS", ())
        strategy = NanobotRunnerStrategy()
        monkeypatch.setattr(strategy, "_run_agent_loop", fake_run_agent_loop)

        result = await strategy.execute(_make_request())

        assert result.error_category in (ErrorCategory.RUNNER, ErrorCategory.PROVIDER), (
            f"Expected RUNNER or PROVIDER error category, got {result.error_category}"
        )

    @pytest.mark.asyncio()
    async def test_success_result_when_loop_returns_no_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When is_error=False, ExecutionResult.success must be True."""
        from mc.application.execution.strategies import nanobot as nanobot_mod

        class FakeLoop:
            memory_workspace = Path("/tmp/fake_memory")

        success_result = _make_fake_loop_result("Task completed successfully.", is_error=False)

        async def fake_run_agent_loop(request, mc_session_id):
            return (success_result, "session_key_ok", FakeLoop())

        monkeypatch.setattr(nanobot_mod, "_PROVIDER_ERRORS", ())
        strategy = NanobotRunnerStrategy()
        monkeypatch.setattr(strategy, "_run_agent_loop", fake_run_agent_loop)

        result = await strategy.execute(_make_request())

        assert result.success is True
        assert "Task completed successfully." in result.output


# ---------------------------------------------------------------------------
# AC5: Regression — Codex ask_user schema failure does not masquerade as success
# ---------------------------------------------------------------------------


class TestCodexAskUserSchemaRegression:
    """AC5: ask_user schema validation failure on Codex must not appear as task success."""

    @pytest.mark.asyncio()
    async def test_codex_ask_user_schema_failure_is_execution_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Codex rejecting ask_user oneOf schema must yield ExecutionResult(success=False)."""
        from mc.application.execution.strategies import nanobot as nanobot_mod

        # Simulate: Codex rejects the ask_user schema (400 error from provider)
        from mc.contexts.execution.agent_runner import AgentRunResult

        schema_fail_result = AgentRunResult(
            content="Sorry, I encountered an error calling the AI model.",
            is_error=True,
            error_message="400: ask_user parameter 'questions[].options' oneOf not supported",
        )

        async def fake_run_agent_loop(request, mc_session_id):
            return (schema_fail_result, "session_key_codex", object())

        monkeypatch.setattr(nanobot_mod, "_PROVIDER_ERRORS", ())
        strategy = NanobotRunnerStrategy()
        monkeypatch.setattr(strategy, "_run_agent_loop", fake_run_agent_loop)

        request = _make_request(
            title="Codex ask_user schema test",
            agent_model="codex/gpt-5.4",
        )
        result = await strategy.execute(request)

        # This is the regression: the task must NOT be marked successful
        assert result.success is False, (
            "Codex ask_user schema failure must not masquerade as successful task completion"
        )
        assert result.error_category is not None, "Error category must be set"

    @pytest.mark.asyncio()
    async def test_string_result_still_treated_as_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A plain string result (old compat) is still treated as success (no regression)."""
        from mc.application.execution.strategies import nanobot as nanobot_mod

        class FakeLoop:
            memory_workspace = Path("/tmp/fake_memory")

        # Old-style: some callers may return a plain string
        async def fake_run_agent_loop(request, mc_session_id):
            return ("Plain string result.", "session_key_str", FakeLoop())

        monkeypatch.setattr(nanobot_mod, "_PROVIDER_ERRORS", ())
        strategy = NanobotRunnerStrategy()
        monkeypatch.setattr(strategy, "_run_agent_loop", fake_run_agent_loop)

        result = await strategy.execute(_make_request())

        assert result.success is True
        assert "Plain string result." in result.output
