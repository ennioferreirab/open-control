"""Tests for ExecutionEngine (AC1, AC3, AC4, AC5).

Tests strategy selection, error categorization, post-execution pipeline,
and the single run() entry point.
"""

from __future__ import annotations

import pytest

from mc.application.execution.engine import ExecutionEngine, categorize_error
from mc.application.execution.request import (
    EntityType,
    ErrorCategory,
    ExecutionRequest,
    ExecutionResult,
    RunnerType,
)
from mc.application.execution.strategies.base import RunnerStrategy

# ── Fake strategies for testing ────────────────────────────────────────


class FakeSuccessStrategy:
    """Always succeeds with a fixed output."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            output=f"Done: {request.title}",
            session_id="fake_session",
        )


class FakeErrorStrategy:
    """Always returns an error result."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return ExecutionResult(
            success=False,
            error_category=ErrorCategory.RUNNER,
            error_message="Simulated failure",
        )


class FakeCrashStrategy:
    """Raises an unexpected exception."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        raise RuntimeError("Unexpected crash in strategy")


class FakeProviderCrashStrategy:
    """Raises an exception that looks like a provider error."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        raise ValueError("tier 'unknown-tier' is not configured")


# ── categorize_error tests (AC3) ──────────────────────────────────────


class TestCategorizeError:
    """AC3: Centralized error categorization."""

    def test_tier_error(self) -> None:
        exc = ValueError("Unknown tier: 'standard-ultra'")
        assert categorize_error(exc) == ErrorCategory.TIER

    def test_generic_value_error_not_tier(self) -> None:
        exc = ValueError("Invalid argument: missing field")
        assert categorize_error(exc) == ErrorCategory.RUNNER

    def test_runtime_error(self) -> None:
        exc = RuntimeError("Agent loop crashed")
        assert categorize_error(exc) == ErrorCategory.RUNNER

    def test_type_error(self) -> None:
        exc = TypeError("wrong type")
        assert categorize_error(exc) == ErrorCategory.RUNNER


# ── ExecutionEngine tests (AC1) ──────────────────────────────────────


class TestExecutionEngine:
    """AC1: ExecutionEngine class with run() as single entry point."""

    @pytest.fixture()
    def engine(self) -> ExecutionEngine:
        return ExecutionEngine(
            strategies={
                RunnerType.NANOBOT: FakeSuccessStrategy(),
                RunnerType.CLAUDE_CODE: FakeSuccessStrategy(),
                RunnerType.HUMAN: FakeSuccessStrategy(),
            }
        )

    @pytest.fixture()
    def nanobot_request(self) -> ExecutionRequest:
        return ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="task_1",
            task_id="task_1",
            title="Write Report",
            agent_name="nanobot",
            runner_type=RunnerType.NANOBOT,
        )

    @pytest.fixture()
    def cc_request(self) -> ExecutionRequest:
        return ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="task_2",
            task_id="task_2",
            title="Build Feature",
            agent_name="coder",
            runner_type=RunnerType.CLAUDE_CODE,
        )

    @pytest.fixture()
    def human_request(self) -> ExecutionRequest:
        return ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="task_3",
            task_id="task_3",
            title="Review Design",
            agent_name="reviewer",
            runner_type=RunnerType.HUMAN,
        )

    @pytest.mark.asyncio()
    async def test_run_nanobot_success(
        self, engine: ExecutionEngine, nanobot_request: ExecutionRequest
    ) -> None:
        result = await engine.run(nanobot_request)
        assert result.success is True
        assert "Write Report" in result.output

    @pytest.mark.asyncio()
    async def test_run_claude_code_success(
        self, engine: ExecutionEngine, cc_request: ExecutionRequest
    ) -> None:
        result = await engine.run(cc_request)
        assert result.success is True
        assert "Build Feature" in result.output

    @pytest.mark.asyncio()
    async def test_run_human_success(
        self, engine: ExecutionEngine, human_request: ExecutionRequest
    ) -> None:
        result = await engine.run(human_request)
        assert result.success is True

    @pytest.mark.asyncio()
    async def test_strategy_selection_by_runner_type(self) -> None:
        """Engine selects correct strategy based on runner_type."""
        nanobot_strategy = FakeSuccessStrategy()
        cc_strategy = FakeErrorStrategy()

        engine = ExecutionEngine(
            strategies={
                RunnerType.NANOBOT: nanobot_strategy,
                RunnerType.CLAUDE_CODE: cc_strategy,
            }
        )

        req_nb = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t1",
            task_id="t1",
            title="NB",
            agent_name="nb",
            runner_type=RunnerType.NANOBOT,
        )
        req_cc = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t2",
            task_id="t2",
            title="CC",
            agent_name="cc",
            runner_type=RunnerType.CLAUDE_CODE,
        )

        result_nb = await engine.run(req_nb)
        result_cc = await engine.run(req_cc)

        assert result_nb.success is True
        assert result_cc.success is False

    @pytest.mark.asyncio()
    async def test_unknown_runner_type(self) -> None:
        """Engine returns workflow error for unknown runner type."""
        engine = ExecutionEngine(strategies={})
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t1",
            task_id="t1",
            title="Test",
            agent_name="a",
            runner_type=RunnerType.NANOBOT,
        )
        result = await engine.run(req)
        assert result.success is False
        assert result.error_category == ErrorCategory.WORKFLOW

    @pytest.mark.asyncio()
    async def test_strategy_crash_is_caught(self) -> None:
        """Unexpected strategy exceptions are caught and categorized (AC3)."""
        engine = ExecutionEngine(strategies={RunnerType.NANOBOT: FakeCrashStrategy()})
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t1",
            task_id="t1",
            title="Crash Test",
            agent_name="a",
            runner_type=RunnerType.NANOBOT,
        )
        result = await engine.run(req)
        assert result.success is False
        assert result.error_category == ErrorCategory.RUNNER
        assert "Unexpected crash" in (result.error_message or "")

    @pytest.mark.asyncio()
    async def test_tier_error_in_strategy_crash(self) -> None:
        """Tier-related ValueError in strategy is categorized as TIER (AC3)."""
        engine = ExecutionEngine(strategies={RunnerType.NANOBOT: FakeProviderCrashStrategy()})
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t1",
            task_id="t1",
            title="Tier Test",
            agent_name="a",
            runner_type=RunnerType.NANOBOT,
        )
        result = await engine.run(req)
        assert result.success is False
        assert result.error_category == ErrorCategory.TIER

    @pytest.mark.asyncio()
    async def test_error_strategy_returns_error_result(self) -> None:
        """Strategy-reported errors are passed through."""
        engine = ExecutionEngine(strategies={RunnerType.NANOBOT: FakeErrorStrategy()})
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t1",
            task_id="t1",
            title="Fail",
            agent_name="a",
            runner_type=RunnerType.NANOBOT,
        )
        result = await engine.run(req)
        assert result.success is False
        assert result.error_category == ErrorCategory.RUNNER
        assert result.error_message == "Simulated failure"

    def test_get_strategy(self, engine: ExecutionEngine) -> None:
        """get_strategy returns the correct strategy."""
        strategy = engine.get_strategy(RunnerType.NANOBOT)
        assert isinstance(strategy, FakeSuccessStrategy)

    def test_get_strategy_missing(self) -> None:
        """get_strategy raises KeyError for missing type."""
        engine = ExecutionEngine(strategies={})
        with pytest.raises(KeyError, match="No strategy registered"):
            engine.get_strategy(RunnerType.NANOBOT)


# ── Post-execution pipeline tests (AC4) ─────────────────────────────


class TestPostExecution:
    """AC4: Post-execution steps run once through the engine."""

    @pytest.mark.asyncio()
    async def test_hooks_run_on_success(self) -> None:
        """Post-execution hooks are called after successful execution."""
        calls: list[tuple[str, bool]] = []

        async def hook(req: ExecutionRequest, res: ExecutionResult) -> None:
            calls.append((req.task_id, res.success))

        engine = ExecutionEngine(
            strategies={RunnerType.NANOBOT: FakeSuccessStrategy()},
            post_execution_hooks=[hook],
        )
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t1",
            task_id="t1",
            title="Test",
            agent_name="a",
            runner_type=RunnerType.NANOBOT,
        )
        await engine.run(req)

        assert len(calls) == 1
        assert calls[0] == ("t1", True)

    @pytest.mark.asyncio()
    async def test_hooks_run_on_failure(self) -> None:
        """Post-execution hooks are called even on failure."""
        calls: list[tuple[str, bool]] = []

        async def hook(req: ExecutionRequest, res: ExecutionResult) -> None:
            calls.append((req.task_id, res.success))

        engine = ExecutionEngine(
            strategies={RunnerType.NANOBOT: FakeErrorStrategy()},
            post_execution_hooks=[hook],
        )
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t_fail",
            task_id="t_fail",
            title="Fail",
            agent_name="a",
            runner_type=RunnerType.NANOBOT,
        )
        await engine.run(req)

        assert len(calls) == 1
        assert calls[0] == ("t_fail", False)

    @pytest.mark.asyncio()
    async def test_hooks_run_on_crash(self) -> None:
        """Post-execution hooks are called even on strategy crash."""
        calls: list[tuple[str, bool]] = []

        async def hook(req: ExecutionRequest, res: ExecutionResult) -> None:
            calls.append((req.task_id, res.success))

        engine = ExecutionEngine(
            strategies={RunnerType.NANOBOT: FakeCrashStrategy()},
            post_execution_hooks=[hook],
        )
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t_crash",
            task_id="t_crash",
            title="Crash",
            agent_name="a",
            runner_type=RunnerType.NANOBOT,
        )
        await engine.run(req)

        assert len(calls) == 1
        assert calls[0] == ("t_crash", False)

    @pytest.mark.asyncio()
    async def test_multiple_hooks_all_run(self) -> None:
        """All hooks run in order."""
        order: list[int] = []

        async def hook1(req: ExecutionRequest, res: ExecutionResult) -> None:
            order.append(1)

        async def hook2(req: ExecutionRequest, res: ExecutionResult) -> None:
            order.append(2)

        async def hook3(req: ExecutionRequest, res: ExecutionResult) -> None:
            order.append(3)

        engine = ExecutionEngine(
            strategies={RunnerType.NANOBOT: FakeSuccessStrategy()},
            post_execution_hooks=[hook1, hook2, hook3],
        )
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t1",
            task_id="t1",
            title="Test",
            agent_name="a",
            runner_type=RunnerType.NANOBOT,
        )
        await engine.run(req)

        assert order == [1, 2, 3]

    @pytest.mark.asyncio()
    async def test_hook_failure_isolated(self) -> None:
        """A failing hook does not prevent subsequent hooks from running."""
        calls: list[int] = []

        async def failing_hook(req: ExecutionRequest, res: ExecutionResult) -> None:
            calls.append(1)
            raise RuntimeError("Hook crashed")

        async def ok_hook(req: ExecutionRequest, res: ExecutionResult) -> None:
            calls.append(2)

        engine = ExecutionEngine(
            strategies={RunnerType.NANOBOT: FakeSuccessStrategy()},
            post_execution_hooks=[failing_hook, ok_hook],
        )
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t1",
            task_id="t1",
            title="Test",
            agent_name="a",
            runner_type=RunnerType.NANOBOT,
        )
        result = await engine.run(req)

        # Both hooks ran, and the overall result is still success
        assert calls == [1, 2]
        assert result.success is True

    @pytest.mark.asyncio()
    async def test_hooks_work_identically_for_step_and_task(self) -> None:
        """AC4: hooks work identically for task and step execution."""
        calls: list[str | None] = []

        async def hook(req: ExecutionRequest, res: ExecutionResult) -> None:
            calls.append(req.step_id)

        engine = ExecutionEngine(
            strategies={RunnerType.NANOBOT: FakeSuccessStrategy()},
            post_execution_hooks=[hook],
        )

        # Task-level (no step_id)
        task_req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t1",
            task_id="t1",
            title="Task",
            agent_name="a",
            runner_type=RunnerType.NANOBOT,
        )
        await engine.run(task_req)

        # Step-level (with step_id)
        step_req = ExecutionRequest(
            entity_type=EntityType.STEP,
            entity_id="step_42",
            task_id="t1",
            title="Step",
            agent_name="a",
            runner_type=RunnerType.NANOBOT,
            step_id="step_42",
        )
        await engine.run(step_req)

        assert calls == [None, "step_42"]


# ── Protocol compliance tests ────────────────────────────────────────


class TestProtocolCompliance:
    """Verify all strategies satisfy the RunnerStrategy protocol."""

    def test_fake_success_is_strategy(self) -> None:
        assert isinstance(FakeSuccessStrategy(), RunnerStrategy)

    def test_fake_error_is_strategy(self) -> None:
        assert isinstance(FakeErrorStrategy(), RunnerStrategy)
