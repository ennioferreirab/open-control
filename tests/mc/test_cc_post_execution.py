"""Tests for CC-11: Post-execution and execution features."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.contexts.execution.executor import TaskExecutor
from mc.types import (
    AgentData,
    CCTaskResult,
    ClaudeCodeOpts,
    TaskStatus,
    WorkspaceContext,
)

_PATCH_WS_MGR = "claude_code.workspace.CCWorkspaceManager"
_PATCH_IPC_SRV = "claude_code.ipc_server.MCSocketServer"
_PATCH_PROVIDER = "claude_code.provider.ClaudeCodeProvider"


def _make_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.query = MagicMock(return_value=None)
    bridge.get_task_messages = MagicMock(return_value=[])
    bridge.get_agent_by_name = MagicMock(return_value=None)
    bridge.send_message = MagicMock(return_value=None)
    bridge.create_activity = MagicMock(return_value=None)
    bridge.update_task_status = MagicMock(return_value=None)
    bridge.mutation = MagicMock(return_value=None)
    bridge.sync_task_output_files = MagicMock(return_value=None)
    bridge.get_board_by_id = MagicMock(return_value={"name": "default"})
    return bridge


def _make_executor(bridge: MagicMock | None = None) -> TaskExecutor:
    bridge = bridge or _make_bridge()
    executor = TaskExecutor(bridge, on_task_completed=None)
    return executor


def _mock_ws_ctx() -> WorkspaceContext:
    return WorkspaceContext(
        cwd=Path("/tmp/test"),
        mcp_config=Path("/tmp/test/.mcp.json"),
        claude_md=Path("/tmp/test/CLAUDE.md"),
        socket_path="/tmp/mc-test.sock",
    )


def _mock_result(output: str = "done", is_error: bool = False) -> CCTaskResult:
    return CCTaskResult(
        output=output,
        session_id="s1",
        cost_usd=0.01,
        usage={},
        is_error=is_error,
    )


class TestTrustLevel:
    @pytest.mark.asyncio
    async def test_trust_autonomous_transitions_review(self):
        """trust_level=autonomous should transition task to REVIEW pending approval."""
        bridge = _make_bridge()
        executor = _make_executor(bridge)

        with (
            patch(_PATCH_WS_MGR) as MockWS,
            patch(_PATCH_IPC_SRV) as MockIPC,
            patch(_PATCH_PROVIDER) as MockProv,
            patch("mc.infrastructure.orientation.load_orientation", return_value=None),
            patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}),
            patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]),
        ):
            MockWS.return_value.prepare.return_value = _mock_ws_ctx()
            MockIPC.return_value.start = AsyncMock()
            MockIPC.return_value.stop = AsyncMock()
            MockProv.return_value.execute_task = AsyncMock(return_value=_mock_result())

            agent_data = AgentData(
                name="test", display_name="Test", role="agent", backend="claude-code"
            )
            await executor._execute_cc_task(
                "t1",
                "Title",
                "desc",
                "test",
                agent_data,
                trust_level="autonomous",
                task_data={"board_id": "board_001"},
            )

        status_calls = bridge.update_task_status.call_args_list
        assert any(c.args[1] == TaskStatus.REVIEW for c in status_calls)

    @pytest.mark.asyncio
    async def test_trust_review_transitions_review(self):
        """trust_level != autonomous should transition task to REVIEW."""
        bridge = _make_bridge()
        executor = _make_executor(bridge)

        with (
            patch(_PATCH_WS_MGR) as MockWS,
            patch(_PATCH_IPC_SRV) as MockIPC,
            patch(_PATCH_PROVIDER) as MockProv,
            patch("mc.infrastructure.orientation.load_orientation", return_value=None),
            patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}),
            patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]),
        ):
            MockWS.return_value.prepare.return_value = _mock_ws_ctx()
            MockIPC.return_value.start = AsyncMock()
            MockIPC.return_value.stop = AsyncMock()
            MockProv.return_value.execute_task = AsyncMock(return_value=_mock_result())

            agent_data = AgentData(
                name="test", display_name="Test", role="agent", backend="claude-code"
            )
            await executor._execute_cc_task(
                "t1",
                "Title",
                "desc",
                "test",
                agent_data,
                trust_level="review",
                task_data={"board_id": "board_001"},
            )

        status_calls = bridge.update_task_status.call_args_list
        assert any(c.args[1] == TaskStatus.REVIEW for c in status_calls)


class TestArtifacts:
    @pytest.mark.asyncio
    async def test_artifacts_collected_and_synced(self):
        """Output artifacts should be collected and synced after success."""
        bridge = _make_bridge()
        executor = _make_executor(bridge)

        with (
            patch(_PATCH_WS_MGR) as MockWS,
            patch(_PATCH_IPC_SRV) as MockIPC,
            patch(_PATCH_PROVIDER) as MockProv,
            patch("mc.infrastructure.orientation.load_orientation", return_value=None),
            patch(
                "mc.contexts.execution.executor._snapshot_output_dir", return_value={}
            ) as mock_snap,
            patch(
                "mc.contexts.execution.executor._collect_output_artifacts",
                return_value=[{"path": "output/report.pdf", "action": "created"}],
            ),
        ):
            MockWS.return_value.prepare.return_value = _mock_ws_ctx()
            MockIPC.return_value.start = AsyncMock()
            MockIPC.return_value.stop = AsyncMock()
            MockProv.return_value.execute_task = AsyncMock(return_value=_mock_result())

            agent_data = AgentData(
                name="test", display_name="Test", role="agent", backend="claude-code"
            )
            await executor._execute_cc_task(
                "t1", "Title", "desc", "test", agent_data, task_data={"board_id": "board_001"}
            )

        mock_snap.assert_called_once_with("t1")
        bridge.sync_task_output_files.assert_called_once()


class TestHeartbeat:
    @pytest.mark.asyncio
    async def test_heartbeat_written(self, tmp_path: Path):
        """HEARTBEAT.md should be written on completion."""
        bridge = _make_bridge()
        executor = _make_executor(bridge)

        heartbeat_dir = tmp_path / ".nanobot" / "workspace"
        heartbeat_dir.mkdir(parents=True)
        heartbeat_file = heartbeat_dir / "HEARTBEAT.md"

        with (
            patch(_PATCH_WS_MGR) as MockWS,
            patch(_PATCH_IPC_SRV) as MockIPC,
            patch(_PATCH_PROVIDER) as MockProv,
            patch("mc.infrastructure.orientation.load_orientation", return_value=None),
            patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}),
            patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]),
            patch(
                "mc.contexts.execution.cc_executor.get_workspace_dir",
                return_value=heartbeat_dir,
            ),
        ):
            MockWS.return_value.prepare.return_value = _mock_ws_ctx()
            MockIPC.return_value.start = AsyncMock()
            MockIPC.return_value.stop = AsyncMock()
            MockProv.return_value.execute_task = AsyncMock(return_value=_mock_result())

            agent_data = AgentData(
                name="test", display_name="Test", role="agent", backend="claude-code"
            )
            await executor._execute_cc_task(
                "t1", "Title", "desc", "test", agent_data, task_data={"board_id": "board_001"}
            )

        assert heartbeat_file.exists()
        content = heartbeat_file.read_text()
        assert "Mission Control Update" in content
        assert "Title" in content


class TestProviderError:
    @pytest.mark.asyncio
    async def test_provider_error_handled_specifically(self):
        """Provider errors should route to _handle_provider_error, not generic crash."""
        bridge = _make_bridge()
        executor = _make_executor(bridge)

        from mc.infrastructure.providers.factory import ProviderError

        with (
            patch(_PATCH_WS_MGR) as MockWS,
            patch(_PATCH_IPC_SRV) as MockIPC,
            patch(_PATCH_PROVIDER) as MockProv,
            patch("mc.infrastructure.orientation.load_orientation", return_value=None),
            patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}),
            patch.object(executor, "_handle_provider_error", new_callable=AsyncMock) as mock_handle,
        ):
            MockWS.return_value.prepare.return_value = _mock_ws_ctx()
            MockIPC.return_value.start = AsyncMock()
            MockIPC.return_value.stop = AsyncMock()
            MockProv.return_value.execute_task = AsyncMock(
                side_effect=ProviderError("auth expired")
            )

            agent_data = AgentData(
                name="test", display_name="Test", role="agent", backend="claude-code"
            )
            await executor._execute_cc_task(
                "t1", "Title", "desc", "test", agent_data, task_data={"board_id": "board_001"}
            )

        mock_handle.assert_called_once()


class TestEffortLevel:
    @pytest.mark.asyncio
    async def test_effort_level_mapped_and_forwarded(self):
        """reasoning_level should be mapped to effort_level on agent_data."""
        bridge = _make_bridge()
        executor = _make_executor(bridge)

        with (
            patch(_PATCH_WS_MGR) as MockWS,
            patch(_PATCH_IPC_SRV) as MockIPC,
            patch(_PATCH_PROVIDER) as MockProv,
            patch("mc.infrastructure.orientation.load_orientation", return_value=None),
            patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}),
            patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]),
        ):
            MockWS.return_value.prepare.return_value = _mock_ws_ctx()
            MockIPC.return_value.start = AsyncMock()
            MockIPC.return_value.stop = AsyncMock()
            MockProv.return_value.execute_task = AsyncMock(return_value=_mock_result())

            agent_data = AgentData(
                name="test", display_name="Test", role="agent", backend="claude-code"
            )
            await executor._execute_cc_task(
                "t1",
                "Title",
                "desc",
                "test",
                agent_data,
                reasoning_level="max",
                task_data={"board_id": "board_001"},
            )

        assert agent_data.claude_code_opts is not None
        assert agent_data.claude_code_opts.effort_level == "high"

    @pytest.mark.asyncio
    async def test_effort_medium_maps_to_medium(self):
        """'medium' reasoning level should map to 'medium' effort."""
        bridge = _make_bridge()
        executor = _make_executor(bridge)

        with (
            patch(_PATCH_WS_MGR) as MockWS,
            patch(_PATCH_IPC_SRV) as MockIPC,
            patch(_PATCH_PROVIDER) as MockProv,
            patch("mc.infrastructure.orientation.load_orientation", return_value=None),
            patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}),
            patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]),
        ):
            MockWS.return_value.prepare.return_value = _mock_ws_ctx()
            MockIPC.return_value.start = AsyncMock()
            MockIPC.return_value.stop = AsyncMock()
            MockProv.return_value.execute_task = AsyncMock(return_value=_mock_result())

            agent_data = AgentData(
                name="test", display_name="Test", role="agent", backend="claude-code"
            )
            await executor._execute_cc_task(
                "t1",
                "Title",
                "desc",
                "test",
                agent_data,
                reasoning_level="medium",
                task_data={"board_id": "board_001"},
            )

        assert agent_data.claude_code_opts is not None
        assert agent_data.claude_code_opts.effort_level == "medium"

    def test_effort_flag_in_cli_command(self):
        """--effort flag should appear in built CLI command."""
        from claude_code.provider import ClaudeCodeProvider

        provider = ClaudeCodeProvider()

        agent_data = AgentData(
            name="test",
            display_name="Test",
            role="agent",
            model="claude-sonnet-4-6",
            claude_code_opts=ClaudeCodeOpts(effort_level="high"),
        )
        ws_ctx = _mock_ws_ctx()
        cmd = provider._build_command("prompt", agent_data, ws_ctx, None)

        assert "--effort" in cmd
        effort_idx = cmd.index("--effort")
        assert cmd[effort_idx + 1] == "high"
