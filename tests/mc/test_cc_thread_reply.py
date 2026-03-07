"""Tests for handle_cc_thread_reply orientation injection (CC-12)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.contexts.execution.executor import TaskExecutor
from mc.types import AgentData, CCTaskResult, WorkspaceContext


def _make_bridge():
    bridge = MagicMock()
    bridge.query = MagicMock(return_value=None)
    bridge.send_message = MagicMock(return_value=None)
    bridge.create_activity = MagicMock(return_value=None)
    bridge.mutation = MagicMock(return_value=None)
    return bridge


def _make_executor(bridge=None):
    bridge = bridge or _make_bridge()
    return TaskExecutor(bridge, on_task_completed=None)


@pytest.mark.asyncio
async def test_thread_reply_passes_orientation_to_prepare():
    """handle_cc_thread_reply should call ws_mgr.prepare() with orientation kwarg."""
    executor = _make_executor()
    agent_data = AgentData(name="test-agent", display_name="Test", role="agent", backend="claude-code")

    mock_ws_ctx = WorkspaceContext(
        cwd=Path("/tmp/test"),
        mcp_config=Path("/tmp/test/.mcp.json"),
        claude_md=Path("/tmp/test/CLAUDE.md"),
        socket_path="/tmp/mc-test.sock",
    )

    mock_result = CCTaskResult(output="done", session_id="s1", cost_usd=0.01, usage={}, is_error=False)

    with patch("claude_code.workspace.CCWorkspaceManager") as MockWS, \
         patch("claude_code.ipc_server.MCSocketServer") as MockIPC, \
         patch("claude_code.provider.ClaudeCodeProvider") as MockProv, \
         patch("mc.infrastructure.orientation.load_orientation", return_value="Global orientation text"):

        MockWS.return_value.prepare.return_value = mock_ws_ctx
        MockIPC.return_value.start = AsyncMock()
        MockIPC.return_value.stop = AsyncMock()
        MockProv.return_value.execute_task = AsyncMock(return_value=mock_result)

        await executor.handle_cc_thread_reply("task1", "test-agent", "hello", agent_data)

        MockWS.return_value.prepare.assert_called_once()
        call_kwargs = MockWS.return_value.prepare.call_args
        assert call_kwargs.kwargs.get("orientation") == "Global orientation text" or \
               (len(call_kwargs.args) >= 4 and "Global orientation text" in str(call_kwargs))
