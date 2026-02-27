"""Tests for the gateway module — Tasks 1–5."""

import asyncio
import dataclasses
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Task 1.1: _resolve_convex_url()
# ---------------------------------------------------------------------------

class TestResolveConvexUrl:
    """Test _resolve_convex_url() resolves from env var or .env.local fallback."""

    def test_returns_env_var_when_set(self, monkeypatch, tmp_path):
        """CONVEX_URL env var takes precedence."""
        from nanobot.mc.gateway import _resolve_convex_url

        monkeypatch.setenv("CONVEX_URL", "https://test.convex.cloud")
        assert _resolve_convex_url() == "https://test.convex.cloud"

    def test_falls_back_to_env_local(self, monkeypatch, tmp_path):
        """When no CONVEX_URL env var, reads from dashboard/.env.local."""
        from nanobot.mc.gateway import _resolve_convex_url

        monkeypatch.delenv("CONVEX_URL", raising=False)
        env_local = tmp_path / "dashboard" / ".env.local"
        env_local.parent.mkdir(parents=True)
        env_local.write_text('NEXT_PUBLIC_CONVEX_URL="https://fallback.convex.cloud"\n')

        result = _resolve_convex_url(dashboard_dir=env_local.parent)
        assert result == "https://fallback.convex.cloud"

    def test_returns_none_when_neither(self, monkeypatch, tmp_path):
        """Returns None when no env var and no .env.local file."""
        from nanobot.mc.gateway import _resolve_convex_url

        monkeypatch.delenv("CONVEX_URL", raising=False)
        result = _resolve_convex_url(dashboard_dir=tmp_path / "nonexistent")
        assert result is None

    def test_env_local_without_quotes(self, monkeypatch, tmp_path):
        """Handles .env.local values without surrounding quotes."""
        from nanobot.mc.gateway import _resolve_convex_url

        monkeypatch.delenv("CONVEX_URL", raising=False)
        env_local = tmp_path / "dashboard" / ".env.local"
        env_local.parent.mkdir(parents=True)
        env_local.write_text("NEXT_PUBLIC_CONVEX_URL=https://noquotes.convex.cloud\n")

        result = _resolve_convex_url(dashboard_dir=env_local.parent)
        assert result == "https://noquotes.convex.cloud"


# ---------------------------------------------------------------------------
# Task 1.2 / 1.3: main() replaces placeholder with real bridge init
# ---------------------------------------------------------------------------

class TestMainFunction:
    """Test that main() creates a bridge, syncs agents, and runs the gateway."""

    @pytest.mark.asyncio
    async def test_main_logs_error_and_exits_when_no_url(self, monkeypatch):
        """main() should log error and exit if Convex URL cannot be resolved."""
        from nanobot.mc.gateway import main

        monkeypatch.delenv("CONVEX_URL", raising=False)
        with patch("nanobot.mc.gateway._resolve_convex_url", return_value=None), \
             patch("nanobot.mc.gateway.logger") as mock_logger:
            # main() should return early (not hang) when URL is unresolvable
            await main()
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_main_creates_bridge_and_calls_run_gateway(self, monkeypatch):
        """main() should create ConvexBridge, sync agents, and call run_gateway."""
        from nanobot.mc.gateway import main

        mock_bridge = MagicMock()
        mock_bridge.close = MagicMock()

        with patch("nanobot.mc.gateway._resolve_convex_url", return_value="https://test.convex.cloud"), \
             patch("nanobot.mc.bridge.ConvexBridge", return_value=mock_bridge) as mock_bridge_cls, \
             patch("nanobot.mc.gateway.sync_agent_registry", return_value=([], {})) as mock_sync, \
             patch("nanobot.mc.gateway.run_gateway", new_callable=AsyncMock) as mock_run, \
             patch("nanobot.mc.gateway.AGENTS_DIR", Path("/nonexistent")):
            monkeypatch.delenv("CONVEX_ADMIN_KEY", raising=False)
            await main()

            mock_bridge_cls.assert_called_once_with("https://test.convex.cloud", None)
            mock_run.assert_called_once_with(mock_bridge)
            mock_bridge.close.assert_called_once()


# ---------------------------------------------------------------------------
# Task 1.4: run_gateway() starts routing loop + timeout checker
# ---------------------------------------------------------------------------

class TestRunGateway:
    """Verify run_gateway starts all loops: routing, review, executor, timeout."""

    @pytest.mark.asyncio
    async def test_run_gateway_starts_all_loops(self):
        """run_gateway should start orchestrator (routing + review), executor, and timeout."""
        from nanobot.mc.gateway import run_gateway

        mock_bridge = MagicMock()

        with patch("nanobot.mc.gateway.TaskOrchestrator") as MockOrch, \
             patch("nanobot.mc.gateway.TimeoutChecker") as MockTC, \
             patch("nanobot.mc.executor.TaskExecutor") as MockExec, \
             patch("nanobot.mc.chat_handler.ChatHandler") as MockCH:
            mock_orch_instance = MockOrch.return_value
            mock_orch_instance.start_routing_loop = AsyncMock()
            mock_orch_instance.start_review_routing_loop = AsyncMock()
            mock_orch_instance.start_kickoff_watch_loop = AsyncMock()

            mock_tc_instance = MockTC.return_value
            mock_tc_instance.start = AsyncMock()

            mock_exec_instance = MockExec.return_value
            mock_exec_instance.start_execution_loop = AsyncMock()

            mock_ch_instance = MockCH.return_value
            mock_ch_instance.run = AsyncMock()

            # run_gateway waits on a stop_event; we need to trigger it
            async def trigger_stop():
                await asyncio.sleep(0.05)
                import signal
                import os
                os.kill(os.getpid(), signal.SIGTERM)

            stop_task = asyncio.create_task(trigger_stop())
            try:
                await run_gateway(mock_bridge)
            except SystemExit:
                pass
            finally:
                stop_task.cancel()
                try:
                    await stop_task
                except asyncio.CancelledError:
                    pass

            MockOrch.assert_called_once_with(mock_bridge)
            MockTC.assert_called_once_with(mock_bridge)
            mock_orch_instance.start_routing_loop.assert_called_once()
            mock_orch_instance.start_review_routing_loop.assert_called_once()
            mock_orch_instance.start_kickoff_watch_loop.assert_called_once()
            mock_tc_instance.start.assert_called_once()
            mock_exec_instance.start_execution_loop.assert_called_once()
            mock_ch_instance.run.assert_called_once()


# ---------------------------------------------------------------------------
# Task 2: AgentData construction filters extra fields
# ---------------------------------------------------------------------------

class TestAgentDataFiltering:
    """Test that AgentData construction tolerates extra fields from Convex."""

    def test_agent_data_rejects_unknown_fields(self):
        """Baseline: raw AgentData(**dict) crashes with extra fields."""
        from nanobot.mc.types import AgentData

        data = {
            "name": "test-agent",
            "display_name": "Test Agent",
            "role": "tester",
            "skills": ["testing"],
            "creation_time": 1234567890,  # extra Convex field
        }
        with pytest.raises(TypeError):
            AgentData(**data)

    def test_filter_agent_data_fields(self):
        """filter_agent_fields should strip unknown fields for safe construction."""
        from nanobot.mc.gateway import filter_agent_fields
        from nanobot.mc.types import AgentData

        data = {
            "name": "test-agent",
            "display_name": "Test Agent",
            "role": "tester",
            "skills": ["testing"],
            "creation_time": 1234567890,
            "_extra": "should be removed",
        }
        filtered = filter_agent_fields(data)
        agent = AgentData(**filtered)
        assert agent.name == "test-agent"
        assert "creation_time" not in filtered
        assert "_extra" not in filtered


# ---------------------------------------------------------------------------
# Task 3: Assigned → in_progress task pickup (execution loop)
# ---------------------------------------------------------------------------

class TestExecutionLoop:
    """Test start_execution_loop() picks up assigned tasks."""

    @pytest.mark.asyncio
    async def test_assigned_task_transitions_to_in_progress(self):
        """When an assigned task is detected, it should transition to in_progress."""
        from nanobot.mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.create_activity = MagicMock()

        task_data = {
            "id": "task_123",
            "title": "Test task",
            "description": "A test",
            "assigned_agent": "test-agent",
            "trust_level": "autonomous",
        }

        # async_subscribe returns an asyncio.Queue
        mock_bridge.async_subscribe = lambda fn, args: _make_test_queue([task_data])

        executor = TaskExecutor(mock_bridge)

        with patch.object(executor, "_execute_task", new_callable=AsyncMock):
            with patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
                task = asyncio.create_task(executor.start_execution_loop())
                await asyncio.sleep(0.05)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        mock_bridge.update_task_status.assert_any_call(
            "task_123", "in_progress", "test-agent",
            unittest_any_string(),
        )

    @pytest.mark.asyncio
    async def test_assigned_task_does_not_duplicate_started_activity(self):
        """Picking up should NOT call create_activity (Convex handles task_started).

        Updated in Story 8.4: activity events for status transitions are
        written only by the Convex tasks:updateStatus mutation.
        """
        from nanobot.mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.create_activity = MagicMock()

        task_data = {
            "id": "task_456",
            "title": "Activity test",
            "assigned_agent": "agent-x",
            "trust_level": "autonomous",
        }

        mock_bridge.async_subscribe = lambda fn, args: _make_test_queue([task_data])

        executor = TaskExecutor(mock_bridge)

        with patch.object(executor, "_execute_task", new_callable=AsyncMock):
            with patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
                task = asyncio.create_task(executor.start_execution_loop())
                await asyncio.sleep(0.05)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        mock_bridge.create_activity.assert_not_called()

    @pytest.mark.asyncio
    async def test_assigned_task_writes_thread_message(self):
        """Picking up should write a system message to the task thread."""
        from nanobot.mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.create_activity = MagicMock()

        task_data = {
            "id": "task_789",
            "title": "Thread test",
            "assigned_agent": "agent-y",
            "trust_level": "autonomous",
        }

        mock_bridge.async_subscribe = lambda fn, args: _make_test_queue([task_data])

        executor = TaskExecutor(mock_bridge)

        with patch.object(executor, "_execute_task", new_callable=AsyncMock):
            with patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
                task = asyncio.create_task(executor.start_execution_loop())
                await asyncio.sleep(0.05)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        mock_bridge.send_message.assert_any_call(
            "task_789",
            "System",
            "system",
            unittest_any_string(),
            "system_event",
        )

    @pytest.mark.asyncio
    async def test_pickup_task_reroutes_lead_agent(self):
        """Lead-agent pickup is intercepted and re-routed via planner."""
        from nanobot.mc.executor import TaskExecutor
        from nanobot.mc.types import ExecutionPlan, ExecutionPlanStep

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.update_execution_plan = MagicMock()
        mock_bridge.list_agents = MagicMock(return_value=[
            {"name": "dev-agent", "display_name": "Dev", "role": "dev", "skills": ["coding"]},
        ])

        task_data = {
            "id": "task_lead_reroute",
            "title": "Task routed to lead",
            "description": "reroute me",
            "assigned_agent": "lead-agent",
            "trust_level": "autonomous",
        }
        plan = ExecutionPlan(steps=[
            ExecutionPlanStep(
                temp_id="step_1",
                title="Execute",
                description="Execute",
                assigned_agent="dev-agent",
            ),
        ])

        executor = TaskExecutor(mock_bridge)

        with patch("nanobot.mc.executor.TaskPlanner") as MockPlanner, \
             patch.object(executor, "_execute_task", new_callable=AsyncMock) as mock_execute, \
             patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
            MockPlanner.return_value.plan_task = AsyncMock(return_value=plan)
            await executor._pickup_task(task_data)

        mock_execute.assert_not_called()
        mock_bridge.update_execution_plan.assert_called_once()
        mock_bridge.update_task_status.assert_called_once()
        status_args = mock_bridge.update_task_status.call_args[0]
        assert status_args[1] == "assigned"
        assert status_args[2] == "dev-agent"
        message_args = mock_bridge.send_message.call_args[0]
        assert "pure orchestrator" in message_args[3].lower()


# ---------------------------------------------------------------------------
# Task 4: Task execution and completion
# ---------------------------------------------------------------------------

class TestTaskExecution:
    """Test task execution writes results and transitions to done/review."""

    @pytest.mark.asyncio
    async def test_autonomous_task_transitions_to_done(self):
        """Autonomous trust level should complete to 'done'."""
        from nanobot.mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.get_agent_by_name = MagicMock(return_value=None)

        executor = TaskExecutor(mock_bridge)

        with patch("nanobot.mc.executor._run_agent_on_task", new_callable=AsyncMock, return_value="Task completed successfully"), \
             patch.object(executor, "_load_agent_config", return_value=(None, None, None)), \
             patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
            await executor._execute_task(
                "task_001", "Test task", "Do testing", "test-agent", "autonomous"
            )

        mock_bridge.update_task_status.assert_any_call(
            "task_001", "done", "test-agent", unittest_any_string()
        )

    @pytest.mark.asyncio
    async def test_human_approved_task_transitions_to_review(self):
        """Human-approved trust level should complete to 'review'."""
        from nanobot.mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.get_agent_by_name = MagicMock(return_value=None)

        executor = TaskExecutor(mock_bridge)

        with patch("nanobot.mc.executor._run_agent_on_task", new_callable=AsyncMock, return_value="Done"), \
             patch.object(executor, "_load_agent_config", return_value=(None, None, None)), \
             patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
            await executor._execute_task(
                "task_002", "Review task", "Do review", "test-agent", "human_approved"
            )

        mock_bridge.update_task_status.assert_any_call(
            "task_002", "review", "test-agent", unittest_any_string()
        )

    @pytest.mark.asyncio
    async def test_execution_writes_work_message(self):
        """Execution output should be written as a 'work' message to the thread."""
        from nanobot.mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.get_agent_by_name = MagicMock(return_value=None)

        executor = TaskExecutor(mock_bridge)

        with patch("nanobot.mc.executor._run_agent_on_task", new_callable=AsyncMock, return_value="Here is my work output"), \
             patch.object(executor, "_load_agent_config", return_value=(None, None, None)), \
             patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
            await executor._execute_task(
                "task_003", "Work task", "Do work", "test-agent", "autonomous"
            )

        mock_bridge.send_message.assert_any_call(
            "task_003",
            "test-agent",
            "agent",
            "Here is my work output",
            "work",
        )

    @pytest.mark.asyncio
    async def test_execution_does_not_duplicate_completed_activity(self):
        """Successful completion should NOT call create_activity (Convex handles it).

        Updated in Story 8.4: activity events for status transitions are
        written only by the Convex tasks:updateStatus mutation.
        """
        from nanobot.mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.get_agent_by_name = MagicMock(return_value=None)

        executor = TaskExecutor(mock_bridge)

        with patch("nanobot.mc.executor._run_agent_on_task", new_callable=AsyncMock, return_value="Done"), \
             patch.object(executor, "_load_agent_config", return_value=(None, None, None)), \
             patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
            await executor._execute_task(
                "task_004", "Event task", "Test events", "test-agent", "autonomous"
            )

        mock_bridge.create_activity.assert_not_called()

    @pytest.mark.asyncio
    async def test_execution_crash_delegates_to_agent_gateway(self):
        """On agent error, should delegate to AgentGateway.handle_agent_crash()."""
        from nanobot.mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.get_agent_by_name = MagicMock(return_value=None)

        executor = TaskExecutor(mock_bridge)

        crash_error = RuntimeError("Agent exploded")
        with patch("nanobot.mc.executor._run_agent_on_task", new_callable=AsyncMock, side_effect=crash_error), \
             patch.object(executor, "_load_agent_config", return_value=(None, None, None)), \
             patch("asyncio.to_thread", side_effect=_to_thread_passthrough), \
             patch.object(executor, "_agent_gateway") as mock_gw:
            mock_gw.handle_agent_crash = AsyncMock()
            await executor._execute_task(
                "task_005", "Crash task", "Will crash", "crash-agent", "autonomous"
            )
            mock_gw.handle_agent_crash.assert_called_once_with(
                "crash-agent", "task_005", crash_error
            )


# ---------------------------------------------------------------------------
# Lead-agent pure-orchestrator guards
# ---------------------------------------------------------------------------

class TestLeadAgentExecutionGuards:
    """Hard guards should block lead-agent from all execution paths."""

    @pytest.mark.asyncio
    async def test_executor_rejects_lead_agent_in_execute_task(self):
        from nanobot.mc.executor import TaskExecutor
        from nanobot.mc.types import LeadAgentExecutionError

        executor = TaskExecutor(MagicMock())

        with pytest.raises(
            LeadAgentExecutionError,
            match="INVARIANT VIOLATION",
        ):
            await executor._execute_task(
                "task_lead_execute",
                "Lead execution",
                None,
                "lead-agent",
                "autonomous",
            )

    @pytest.mark.asyncio
    async def test_executor_rejects_lead_agent_in_run_agent_on_task(self):
        from nanobot.mc.executor import _run_agent_on_task
        from nanobot.mc.types import LeadAgentExecutionError

        with pytest.raises(
            LeadAgentExecutionError,
            match="must never be passed to _run_agent_on_task",
        ):
            await _run_agent_on_task(
                agent_name="lead-agent",
                agent_prompt=None,
                agent_model=None,
                task_title="Task",
                task_description=None,
            )


# ---------------------------------------------------------------------------
# Test 5.5: Trust level determines final status
# ---------------------------------------------------------------------------

class TestTrustLevelStatus:
    """Test trust level determines done vs review."""

    @pytest.mark.asyncio
    async def test_agent_reviewed_transitions_to_review(self):
        """agent_reviewed trust level should transition to 'review'."""
        from nanobot.mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.get_agent_by_name = MagicMock(return_value=None)

        executor = TaskExecutor(mock_bridge)

        with patch("nanobot.mc.executor._run_agent_on_task", new_callable=AsyncMock, return_value="Reviewed"), \
             patch.object(executor, "_load_agent_config", return_value=(None, None, None)), \
             patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
            await executor._execute_task(
                "task_006", "Reviewed task", "For review", "review-agent", "agent_reviewed"
            )

        mock_bridge.update_task_status.assert_any_call(
            "task_006", "review", "review-agent", unittest_any_string()
        )


# ---------------------------------------------------------------------------
# Agent config loading and memory cleanup
# ---------------------------------------------------------------------------

class TestLoadAgentConfig:
    """Test _load_agent_config loads prompt and model from YAML."""

    def test_loads_prompt_and_model_from_yaml(self, tmp_path):
        """Should return prompt and model from a valid agent config."""
        from nanobot.mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        executor = TaskExecutor(mock_bridge)

        agent_dir = tmp_path / "test-agent"
        agent_dir.mkdir()
        config = agent_dir / "config.yaml"
        config.write_text(
            "name: test-agent\n"
            "display_name: Test Agent\n"
            "role: tester\n"
            "prompt: You are a test agent.\n"
            "model: anthropic/claude-haiku-3\n"
        )

        with patch("nanobot.mc.gateway.AGENTS_DIR", tmp_path):
            prompt, model, skills = executor._load_agent_config("test-agent")

        assert prompt == "You are a test agent."
        assert model == "anthropic/claude-haiku-3"
        assert skills == []

    def test_returns_none_when_no_config(self, tmp_path):
        """Should return (None, None, None) when agent dir doesn't exist."""
        from nanobot.mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        executor = TaskExecutor(mock_bridge)

        with patch("nanobot.mc.gateway.AGENTS_DIR", tmp_path):
            prompt, model, skills = executor._load_agent_config("nonexistent")

        assert prompt is None
        assert model is None
        assert skills is None


class TestKnownAssignedIdsCleanup:
    """Test that _known_assigned_ids is cleaned up after execution."""

    @pytest.mark.asyncio
    async def test_task_id_removed_after_success(self):
        """Task ID should be removed from _known_assigned_ids after successful execution."""
        from nanobot.mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.get_agent_by_name = MagicMock(return_value=None)

        executor = TaskExecutor(mock_bridge)
        executor._known_assigned_ids.add("task_cleanup")

        with patch("nanobot.mc.executor._run_agent_on_task", new_callable=AsyncMock, return_value="Done"), \
             patch.object(executor, "_load_agent_config", return_value=(None, None, None)), \
             patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
            await executor._execute_task(
                "task_cleanup", "Cleanup test", None, "agent", "autonomous"
            )

        assert "task_cleanup" not in executor._known_assigned_ids

    @pytest.mark.asyncio
    async def test_task_id_removed_after_crash(self):
        """Task ID should be removed from _known_assigned_ids even after crash."""
        from nanobot.mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.get_agent_by_name = MagicMock(return_value=None)

        executor = TaskExecutor(mock_bridge)
        executor._known_assigned_ids.add("task_crash_cleanup")

        with patch("nanobot.mc.executor._run_agent_on_task", new_callable=AsyncMock, side_effect=RuntimeError("boom")), \
             patch.object(executor, "_load_agent_config", return_value=(None, None, None)), \
             patch("asyncio.to_thread", side_effect=_to_thread_passthrough), \
             patch.object(executor._agent_gateway, "handle_agent_crash", new_callable=AsyncMock):
            await executor._execute_task(
                "task_crash_cleanup", "Crash", None, "agent", "autonomous"
            )

        assert "task_crash_cleanup" not in executor._known_assigned_ids


# ---------------------------------------------------------------------------
# Story 8.4 Task 1: Orchestrator does NOT create duplicate activity events
# ---------------------------------------------------------------------------

class TestOrchestratorNoDuplicateActivity:
    """After Story 8.4, orchestrator must NOT call create_activity for transitions
    that are already handled by the Convex tasks:updateStatus mutation."""

    @pytest.mark.asyncio
    async def test_explicit_assignment_no_duplicate_status_activity(self):
        """Explicit assignment uses planner; update_task_status called once (Convex handles event).

        Updated in Story 4.5: explicit assignments now go through the planner
        (AC #8). create_activity is called for step dispatch (TASK_STARTED),
        which is expected — only duplicate STATUS TRANSITION events are avoided.
        """
        from nanobot.mc.orchestrator import TaskOrchestrator
        from nanobot.mc.types import ExecutionPlan, ExecutionPlanStep

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.update_execution_plan = MagicMock()
        mock_bridge.list_agents = MagicMock(return_value=[
            {"name": "agent-a", "display_name": "Agent A", "role": "dev", "skills": ["coding"]},
        ])

        plan = ExecutionPlan(steps=[
            ExecutionPlanStep(temp_id="step_1", title="Do it", description="Do it", assigned_agent="agent-a"),
        ])

        orch = TaskOrchestrator(mock_bridge)
        task_data = {
            "id": "task_dedup_1",
            "title": "Explicit assign",
            "assigned_agent": "agent-a",
        }

        with patch("nanobot.mc.orchestrator.TaskPlanner") as MockPlanner, \
             patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
            MockPlanner.return_value.plan_task = AsyncMock(return_value=plan)
            await orch._process_inbox_task(task_data)

        # update_task_status called once for assignment (Convex handles the activity)
        mock_bridge.update_task_status.assert_called_once()
        # create_activity is only for step dispatch (TASK_STARTED), not status transitions
        for call_args in mock_bridge.create_activity.call_args_list:
            assert call_args[0][0] != "task_assigned"

    @pytest.mark.asyncio
    async def test_best_match_routing_no_duplicate_status_activity(self):
        """Best-match routing uses planner; only step dispatch activity events created.

        Updated in Story 4.5: all tasks go through the LLM planner now.
        """
        from nanobot.mc.orchestrator import TaskOrchestrator
        from nanobot.mc.types import ExecutionPlan, ExecutionPlanStep

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.update_execution_plan = MagicMock()
        mock_bridge.list_agents = MagicMock(return_value=[
            {"name": "test-agent", "display_name": "Test", "role": "dev", "skills": ["testing"]},
        ])

        plan = ExecutionPlan(steps=[
            ExecutionPlanStep(temp_id="step_1", title="Run tests", description="Run tests", assigned_agent="test-agent"),
        ])

        orch = TaskOrchestrator(mock_bridge)
        task_data = {
            "id": "task_dedup_2",
            "title": "Run testing suite",
            "description": None,
        }

        with patch("nanobot.mc.orchestrator.TaskPlanner") as MockPlanner, \
             patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
            MockPlanner.return_value.plan_task = AsyncMock(return_value=plan)
            await orch._process_inbox_task(task_data)

        mock_bridge.update_task_status.assert_called_once()
        # create_activity is only for step dispatch, not status transitions
        for call_args in mock_bridge.create_activity.call_args_list:
            assert call_args[0][0] != "task_assigned"

    @pytest.mark.asyncio
    async def test_fallback_routing_no_duplicate_status_activity(self):
        """Fallback (no agent match) uses planner; only step dispatch events created.

        Updated in Story 4.5: all tasks go through the LLM planner now.
        """
        from nanobot.mc.orchestrator import TaskOrchestrator
        from nanobot.mc.types import ExecutionPlan, ExecutionPlanStep

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.update_execution_plan = MagicMock()
        mock_bridge.list_agents = MagicMock(return_value=[])

        plan = ExecutionPlan(steps=[
            ExecutionPlanStep(temp_id="step_1", title="Do task", description="Do task", assigned_agent="lead-agent"),
        ])

        orch = TaskOrchestrator(mock_bridge)
        task_data = {
            "id": "task_dedup_3",
            "title": "No match task",
            "description": None,
        }

        with patch("nanobot.mc.orchestrator.TaskPlanner") as MockPlanner, \
             patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
            MockPlanner.return_value.plan_task = AsyncMock(return_value=plan)
            await orch._process_inbox_task(task_data)

        mock_bridge.update_task_status.assert_called_once()
        # create_activity is only for step dispatch, not status transitions
        for call_args in mock_bridge.create_activity.call_args_list:
            assert call_args[0][0] != "task_assigned"

    @pytest.mark.asyncio
    async def test_review_keeps_standalone_activity_events(self):
        """Review routing should still create standalone activity events
        (review_requested, hitl_requested) that have no status transition."""
        from nanobot.mc.orchestrator import TaskOrchestrator

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.get_steps_by_task = MagicMock(return_value=[])

        orch = TaskOrchestrator(mock_bridge)
        task_data = {
            "title": "Review me",
            "reviewers": ["reviewer-agent"],
            "trust_level": "agent_reviewed",
        }

        with patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
            await orch._handle_review_transition("task_review_1", task_data)

        # Should create review_requested (standalone event, no status change)
        mock_bridge.create_activity.assert_called_once()
        args = mock_bridge.create_activity.call_args
        assert args[0][0] == "review_requested"

    @pytest.mark.asyncio
    async def test_auto_complete_review_no_create_activity(self):
        """Autonomous task with no reviewers transitions directly to done
        via update_task_status — should NOT call create_activity."""
        from nanobot.mc.orchestrator import TaskOrchestrator

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.get_steps_by_task = MagicMock(return_value=[])

        orch = TaskOrchestrator(mock_bridge)
        task_data = {
            "title": "Auto complete",
            "reviewers": [],
            "trust_level": "autonomous",
        }

        with patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
            await orch._handle_review_transition("task_auto_1", task_data)

        mock_bridge.update_task_status.assert_called_once()
        mock_bridge.create_activity.assert_not_called()


# ---------------------------------------------------------------------------
# Story 8.4 Task 2: Executor does NOT create duplicate activity events
# ---------------------------------------------------------------------------

class TestExecutorNoDuplicateActivity:
    """After Story 8.4, executor must NOT call create_activity for
    task_started and task_completed (Convex handles them)."""

    @pytest.mark.asyncio
    async def test_pickup_does_not_call_create_activity(self):
        """_pickup_task should NOT call create_activity (Convex handles task_started)."""
        from nanobot.mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.create_activity = MagicMock()

        task_data = {
            "id": "task_no_dup_1",
            "title": "No dup pickup",
            "description": None,
            "assigned_agent": "agent-z",
            "trust_level": "autonomous",
        }

        executor = TaskExecutor(mock_bridge)

        with patch.object(executor, "_execute_task", new_callable=AsyncMock), \
             patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
            await executor._pickup_task(task_data)

        mock_bridge.create_activity.assert_not_called()

    @pytest.mark.asyncio
    async def test_completion_does_not_call_create_activity(self):
        """_execute_task should NOT call create_activity on success
        (Convex handles task_completed)."""
        from nanobot.mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.get_agent_by_name = MagicMock(return_value=None)

        executor = TaskExecutor(mock_bridge)

        with patch("nanobot.mc.executor._run_agent_on_task", new_callable=AsyncMock, return_value="Done"), \
             patch.object(executor, "_load_agent_config", return_value=(None, None, None)), \
             patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
            await executor._execute_task(
                "task_no_dup_2", "No dup complete", None, "agent", "autonomous"
            )

        mock_bridge.create_activity.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_message_still_called_on_pickup(self):
        """_pickup_task should still write a system message (messages != activities)."""
        from nanobot.mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.create_activity = MagicMock()

        task_data = {
            "id": "task_msg_1",
            "title": "Msg test",
            "description": None,
            "assigned_agent": "agent-m",
            "trust_level": "autonomous",
        }

        executor = TaskExecutor(mock_bridge)

        with patch.object(executor, "_execute_task", new_callable=AsyncMock), \
             patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
            await executor._pickup_task(task_data)

        mock_bridge.send_message.assert_called_once()


# ---------------------------------------------------------------------------
# Story 8.4 Task 3: Orchestrator inbox deduplication
# ---------------------------------------------------------------------------

class TestOrchestratorDeduplication:
    """The orchestrator must skip already-routed inbox tasks."""

    @pytest.mark.asyncio
    async def test_duplicate_inbox_task_skipped(self):
        """Same task ID appearing twice should only be processed once."""
        from nanobot.mc.orchestrator import TaskOrchestrator

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.list_agents = MagicMock(return_value=[])

        task_data = {"id": "task_dup_inbox", "title": "Dup", "description": None}

        # Two subscription updates with the same task
        q = asyncio.Queue()
        q.put_nowait([task_data])
        q.put_nowait([task_data])
        mock_bridge.async_subscribe = lambda fn, args: q

        orch = TaskOrchestrator(mock_bridge)

        with patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
            loop_task = asyncio.create_task(orch.start_routing_loop())
            await asyncio.sleep(0.05)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        # Should only be called once despite appearing twice
        assert mock_bridge.update_task_status.call_count == 1

    @pytest.mark.asyncio
    async def test_process_inbox_error_does_not_crash_loop(self):
        """An error in _process_inbox_task should not crash the routing loop."""
        from nanobot.mc.orchestrator import TaskOrchestrator

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock(side_effect=RuntimeError("Convex down"))
        mock_bridge.create_activity = MagicMock()
        mock_bridge.list_agents = MagicMock(return_value=[])

        task1 = {"id": "task_err_1", "title": "Will fail", "description": None}
        task2 = {"id": "task_err_2", "title": "Should still run", "description": None}

        q = asyncio.Queue()
        q.put_nowait([task1])
        q.put_nowait([task2])
        mock_bridge.async_subscribe = lambda fn, args: q

        orch = TaskOrchestrator(mock_bridge)

        with patch("asyncio.to_thread", side_effect=_to_thread_passthrough):
            loop_task = asyncio.create_task(orch.start_routing_loop())
            await asyncio.sleep(0.05)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        # Both tasks attempted (loop didn't crash on first error)
        assert mock_bridge.update_task_status.call_count == 2


# ---------------------------------------------------------------------------
# Story 8.4 Task 4: Bridge subscription reconnection
# ---------------------------------------------------------------------------

class TestBridgeAsyncSubscribe:
    """Test bridge async_subscribe uses get_running_loop and reconnects."""

    @pytest.mark.asyncio
    async def test_poll_retries_on_query_error(self):
        """When query() raises, polling should retry and deliver data on success."""
        from nanobot.mc.bridge import ConvexBridge

        mock_client = MagicMock()
        bridge = ConvexBridge.__new__(ConvexBridge)
        bridge._client = mock_client

        calls = []

        def fake_query(fn, args=None):
            calls.append(1)
            n = len(calls)
            if n <= 2:
                raise ConnectionError("Connection lost")
            return [{"id": "task_1"}]

        with patch.object(bridge, "query", side_effect=fake_query):
            q = bridge.async_subscribe(
                "tasks:listByStatus", {"status": "inbox"}, poll_interval=0.05
            )
            result = await asyncio.wait_for(q.get(), timeout=5.0)

        assert result == [{"id": "task_1"}]
        assert len(calls) >= 3

    @pytest.mark.asyncio
    async def test_poll_exhausted_sends_error_sentinel(self):
        """When max consecutive errors are hit, push an error sentinel."""
        from nanobot.mc.bridge import ConvexBridge

        mock_client = MagicMock()
        bridge = ConvexBridge.__new__(ConvexBridge)
        bridge._client = mock_client

        def always_fail(fn, args=None):
            raise ConnectionError("Permanent failure")

        with patch.object(bridge, "query", side_effect=always_fail):
            q = bridge.async_subscribe(
                "tasks:listByStatus", {"status": "inbox"}, poll_interval=0.01
            )
            result = await asyncio.wait_for(q.get(), timeout=10.0)

        assert isinstance(result, dict)
        assert result.get("_error") is True
        assert "Permanent failure" in result.get("message", "")

    @pytest.mark.asyncio
    async def test_deduplicates_identical_results(self):
        """Only enqueue changed poll results; suppress identical repeats."""
        from nanobot.mc.bridge import ConvexBridge

        mock_client = MagicMock()
        bridge = ConvexBridge.__new__(ConvexBridge)
        bridge._client = mock_client

        calls = []

        def fake_query(fn, args=None):
            calls.append(1)
            n = len(calls)
            if n <= 3:
                return [{"id": "task_1"}]
            if n == 4:
                return [{"id": "task_1"}, {"id": "task_2"}]
            raise asyncio.CancelledError()

        with patch.object(bridge, "query", side_effect=fake_query):
            q = bridge.async_subscribe(
                "tasks:listByStatus", {"status": "inbox"}, poll_interval=0.01
            )
            first = await asyncio.wait_for(q.get(), timeout=5.0)
            second = await asyncio.wait_for(q.get(), timeout=5.0)

        assert first == [{"id": "task_1"}]
        assert second == [{"id": "task_1"}, {"id": "task_2"}]
        assert q.empty()

    @pytest.mark.asyncio
    async def test_first_result_always_emitted(self):
        """First poll result should be enqueued even when it's an empty list."""
        from nanobot.mc.bridge import ConvexBridge

        mock_client = MagicMock()
        bridge = ConvexBridge.__new__(ConvexBridge)
        bridge._client = mock_client

        calls = []

        def fake_query(fn, args=None):
            calls.append(1)
            if len(calls) == 1:
                return []
            raise asyncio.CancelledError()

        with patch.object(bridge, "query", side_effect=fake_query):
            q = bridge.async_subscribe(
                "tasks:listByStatus", {"status": "inbox"}, poll_interval=0.01
            )
            first = await asyncio.wait_for(q.get(), timeout=5.0)

        assert first == []


# ---------------------------------------------------------------------------
# Story 8.4 Task 5: Fix empty agent_name in bridge
# ---------------------------------------------------------------------------

class TestBridgeAgentNameHandling:
    """Test that bridge.update_task_status omits agent_name when None."""

    def test_agent_name_none_omitted(self):
        """When agent_name is None, it should not be in mutation args."""
        from nanobot.mc.bridge import ConvexBridge

        mock_client = MagicMock()
        mock_client.mutation = MagicMock(return_value=None)
        bridge = ConvexBridge.__new__(ConvexBridge)
        bridge._client = mock_client

        bridge.update_task_status("task_id_1", "done")

        call_args = mock_client.mutation.call_args
        mutation_args = call_args[0][1]
        assert "agentName" not in mutation_args

    def test_agent_name_provided_included(self):
        """When agent_name is provided, it should be in mutation args."""
        from nanobot.mc.bridge import ConvexBridge

        mock_client = MagicMock()
        mock_client.mutation = MagicMock(return_value=None)
        bridge = ConvexBridge.__new__(ConvexBridge)
        bridge._client = mock_client

        bridge.update_task_status("task_id_2", "assigned", agent_name="agent-x")

        call_args = mock_client.mutation.call_args
        mutation_args = call_args[0][1]
        assert mutation_args["agentName"] == "agent-x"


# ---------------------------------------------------------------------------
# Agent delete/restore: _cleanup_deleted_agents, _restore_archived_files,
# _write_back with archive restoration, upsertByName skip for deleted agents
# ---------------------------------------------------------------------------

class TestCleanupDeletedAgents:
    """Test _cleanup_deleted_agents archives and removes local agent folders."""

    def test_archives_and_removes_local_folder(self, tmp_path):
        """Given a deleted agent with a local folder, archive its data and remove the folder."""
        from nanobot.mc.gateway import _cleanup_deleted_agents

        agent_dir = tmp_path / "test-agent"
        memory_dir = agent_dir / "memory"
        sessions_dir = agent_dir / "sessions"
        memory_dir.mkdir(parents=True)
        sessions_dir.mkdir()
        (memory_dir / "MEMORY.md").write_text("# Memory content", encoding="utf-8")
        (memory_dir / "HISTORY.md").write_text("# History content", encoding="utf-8")
        (sessions_dir / "mc_task_test-agent.jsonl").write_text('{"msg":"hello"}', encoding="utf-8")

        mock_bridge = MagicMock()
        mock_bridge.list_deleted_agents.return_value = [{"name": "test-agent"}]
        mock_bridge.archive_agent_data.return_value = None

        _cleanup_deleted_agents(mock_bridge, tmp_path)

        mock_bridge.archive_agent_data.assert_called_once_with(
            "test-agent",
            "# Memory content",
            "# History content",
            '{"msg":"hello"}',
        )
        assert not agent_dir.exists(), "Local folder should be removed after successful archive"

    def test_skips_if_no_local_folder(self, tmp_path):
        """Deleted agent with no local folder: no archive call, no error."""
        from nanobot.mc.gateway import _cleanup_deleted_agents

        mock_bridge = MagicMock()
        mock_bridge.list_deleted_agents.return_value = [{"name": "ghost-agent"}]

        _cleanup_deleted_agents(mock_bridge, tmp_path)

        mock_bridge.archive_agent_data.assert_not_called()

    def test_preserves_folder_on_archive_failure(self, tmp_path):
        """If archive call fails, local folder must NOT be deleted (fail-safe)."""
        from nanobot.mc.gateway import _cleanup_deleted_agents

        agent_dir = tmp_path / "fragile-agent"
        (agent_dir / "memory").mkdir(parents=True)
        (agent_dir / "memory" / "MEMORY.md").write_text("data", encoding="utf-8")

        mock_bridge = MagicMock()
        mock_bridge.list_deleted_agents.return_value = [{"name": "fragile-agent"}]
        mock_bridge.archive_agent_data.side_effect = RuntimeError("Convex unavailable")

        _cleanup_deleted_agents(mock_bridge, tmp_path)

        assert agent_dir.exists(), "Local folder should be preserved when archive fails"

    def test_skips_agents_with_no_name(self, tmp_path):
        """Agent dicts without a 'name' key are silently skipped."""
        from nanobot.mc.gateway import _cleanup_deleted_agents

        mock_bridge = MagicMock()
        mock_bridge.list_deleted_agents.return_value = [{"name": ""}, {}]

        _cleanup_deleted_agents(mock_bridge, tmp_path)

        mock_bridge.archive_agent_data.assert_not_called()

    def test_handles_list_failure_gracefully(self, tmp_path):
        """If list_deleted_agents raises, cleanup exits without crashing."""
        from nanobot.mc.gateway import _cleanup_deleted_agents

        mock_bridge = MagicMock()
        mock_bridge.list_deleted_agents.side_effect = RuntimeError("Convex down")

        # Should not raise
        _cleanup_deleted_agents(mock_bridge, tmp_path)

    def test_idempotent_for_already_cleaned_agents(self, tmp_path):
        """Running cleanup twice for the same agent (folder already gone) is a no-op."""
        from nanobot.mc.gateway import _cleanup_deleted_agents

        mock_bridge = MagicMock()
        mock_bridge.list_deleted_agents.return_value = [{"name": "already-gone"}]
        # No local folder exists

        _cleanup_deleted_agents(mock_bridge, tmp_path)
        _cleanup_deleted_agents(mock_bridge, tmp_path)

        mock_bridge.archive_agent_data.assert_not_called()

    def test_skips_archive_call_when_no_content(self, tmp_path):
        """If agent folder exists but has no memory/history/session files, archive is NOT called."""
        from nanobot.mc.gateway import _cleanup_deleted_agents

        agent_dir = tmp_path / "empty-agent"
        agent_dir.mkdir()  # Folder exists but no files inside

        mock_bridge = MagicMock()
        mock_bridge.list_deleted_agents.return_value = [{"name": "empty-agent"}]

        _cleanup_deleted_agents(mock_bridge, tmp_path)

        mock_bridge.archive_agent_data.assert_not_called()
        assert not agent_dir.exists(), "Folder should still be removed when there is no content to archive"

    def test_continues_after_rmtree_failure(self, tmp_path):
        """If shutil.rmtree fails, logs error but continues cleanup for subsequent agents."""
        from nanobot.mc.gateway import _cleanup_deleted_agents

        # Give each agent a MEMORY.md so archive_agent_data is called (non-empty content)
        for agent_name in ("agent-one", "agent-two"):
            memory_dir = tmp_path / agent_name / "memory"
            memory_dir.mkdir(parents=True)
            (memory_dir / "MEMORY.md").write_text("data", encoding="utf-8")

        mock_bridge = MagicMock()
        mock_bridge.list_deleted_agents.return_value = [{"name": "agent-one"}, {"name": "agent-two"}]
        mock_bridge.archive_agent_data.return_value = None

        with patch("shutil.rmtree", side_effect=[OSError("Permission denied"), None]):
            _cleanup_deleted_agents(mock_bridge, tmp_path)

        # archive_agent_data called for both agents despite first rmtree failing
        assert mock_bridge.archive_agent_data.call_count == 2


class TestRestoreArchivedFiles:
    """Test _restore_archived_files writes files to the correct locations."""

    def test_writes_memory_and_history(self, tmp_path):
        """memory_content and history_content are written to memory/ subdirectory."""
        from nanobot.mc.gateway import _restore_archived_files

        agent_dir = tmp_path / "my-agent"
        agent_dir.mkdir()

        archive = {
            "memory_content": "# My memories",
            "history_content": "## Past actions",
            "session_data": None,
        }
        _restore_archived_files(agent_dir, archive)

        assert (agent_dir / "memory" / "MEMORY.md").read_text() == "# My memories"
        assert (agent_dir / "memory" / "HISTORY.md").read_text() == "## Past actions"
        assert not (agent_dir / "sessions").exists()

    def test_writes_session_data(self, tmp_path):
        """session_data is written to sessions/mc_task_{name}.jsonl."""
        from nanobot.mc.gateway import _restore_archived_files

        agent_dir = tmp_path / "session-agent"
        agent_dir.mkdir()

        archive = {
            "memory_content": None,
            "history_content": None,
            "session_data": '{"task":"do it"}',
        }
        _restore_archived_files(agent_dir, archive)

        session_file = agent_dir / "sessions" / "mc_task_session-agent.jsonl"
        assert session_file.read_text() == '{"task":"do it"}'

    def test_skips_none_values(self, tmp_path):
        """Fields that are None are not written."""
        from nanobot.mc.gateway import _restore_archived_files

        agent_dir = tmp_path / "empty-agent"
        agent_dir.mkdir()

        _restore_archived_files(agent_dir, {"memory_content": None, "history_content": None, "session_data": None})

        assert not (agent_dir / "memory").exists()
        assert not (agent_dir / "sessions").exists()


class TestWriteBackRestoresArchive:
    """Test _write_back_convex_agents calls get_agent_archive for new agents."""

    def test_calls_restore_for_new_agent(self, tmp_path):
        """When writing back a new agent (no local YAML), get_agent_archive is called."""
        from nanobot.mc.gateway import _write_back_convex_agents

        mock_bridge = MagicMock()
        mock_bridge.list_agents.return_value = [{
            "name": "restored-agent",
            "display_name": "Restored Agent",
            "role": "tester",
            "last_active_at": "2026-02-23T12:00:00Z",
            "skills": [],
        }]
        mock_bridge.write_agent_config.return_value = None
        mock_bridge.get_agent_archive.return_value = None  # No archive

        _write_back_convex_agents(mock_bridge, tmp_path)

        mock_bridge.get_agent_archive.assert_called_once_with("restored-agent")

    def test_restores_files_when_archive_present(self, tmp_path):
        """When archive data exists, _restore_archived_files is called for the new agent."""
        from nanobot.mc.gateway import _write_back_convex_agents

        mock_bridge = MagicMock()
        mock_bridge.list_agents.return_value = [{
            "name": "restored-agent",
            "display_name": "Restored Agent",
            "role": "tester",
            "last_active_at": "2026-02-23T12:00:00Z",
            "skills": [],
        }]
        mock_bridge.write_agent_config.return_value = None
        mock_bridge.get_agent_archive.return_value = {
            "memory_content": "# Memories",
            "history_content": None,
            "session_data": None,
        }

        # write_agent_config creates the dir
        agent_dir = tmp_path / "restored-agent"
        agent_dir.mkdir()
        (agent_dir / "memory").mkdir()

        with patch("nanobot.mc.gateway._restore_archived_files") as mock_restore:
            _write_back_convex_agents(mock_bridge, tmp_path)

        mock_restore.assert_called_once()
        call_args = mock_restore.call_args[0]
        assert call_args[0] == tmp_path / "restored-agent"

    def test_does_not_call_restore_for_existing_agent(self, tmp_path):
        """For agents with existing local YAML (update path), archive is NOT fetched."""
        from nanobot.mc.gateway import _write_back_convex_agents
        import time

        # Create existing local YAML
        agent_dir = tmp_path / "existing-agent"
        agent_dir.mkdir()
        config = agent_dir / "config.yaml"
        config.write_text("name: existing-agent\n")

        # Convex timestamp older than local file
        old_ts = "2020-01-01T00:00:00Z"

        mock_bridge = MagicMock()
        mock_bridge.list_agents.return_value = [{
            "name": "existing-agent",
            "display_name": "Existing Agent",
            "role": "tester",
            "last_active_at": old_ts,
            "skills": [],
        }]

        _write_back_convex_agents(mock_bridge, tmp_path)

        mock_bridge.get_agent_archive.assert_not_called()


class TestSyncAgentRegistryCallsCleanup:
    """Test sync_agent_registry calls _cleanup_deleted_agents as Step 0a."""

    def test_cleanup_called_before_write_back(self, tmp_path):
        """_cleanup_deleted_agents should be called before _write_back_convex_agents."""
        from nanobot.mc.gateway import sync_agent_registry

        mock_bridge = MagicMock()
        call_order = []

        with patch("nanobot.mc.gateway._cleanup_deleted_agents", side_effect=lambda b, d: call_order.append("cleanup")), \
             patch("nanobot.mc.gateway._write_back_convex_agents", side_effect=lambda b, d: call_order.append("write_back")), \
             patch("nanobot.mc.gateway._config_default_model", return_value="anthropic/claude-haiku-4-5"):
            sync_agent_registry(mock_bridge, tmp_path)

        assert call_order[0] == "cleanup", "cleanup must run before write_back"
        assert "write_back" in call_order


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _AnyString:
    """Matches any string in assertions."""
    def __eq__(self, other):
        return isinstance(other, str)
    def __repr__(self):
        return "<ANY_STRING>"


def unittest_any_string():
    return _AnyString()


async def _to_thread_passthrough(fn, *args, **kwargs):
    """Replacement for asyncio.to_thread that calls synchronously."""
    return fn(*args, **kwargs)


def _make_test_queue(initial_data):
    """Create an asyncio.Queue pre-loaded with test data for async_subscribe mocking."""
    q = asyncio.Queue()
    q.put_nowait(initial_data)
    return q
