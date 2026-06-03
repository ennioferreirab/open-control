"""Tests for runner strategies (AC2, AC5).

Tests each strategy's happy path and error paths.
"""

from __future__ import annotations

import pytest

from mc.application.execution.request import (
    EntityType,
    ExecutionRequest,
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
