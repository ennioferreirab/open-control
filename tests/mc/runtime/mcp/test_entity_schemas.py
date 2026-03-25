"""Tests for mc.runtime.mcp.entity_schemas — spec-driven tool generation."""

from __future__ import annotations

from mc.runtime.mcp.entity_schemas import (
    generate_all_tools,
    generate_tool,
    get_field_names,
    get_operation_meta,
    load_all_specs,
)


class TestSpecLoading:
    def test_load_all_specs_finds_all_entities(self):
        specs = load_all_specs()
        assert set(specs.keys()) >= {"agent", "skill", "squad", "workflow", "reviewSpec"}

    def test_each_spec_has_required_keys(self):
        for name, spec in load_all_specs().items():
            assert "entity" in spec, f"{name} missing entity"
            assert "operations" in spec, f"{name} missing operations"
            assert "fields" in spec, f"{name} missing fields"


class TestToolGeneration:
    def test_generate_agent_create_tool(self):
        tool = generate_tool("agent", "create")
        assert tool.name == "create_agent_spec"
        props = tool.inputSchema["properties"]
        assert "name" in props
        assert "displayName" in props
        assert "role" in props
        assert "prompt" in props
        assert "soul" in props
        assert "skills" in props
        assert tool.inputSchema.get("additionalProperties") is False

    def test_generate_agent_create_required_fields(self):
        tool = generate_tool("agent", "create")
        required = tool.inputSchema.get("required", [])
        assert "name" in required
        assert "displayName" not in required
        assert "role" in required
        assert "prompt" not in required

    def test_generate_agent_update_tool(self):
        tool = generate_tool("agent", "update")
        assert tool.name == "update_agent"
        props = tool.inputSchema["properties"]
        assert "name" in props
        assert "skills" in props
        assert "prompt" in props
        # V2-only fields should not appear in update
        assert "responsibilities" not in props

    def test_generate_skill_register_tool(self):
        tool = generate_tool("skill", "register")
        assert tool.name == "register_skill"
        props = tool.inputSchema["properties"]
        assert "name" in props
        assert "description" in props
        assert "content" in props
        assert "supportedProviders" in props

    def test_generate_skill_delete_tool(self):
        tool = generate_tool("skill", "delete")
        assert tool.name == "delete_skill"
        props = tool.inputSchema["properties"]
        assert "name" in props
        # delete should only have name
        assert "content" not in props

    def test_generate_skill_list_tool(self):
        tool = generate_tool("skill", "list")
        assert tool.name == "list_skills"
        props = tool.inputSchema["properties"]
        assert "available_only" in props

    def test_generate_review_spec_create_tool(self):
        tool = generate_tool("review_spec", "create")
        assert tool.name == "create_review_spec"
        props = tool.inputSchema["properties"]
        assert "name" in props
        assert "scope" in props
        assert "criteria" in props
        assert "approvalThreshold" in props
        # scope should have enum
        assert props["scope"].get("enum") == ["agent", "workflow", "execution"]

    def test_generate_squad_publish_tool(self):
        tool = generate_tool("squad", "publish")
        assert tool.name == "publish_squad_graph"
        props = tool.inputSchema["properties"]
        assert "squad" in props
        assert "agents" in props
        assert "workflows" in props

    def test_generate_squad_archive_tool(self):
        tool = generate_tool("squad", "archive")
        assert tool.name == "archive_squad"
        props = tool.inputSchema["properties"]
        assert "squadSpecId" in props

    def test_generate_workflow_publish_tool(self):
        tool = generate_tool("workflow", "publish")
        assert tool.name == "publish_workflow"
        props = tool.inputSchema["properties"]
        assert "squadSpecId" in props
        assert "workflow" in props

    def test_generate_all_tools_returns_complete_set(self):
        tools = generate_all_tools()
        names = {t.name for t in tools}
        assert names >= {
            "create_agent_spec",
            "update_agent",
            "register_skill",
            "delete_skill",
            "list_skills",
            "publish_squad_graph",
            "archive_squad",
            "publish_workflow",
            "archive_workflow",
            "create_review_spec",
        }

    def test_all_tools_have_additional_properties_false(self):
        for tool in generate_all_tools():
            assert tool.inputSchema.get("additionalProperties") is False, (
                f"{tool.name} missing additionalProperties: false"
            )


class TestFieldNames:
    def test_get_agent_create_fields(self):
        names = get_field_names("agent", "create")
        assert "name" in names
        assert "prompt" in names
        assert "responsibilities" in names

    def test_get_agent_update_fields(self):
        names = get_field_names("agent", "update")
        assert "name" in names
        assert "skills" in names
        # V2-only fields filtered out
        assert "responsibilities" not in names

    def test_get_skill_register_fields(self):
        names = get_field_names("skill", "register")
        assert "name" in names
        assert "content" in names

    def test_get_skill_delete_fields(self):
        names = get_field_names("skill", "delete")
        assert "name" in names
        assert "content" not in names


class TestOperationMeta:
    def test_agent_create_meta(self):
        meta = get_operation_meta("agent", "create")
        assert meta["mcpTool"] == "create_agent_spec"
        assert meta["ipcMethod"] == "create_agent_spec"
        assert meta["convexMutation"] == "agentSpecs:createDraft"

    def test_skill_register_meta(self):
        meta = get_operation_meta("skill", "register")
        assert meta["mcpTool"] == "register_skill"
        assert meta["convexMutation"] == "skills:upsertByName"
