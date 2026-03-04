"""Tests for Claude Code backend integration in TaskExecutor (Story CC-5).

Covers:
- Backend routing: claude-code → _execute_cc_task
- Nanobot backend → existing nanobot path
- No backend field → existing nanobot path
- Workspace preparation failure → crash
- IPC server failure → crash
- CC execution failure → crash
- Successful CC execution → done (message + activity + status)
- Stream callback posts step_started activities
- Cost tracking in completion activity
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from mc.executor import TaskExecutor
from mc.types import (
    AgentData,
    CCTaskResult,
    ClaudeCodeOpts,
    WorkspaceContext,
    TaskStatus,
    ActivityEventType,
    AuthorType,
    MessageType,
)

# Patch targets for lazy-imported CC modules (imported inside _execute_cc_task).
# These must match the location where the name is looked up (the source module).
_PATCH_WS_MGR = "mc.cc_workspace.CCWorkspaceManager"
_PATCH_IPC_SRV = "mc.mcp_ipc_server.MCSocketServer"
_PATCH_PROVIDER = "mc.cc_provider.ClaudeCodeProvider"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_bridge() -> MagicMock:
    """Return a minimal ConvexBridge mock."""
    bridge = MagicMock()
    bridge.send_message = MagicMock(return_value=None)
    bridge.create_activity = MagicMock(return_value=None)
    bridge.update_task_status = MagicMock(return_value=None)
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


def _ws_ctx() -> WorkspaceContext:
    return WorkspaceContext(
        cwd=Path("/tmp/test-ws"),
        mcp_config=Path("/tmp/test-ws/.mcp.json"),
        claude_md=Path("/tmp/test-ws/CLAUDE.md"),
        socket_path="/tmp/mc-test.sock",
    )


def _cc_result(
    output: str = "All done",
    cost_usd: float = 0.0123,
    is_error: bool = False,
) -> CCTaskResult:
    return CCTaskResult(
        output=output,
        session_id="sess-abc",
        cost_usd=cost_usd,
        usage={"input_tokens": 100, "output_tokens": 50},
        is_error=is_error,
    )


# ---------------------------------------------------------------------------
# Backend routing: claude-code → _execute_cc_task
# ---------------------------------------------------------------------------


class TestBackendRouting:
    """_execute_task routes to _execute_cc_task when backend == 'claude-code'."""

    @pytest.mark.asyncio
    async def test_claude_code_backend_routes_to_execute_cc_task(self):
        executor = _make_executor()
        agent_data = _cc_agent(backend="claude-code")

        with (
            patch.object(executor, "_load_agent_data", return_value=agent_data),
            patch.object(executor, "_execute_cc_task", new_callable=AsyncMock) as mock_cc,
        ):
            await executor._execute_task(
                task_id="t1",
                title="Test task",
                description="desc",
                agent_name="my-cc-agent",
                trust_level="autonomous",
            )

        mock_cc.assert_awaited_once_with(
            "t1", "Test task", "desc", "my-cc-agent", agent_data
        )

    @pytest.mark.asyncio
    async def test_nanobot_backend_skips_cc_task(self):
        executor = _make_executor()
        agent_data = _cc_agent(backend="nanobot")

        with (
            patch.object(executor, "_load_agent_data", return_value=agent_data),
            patch.object(executor, "_execute_cc_task", new_callable=AsyncMock) as mock_cc,
            # Patch the nanobot path so it doesn't actually run
            patch("mc.executor._run_agent_on_task", new_callable=AsyncMock) as mock_run,
            patch("mc.executor._snapshot_output_dir", return_value={}),
            patch("mc.executor._collect_output_artifacts", return_value=[]),
            patch.object(executor, "_load_agent_config", return_value=(None, None, None)),
            patch.object(executor._bridge, "query", return_value={}),
            patch.object(executor._bridge, "update_task_status", return_value=None),
            patch.object(executor._bridge, "send_message", return_value=None),
            patch.object(executor._bridge, "get_agent_by_name", return_value=None),
        ):
            mock_run.return_value = ("result", "key", MagicMock())
            await executor._execute_task(
                task_id="t2",
                title="Nanobot task",
                description=None,
                agent_name="my-cc-agent",
                trust_level="autonomous",
            )

        mock_cc.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_agent_data_skips_cc_task(self):
        executor = _make_executor()

        with (
            patch.object(executor, "_load_agent_data", return_value=None),
            patch.object(executor, "_execute_cc_task", new_callable=AsyncMock) as mock_cc,
            patch("mc.executor._run_agent_on_task", new_callable=AsyncMock) as mock_run,
            patch("mc.executor._snapshot_output_dir", return_value={}),
            patch("mc.executor._collect_output_artifacts", return_value=[]),
            patch.object(executor, "_load_agent_config", return_value=(None, None, None)),
            patch.object(executor._bridge, "query", return_value={}),
            patch.object(executor._bridge, "update_task_status", return_value=None),
            patch.object(executor._bridge, "send_message", return_value=None),
            patch.object(executor._bridge, "get_agent_by_name", return_value=None),
        ):
            mock_run.return_value = ("result", "key", MagicMock())
            await executor._execute_task(
                task_id="t3",
                title="Unregistered agent",
                description=None,
                agent_name="unknown-agent",
                trust_level="autonomous",
            )

        mock_cc.assert_not_awaited()


# ---------------------------------------------------------------------------
# _execute_cc_task happy path
# ---------------------------------------------------------------------------


class TestExecuteCCTaskHappyPath:

    @pytest.mark.asyncio
    async def test_successful_execution_transitions_to_done(self):
        bridge = _make_bridge()
        executor = _make_executor(bridge)
        agent_data = _cc_agent()
        ws_ctx = _ws_ctx()
        result = _cc_result(output="All done", cost_usd=0.0123)

        mock_ws_mgr = MagicMock()
        mock_ws_mgr.prepare.return_value = ws_ctx

        mock_ipc = AsyncMock()
        mock_provider = MagicMock()
        mock_provider.execute_task = AsyncMock(return_value=result)

        with (
            patch(_PATCH_WS_MGR, return_value=mock_ws_mgr),
            patch(_PATCH_IPC_SRV, return_value=mock_ipc),
            patch(_PATCH_PROVIDER, return_value=mock_provider),
        ):
            await executor._execute_cc_task(
                "t1", "My task", "desc", "my-cc-agent", agent_data
            )

        # Should send a work message
        bridge.send_message.assert_called_once()
        call_args = bridge.send_message.call_args[0]
        assert call_args[0] == "t1"           # task_id
        assert call_args[1] == "my-cc-agent"  # author_name
        assert call_args[2] == AuthorType.AGENT
        assert "All done" in call_args[3]     # content

        # Should update status to DONE
        bridge.update_task_status.assert_called_once()
        status_args = bridge.update_task_status.call_args[0]
        assert status_args[1] == TaskStatus.DONE

        # IPC server should be stopped
        mock_ipc.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_prompt_combines_title_and_description(self):
        executor = _make_executor()
        agent_data = _cc_agent()
        ws_ctx = _ws_ctx()

        mock_ws_mgr = MagicMock()
        mock_ws_mgr.prepare.return_value = ws_ctx

        mock_ipc = AsyncMock()
        mock_provider = MagicMock()
        captured: list[str] = []

        async def capture_execute_task(**kwargs):
            captured.append(kwargs["prompt"])
            return _cc_result()

        mock_provider.execute_task = capture_execute_task

        with (
            patch(_PATCH_WS_MGR, return_value=mock_ws_mgr),
            patch(_PATCH_IPC_SRV, return_value=mock_ipc),
            patch(_PATCH_PROVIDER, return_value=mock_provider),
        ):
            await executor._execute_cc_task(
                "t1", "My title", "My description", "agent", agent_data
            )

        assert len(captured) == 1
        assert "My title" in captured[0]
        assert "My description" in captured[0]

    @pytest.mark.asyncio
    async def test_prompt_uses_title_only_when_no_description(self):
        executor = _make_executor()
        agent_data = _cc_agent()
        ws_ctx = _ws_ctx()

        mock_ws_mgr = MagicMock()
        mock_ws_mgr.prepare.return_value = ws_ctx

        mock_ipc = AsyncMock()
        mock_provider = MagicMock()
        captured: list[str] = []

        async def capture_execute_task(**kwargs):
            captured.append(kwargs["prompt"])
            return _cc_result()

        mock_provider.execute_task = capture_execute_task

        with (
            patch(_PATCH_WS_MGR, return_value=mock_ws_mgr),
            patch(_PATCH_IPC_SRV, return_value=mock_ipc),
            patch(_PATCH_PROVIDER, return_value=mock_provider),
        ):
            await executor._execute_cc_task(
                "t1", "Title only", None, "agent", agent_data
            )

        assert captured[0] == "Title only"


# ---------------------------------------------------------------------------
# _execute_cc_task failure scenarios
# ---------------------------------------------------------------------------


class TestExecuteCCTaskFailures:

    @pytest.mark.asyncio
    async def test_workspace_prep_failure_crashes_task(self):
        executor = _make_executor()
        agent_data = _cc_agent()

        mock_ws_mgr = MagicMock()
        mock_ws_mgr.prepare.side_effect = RuntimeError("disk full")

        with (
            patch(_PATCH_WS_MGR, return_value=mock_ws_mgr),
            patch.object(executor, "_crash_task", new_callable=AsyncMock) as mock_crash,
        ):
            await executor._execute_cc_task(
                "t1", "Failing task", None, "agent", agent_data
            )

        mock_crash.assert_awaited_once()
        crash_args = mock_crash.call_args[0]
        assert "Workspace preparation failed" in crash_args[2]
        assert "disk full" in crash_args[2]

    @pytest.mark.asyncio
    async def test_ipc_server_failure_crashes_task(self):
        executor = _make_executor()
        agent_data = _cc_agent()

        mock_ws_mgr = MagicMock()
        mock_ws_mgr.prepare.return_value = _ws_ctx()

        mock_ipc = AsyncMock()
        mock_ipc.start.side_effect = OSError("address in use")

        with (
            patch(_PATCH_WS_MGR, return_value=mock_ws_mgr),
            patch(_PATCH_IPC_SRV, return_value=mock_ipc),
            patch.object(executor, "_crash_task", new_callable=AsyncMock) as mock_crash,
        ):
            await executor._execute_cc_task(
                "t1", "IPC failure", None, "agent", agent_data
            )

        mock_crash.assert_awaited_once()
        crash_args = mock_crash.call_args[0]
        assert "MCP IPC server failed" in crash_args[2]

    @pytest.mark.asyncio
    async def test_cc_execution_failure_crashes_task(self):
        executor = _make_executor()
        agent_data = _cc_agent()
        ws_ctx = _ws_ctx()

        mock_ws_mgr = MagicMock()
        mock_ws_mgr.prepare.return_value = ws_ctx

        mock_ipc = AsyncMock()
        mock_provider = MagicMock()
        mock_provider.execute_task = AsyncMock(side_effect=RuntimeError("subprocess died"))

        with (
            patch(_PATCH_WS_MGR, return_value=mock_ws_mgr),
            patch(_PATCH_IPC_SRV, return_value=mock_ipc),
            patch(_PATCH_PROVIDER, return_value=mock_provider),
            patch.object(executor, "_crash_task", new_callable=AsyncMock) as mock_crash,
        ):
            await executor._execute_cc_task(
                "t1", "Exec failure", None, "agent", agent_data
            )

        mock_crash.assert_awaited_once()
        crash_args = mock_crash.call_args[0]
        assert "Claude Code execution failed" in crash_args[2]
        # IPC server should still be stopped even on provider failure
        mock_ipc.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cc_error_result_crashes_task(self):
        executor = _make_executor()
        agent_data = _cc_agent()
        ws_ctx = _ws_ctx()
        error_result = _cc_result(output="something went wrong", is_error=True)

        mock_ws_mgr = MagicMock()
        mock_ws_mgr.prepare.return_value = ws_ctx

        mock_ipc = AsyncMock()
        mock_provider = MagicMock()
        mock_provider.execute_task = AsyncMock(return_value=error_result)

        with (
            patch(_PATCH_WS_MGR, return_value=mock_ws_mgr),
            patch(_PATCH_IPC_SRV, return_value=mock_ipc),
            patch(_PATCH_PROVIDER, return_value=mock_provider),
            patch.object(executor, "_crash_task", new_callable=AsyncMock) as mock_crash,
        ):
            await executor._execute_cc_task(
                "t1", "Error result", None, "agent", agent_data
            )

        mock_crash.assert_awaited_once()
        crash_args = mock_crash.call_args[0]
        assert "Claude Code error" in crash_args[2]


# ---------------------------------------------------------------------------
# IPC server always stopped (finally block)
# ---------------------------------------------------------------------------


class TestIPCServerCleanup:

    @pytest.mark.asyncio
    async def test_ipc_server_stopped_on_success(self):
        executor = _make_executor()
        agent_data = _cc_agent()
        ws_ctx = _ws_ctx()

        mock_ws_mgr = MagicMock()
        mock_ws_mgr.prepare.return_value = ws_ctx

        mock_ipc = AsyncMock()
        mock_provider = MagicMock()
        mock_provider.execute_task = AsyncMock(return_value=_cc_result())

        with (
            patch(_PATCH_WS_MGR, return_value=mock_ws_mgr),
            patch(_PATCH_IPC_SRV, return_value=mock_ipc),
            patch(_PATCH_PROVIDER, return_value=mock_provider),
        ):
            await executor._execute_cc_task(
                "t1", "title", None, "agent", agent_data
            )

        mock_ipc.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ipc_server_stopped_on_provider_exception(self):
        executor = _make_executor()
        agent_data = _cc_agent()
        ws_ctx = _ws_ctx()

        mock_ws_mgr = MagicMock()
        mock_ws_mgr.prepare.return_value = ws_ctx

        mock_ipc = AsyncMock()
        mock_provider = MagicMock()
        mock_provider.execute_task = AsyncMock(side_effect=RuntimeError("boom"))

        with (
            patch(_PATCH_WS_MGR, return_value=mock_ws_mgr),
            patch(_PATCH_IPC_SRV, return_value=mock_ipc),
            patch(_PATCH_PROVIDER, return_value=mock_provider),
            patch.object(executor, "_crash_task", new_callable=AsyncMock),
        ):
            await executor._execute_cc_task(
                "t1", "title", None, "agent", agent_data
            )

        mock_ipc.stop.assert_awaited_once()


# ---------------------------------------------------------------------------
# Stream callback posts activities
# ---------------------------------------------------------------------------


class TestStreamCallback:

    @pytest.mark.asyncio
    async def test_on_stream_callback_posts_activity(self):
        bridge = _make_bridge()
        executor = _make_executor(bridge)
        agent_data = _cc_agent()
        ws_ctx = _ws_ctx()

        mock_ws_mgr = MagicMock()
        mock_ws_mgr.prepare.return_value = ws_ctx

        mock_ipc = AsyncMock()

        # Capture the on_stream callback and call it during execute_task
        captured_callback: list = []

        async def execute_task_with_stream(**kwargs):
            cb = kwargs.get("on_stream")
            if cb:
                captured_callback.append(cb)
                cb({"type": "text", "text": "Working on it..."})
            return _cc_result()

        mock_provider = MagicMock()
        mock_provider.execute_task = execute_task_with_stream

        with (
            patch(_PATCH_WS_MGR, return_value=mock_ws_mgr),
            patch(_PATCH_IPC_SRV, return_value=mock_ipc),
            patch(_PATCH_PROVIDER, return_value=mock_provider),
        ):
            await executor._execute_cc_task(
                "t1", "Stream task", "desc", "my-cc-agent", agent_data
            )

        assert len(captured_callback) == 1

        # Drain any pending asyncio tasks (the create_task from on_stream callback)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        # An activity should have been created for the stream text
        activity_calls = bridge.create_activity.call_args_list
        # The completion activity is also posted; find the step_started one
        step_started_calls = [
            c for c in activity_calls
            if c[0][0] == ActivityEventType.STEP_STARTED
        ]
        assert len(step_started_calls) >= 1
        assert "Working on it..." in step_started_calls[0][0][1]

    @pytest.mark.asyncio
    async def test_non_text_stream_events_do_not_post_activity(self):
        bridge = _make_bridge()
        executor = _make_executor(bridge)
        agent_data = _cc_agent()
        ws_ctx = _ws_ctx()

        mock_ws_mgr = MagicMock()
        mock_ws_mgr.prepare.return_value = ws_ctx

        mock_ipc = AsyncMock()

        async def execute_task_with_tool_use(**kwargs):
            cb = kwargs.get("on_stream")
            if cb:
                cb({"type": "tool_use", "name": "Read"})  # should NOT post activity
            return _cc_result()

        mock_provider = MagicMock()
        mock_provider.execute_task = execute_task_with_tool_use

        with (
            patch(_PATCH_WS_MGR, return_value=mock_ws_mgr),
            patch(_PATCH_IPC_SRV, return_value=mock_ipc),
            patch(_PATCH_PROVIDER, return_value=mock_provider),
        ):
            await executor._execute_cc_task(
                "t1", "tool use task", None, "agent", agent_data
            )

        await asyncio.sleep(0)

        # Only the completion activity should be posted
        activity_calls = bridge.create_activity.call_args_list
        step_started_calls = [
            c for c in activity_calls
            if c[0][0] == ActivityEventType.STEP_STARTED
        ]
        assert len(step_started_calls) == 0


# ---------------------------------------------------------------------------
# Cost tracking
# ---------------------------------------------------------------------------


class TestCostTracking:

    @pytest.mark.asyncio
    async def test_completion_activity_includes_cost(self):
        bridge = _make_bridge()
        executor = _make_executor(bridge)
        agent_data = _cc_agent()
        ws_ctx = _ws_ctx()
        result = _cc_result(cost_usd=0.0456)

        mock_ws_mgr = MagicMock()
        mock_ws_mgr.prepare.return_value = ws_ctx

        mock_ipc = AsyncMock()
        mock_provider = MagicMock()
        mock_provider.execute_task = AsyncMock(return_value=result)

        with (
            patch(_PATCH_WS_MGR, return_value=mock_ws_mgr),
            patch(_PATCH_IPC_SRV, return_value=mock_ipc),
            patch(_PATCH_PROVIDER, return_value=mock_provider),
        ):
            await executor._execute_cc_task(
                "t1", "Cost task", None, "my-cc-agent", agent_data
            )

        # Find the TASK_COMPLETED activity (posted in _complete_cc_task)
        activity_calls = bridge.create_activity.call_args_list
        completed_calls = [
            c for c in activity_calls
            if c[0][0] == ActivityEventType.TASK_COMPLETED
        ]
        assert len(completed_calls) == 1
        description = completed_calls[0][0][1]
        assert "0.0456" in description
        assert "Cost" in description


# ---------------------------------------------------------------------------
# _crash_task
# ---------------------------------------------------------------------------


class TestCrashTask:

    @pytest.mark.asyncio
    async def test_crash_task_sends_message_and_updates_status(self):
        bridge = _make_bridge()
        executor = _make_executor(bridge)

        await executor._crash_task("t1", "Crashed task", "Something went wrong")

        bridge.send_message.assert_called_once()
        msg_args = bridge.send_message.call_args[0]
        assert "Something went wrong" in msg_args[3]

        bridge.update_task_status.assert_called_once()
        status_args = bridge.update_task_status.call_args[0]
        assert status_args[1] == TaskStatus.CRASHED

    @pytest.mark.asyncio
    async def test_crash_task_tolerates_bridge_errors(self):
        bridge = _make_bridge()
        executor = _make_executor(bridge)
        bridge.send_message.side_effect = RuntimeError("connection lost")
        bridge.update_task_status.side_effect = RuntimeError("connection lost")

        # Must not raise
        await executor._crash_task("t1", "Flaky task", "error")


# ---------------------------------------------------------------------------
# _complete_cc_task
# ---------------------------------------------------------------------------


class TestCompleteCCTask:

    @pytest.mark.asyncio
    async def test_complete_sends_message_activity_and_status(self):
        bridge = _make_bridge()
        executor = _make_executor(bridge)
        result = _cc_result(output="Great success", cost_usd=0.001)

        await executor._complete_cc_task("t1", "My task", "agent-x", result)

        # Work message
        bridge.send_message.assert_called_once()
        msg_args = bridge.send_message.call_args[0]
        assert "Great success" in msg_args[3]
        assert msg_args[2] == AuthorType.AGENT
        assert msg_args[4] == MessageType.WORK

        # Cost activity
        bridge.create_activity.assert_called_once()
        act_args = bridge.create_activity.call_args[0]
        assert act_args[0] == ActivityEventType.TASK_COMPLETED
        assert "0.0010" in act_args[1]

        # Status update to DONE
        bridge.update_task_status.assert_called_once()
        status_args = bridge.update_task_status.call_args[0]
        assert status_args[1] == TaskStatus.DONE


# ---------------------------------------------------------------------------
# _load_agent_data
# ---------------------------------------------------------------------------


class TestLoadAgentData:

    def test_returns_none_for_missing_config(self, tmp_path):
        executor = _make_executor()
        # Patch AGENTS_DIR to a temp directory where the agent dir does NOT exist
        with patch("mc.gateway.AGENTS_DIR", tmp_path):
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
            patch("mc.gateway.AGENTS_DIR", tmp_path),
            patch("mc.yaml_validator.validate_agent_file", return_value=expected),
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
            patch("mc.gateway.AGENTS_DIR", tmp_path),
            patch("mc.yaml_validator.validate_agent_file", return_value=["validation error"]),
        ):
            result = executor._load_agent_data("bad-agent")

        assert result is None
