"""Tests for AgentRepository.list_active_registry_view (Story 31.2)."""

from unittest.mock import MagicMock

from mc.bridge.repositories.agents import AgentRepository
from mc.types import AgentData


def _make_client() -> MagicMock:
    client = MagicMock()
    client.query.return_value = None
    client.mutation.return_value = None
    return client


class TestSyncAgentModel:
    def test_omits_model_when_none(self):
        client = _make_client()
        repo = AgentRepository(client)
        agent = AgentData(name="codex-live", display_name="Codex Live", role="test")

        repo.sync_agent(agent)

        _, args = client.mutation.call_args[0]
        assert "model" not in args

    def test_includes_model_when_set(self):
        client = _make_client()
        repo = AgentRepository(client)
        agent = AgentData(
            name="strategist", display_name="Strategist", role="test", model="cc/claude-sonnet-4-6"
        )

        repo.sync_agent(agent)

        _, args = client.mutation.call_args[0]
        assert args["model"] == "cc/claude-sonnet-4-6"


class TestListActiveRegistryView:
    def test_returns_registry_entries(self):
        client = _make_client()
        entry = {
            "agentId": "agent-id-1",
            "name": "dev-agent",
            "displayName": "Dev Agent",
            "role": "Developer",
            "skills": ["git"],
            "squads": [],
            "enabled": True,
            "status": "active",
            "tasksExecuted": 3,
            "stepsExecuted": 7,
            "lastTaskExecutedAt": "2026-03-10T10:00:00.000Z",
            "lastStepExecutedAt": "2026-03-10T11:00:00.000Z",
            "lastActiveAt": "2026-03-10T11:30:00.000Z",
        }
        client.query.return_value = [entry]
        repo = AgentRepository(client)

        result = repo.list_active_registry_view()

        client.query.assert_called_once_with("agents:listActiveRegistryView")
        assert result == [entry]

    def test_returns_empty_list_when_none(self):
        client = _make_client()
        client.query.return_value = None
        repo = AgentRepository(client)

        result = repo.list_active_registry_view()
        assert result == []
