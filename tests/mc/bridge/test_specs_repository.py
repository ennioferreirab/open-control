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
        assert "agentSpecs:create" in call_args[0][0]

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
