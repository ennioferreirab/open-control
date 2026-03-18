"""Tests for the repo-owned MC MCP bridge and canonical Phase 1 tool surface."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# AC1 / AC3: Canonical tool names
# ---------------------------------------------------------------------------

EXPECTED_PHASE1_TOOLS = {
    "ask_user",
    "ask_agent",
    "delegate_task",
    "send_message",
    "cron",
    "report_progress",
    "record_final_result",
    "create_agent_spec",
    "publish_squad_graph",
}

# AC3: Transport-coupled names must never appear on the public surface.
FORBIDDEN_TOOL_NAMES = {
    "message",
    "send_message_mc",
    "ask_user_mc",
}


def _make_mock_ipc(responses: dict) -> MagicMock:
    """Create an IPC client mock whose request() returns canned responses."""
    mock = MagicMock()

    async def request(method, params):
        return responses.get(method, {"error": f"Unknown method: {method}"})

    mock.request = request
    return mock


class TestToolSpecs:
    """AC1 / AC3: tool_specs.py exposes exactly the Phase 1 canonical surface."""

    def test_phase1_tool_names_present(self):
        """All 7 Phase 1 tools are defined in PHASE1_TOOLS."""
        from mc.runtime.mcp.tool_specs import PHASE1_TOOLS

        names = {t.name for t in PHASE1_TOOLS}
        assert names == EXPECTED_PHASE1_TOOLS

    def test_send_message_is_present_not_message(self):
        """send_message is present; 'message' is not."""
        from mc.runtime.mcp.tool_specs import PHASE1_TOOLS

        names = {t.name for t in PHASE1_TOOLS}
        assert "send_message" in names
        assert "message" not in names

    def test_no_transport_coupled_names(self):
        """No forbidden transport-coupled names appear in the surface."""
        from mc.runtime.mcp.tool_specs import PHASE1_TOOLS

        names = {t.name for t in PHASE1_TOOLS}
        assert names.isdisjoint(FORBIDDEN_TOOL_NAMES)

    def test_each_tool_has_description(self):
        """Every tool spec has a non-empty description."""
        from mc.runtime.mcp.tool_specs import PHASE1_TOOLS

        for tool in PHASE1_TOOLS:
            assert tool.description, f"Tool '{tool.name}' has no description"

    def test_each_tool_has_input_schema(self):
        """Every tool spec has an inputSchema dict."""
        from mc.runtime.mcp.tool_specs import PHASE1_TOOLS

        for tool in PHASE1_TOOLS:
            assert isinstance(tool.inputSchema, dict), (
                f"Tool '{tool.name}' inputSchema must be a dict"
            )

    def test_phase1_tools_is_list(self):
        """PHASE1_TOOLS is a list of Tool objects."""
        from mcp.types import Tool

        from mc.runtime.mcp.tool_specs import PHASE1_TOOLS

        assert isinstance(PHASE1_TOOLS, list)
        for item in PHASE1_TOOLS:
            assert isinstance(item, Tool)


# ---------------------------------------------------------------------------
# AC2 / AC5: Bridge lists expected tools and forwards calls
# ---------------------------------------------------------------------------


class TestMCMcpBridgeListTools:
    """AC2: The repo-owned MC MCP bridge lists exactly the Phase 1 tools."""

    pytestmark = pytest.mark.asyncio

    async def test_list_tools_returns_phase1_set(self):
        """list_tools() returns all 7 Phase 1 tools."""
        import mc.runtime.mcp.bridge as bridge_mod

        tools = await bridge_mod.list_tools()
        names = {t.name for t in tools}
        assert names == EXPECTED_PHASE1_TOOLS

    async def test_list_tools_excludes_forbidden_names(self):
        """list_tools() does not return any transport-coupled names."""
        import mc.runtime.mcp.bridge as bridge_mod

        tools = await bridge_mod.list_tools()
        names = {t.name for t in tools}
        assert names.isdisjoint(FORBIDDEN_TOOL_NAMES)

    async def test_list_tools_uses_canonical_specs(self):
        """Tools returned by list_tools() match the canonical PHASE1_TOOLS specs."""
        import mc.runtime.mcp.bridge as bridge_mod
        from mc.runtime.mcp.tool_specs import PHASE1_TOOLS

        tools = await bridge_mod.list_tools()
        bridge_names = {t.name for t in tools}
        canonical_names = {t.name for t in PHASE1_TOOLS}
        assert bridge_names == canonical_names

    async def test_ask_user_schema_has_no_top_level_one_of(self):
        """ask_user must not expose top-level oneOf in the public MCP surface."""
        import mc.runtime.mcp.bridge as bridge_mod

        tools = await bridge_mod.list_tools()
        ask_user = next(tool for tool in tools if tool.name == "ask_user")

        assert "oneOf" not in ask_user.inputSchema


class TestMCMcpBridgeCallTool:
    """AC5: Bridge forwards tool calls correctly through the existing IPC path."""

    pytestmark = pytest.mark.asyncio

    async def test_send_message_forwarded(self):
        """send_message is forwarded to IPC with content."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"send_message": {"status": "Message sent"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("send_message", {"content": "Hello!"})

        assert len(result) == 1
        assert "sent" in result[0].text.lower() or result[0].text

    async def test_ask_user_forwarded(self):
        """ask_user is forwarded to IPC and returns the answer."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"ask_user": {"answer": "Yes!"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("ask_user", {"question": "Ready?"})

        assert len(result) == 1
        assert result[0].text == "Yes!"

    async def test_ask_user_prefers_convex_interaction_service(self):
        import mc.runtime.mcp.bridge as bridge_mod

        service = MagicMock()
        service.ask_user = MagicMock(return_value="Yes!")

        with (
            patch.object(bridge_mod, "_get_interaction_service", return_value=service),
            patch.object(bridge_mod, "_build_interaction_context", return_value=object()),
        ):
            result = await bridge_mod.call_tool("ask_user", {"question": "Ready?"})

        assert result[0].text == "Yes!"
        service.ask_user.assert_called_once()

    async def test_delegate_task_forwarded(self):
        """delegate_task is forwarded to IPC."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"delegate_task": {"task_id": "t1", "status": "created"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("delegate_task", {"description": "Do X"})

        assert len(result) == 1
        assert "t1" in result[0].text or "created" in result[0].text

    async def test_ask_agent_forwarded(self):
        """ask_agent is forwarded to IPC."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"ask_agent": {"response": "I am fine."}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "ask_agent", {"agent_name": "helper", "question": "How are you?"}
            )

        assert len(result) == 1
        assert result[0].text == "I am fine."

    async def test_report_progress_forwarded(self):
        """report_progress is forwarded to IPC."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"report_progress": {"status": "Progress reported"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "report_progress", {"message": "50% done", "percentage": 50}
            )

        assert len(result) == 1
        assert result[0].text

    async def test_report_progress_prefers_convex_interaction_service(self):
        import mc.runtime.mcp.bridge as bridge_mod

        service = MagicMock()
        service.report_progress = MagicMock(return_value=None)

        with (
            patch.object(bridge_mod, "_get_interaction_service", return_value=service),
            patch.object(bridge_mod, "_build_interaction_context", return_value=object()),
        ):
            result = await bridge_mod.call_tool(
                "report_progress", {"message": "50% done", "percentage": 50}
            )

        assert result[0].text == "Progress reported"
        service.report_progress.assert_called_once()

    async def test_cron_forwarded(self):
        """cron is forwarded to IPC."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"cron": {"result": "No scheduled jobs."}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("cron", {"action": "list"})

        assert len(result) == 1
        assert result[0].text

    async def test_record_final_result_forwarded(self):
        """record_final_result is forwarded to IPC."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"record_final_result": {"status": "Final result recorded"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("record_final_result", {"content": "All done!"})

        assert len(result) == 1
        assert result[0].text

    async def test_unknown_tool_returns_error(self):
        """Unknown tool names return an error message."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("nonexistent_tool", {})

        assert len(result) == 1
        assert "unknown" in result[0].text.lower() or "nonexistent" in result[0].text.lower()

    async def test_connection_error_handled(self):
        """ConnectionError from IPC is caught and returns a user-friendly message."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = MagicMock()

        async def failing_request(method, params):
            raise ConnectionError("Cannot connect")

        mock_ipc.request = failing_request

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("send_message", {"content": "Hi"})

        assert len(result) == 1
        assert "not reachable" in result[0].text.lower() or "gateway" in result[0].text.lower()


# ---------------------------------------------------------------------------
# AC4: Canonical tool surface lives under mc/
# ---------------------------------------------------------------------------


class TestAC4LowVendorImpact:
    """AC4: The canonical surface lives under mc/, vendor edits are minimal."""

    def test_tool_specs_importable_from_mc(self):
        """mc.runtime.mcp.tool_specs is importable."""
        from mc.runtime.mcp import tool_specs

        assert hasattr(tool_specs, "PHASE1_TOOLS")

    def test_bridge_importable_from_mc(self):
        """mc.runtime.mcp.bridge is importable."""
        from mc.runtime.mcp import bridge

        assert hasattr(bridge, "list_tools")
        assert hasattr(bridge, "call_tool")


class TestSpecToolsRegistration:
    """Verify create_agent_spec and publish_squad_graph are in PHASE1_TOOLS."""

    def test_create_agent_spec_tool_present(self):
        """create_agent_spec tool is registered in PHASE1_TOOLS."""
        from mc.runtime.mcp.tool_specs import PHASE1_TOOLS

        names = {t.name for t in PHASE1_TOOLS}
        assert "create_agent_spec" in names

    def test_publish_squad_graph_tool_present(self):
        """publish_squad_graph tool is registered in PHASE1_TOOLS."""
        from mc.runtime.mcp.tool_specs import PHASE1_TOOLS

        names = {t.name for t in PHASE1_TOOLS}
        assert "publish_squad_graph" in names

    def test_create_agent_spec_has_required_fields_in_schema(self):
        """create_agent_spec schema requires name, displayName, role."""
        from mc.runtime.mcp.tool_specs import PHASE1_TOOLS

        tool = next(t for t in PHASE1_TOOLS if t.name == "create_agent_spec")
        required = tool.inputSchema.get("required", [])
        assert "name" in required
        assert "displayName" in required
        assert "role" in required

    def test_publish_squad_graph_has_required_fields_in_schema(self):
        """publish_squad_graph schema requires squad, agents, workflows."""
        from mc.runtime.mcp.tool_specs import PHASE1_TOOLS

        tool = next(t for t in PHASE1_TOOLS if t.name == "publish_squad_graph")
        required = tool.inputSchema.get("required", [])
        assert "squad" in required
        assert "agents" in required
        assert "workflows" in required


class TestSpecToolsDispatch:
    """Verify create_agent_spec and publish_squad_graph are dispatched via IPC."""

    pytestmark = pytest.mark.asyncio

    async def test_create_agent_spec_forwarded_via_ipc(self):
        """create_agent_spec dispatches to IPC with correct payload."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"create_agent_spec": {"spec_id": "spec-abc-123"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "create_agent_spec",
                {
                    "name": "my-agent",
                    "displayName": "My Agent",
                    "role": "Developer",
                    "responsibilities": ["Write code"],
                    "principles": ["DRY"],
                },
            )

        assert len(result) == 1
        assert "spec-abc-123" in result[0].text

    async def test_create_agent_spec_connection_error_handled(self):
        """ConnectionError during create_agent_spec returns a friendly message."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = MagicMock()

        async def failing_request(method, params):
            raise ConnectionError("Cannot connect")

        mock_ipc.request = failing_request

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "create_agent_spec",
                {"name": "x", "displayName": "X", "role": "Dev"},
            )

        assert len(result) == 1
        assert (
            "not reachable" in result[0].text.lower() or "mission control" in result[0].text.lower()
        )

    async def test_publish_squad_graph_forwarded_via_ipc(self):
        """publish_squad_graph dispatches to IPC with correct payload."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"publish_squad_graph": {"squad_id": "squad-xyz-456"}})

        graph_args = {
            "squad": {"name": "my-squad", "displayName": "My Squad"},
            "agents": [{"key": "a1", "name": "agent1", "role": "Dev"}],
            "workflows": [
                {
                    "key": "w1",
                    "name": "Workflow 1",
                    "steps": [{"key": "s1", "type": "task", "agentKey": "a1"}],
                }
            ],
        }

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool("publish_squad_graph", graph_args)

        assert len(result) == 1
        assert "squad-xyz-456" in result[0].text

    async def test_publish_squad_graph_connection_error_handled(self):
        """ConnectionError during publish_squad_graph returns a friendly message."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = MagicMock()

        async def failing_request(method, params):
            raise ConnectionError("Cannot connect")

        mock_ipc.request = failing_request

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "publish_squad_graph",
                {
                    "squad": {"name": "x", "displayName": "X"},
                    "agents": [],
                    "workflows": [],
                },
            )

        assert len(result) == 1
        assert (
            "not reachable" in result[0].text.lower() or "mission control" in result[0].text.lower()
        )

    async def test_create_agent_spec_ipc_error_returned(self):
        """IPC error response for create_agent_spec is returned to caller."""
        import mc.runtime.mcp.bridge as bridge_mod

        mock_ipc = _make_mock_ipc({"create_agent_spec": {"error": "Spec already exists"}})

        with patch.object(bridge_mod, "_ipc_client", mock_ipc):
            result = await bridge_mod.call_tool(
                "create_agent_spec",
                {"name": "existing", "displayName": "Existing", "role": "Dev"},
            )

        assert len(result) == 1
        assert "error" in result[0].text.lower() or "already exists" in result[0].text.lower()
