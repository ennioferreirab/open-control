"""Unit tests for the MCP bridge tool handlers with mocked IPC.

These tests verify the canonical MC MCP bridge (mc.runtime.mcp.bridge).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_ipc(responses: dict) -> MagicMock:
    """Create an IPC client mock whose request() returns canned responses."""
    mock = MagicMock()

    async def request(method, params):
        return responses.get(method, {"error": f"Unknown method: {method}"})

    mock.request = request
    return mock


# ---------------------------------------------------------------------------
# Test ask_user tool
# ---------------------------------------------------------------------------


class TestAskUserTool:
    async def test_ask_user_returns_answer(self):
        """ask_user forwards question to IPC and returns the answer."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"ask_user": {"answer": "Yes!"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("ask_user", {"question": "Ready?"})

        assert len(result) == 1
        assert result[0].text == "Yes!"

    async def test_ask_user_with_options(self):
        """ask_user passes options to IPC."""
        import mc.runtime.mcp.bridge as bridge_mod

        received_params: dict = {}

        async def capture_request(method, params):
            received_params.update(params)
            return {"answer": "Option A"}

        mock_ipc = MagicMock()
        mock_ipc.request = capture_request

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "ask_user",
                {"question": "Choose?", "options": ["A", "B"]},
            )

        assert received_params["options"] == ["A", "B"]
        assert result[0].text == "Option A"

    async def test_ask_user_with_structured_questions(self):
        """ask_user passes structured question arrays to IPC."""
        import mc.runtime.mcp.bridge as bridge_mod

        received_params: dict = {}

        async def capture_request(method, params):
            received_params.update(params)
            return {"answer": '{"goal":"recommended","audience":"custom"}'}

        mock_ipc = MagicMock()
        mock_ipc.request = capture_request

        questions = [
            {
                "header": "Goal",
                "id": "goal",
                "question": "What is the main goal?",
                "options": [
                    {"label": "Speed", "description": "Move quickly."},
                    {"label": "Quality", "description": "Optimize for quality."},
                    {"label": "Cost", "description": "Minimize spend."},
                ],
            }
        ]

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "ask_user",
                {"questions": questions},
            )

        assert received_params["questions"] == questions
        assert result[0].text == '{"goal":"recommended","audience":"custom"}'

    async def test_ask_user_ipc_failure(self):
        """ask_user handles IPC ConnectionError gracefully and returns friendly message.

        M4: Verify the friendly error message is returned (not a raised exception).
        """
        import mc.runtime.mcp.bridge as bridge_mod

        async def failing_request(method, params):
            raise ConnectionError("socket not found")

        mock_ipc = MagicMock()
        mock_ipc.request = failing_request

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("ask_user", {"question": "hello?"})

        assert len(result) == 1
        assert "Mission Control not reachable" in result[0].text

    async def test_ask_user_prefers_convex_interaction_service(self):
        import mc.runtime.mcp.bridge as bridge_mod

        service = MagicMock()
        service.ask_user = MagicMock(return_value="Blue")

        with (
            patch.object(bridge_mod, "_get_interaction_service", return_value=service),
            patch.object(bridge_mod, "_build_interaction_context", return_value=object()),
        ):
            result = await bridge_mod.call_tool("ask_user", {"question": "Ready?"})

        assert result[0].text == "Blue"
        service.ask_user.assert_called_once()


# ---------------------------------------------------------------------------
# Test send_message tool
# ---------------------------------------------------------------------------


class TestSendMessageTool:
    async def test_send_message_returns_status(self):
        """send_message returns the IPC status string."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"send_message": {"status": "Message sent"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("send_message", {"content": "hello world"})

        assert result[0].text == "Message sent"

    async def test_send_message_passes_optional_channel(self):
        """send_message includes channel/chat_id in IPC params when given."""
        import mc.runtime.mcp.bridge as bridge_mod

        received: dict = {}

        async def capture(method, params):
            received.update(params)
            return {"status": "Message sent"}

        mock_ipc = MagicMock()
        mock_ipc.request = capture

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            await bridge_mod.call_tool(
                "send_message",
                {"content": "hi", "channel": "telegram", "chat_id": "123"},
            )

        assert received["channel"] == "telegram"

    async def test_send_message_prefers_convex_interaction_service(self):
        import mc.runtime.mcp.bridge as bridge_mod

        service = MagicMock()
        service.post_message = MagicMock(return_value=None)

        with (
            patch.object(bridge_mod, "_get_interaction_service", return_value=service),
            patch.object(bridge_mod, "_build_interaction_context", return_value=object()),
        ):
            result = await bridge_mod.call_tool("send_message", {"content": "hello"})

        assert result[0].text == "Message sent"
        service.post_message.assert_called_once()

    async def test_send_message_passes_media(self):
        """send_message includes media paths in IPC params when given."""
        import mc.runtime.mcp.bridge as bridge_mod

        received: dict = {}

        async def capture(method, params):
            received.update(params)
            return {"status": "Message sent"}

        mock_ipc = MagicMock()
        mock_ipc.request = capture

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            await bridge_mod.call_tool(
                "send_message",
                {
                    "content": "here are the results",
                    "media": ["/tmp/output.png", "/tmp/report.pdf"],
                },
            )

        assert received["media"] == ["/tmp/output.png", "/tmp/report.pdf"]


# ---------------------------------------------------------------------------
# Test delegate_task tool
# ---------------------------------------------------------------------------


class TestDelegateTaskTool:
    async def test_delegate_task_success(self):
        """delegate_task returns task_id and status on success."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"delegate_task": {"task_id": "abc123", "status": "created"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("delegate_task", {"description": "write a report"})

        assert "abc123" in result[0].text
        assert "created" in result[0].text

    async def test_delegate_task_error_propagated(self):
        """delegate_task surfaces IPC errors."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"delegate_task": {"error": "Self-delegation prevented"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "delegate_task",
                {"description": "do it", "agent": "myagent"},
            )

        assert "Error" in result[0].text
        assert "Self-delegation" in result[0].text

    async def test_self_delegation_prevention(self):
        """Verify self-delegation guard is enforced at IPC server side (integration path).

        The bridge itself does not enforce this; the server-side handler does.
        We test that the server returns the correct error which the bridge surfaces.
        """
        import mc.runtime.mcp.bridge as bridge_mod

        received: dict = {}

        async def capture(method, params):
            received.update({"method": method, "params": params})
            # Simulate server-side enforcement
            if params.get("agent") == params.get("agent_name"):
                return {"error": "Self-delegation prevented: agent cannot delegate to itself."}
            return {"task_id": "t1", "status": "created"}

        mock_ipc = MagicMock()
        mock_ipc.request = capture

        # Patch AGENT_NAME to match the agent param
        with patch.object(bridge_mod, "AGENT_NAME", "bob"):
            with patch.object(bridge_mod, "_ipc_client", mock_ipc):
                result = await bridge_mod.call_tool(
                    "delegate_task",
                    {"description": "loop", "agent": "bob"},
                )

        assert "Error" in result[0].text


# ---------------------------------------------------------------------------
# Test ask_agent tool
# ---------------------------------------------------------------------------


class TestAskAgentTool:
    async def test_ask_agent_returns_response(self):
        """ask_agent returns the IPC response string."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"ask_agent": {"response": "The answer is 42."}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "ask_agent", {"agent_name": "researcher", "question": "What is 6*7?"}
            )

        assert result[0].text == "The answer is 42."

    async def test_ask_agent_error_response(self):
        """ask_agent surfaces IPC errors in the result text."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"ask_agent": {"error": "Agent 'ghost' not found."}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "ask_agent", {"agent_name": "ghost", "question": "hello?"}
            )

        assert "Error" in result[0].text
        assert "ghost" in result[0].text

    async def test_ask_agent_passes_caller_and_task(self):
        """ask_agent passes AGENT_NAME and TASK_ID to IPC."""
        import mc.runtime.mcp.bridge as bridge_mod

        received: dict = {}

        async def capture(method, params):
            received.update(params)
            return {"response": "ok"}

        mock_ipc = MagicMock()
        mock_ipc.request = capture

        with patch.object(bridge_mod, "AGENT_NAME", "alice"):
            with patch.object(bridge_mod, "TASK_ID", "task-99"):
                with patch.object(bridge_mod, "_ipc_client", mock_ipc):
                    await bridge_mod.call_tool(
                        "ask_agent",
                        {"agent_name": "bob", "question": "how?"},
                    )

        assert received["caller_agent"] == "alice"
        assert received["task_id"] == "task-99"


# ---------------------------------------------------------------------------
# Test list_tools
# ---------------------------------------------------------------------------


class TestListTools:
    async def test_list_tools_returns_all_expected(self):
        """list_tools returns all expected tools."""
        import mc.runtime.mcp.bridge as bridge_mod

        tools = await bridge_mod.list_tools()
        names = {t.name for t in tools}

        assert names == {
            "ask_user",
            "send_message",
            "delegate_task",
            "ask_agent",
            "cron",
            "search_memory",
            "create_agent_spec",
            "publish_squad_graph",
            "publish_workflow",
            "create_review_spec",
            "list_skills",
            "register_skill",
            "update_agent",
            "delete_skill",
            "archive_squad",
            "archive_workflow",
        }

    async def test_tools_have_required_fields(self):
        """Each tool has name, description, and inputSchema."""
        import mc.runtime.mcp.bridge as bridge_mod

        tools = await bridge_mod.list_tools()
        for tool in tools:
            assert tool.name
            assert tool.description
            assert tool.inputSchema

    async def test_ask_user_schema_supports_structured_questions(self):
        """ask_user tool supports questionnaire-style structured prompts."""
        import mc.runtime.mcp.bridge as bridge_mod

        tools = await bridge_mod.list_tools()
        ask_user = next(tool for tool in tools if tool.name == "ask_user")

        questions_schema = ask_user.inputSchema["properties"]["questions"]
        assert questions_schema["type"] == "array"
        item_properties = questions_schema["items"]["properties"]
        assert set(item_properties) >= {"header", "id", "question", "options"}

    async def test_ask_user_schema_has_no_top_level_one_of(self):
        """ask_user must not expose top-level oneOf because Claude rejects it."""
        import mc.runtime.mcp.bridge as bridge_mod

        tools = await bridge_mod.list_tools()
        ask_user = next(tool for tool in tools if tool.name == "ask_user")

        assert "oneOf" not in ask_user.inputSchema

    async def test_unknown_tool_returns_error_text(self):
        """Calling an unregistered tool name returns an error text content."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("nonexistent_tool", {})

        assert result[0].text == "Unknown tool: nonexistent_tool"


# ---------------------------------------------------------------------------
# Test cron tool
# ---------------------------------------------------------------------------


class TestCronTool:
    async def test_cron_list_returns_jobs(self):
        """cron list action returns the job listing from IPC."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"cron": {"result": "No scheduled jobs."}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("cron", {"action": "list"})

        assert len(result) == 1
        assert "No scheduled jobs" in result[0].text

    async def test_cron_add_returns_confirmation(self):
        """cron add action returns creation confirmation."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"cron": {"result": "Created job 'daily report' (id: abc123)"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "cron",
                {
                    "action": "add",
                    "message": "daily report",
                    "cron_expr": "0 9 * * *",
                },
            )

        assert len(result) == 1
        assert "Created job" in result[0].text
        assert "abc123" in result[0].text

    async def test_cron_remove_returns_confirmation(self):
        """cron remove action returns removal confirmation."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"cron": {"result": "Removed job abc123"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("cron", {"action": "remove", "job_id": "abc123"})

        assert len(result) == 1
        assert "Removed job abc123" in result[0].text

    async def test_cron_ipc_failure(self):
        """cron handles IPC ConnectionError gracefully."""
        import mc.runtime.mcp.bridge as bridge_mod

        async def failing_request(method, params):
            raise ConnectionError("socket not found")

        mock_ipc = MagicMock()
        mock_ipc.request = failing_request

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("cron", {"action": "list"})

        assert len(result) == 1
        assert "Mission Control not reachable" in result[0].text

    async def test_cron_in_tool_list(self):
        """list_tools includes the cron tool."""
        import mc.runtime.mcp.bridge as bridge_mod

        tools = await bridge_mod.list_tools()
        names = {t.name for t in tools}

        assert "cron" in names


# ---------------------------------------------------------------------------
# Test publish_workflow tool
# ---------------------------------------------------------------------------


class TestPublishWorkflowTool:
    async def test_publish_workflow_success(self):
        """publish_workflow returns workflow_spec_id on success."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"publish_workflow": {"workflow_spec_id": "wf123"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "publish_workflow",
                {
                    "squadSpecId": "squad-1",
                    "workflow": {
                        "name": "default",
                        "steps": [{"title": "Draft", "type": "agent", "agentKey": "writer"}],
                    },
                },
            )

        assert "wf123" in result[0].text

    async def test_publish_workflow_error(self):
        """publish_workflow surfaces IPC errors."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"publish_workflow": {"error": "Squad not found"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "publish_workflow",
                {"squadSpecId": "bad", "workflow": {"name": "x", "steps": []}},
            )

        assert "Error" in result[0].text


# ---------------------------------------------------------------------------
# Test create_review_spec tool
# ---------------------------------------------------------------------------


class TestCreateReviewSpecTool:
    async def test_create_review_spec_success(self):
        """create_review_spec returns spec_id on success."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"create_review_spec": {"spec_id": "rs456"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "create_review_spec",
                {
                    "name": "quality-check",
                    "scope": "workflow",
                    "criteria": [{"id": "accuracy", "label": "Accuracy", "weight": 1.0}],
                    "approvalThreshold": 0.8,
                },
            )

        assert "rs456" in result[0].text


# ---------------------------------------------------------------------------
# Test list_skills tool
# ---------------------------------------------------------------------------


class TestListSkillsTool:
    async def test_list_skills_returns_json(self):
        """list_skills returns JSON array of skills."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc(
            {"list_skills": {"skills": [{"name": "writing", "available": True}]}}
        )

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("list_skills", {})

        assert "writing" in result[0].text


# ---------------------------------------------------------------------------
# Test register_skill tool
# ---------------------------------------------------------------------------


class TestRegisterSkillTool:
    async def test_register_skill_success(self):
        """register_skill returns confirmation."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"register_skill": {"name": "my-skill"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "register_skill",
                {
                    "name": "my-skill",
                    "description": "Does things",
                    "content": "# My Skill\nDo the thing.",
                },
            )

        assert "my-skill" in result[0].text


# ---------------------------------------------------------------------------
# Test update_agent tool
# ---------------------------------------------------------------------------


class TestUpdateAgentTool:
    async def test_update_agent_success(self):
        """update_agent returns confirmation."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"update_agent": {"name": "my-agent"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "update_agent",
                {"name": "my-agent", "skills": ["coding", "testing"], "model": "claude-opus-4-6"},
            )

        assert "my-agent" in result[0].text

    async def test_update_agent_error(self):
        """update_agent surfaces IPC errors."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"update_agent": {"error": "Agent not found"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("update_agent", {"name": "ghost"})

        assert "Error" in result[0].text


# ---------------------------------------------------------------------------
# Test delete_skill tool
# ---------------------------------------------------------------------------


class TestDeleteSkillTool:
    async def test_delete_skill_success(self):
        """delete_skill returns confirmation."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"delete_skill": {"name": "old-skill"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("delete_skill", {"name": "old-skill"})

        assert "old-skill" in result[0].text

    async def test_delete_skill_error(self):
        """delete_skill surfaces IPC errors."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"delete_skill": {"error": "Skill not found"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("delete_skill", {"name": "ghost"})

        assert "Error" in result[0].text


# ---------------------------------------------------------------------------
# Test archive_squad tool
# ---------------------------------------------------------------------------


class TestArchiveSquadTool:
    async def test_archive_squad_success(self):
        """archive_squad returns confirmation."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"archive_squad": {"squad_spec_id": "sq1"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("archive_squad", {"squadSpecId": "sq1"})

        assert "sq1" in result[0].text


# ---------------------------------------------------------------------------
# Test archive_workflow tool
# ---------------------------------------------------------------------------


class TestArchiveWorkflowTool:
    async def test_archive_workflow_success(self):
        """archive_workflow returns confirmation."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"archive_workflow": {"workflow_spec_id": "wf1"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("archive_workflow", {"workflowSpecId": "wf1"})

        assert "wf1" in result[0].text


# ---------------------------------------------------------------------------
# Test search_memory board-scoped workspace
# ---------------------------------------------------------------------------


class TestSearchMemoryBoardScope:
    async def test_search_memory_uses_board_workspace_when_set(self, tmp_path):
        """search_memory resolves board-scoped workspace when BOARD_NAME is set."""
        import mc.runtime.mcp.bridge as bridge_mod
        from mc.memory.store import HybridMemoryStore

        board_ws = tmp_path / "board-agent"
        store = HybridMemoryStore(board_ws)
        store.write_long_term("Board-specific fact about deployment")

        with patch.object(bridge_mod, "_resolve_memory_workspace", return_value=board_ws):
            result = await bridge_mod.call_tool("search_memory", {"query": "deployment"})

        assert len(result) == 1
        assert "deployment" in result[0].text

    async def test_search_memory_uses_global_workspace_without_board(self, tmp_path):
        """search_memory falls back to global agent workspace when no BOARD_NAME."""
        import mc.runtime.mcp.bridge as bridge_mod
        from mc.memory.store import HybridMemoryStore

        global_ws = tmp_path / "global-agent"
        store = HybridMemoryStore(global_ws)
        store.write_long_term("Global fact about infrastructure")

        with patch.object(bridge_mod, "_resolve_memory_workspace", return_value=global_ws):
            result = await bridge_mod.call_tool("search_memory", {"query": "infrastructure"})

        assert len(result) == 1
        assert "infrastructure" in result[0].text

    async def test_resolve_memory_workspace_with_board(self):
        """_resolve_memory_workspace constructs board-scoped path when BOARD_NAME set."""
        from pathlib import Path

        import mc.runtime.mcp.bridge as bridge_mod

        with (
            patch.object(bridge_mod, "_get_agent_name", return_value="owl"),
            patch.object(bridge_mod, "_get_board_name", return_value="default"),
        ):
            ws = bridge_mod._resolve_memory_workspace()

        expected = Path.home() / ".nanobot" / "boards" / "default" / "agents" / "owl"
        assert ws == expected

    async def test_resolve_memory_workspace_without_board(self):
        """_resolve_memory_workspace constructs global path when no BOARD_NAME."""
        from pathlib import Path

        import mc.runtime.mcp.bridge as bridge_mod

        with (
            patch.object(bridge_mod, "_get_agent_name", return_value="owl"),
            patch.object(bridge_mod, "_get_board_name", return_value=None),
        ):
            ws = bridge_mod._resolve_memory_workspace()

        expected = Path.home() / ".nanobot" / "agents" / "owl"
        assert ws == expected

    async def test_resolve_memory_workspace_prefers_explicit_env_path(self):
        """_resolve_memory_workspace uses the exact execution workspace when provided."""
        from pathlib import Path

        import mc.runtime.mcp.bridge as bridge_mod

        explicit_ws = Path("/tmp/custom-memory-workspace")
        with (
            patch.dict("os.environ", {"MEMORY_WORKSPACE": str(explicit_ws)}, clear=False),
            patch.object(bridge_mod, "_get_agent_name", return_value="owl"),
            patch.object(bridge_mod, "_get_board_name", return_value="default"),
        ):
            ws = bridge_mod._resolve_memory_workspace()

        assert ws == explicit_ws

    async def test_search_memory_finds_cc_consolidated_content(self, tmp_path):
        """search_memory must retrieve facts written by the CC consolidator."""
        from claude_code.memory_consolidator import CCMemoryConsolidator

        import mc.runtime.mcp.bridge as bridge_mod

        response = MagicMock()
        tool_call = MagicMock()
        tool_call.arguments = json.dumps(
            {
                "history_entry": "[2026-03-05 12:07] Stored rollback checklist for payments.",
                "memory_update": "Payments deploys require a rollback checklist before release.",
            }
        )
        response.tool_calls = [tool_call]
        provider = MagicMock()
        provider.chat = AsyncMock(return_value=response)

        with patch(
            "mc.memory.service.create_provider",
            return_value=(provider, "resolved-model"),
        ):
            ok = await CCMemoryConsolidator(tmp_path).consolidate(
                task_title="Payments release",
                task_output="Prepared rollback checklist and release notes",
                task_status="completed",
                task_id="task-9",
                model="claude-haiku",
            )

        assert ok is True

        with patch.object(bridge_mod, "_resolve_memory_workspace", return_value=tmp_path):
            result = await bridge_mod.call_tool("search_memory", {"query": "rollback checklist"})

        assert len(result) == 1
        assert "rollback checklist" in result[0].text.lower()
