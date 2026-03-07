"""Tests for cc_step_runner ExecutionEngine integration (Story 20.1, Task 2).

Verifies that execute_step_via_cc delegates to ExecutionEngine.run() and
no longer calls executor private functions directly.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.application.execution.request import (
    EntityType,
    ExecutionRequest,
    ExecutionResult,
    RunnerType,
)

MC_ROOT = Path(__file__).resolve().parent.parent.parent / "mc"


# ── Architecture: cc_step_runner must not import mc.executor ────────────


class TestCCStepRunnerArchitecture:
    """Verify cc_step_runner does not import mc.executor directly."""

    def test_no_executor_imports(self) -> None:
        """cc_step_runner must not import from mc.executor."""
        filepath = MC_ROOT / "cc_step_runner.py"
        assert filepath.exists(), "cc_step_runner.py must exist"

        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
        executor_imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "mc.executor" or alias.name.startswith(
                        "mc.executor."
                    ):
                        executor_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and (
                    node.module == "mc.executor"
                    or node.module.startswith("mc.executor.")
                ):
                    executor_imports.append(node.module)
        assert executor_imports == [], (
            f"cc_step_runner.py still imports from mc.executor: {executor_imports}"
        )


# ── Integration: cc_step_runner delegates to ExecutionEngine ──────────


class TestCCStepRunnerEngineIntegration:
    """Verify execute_step_via_cc routes through ExecutionEngine.run()."""

    @pytest.mark.asyncio
    async def test_delegates_to_execution_engine(self, tmp_path: Path) -> None:
        """execute_step_via_cc must call ExecutionEngine.run()."""
        from mc.cc_step_runner import execute_step_via_cc

        mock_engine_result = ExecutionResult(
            success=True,
            output="Step completed via engine",
            session_id="sess-1",
            memory_workspace=tmp_path,
        )

        mock_engine = MagicMock()
        mock_engine.run = AsyncMock(return_value=mock_engine_result)

        bridge = MagicMock()
        bridge.check_and_unblock_dependents = MagicMock(return_value=["step-2"])
        bridge.post_step_completion = MagicMock()
        bridge.update_step_status = MagicMock()
        bridge.create_activity = MagicMock()
        bridge.sync_task_output_files = MagicMock()
        bridge.get_agent_by_name = MagicMock(return_value=None)

        agents_dir = tmp_path / "agents"
        config_dir = agents_dir / "test-agent"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "name: test-agent\nmodel: cc/claude-sonnet-4-6"
        )

        with (
            patch(
                "mc.cc_step_runner.ExecutionEngine",
                return_value=mock_engine,
            ),
            patch(
                "mc.infrastructure.config.AGENTS_DIR",
                agents_dir,
            ),
            patch(
                "mc.infrastructure.agents.yaml_validator.validate_agent_file",
                return_value=MagicMock(
                    name="test-agent",
                    display_name="Test Agent",
                    model="cc/claude-sonnet-4-6",
                    skills=[],
                    prompt="Be helpful",
                    backend="claude-code",
                ),
            ),
        ):
            unblocked = await execute_step_via_cc(
                bridge=bridge,
                step_id="step-1",
                task_id="task-1",
                agent_name="test-agent",
                agent_model="cc/claude-sonnet-4-6",
                agent_prompt="Be helpful",
                agent_skills=[],
                step_title="Test Step",
                execution_description="Do the thing",
                task_data={},
                pre_snapshot={},
            )

        # ExecutionEngine.run() was called
        mock_engine.run.assert_called_once()

        # The request passed to run() is an ExecutionRequest
        call_args = mock_engine.run.call_args
        request = call_args[0][0]
        assert isinstance(request, ExecutionRequest)
        assert request.runner_type == RunnerType.CLAUDE_CODE
        assert request.task_id == "task-1"
        assert request.step_id == "step-1"
        assert request.agent_name == "test-agent"

    @pytest.mark.asyncio
    async def test_builds_correct_execution_request(
        self, tmp_path: Path
    ) -> None:
        """The ExecutionRequest has correct step context fields."""
        from mc.cc_step_runner import execute_step_via_cc

        mock_engine_result = ExecutionResult(
            success=True,
            output="Done",
            memory_workspace=tmp_path,
        )

        captured_request: list[ExecutionRequest] = []

        async def capture_run(req: ExecutionRequest) -> ExecutionResult:
            captured_request.append(req)
            return mock_engine_result

        mock_engine = MagicMock()
        mock_engine.run = AsyncMock(side_effect=capture_run)

        bridge = MagicMock()
        bridge.check_and_unblock_dependents = MagicMock(return_value=[])
        bridge.post_step_completion = MagicMock()
        bridge.update_step_status = MagicMock()
        bridge.create_activity = MagicMock()
        bridge.sync_task_output_files = MagicMock()
        bridge.get_agent_by_name = MagicMock(return_value=None)

        agents_dir = tmp_path / "agents"
        config_dir = agents_dir / "test-agent"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "name: test-agent\nmodel: cc/claude-sonnet-4-6"
        )

        with (
            patch(
                "mc.cc_step_runner.ExecutionEngine",
                return_value=mock_engine,
            ),
            patch(
                "mc.infrastructure.config.AGENTS_DIR",
                agents_dir,
            ),
            patch(
                "mc.infrastructure.agents.yaml_validator.validate_agent_file",
                return_value=MagicMock(
                    name="test-agent",
                    display_name="Test Agent",
                    model="cc/claude-sonnet-4-6",
                    skills=["skill-a"],
                    prompt="System prompt",
                    backend="claude-code",
                ),
            ),
        ):
            await execute_step_via_cc(
                bridge=bridge,
                step_id="step-42",
                task_id="task-7",
                agent_name="test-agent",
                agent_model="cc/claude-sonnet-4-6",
                agent_prompt="System prompt",
                agent_skills=["skill-a"],
                step_title="Build Feature",
                execution_description="Implement the module",
                task_data={"title": "Parent Task"},
                pre_snapshot={"output/old.txt": 1234.0},
            )

        assert len(captured_request) == 1
        req = captured_request[0]
        assert req.entity_type == EntityType.STEP
        assert req.entity_id == "step-42"
        assert req.step_id == "step-42"
        assert req.task_id == "task-7"
        assert req.title == "Build Feature"
        assert req.agent_name == "test-agent"
        assert req.runner_type == RunnerType.CLAUDE_CODE

    @pytest.mark.asyncio
    async def test_post_execution_on_success(self, tmp_path: Path) -> None:
        """On success, post-execution steps (completion, status, activity) run."""
        from mc.cc_step_runner import execute_step_via_cc

        mock_engine_result = ExecutionResult(
            success=True,
            output="Step done",
            memory_workspace=tmp_path,
        )

        mock_engine = MagicMock()
        mock_engine.run = AsyncMock(return_value=mock_engine_result)

        bridge = MagicMock()
        bridge.check_and_unblock_dependents = MagicMock(
            return_value=["step-next"]
        )
        bridge.post_step_completion = MagicMock()
        bridge.update_step_status = MagicMock()
        bridge.create_activity = MagicMock()
        bridge.sync_task_output_files = MagicMock()
        bridge.get_agent_by_name = MagicMock(return_value=None)

        agents_dir = tmp_path / "agents"
        config_dir = agents_dir / "test-agent"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "name: test-agent\nmodel: cc/claude-sonnet-4-6"
        )

        with (
            patch(
                "mc.cc_step_runner.ExecutionEngine",
                return_value=mock_engine,
            ),
            patch(
                "mc.infrastructure.config.AGENTS_DIR",
                agents_dir,
            ),
            patch(
                "mc.infrastructure.agents.yaml_validator.validate_agent_file",
                return_value=MagicMock(
                    name="test-agent",
                    display_name="Test Agent",
                    model="cc/claude-sonnet-4-6",
                    skills=[],
                    prompt=None,
                    backend="claude-code",
                ),
            ),
        ):
            unblocked = await execute_step_via_cc(
                bridge=bridge,
                step_id="step-1",
                task_id="task-1",
                agent_name="test-agent",
                agent_model="cc/claude-sonnet-4-6",
                agent_prompt=None,
                agent_skills=[],
                step_title="Test Step",
                execution_description="Do it",
                task_data={},
                pre_snapshot={},
            )

        # post_step_completion called
        bridge.post_step_completion.assert_called_once()
        # update_step_status called with COMPLETED
        bridge.update_step_status.assert_called_once()
        # create_activity called
        bridge.create_activity.assert_called_once()
        # unblocked list returned
        assert unblocked == ["step-next"]

    @pytest.mark.asyncio
    async def test_engine_failure_raises(self, tmp_path: Path) -> None:
        """When ExecutionEngine returns failure, an exception is raised."""
        from mc.cc_step_runner import execute_step_via_cc

        mock_engine_result = ExecutionResult(
            success=False,
            error_message="CC execution failed",
            memory_workspace=tmp_path,
        )

        mock_engine = MagicMock()
        mock_engine.run = AsyncMock(return_value=mock_engine_result)

        bridge = MagicMock()
        bridge.get_agent_by_name = MagicMock(return_value=None)

        agents_dir = tmp_path / "agents"
        config_dir = agents_dir / "test-agent"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "name: test-agent\nmodel: cc/claude-sonnet-4-6"
        )

        with (
            patch(
                "mc.cc_step_runner.ExecutionEngine",
                return_value=mock_engine,
            ),
            patch(
                "mc.infrastructure.config.AGENTS_DIR",
                agents_dir,
            ),
            patch(
                "mc.infrastructure.agents.yaml_validator.validate_agent_file",
                return_value=MagicMock(
                    name="test-agent",
                    display_name="Test Agent",
                    model="cc/claude-sonnet-4-6",
                    skills=[],
                    prompt=None,
                    backend="claude-code",
                ),
            ),
        ):
            with pytest.raises(RuntimeError, match="CC execution failed"):
                await execute_step_via_cc(
                    bridge=bridge,
                    step_id="step-1",
                    task_id="task-1",
                    agent_name="test-agent",
                    agent_model="cc/claude-sonnet-4-6",
                    agent_prompt=None,
                    agent_skills=[],
                    step_title="Failing Step",
                    execution_description="This will fail",
                    task_data={},
                    pre_snapshot={},
                )
