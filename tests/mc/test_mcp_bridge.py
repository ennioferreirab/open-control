"""Unit tests for the MCP bridge tool handlers with mocked IPC."""

from __future__ import annotations

import asyncio
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
        import mc.mcp_bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"ask_user": {"answer": "Yes!"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("ask_user", {"question": "Ready?"})

        assert len(result) == 1
        assert result[0].text == "Yes!"

    async def test_ask_user_with_options(self):
        """ask_user passes options to IPC."""
        import mc.mcp_bridge as bridge_mod

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

    async def test_ask_user_ipc_failure(self):
        """ask_user handles IPC ConnectionError gracefully and returns friendly message.

        M4: Verify the friendly error message is returned (not a raised exception).
        """
        import mc.mcp_bridge as bridge_mod

        async def failing_request(method, params):
            raise ConnectionError("socket not found")

        mock_ipc = MagicMock()
        mock_ipc.request = failing_request

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("ask_user", {"question": "hello?"})

        assert len(result) == 1
        assert "Mission Control not reachable" in result[0].text


# ---------------------------------------------------------------------------
# Test send_message tool
# ---------------------------------------------------------------------------

class TestSendMessageTool:
    async def test_send_message_returns_status(self):
        """send_message returns the IPC status string."""
        import mc.mcp_bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"send_message": {"status": "Message sent"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "send_message", {"content": "hello world"}
            )

        assert result[0].text == "Message sent"

    async def test_send_message_passes_optional_channel(self):
        """send_message includes channel/chat_id in IPC params when given."""
        import mc.mcp_bridge as bridge_mod

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
        assert received["chat_id"] == "123"


# ---------------------------------------------------------------------------
# Test delegate_task tool
# ---------------------------------------------------------------------------

class TestDelegateTaskTool:
    async def test_delegate_task_success(self):
        """delegate_task returns task_id and status on success."""
        import mc.mcp_bridge as bridge_mod

        mock_ipc = _make_mock_ipc(
            {"delegate_task": {"task_id": "abc123", "status": "created"}}
        )

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "delegate_task", {"description": "write a report"}
            )

        assert "abc123" in result[0].text
        assert "created" in result[0].text

    async def test_delegate_task_error_propagated(self):
        """delegate_task surfaces IPC errors."""
        import mc.mcp_bridge as bridge_mod

        mock_ipc = _make_mock_ipc(
            {"delegate_task": {"error": "Self-delegation prevented"}}
        )

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
        import mc.mcp_bridge as bridge_mod

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
        import mc.mcp_bridge as bridge_mod

        mock_ipc = _make_mock_ipc(
            {"ask_agent": {"response": "The answer is 42."}}
        )

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "ask_agent", {"agent_name": "researcher", "question": "What is 6*7?"}
            )

        assert result[0].text == "The answer is 42."

    async def test_ask_agent_error_response(self):
        """ask_agent surfaces IPC errors in the result text."""
        import mc.mcp_bridge as bridge_mod

        mock_ipc = _make_mock_ipc(
            {"ask_agent": {"error": "Agent 'ghost' not found."}}
        )

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "ask_agent", {"agent_name": "ghost", "question": "hello?"}
            )

        assert "Error" in result[0].text
        assert "ghost" in result[0].text

    async def test_ask_agent_passes_caller_and_task(self):
        """ask_agent passes AGENT_NAME and TASK_ID to IPC."""
        import mc.mcp_bridge as bridge_mod

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
# Test report_progress tool
# ---------------------------------------------------------------------------

class TestReportProgressTool:
    async def test_report_progress_returns_status(self):
        """report_progress returns 'Progress reported'."""
        import mc.mcp_bridge as bridge_mod

        mock_ipc = _make_mock_ipc(
            {"report_progress": {"status": "Progress reported"}}
        )

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "report_progress", {"message": "halfway done", "percentage": 50}
            )

        assert result[0].text == "Progress reported"

    async def test_report_progress_passes_percentage(self):
        """report_progress includes percentage in IPC params."""
        import mc.mcp_bridge as bridge_mod

        received: dict = {}

        async def capture(method, params):
            received.update(params)
            return {"status": "Progress reported"}

        mock_ipc = MagicMock()
        mock_ipc.request = capture

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            await bridge_mod.call_tool(
                "report_progress", {"message": "done", "percentage": 100}
            )

        assert received["percentage"] == 100
        assert received["message"] == "done"

    async def test_report_progress_without_percentage(self):
        """report_progress works without the optional percentage."""
        import mc.mcp_bridge as bridge_mod

        mock_ipc = _make_mock_ipc(
            {"report_progress": {"status": "Progress reported"}}
        )

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "report_progress", {"message": "starting"}
            )

        assert result[0].text == "Progress reported"


# ---------------------------------------------------------------------------
# Test list_tools
# ---------------------------------------------------------------------------

class TestListTools:
    async def test_list_tools_returns_all_five(self):
        """list_tools returns all 5 expected tools."""
        import mc.mcp_bridge as bridge_mod

        tools = await bridge_mod.list_tools()
        names = {t.name for t in tools}

        assert names == {
            "ask_user",
            "send_message",
            "delegate_task",
            "ask_agent",
            "report_progress",
        }

    async def test_tools_have_required_fields(self):
        """Each tool has name, description, and inputSchema."""
        import mc.mcp_bridge as bridge_mod

        tools = await bridge_mod.list_tools()
        for tool in tools:
            assert tool.name
            assert tool.description
            assert tool.inputSchema

    async def test_unknown_tool_returns_error_text(self):
        """Calling an unregistered tool name returns an error text content."""
        import mc.mcp_bridge as bridge_mod

        mock_ipc = _make_mock_ipc({})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("nonexistent_tool", {})

        assert result[0].text == "Unknown tool: nonexistent_tool"
