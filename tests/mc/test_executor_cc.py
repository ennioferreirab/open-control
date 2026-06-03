"""Tests for Claude Code backend integration in TaskExecutor.

Covers:
- Backend routing: claude-code → ACP engine path
- Provider CLI backend → engine execution path
- cc/ model prefix → ACP engine path with synthetic agent data
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.contexts.execution.executor import TaskExecutor
from mc.types import (
    AgentData,
    ClaudeCodeOpts,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.send_message = MagicMock(return_value=None)
    bridge.create_activity = MagicMock(return_value=None)
    bridge.update_task_status = MagicMock(return_value=None)
    bridge.get_board_by_id = MagicMock(return_value={"name": "default"})
    return bridge


def _make_executor(bridge: MagicMock | None = None) -> TaskExecutor:
    bridge = bridge or _make_bridge()
    return TaskExecutor(bridge)


def _cc_agent(backend: str = "claude-code") -> AgentData:
    return AgentData(
        name="my-cc-agent",
        display_name="CC Agent",
        role="developer",
        backend=backend,
        claude_code_opts=ClaudeCodeOpts(max_budget_usd=1.0, max_turns=10),
    )


# ---------------------------------------------------------------------------
# Backend routing: claude-code → ACP engine
# ---------------------------------------------------------------------------


class TestBackendRouting:
    """_execute_task routes direct interactive work through the ExecutionEngine."""

    @pytest.mark.asyncio
    async def test_claude_code_backend_routes_direct_task_through_acp(self):
        executor = _make_executor()
        agent_data = _cc_agent(backend="claude-code")

        from mc.application.execution.request import (
            EntityType,
            ExecutionRequest,
            ExecutionResult,
            RunnerType,
        )

        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t1",
            task_id="t1",
            title="Test task",
            description="desc",
            agent_name="my-cc-agent",
            is_cc=False,
            files_dir="/tmp/test-files",
            output_dir="/tmp/test-output",
        )
        engine = MagicMock()
        engine.run = AsyncMock(return_value=ExecutionResult(success=True, output="cc result"))

        with (
            patch(
                "mc.application.execution.context_builder.ContextBuilder.build_task_context",
                new_callable=AsyncMock,
                return_value=req,
            ),
            patch.object(executor, "_load_agent_data", return_value=agent_data),
            patch.object(
                executor,
                "_build_execution_engine",
                return_value=engine,
                create=True,
            ),
            patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]),
        ):
            await executor._execute_task(
                task_id="t1",
                title="Test task",
                description="desc",
                agent_name="my-cc-agent",
                trust_level="autonomous",
            )

        engine.run.assert_awaited_once()
        request = engine.run.await_args.args[0]
        assert request.runner_type == RunnerType.ACP
        assert request.agent == agent_data
        assert request.agent_name == "my-cc-agent"

    @pytest.mark.asyncio
    async def test_provider_cli_backend_routes_through_engine(self):
        executor = _make_executor()
        agent_data = _cc_agent(backend="claude-code")

        from mc.application.execution.request import (
            EntityType,
            ExecutionRequest,
            ExecutionResult,
        )

        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t2",
            task_id="t2",
            title="Provider CLI task",
            agent_name="my-cc-agent",
            is_cc=False,
            files_dir="/tmp/test-files",
            output_dir="/tmp/test-output",
        )

        engine = MagicMock()
        engine.run = AsyncMock(return_value=ExecutionResult(success=True, output="result"))

        with (
            patch(
                "mc.application.execution.context_builder.ContextBuilder.build_task_context",
                new_callable=AsyncMock,
                return_value=req,
            ),
            patch.object(executor, "_load_agent_data", return_value=agent_data),
            patch.object(
                executor,
                "_build_execution_engine",
                return_value=engine,
                create=True,
            ),
            patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]),
        ):
            await executor._execute_task(
                task_id="t2",
                title="Provider CLI task",
                description=None,
                agent_name="my-cc-agent",
                trust_level="autonomous",
            )

        engine.run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_agent_data_routes_through_engine(self):
        """When no agent data exists, executor still routes through ExecutionEngine."""
        executor = _make_executor()

        from mc.application.execution.request import (
            EntityType,
            ExecutionRequest,
            ExecutionResult,
        )

        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t3",
            task_id="t3",
            title="Unregistered agent",
            agent_name="unknown-agent",
            is_cc=False,
            files_dir="/tmp/test-files",
            output_dir="/tmp/test-output",
        )

        engine = MagicMock()
        engine.run = AsyncMock(return_value=ExecutionResult(success=True, output="result"))

        with (
            patch(
                "mc.application.execution.context_builder.ContextBuilder.build_task_context",
                new_callable=AsyncMock,
                return_value=req,
            ),
            patch.object(executor, "_load_agent_data", return_value=None),
            patch.object(
                executor,
                "_build_execution_engine",
                return_value=engine,
                create=True,
            ),
            patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]),
        ):
            await executor._execute_task(
                task_id="t3",
                title="Unregistered agent",
                description=None,
                agent_name="unknown-agent",
                trust_level="autonomous",
            )

        engine.run.assert_awaited_once()


# ---------------------------------------------------------------------------
# cc/ model prefix routing
# ---------------------------------------------------------------------------


class TestCCModelRouting:
    """cc/ model prefix detected by ContextBuilder routes through ExecutionEngine to ACP."""

    @pytest.mark.asyncio
    async def test_cc_model_routes_direct_task_through_acp(self):
        """When agent_model resolves to cc/*, direct tasks should use ACP."""
        bridge = _make_bridge()
        executor = _make_executor(bridge)

        cc_agent = AgentData(
            name="test-agent",
            display_name="Test Agent",
            role="worker",
            model="cc/claude-sonnet-4-6",
            backend="claude-code",
        )

        from mc.application.execution.request import (
            EntityType,
            ExecutionRequest,
            ExecutionResult,
            RunnerType,
        )

        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="task-123",
            task_id="task-123",
            title="Test Task",
            description="Test description",
            agent_name="test-agent",
            agent_model="cc/claude-sonnet-4-6",
            is_cc=True,
            model="claude-sonnet-4-6",
            agent=cc_agent,
            files_dir="/tmp/test-files",
            output_dir="/tmp/test-output",
        )
        engine = MagicMock()
        engine.run = AsyncMock(return_value=ExecutionResult(success=True, output="cc result"))

        with (
            patch(
                "mc.application.execution.context_builder.ContextBuilder.build_task_context",
                new_callable=AsyncMock,
                return_value=req,
            ),
            patch.object(executor, "_load_agent_data", return_value=cc_agent),
            patch.object(
                executor,
                "_build_execution_engine",
                return_value=engine,
                create=True,
            ),
            patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]),
        ):
            await executor._execute_task(
                task_id="task-123",
                title="Test Task",
                description="Test description",
                agent_name="test-agent",
                trust_level="autonomous",
            )

        engine.run.assert_awaited_once()
        request = engine.run.await_args.args[0]
        assert request.runner_type == RunnerType.ACP
        assert request.agent is cc_agent
        assert request.agent.model == "claude-sonnet-4-6"
        assert request.agent.backend == "claude-code"
        assert request.session_boundary_reason == "task_completion"

    @pytest.mark.asyncio
    async def test_cc_model_creates_synthetic_agent_data_when_none(self):
        """When _load_agent_data returns None, the engine gets synthetic CC agent data."""
        bridge = _make_bridge()
        executor = _make_executor(bridge)

        from mc.application.execution.request import (
            EntityType,
            ExecutionRequest,
            ExecutionResult,
            RunnerType,
        )

        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="task-456",
            task_id="task-456",
            title="Opus Task",
            agent_name="unknown-agent",
            is_cc=True,
            model="claude-opus-4-6",
            agent=None,
            files_dir="/tmp/test-files",
            output_dir="/tmp/test-output",
        )
        engine = MagicMock()
        engine.run = AsyncMock(return_value=ExecutionResult(success=True, output="cc result"))

        with (
            patch(
                "mc.application.execution.context_builder.ContextBuilder.build_task_context",
                new_callable=AsyncMock,
                return_value=req,
            ),
            patch.object(executor, "_load_agent_data", return_value=None),
            patch.object(
                executor,
                "_build_execution_engine",
                return_value=engine,
                create=True,
            ),
            patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]),
        ):
            await executor._execute_task(
                task_id="task-456",
                title="Opus Task",
                description=None,
                agent_name="unknown-agent",
                trust_level="autonomous",
            )

        engine.run.assert_awaited_once()
        request = engine.run.await_args.args[0]
        assert request.runner_type == RunnerType.ACP
        assert request.agent is not None
        assert request.agent.model == "claude-opus-4-6"
        assert request.agent.backend == "claude-code"
        assert request.agent.name == "unknown-agent"
        assert request.session_boundary_reason == "task_completion"


# ---------------------------------------------------------------------------
# _load_agent_data
# ---------------------------------------------------------------------------


class TestLoadAgentData:
    def test_returns_none_for_missing_config(self, tmp_path):
        executor = _make_executor()
        with patch("mc.infrastructure.config.AGENTS_DIR", tmp_path):
            result = executor._load_agent_data("no-such-agent")
        assert result is None

    def test_returns_agent_data_for_valid_config(self, tmp_path):
        agent_dir = tmp_path / "my-agent"
        agent_dir.mkdir()
        (agent_dir / "config.yaml").write_text("name: my-agent\n")

        expected = AgentData(
            name="my-agent",
            display_name="My Agent",
            role="developer",
            backend="claude-code",
        )

        executor = _make_executor()
        with (
            patch("mc.infrastructure.config.AGENTS_DIR", tmp_path),
            patch(
                "mc.infrastructure.agents.yaml_validator.validate_agent_file", return_value=expected
            ),
        ):
            result = executor._load_agent_data("my-agent")

        assert result is not None
        assert result.backend == "claude-code"

    def test_returns_none_for_invalid_config(self, tmp_path):
        agent_dir = tmp_path / "bad-agent"
        agent_dir.mkdir()
        (agent_dir / "config.yaml").write_text("name: bad-agent\n")

        executor = _make_executor()
        with (
            patch("mc.infrastructure.config.AGENTS_DIR", tmp_path),
            patch(
                "mc.infrastructure.agents.yaml_validator.validate_agent_file",
                return_value=["validation error"],
            ),
        ):
            result = executor._load_agent_data("bad-agent")

        assert result is None
