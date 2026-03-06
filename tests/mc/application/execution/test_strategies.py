"""Tests for runner strategies (AC2, AC5).

Tests each strategy's happy path and error paths.
"""

from __future__ import annotations

import pytest

from mc.application.execution.request import (
    EntityType,
    ErrorCategory,
    ExecutionRequest,
    ExecutionResult,
    RunnerType,
)
from mc.application.execution.strategies.base import RunnerStrategy
from mc.application.execution.strategies.human import HumanRunnerStrategy

# ── HumanRunnerStrategy Tests ──────────────────────────────────────────


class TestHumanRunnerStrategy:
    """AC2: Human strategy NEVER spawns a process."""

    @pytest.fixture()
    def strategy(self) -> HumanRunnerStrategy:
        return HumanRunnerStrategy()

    @pytest.fixture()
    def exec_request(self) -> ExecutionRequest:
        return ExecutionRequest(
            entity_type=EntityType.STEP,
            entity_id="step_42",
            task_id="task_human_1",
            title="Review Design",
            agent_name="human-reviewer",
            runner_type=RunnerType.HUMAN,
            step_id="step_42",
        )

    @pytest.mark.asyncio()
    async def test_returns_waiting_human_transition(
        self, strategy: HumanRunnerStrategy, exec_request: ExecutionRequest
    ) -> None:
        result = await strategy.execute(exec_request)
        assert result.success is True
        assert result.transition_status == "waiting_human"
        assert result.output  # non-empty message

    @pytest.mark.asyncio()
    async def test_no_process_spawned(
        self, strategy: HumanRunnerStrategy, exec_request: ExecutionRequest
    ) -> None:
        """Verify no external process or network call is made."""
        result = await strategy.execute(exec_request)
        assert result.success is True
        assert result.error_category is None
        assert result.error_message is None
        assert result.cost_usd == 0.0
        assert result.session_id is None

    @pytest.mark.asyncio()
    async def test_without_step_id(self, strategy: HumanRunnerStrategy) -> None:
        """Works for task-level execution too (no step_id)."""
        request = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="task_human_2",
            task_id="task_human_2",
            title="Manual Task",
            agent_name="user",
            runner_type=RunnerType.HUMAN,
        )
        result = await strategy.execute(request)
        assert result.success is True
        assert result.transition_status == "waiting_human"

    def test_satisfies_protocol(self, strategy: HumanRunnerStrategy) -> None:
        assert isinstance(strategy, RunnerStrategy)


# ── NanobotRunnerStrategy Tests ──────────────────────────────────────


class TestNanobotRunnerStrategy:
    """AC2 + AC5: Nanobot strategy happy path and error paths."""

    @pytest.fixture()
    def exec_request(self) -> ExecutionRequest:
        return ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="task_nb_1",
            task_id="task_nb_1",
            title="Write Report",
            agent_name="nanobot",
            runner_type=RunnerType.NANOBOT,
            agent_model="gpt-4o",
            description="Write a summary report",
        )

    @pytest.mark.asyncio()
    async def test_happy_path(
        self, exec_request: ExecutionRequest, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Successful nanobot execution returns output."""
        from mc.application.execution.strategies import nanobot as nanobot_mod

        class FakeLoop:
            memory_workspace = "/tmp/fake"

        async def fake_run(*args, **kwargs):
            return ("Report written.", "session_key_1", FakeLoop())

        monkeypatch.setattr(nanobot_mod, "_collect_provider_error_types", lambda: ())
        # Need to patch _PROVIDER_ERRORS at module level
        monkeypatch.setattr(nanobot_mod, "_PROVIDER_ERRORS", ())

        from mc.application.execution.strategies.nanobot import NanobotRunnerStrategy

        strategy = NanobotRunnerStrategy()
        monkeypatch.setattr(strategy, "_run_agent_loop", fake_run)

        result = await strategy.execute(exec_request)
        assert result.success is True
        assert result.output == "Report written."
        assert result.session_id == "session_key_1"

    @pytest.mark.asyncio()
    async def test_runner_error(
        self, exec_request: ExecutionRequest, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Runner errors are categorized correctly."""
        from mc.application.execution.strategies import nanobot as nanobot_mod

        monkeypatch.setattr(nanobot_mod, "_PROVIDER_ERRORS", ())

        from mc.application.execution.strategies.nanobot import NanobotRunnerStrategy

        strategy = NanobotRunnerStrategy()

        async def failing_run(*args, **kwargs):
            raise RuntimeError("Agent loop crashed")

        monkeypatch.setattr(strategy, "_run_agent_loop", failing_run)

        result = await strategy.execute(exec_request)
        assert result.success is False
        assert result.error_category == ErrorCategory.RUNNER
        assert "Agent loop crashed" in (result.error_message or "")

    @pytest.mark.asyncio()
    async def test_provider_error(
        self, exec_request: ExecutionRequest, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider errors are categorized as PROVIDER."""
        from mc.application.execution.strategies import nanobot as nanobot_mod

        class FakeProviderError(Exception):
            pass

        monkeypatch.setattr(nanobot_mod, "_PROVIDER_ERRORS", (FakeProviderError,))

        from mc.application.execution.strategies.nanobot import NanobotRunnerStrategy

        strategy = NanobotRunnerStrategy()

        async def provider_fail(*args, **kwargs):
            raise FakeProviderError("OAuth expired")

        monkeypatch.setattr(strategy, "_run_agent_loop", provider_fail)

        result = await strategy.execute(exec_request)
        assert result.success is False
        assert result.error_category == ErrorCategory.PROVIDER
        assert "OAuth expired" in (result.error_message or "")

    def test_satisfies_protocol(self) -> None:
        from mc.application.execution.strategies.nanobot import NanobotRunnerStrategy

        assert isinstance(NanobotRunnerStrategy(), RunnerStrategy)


# ── ClaudeCodeRunnerStrategy Tests ──────────────────────────────────


class TestClaudeCodeRunnerStrategy:
    """AC2 + AC5: Claude Code strategy happy path and error paths."""

    @pytest.fixture()
    def exec_request(self) -> ExecutionRequest:
        return ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="task_cc_1",
            task_id="task_cc_1",
            title="Build Feature",
            agent_name="coder",
            runner_type=RunnerType.CLAUDE_CODE,
            agent_model="cc/claude-sonnet-4-20250514",
            description="Implement the feature",
        )

    @pytest.mark.asyncio()
    async def test_happy_path(
        self, exec_request: ExecutionRequest, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Successful CC execution returns output and cost."""
        from mc.application.execution.strategies import claude_code as cc_mod

        monkeypatch.setattr(cc_mod, "_PROVIDER_ERRORS", ())

        from mc.application.execution.strategies.claude_code import (
            ClaudeCodeRunnerStrategy,
        )

        strategy = ClaudeCodeRunnerStrategy()

        async def fake_run(req: ExecutionRequest) -> ExecutionResult:
            return ExecutionResult(
                success=True,
                output="Feature implemented.",
                cost_usd=0.05,
                session_id="cc_sess_1",
            )

        monkeypatch.setattr(strategy, "_run_cc", fake_run)

        result = await strategy.execute(exec_request)
        assert result.success is True
        assert result.output == "Feature implemented."
        assert result.cost_usd == 0.05
        assert result.session_id == "cc_sess_1"

    @pytest.mark.asyncio()
    async def test_runner_error(
        self, exec_request: ExecutionRequest, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Runner errors are categorized correctly."""
        from mc.application.execution.strategies import claude_code as cc_mod

        monkeypatch.setattr(cc_mod, "_PROVIDER_ERRORS", ())

        from mc.application.execution.strategies.claude_code import (
            ClaudeCodeRunnerStrategy,
        )

        strategy = ClaudeCodeRunnerStrategy()

        async def failing_run(req: ExecutionRequest) -> ExecutionResult:
            raise RuntimeError("CC workspace prep failed")

        monkeypatch.setattr(strategy, "_run_cc", failing_run)

        result = await strategy.execute(exec_request)
        assert result.success is False
        assert result.error_category == ErrorCategory.RUNNER
        assert "CC workspace prep failed" in (result.error_message or "")

    @pytest.mark.asyncio()
    async def test_provider_error(
        self, exec_request: ExecutionRequest, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider errors are categorized as PROVIDER."""
        from mc.application.execution.strategies import claude_code as cc_mod

        class FakeProviderError(Exception):
            pass

        monkeypatch.setattr(cc_mod, "_PROVIDER_ERRORS", (FakeProviderError,))

        from mc.application.execution.strategies.claude_code import (
            ClaudeCodeRunnerStrategy,
        )

        strategy = ClaudeCodeRunnerStrategy()

        async def provider_fail(req: ExecutionRequest) -> ExecutionResult:
            raise FakeProviderError("API key invalid")

        monkeypatch.setattr(strategy, "_run_cc", provider_fail)

        result = await strategy.execute(exec_request)
        assert result.success is False
        assert result.error_category == ErrorCategory.PROVIDER

    def test_satisfies_protocol(self) -> None:
        from mc.application.execution.strategies.claude_code import (
            ClaudeCodeRunnerStrategy,
        )

        assert isinstance(ClaudeCodeRunnerStrategy(), RunnerStrategy)
