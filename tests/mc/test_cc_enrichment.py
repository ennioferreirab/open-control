"""Tests for CC-10: Context enrichment for CC task path."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.contexts.execution.executor import TaskExecutor
from mc.types import AgentData, CCTaskResult, WorkspaceContext


def _make_bridge():
    bridge = MagicMock()
    bridge.query = MagicMock(return_value=None)
    bridge.get_task_messages = MagicMock(return_value=[])
    bridge.get_agent_by_name = MagicMock(return_value=None)
    bridge.send_message = MagicMock(return_value=None)
    bridge.create_activity = MagicMock(return_value=None)
    bridge.update_task_status = MagicMock(return_value=None)
    bridge.mutation = MagicMock(return_value=None)
    return bridge


def _make_executor(bridge=None):
    bridge = bridge or _make_bridge()
    return TaskExecutor(bridge, on_task_completed=None)


class TestEnrichCCDescription:
    @pytest.mark.asyncio
    async def test_enrich_appends_file_manifest(self):
        bridge = _make_bridge()
        bridge.query = MagicMock(return_value={
            "files": [
                {
                    "name": "report.pdf",
                    "type": "application/pdf",
                    "size": 1024,
                    "subfolder": "attachments",
                }
            ]
        })
        executor = _make_executor(bridge)
        result = await executor._enrich_cc_description("task1", "Base desc", None)
        assert "Task workspace:" in result
        assert "report.pdf" in result
        assert "Save ALL output files" in result

    @pytest.mark.asyncio
    async def test_enrich_appends_thread_context(self):
        bridge = _make_bridge()
        bridge.get_task_messages = MagicMock(return_value=[
            {
                "author": "user",
                "authorType": "user",
                "content": "Please help",
                "createdAt": 1000,
            }
        ])
        executor = _make_executor(bridge)

        with patch("mc.contexts.execution.executor._build_thread_context", return_value="[Thread]\nuser: Please help"):
            result = await executor._enrich_cc_description("task1", "Base desc", None)

        assert "[Thread]" in result or "Please help" in result

    @pytest.mark.asyncio
    async def test_enrich_appends_tag_attributes(self):
        bridge = _make_bridge()
        tag_values = [{"tag_name": "client", "attribute_id": "a1", "value": "high"}]
        tag_catalog = [{"id": "a1", "name": "priority"}]

        def mock_query(fn, args):
            if fn == "tasks:getById":
                return None
            if fn == "tagAttributeValues:getByTask":
                return tag_values
            if fn == "tagAttributes:list":
                return tag_catalog
            return None

        bridge.query = MagicMock(side_effect=mock_query)
        executor = _make_executor(bridge)

        task_data = {"tags": ["client"]}
        with patch(
            "mc.contexts.execution.executor._build_tag_attributes_context",
            return_value="[Task Tag Attributes]\nclient: priority=high",
        ):
            result = await executor._enrich_cc_description("task1", "Base desc", task_data)

        assert "Tag Attributes" in result

    @pytest.mark.asyncio
    async def test_enrich_continues_on_partial_failure(self):
        bridge = _make_bridge()
        bridge.query = MagicMock(side_effect=Exception("Convex down"))
        bridge.get_task_messages = MagicMock(return_value=[])
        executor = _make_executor(bridge)

        result = await executor._enrich_cc_description("task1", "Base desc", None)
        # Should not raise, should return at least the base desc
        assert "Base desc" in result

    @pytest.mark.asyncio
    async def test_convex_prompt_synced_to_agent_data(self):
        bridge = _make_bridge()
        bridge.get_agent_by_name = MagicMock(return_value={
            "prompt": "Convex prompt content",
            "model": "cc/claude-sonnet-4-6",
        })
        executor = _make_executor(bridge)
        agent_data = AgentData(
            name="test", display_name="Test", role="agent", backend="claude-code"
        )

        mock_ws_ctx = WorkspaceContext(
            cwd=Path("/tmp/test"),
            mcp_config=Path("/tmp/.mcp.json"),
            claude_md=Path("/tmp/CLAUDE.md"),
            socket_path="/tmp/mc-test.sock",
        )
        mock_result = CCTaskResult(
            output="done", session_id="s1", cost_usd=0.01, usage={}, is_error=False
        )

        with patch("claude_code.workspace.CCWorkspaceManager") as MockWS, patch(
            "claude_code.ipc_server.MCSocketServer"
        ) as MockIPC, patch("claude_code.provider.ClaudeCodeProvider") as MockProv, patch(
            "mc.infrastructure.orientation.load_orientation", return_value=None
        ):
            MockWS.return_value.prepare.return_value = mock_ws_ctx
            MockIPC.return_value.start = AsyncMock()
            MockIPC.return_value.stop = AsyncMock()
            MockProv.return_value.execute_task = AsyncMock(return_value=mock_result)

            await executor._execute_cc_task("task1", "Test", "desc", "test", agent_data)

        assert agent_data.prompt == "Convex prompt content"

    @pytest.mark.asyncio
    async def test_variable_interpolation_applied(self):
        bridge = _make_bridge()
        bridge.get_agent_by_name = MagicMock(return_value={
            "prompt": "Hello {{name}}, you are {{role}}",
            "variables": [
                {"name": "name", "value": "Bot"},
                {"name": "role", "value": "assistant"},
            ],
        })
        executor = _make_executor(bridge)
        agent_data = AgentData(
            name="test", display_name="Test", role="agent", backend="claude-code"
        )

        mock_ws_ctx = WorkspaceContext(
            cwd=Path("/tmp/test"),
            mcp_config=Path("/tmp/.mcp.json"),
            claude_md=Path("/tmp/CLAUDE.md"),
            socket_path="/tmp/mc-test.sock",
        )
        mock_result = CCTaskResult(
            output="done", session_id="s1", cost_usd=0.01, usage={}, is_error=False
        )

        with patch("claude_code.workspace.CCWorkspaceManager") as MockWS, patch(
            "claude_code.ipc_server.MCSocketServer"
        ) as MockIPC, patch("claude_code.provider.ClaudeCodeProvider") as MockProv, patch(
            "mc.infrastructure.orientation.load_orientation", return_value=None
        ):
            MockWS.return_value.prepare.return_value = mock_ws_ctx
            MockIPC.return_value.start = AsyncMock()
            MockIPC.return_value.stop = AsyncMock()
            MockProv.return_value.execute_task = AsyncMock(return_value=mock_result)

            await executor._execute_cc_task("task1", "Test", "desc", "test", agent_data)

        assert agent_data.prompt == "Hello Bot, you are assistant"

    @pytest.mark.asyncio
    async def test_convex_prompt_appears_in_claude_md(self, tmp_path):
        """Integration: Convex prompt synced to agent_data should appear in generated CLAUDE.md."""
        bridge = _make_bridge()
        bridge.get_agent_by_name = MagicMock(return_value={
            "prompt": "You are a specialist in data analysis.",
        })
        executor = _make_executor(bridge)
        agent_data = AgentData(
            name="analyst", display_name="Analyst", role="agent", backend="claude-code"
        )

        from claude_code.workspace import CCWorkspaceManager

        ws_mgr = CCWorkspaceManager(workspace_root=tmp_path)

        mock_result = CCTaskResult(
            output="done", session_id="s1", cost_usd=0.01, usage={}, is_error=False
        )

        # Use real workspace manager but mock IPC/provider
        with patch("claude_code.ipc_server.MCSocketServer") as MockIPC, \
             patch("claude_code.provider.ClaudeCodeProvider") as MockProv, \
             patch("mc.infrastructure.orientation.load_orientation", return_value=None), \
             patch("claude_code.workspace.CCWorkspaceManager", return_value=ws_mgr), \
             patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}), \
             patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]):
            MockIPC.return_value.start = AsyncMock()
            MockIPC.return_value.stop = AsyncMock()
            MockProv.return_value.execute_task = AsyncMock(return_value=mock_result)

            await executor._execute_cc_task(
                "task1", "Test", "desc", "analyst", agent_data,
                needs_enrichment=False,
            )

        # Convex prompt should have been synced to agent_data
        assert agent_data.prompt == "You are a specialist in data analysis."
        # And the workspace manager should have written it into CLAUDE.md
        claude_md = tmp_path / "agents" / "analyst" / "CLAUDE.md"
        assert claude_md.exists()
        content = claude_md.read_text(encoding="utf-8")
        assert "You are a specialist in data analysis." in content
