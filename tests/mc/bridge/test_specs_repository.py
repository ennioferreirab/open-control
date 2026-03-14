"""Tests for mc.bridge.repositories.specs — Agent Spec V2 bridge repository."""

from __future__ import annotations

from unittest.mock import MagicMock


def _make_client_mock() -> MagicMock:
    """Create a mock BridgeClient with query and mutation methods."""
    client = MagicMock()
    client.query.return_value = None
    client.mutation.return_value = None
    return client


class TestSpecsRepositoryExists:
    """Verify the SpecsRepository class can be imported and instantiated."""

    def test_can_import_specs_repository(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository  # noqa: F401

    def test_can_instantiate(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)
        assert repo is not None


class TestSpecsRepositoryCreateSpec:
    """Tests for creating agent specs via the bridge."""

    def test_create_agent_spec_calls_mutation(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        client.mutation.return_value = "spec-id-123"
        repo = SpecsRepository(client)

        result = repo.create_agent_spec(
            name="my-agent",
            role="Developer",
            prompt="You are a developer.",
        )

        assert result == "spec-id-123"
        client.mutation.assert_called_once()
        call_args = client.mutation.call_args
        assert call_args[0][0] == "agentSpecs:createDraft"

    def test_create_agent_spec_includes_required_fields(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.create_agent_spec(
            name="test-agent",
            role="Tester",
            prompt="You test things.",
        )

        call_args = client.mutation.call_args[0][1]
        assert call_args["name"] == "test-agent"
        assert call_args["role"] == "Tester"
        assert call_args["prompt"] == "You test things."

    def test_create_agent_spec_accepts_optional_fields(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.create_agent_spec(
            name="rich-agent",
            role="Architect",
            prompt="You design systems.",
            display_name="Rich Agent",
            model="anthropic/claude-sonnet-4-5",
            skills=["coding", "research"],
            soul="This agent values clean design.",
        )

        call_args = client.mutation.call_args[0][1]
        assert call_args.get("display_name") == "Rich Agent"
        assert call_args.get("model") == "anthropic/claude-sonnet-4-5"
        assert call_args.get("skills") == ["coding", "research"]
        assert call_args.get("soul") == "This agent values clean design."


class TestSpecsRepositoryGetSpec:
    """Tests for querying agent specs."""

    def test_get_agent_spec_by_name_returns_none_when_missing(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        client.query.return_value = None
        repo = SpecsRepository(client)

        result = repo.get_agent_spec_by_name("nonexistent")
        assert result is None

    def test_get_agent_spec_by_name_returns_doc_when_found(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        client.query.return_value = {
            "_id": "spec-id-456",
            "name": "my-agent",
            "role": "Developer",
            "compiled_from_spec_id": None,
        }
        repo = SpecsRepository(client)

        result = repo.get_agent_spec_by_name("my-agent")
        assert result is not None
        assert result["name"] == "my-agent"


class TestSpecsRepositoryPublish:
    """Tests for publishing a spec into a runtime projection."""

    def test_publish_agent_spec_calls_mutation(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.publish_agent_spec("spec-id-789")

        client.mutation.assert_called_once()
        call_args = client.mutation.call_args[0]
        assert "agentSpecs:publish" in call_args[0]

    def test_publish_agent_spec_passes_spec_id(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.publish_agent_spec("spec-id-999")

        call_args = client.mutation.call_args[0][1]
        assert call_args.get("spec_id") == "spec-id-999"


class TestSpecsRepositoryBoardBinding:
    """Tests for board binding creation."""

    def test_create_board_binding_calls_mutation(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.create_board_agent_binding(
            board_id="board-abc",
            agent_name="my-agent",
        )

        client.mutation.assert_called_once()
        call_args = client.mutation.call_args[0]
        assert "agentSpecs:bindToBoard" in call_args[0]

    def test_create_board_binding_passes_fields(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.create_board_agent_binding(
            board_id="board-xyz",
            agent_name="dev-agent",
        )

        call_args = client.mutation.call_args[0][1]
        assert call_args.get("board_id") == "board-xyz"
        assert call_args.get("agent_name") == "dev-agent"


class TestFacadeExposesMethods:
    """Bridge facade exposes spec repository methods."""

    def test_bridge_has_create_agent_spec_method(self) -> None:
        from mc.bridge import ConvexBridge

        bridge = object.__new__(ConvexBridge)
        bridge._client = MagicMock()
        bridge._init_repositories()

        assert hasattr(bridge, "create_agent_spec")
        assert callable(bridge.create_agent_spec)

    def test_bridge_has_get_agent_spec_by_name_method(self) -> None:
        from mc.bridge import ConvexBridge

        bridge = object.__new__(ConvexBridge)
        bridge._client = MagicMock()
        bridge._init_repositories()

        assert hasattr(bridge, "get_agent_spec_by_name")
        assert callable(bridge.get_agent_spec_by_name)

    def test_bridge_has_publish_agent_spec_method(self) -> None:
        from mc.bridge import ConvexBridge

        bridge = object.__new__(ConvexBridge)
        bridge._client = MagicMock()
        bridge._init_repositories()

        assert hasattr(bridge, "publish_agent_spec")
        assert callable(bridge.publish_agent_spec)

    def test_bridge_has_create_board_agent_binding_method(self) -> None:
        from mc.bridge import ConvexBridge

        bridge = object.__new__(ConvexBridge)
        bridge._client = MagicMock()
        bridge._init_repositories()

        assert hasattr(bridge, "create_board_agent_binding")
        assert callable(bridge.create_board_agent_binding)

    def test_bridge_has_publish_squad_graph_method(self) -> None:
        from mc.bridge import ConvexBridge

        bridge = object.__new__(ConvexBridge)
        bridge._client = MagicMock()
        bridge._init_repositories()

        assert hasattr(bridge, "publish_squad_graph")
        assert callable(bridge.publish_squad_graph)


class TestSpecsRepositoryV2Fields:
    """Tests for V2 fields on create_agent_spec and createDraft mutation name."""

    def test_create_agent_spec_calls_create_draft_mutation(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        client.mutation.return_value = "spec-id-v2"
        repo = SpecsRepository(client)

        result = repo.create_agent_spec(
            name="v2-agent",
            role="Architect",
            display_name="V2 Agent",
        )

        assert result == "spec-id-v2"
        client.mutation.assert_called_once()
        call_args = client.mutation.call_args
        assert call_args[0][0] == "agentSpecs:createDraft"

    def test_create_agent_spec_passes_v2_responsibilities(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.create_agent_spec(
            name="v2-agent",
            role="Dev",
            display_name="V2 Agent",
            responsibilities=["Write code", "Review PRs"],
        )

        call_args = client.mutation.call_args[0][1]
        assert call_args.get("responsibilities") == ["Write code", "Review PRs"]

    def test_create_agent_spec_passes_v2_non_goals(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.create_agent_spec(
            name="v2-agent",
            role="Dev",
            display_name="V2 Agent",
            non_goals=["Deploy", "Monitor"],
        )

        call_args = client.mutation.call_args[0][1]
        assert call_args.get("non_goals") == ["Deploy", "Monitor"]

    def test_create_agent_spec_passes_v2_principles(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.create_agent_spec(
            name="v2-agent",
            role="Dev",
            display_name="V2 Agent",
            principles=["DRY", "SOLID"],
        )

        call_args = client.mutation.call_args[0][1]
        assert call_args.get("principles") == ["DRY", "SOLID"]

    def test_create_agent_spec_passes_v2_working_style(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.create_agent_spec(
            name="v2-agent",
            role="Dev",
            display_name="V2 Agent",
            working_style="Iterative and collaborative",
        )

        call_args = client.mutation.call_args[0][1]
        assert call_args.get("working_style") == "Iterative and collaborative"

    def test_create_agent_spec_passes_v2_quality_rules(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.create_agent_spec(
            name="v2-agent",
            role="Dev",
            display_name="V2 Agent",
            quality_rules=["Test coverage >80%"],
        )

        call_args = client.mutation.call_args[0][1]
        assert call_args.get("quality_rules") == ["Test coverage >80%"]

    def test_create_agent_spec_passes_v2_anti_patterns(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.create_agent_spec(
            name="v2-agent",
            role="Dev",
            display_name="V2 Agent",
            anti_patterns=["God objects", "Spaghetti code"],
        )

        call_args = client.mutation.call_args[0][1]
        assert call_args.get("anti_patterns") == ["God objects", "Spaghetti code"]

    def test_create_agent_spec_passes_v2_output_contract(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.create_agent_spec(
            name="v2-agent",
            role="Dev",
            display_name="V2 Agent",
            output_contract="Returns JSON with status field",
        )

        call_args = client.mutation.call_args[0][1]
        assert call_args.get("output_contract") == "Returns JSON with status field"

    def test_create_agent_spec_passes_v2_tool_policy(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.create_agent_spec(
            name="v2-agent",
            role="Dev",
            display_name="V2 Agent",
            tool_policy="Use minimal tools",
        )

        call_args = client.mutation.call_args[0][1]
        assert call_args.get("tool_policy") == "Use minimal tools"

    def test_create_agent_spec_passes_v2_memory_policy(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.create_agent_spec(
            name="v2-agent",
            role="Dev",
            display_name="V2 Agent",
            memory_policy="Persist context across sessions",
        )

        call_args = client.mutation.call_args[0][1]
        assert call_args.get("memory_policy") == "Persist context across sessions"

    def test_create_agent_spec_passes_v2_execution_policy(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.create_agent_spec(
            name="v2-agent",
            role="Dev",
            display_name="V2 Agent",
            execution_policy="Run sequentially",
        )

        call_args = client.mutation.call_args[0][1]
        assert call_args.get("execution_policy") == "Run sequentially"

    def test_create_agent_spec_passes_v2_review_policy_ref(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.create_agent_spec(
            name="v2-agent",
            role="Dev",
            display_name="V2 Agent",
            review_policy_ref="default-review-policy",
        )

        call_args = client.mutation.call_args[0][1]
        assert call_args.get("review_policy_ref") == "default-review-policy"

    def test_create_agent_spec_omits_none_optional_fields(self) -> None:
        """Fields not provided should not appear in the mutation args."""
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.create_agent_spec(
            name="minimal-agent",
            role="Dev",
            display_name="Minimal",
        )

        call_args = client.mutation.call_args[0][1]
        assert "responsibilities" not in call_args
        assert "non_goals" not in call_args
        assert "principles" not in call_args
        assert "working_style" not in call_args
        assert "quality_rules" not in call_args
        assert "anti_patterns" not in call_args
        assert "output_contract" not in call_args
        assert "tool_policy" not in call_args
        assert "memory_policy" not in call_args
        assert "execution_policy" not in call_args
        assert "review_policy_ref" not in call_args

    def test_create_agent_spec_has_name_role_display_name_required(self) -> None:
        """name, role, and display_name are present in the mutation args."""
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        repo.create_agent_spec(
            name="v2-agent",
            role="Dev",
            display_name="V2 Agent",
        )

        call_args = client.mutation.call_args[0][1]
        assert call_args["name"] == "v2-agent"
        assert call_args["role"] == "Dev"
        assert call_args["display_name"] == "V2 Agent"


class TestSpecsRepositoryPublishSquadGraph:
    """Tests for publish_squad_graph method."""

    def test_publish_squad_graph_calls_mutation(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        client.mutation.return_value = "squad-id-abc"
        repo = SpecsRepository(client)

        graph = {
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

        result = repo.publish_squad_graph(graph)

        assert result == "squad-id-abc"
        client.mutation.assert_called_once()
        call_args = client.mutation.call_args
        assert call_args[0][0] == "squadSpecs:publishGraph"

    def test_publish_squad_graph_passes_graph_argument(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        client.mutation.return_value = "squad-id-xyz"
        repo = SpecsRepository(client)

        graph = {
            "squad": {"name": "test-squad", "displayName": "Test Squad"},
            "agents": [],
            "workflows": [],
        }

        repo.publish_squad_graph(graph)

        call_args = client.mutation.call_args[0][1]
        assert call_args.get("graph") == graph

    def test_publish_squad_graph_accepts_review_policy(self) -> None:
        from mc.bridge.repositories.specs import SpecsRepository

        client = _make_client_mock()
        repo = SpecsRepository(client)

        graph = {
            "squad": {"name": "my-squad", "displayName": "My Squad"},
            "agents": [],
            "workflows": [],
            "reviewPolicy": "strict",
        }

        repo.publish_squad_graph(graph)

        call_args = client.mutation.call_args[0][1]
        assert call_args.get("graph") == graph
