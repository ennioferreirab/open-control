"""Tests for AgentSyncService — Story 17.2, Task 2."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mc.contexts.agents.sync import AgentSyncService


@pytest.fixture
def bridge() -> MagicMock:
    """Create a mock ConvexBridge."""
    b = MagicMock()
    b.query = MagicMock(return_value=None)
    b.mutation = MagicMock(return_value=None)
    b.sync_agent = MagicMock()
    b.deactivate_agents_except = MagicMock()
    b.list_deleted_agents = MagicMock(return_value=[])
    b.list_agents = MagicMock(return_value=[])
    b.archive_agent_data = MagicMock()
    b.write_agent_config = MagicMock()
    b.get_agent_archive = MagicMock(return_value=None)
    b.clear_agent_archive = MagicMock()
    b.get_agent_by_name = MagicMock(return_value=None)
    return b


@pytest.fixture
def agents_dir(tmp_path: Path) -> Path:
    """Create a temporary agents directory."""
    d = tmp_path / "agents"
    d.mkdir()
    return d


@pytest.fixture
def service(bridge: MagicMock, agents_dir: Path) -> AgentSyncService:
    """Create an AgentSyncService instance."""
    return AgentSyncService(bridge=bridge, agents_dir=agents_dir)


def _write_agent_yaml(agents_dir: Path, name: str, role: str = "Test Agent") -> Path:
    """Helper: write a minimal valid agent config.yaml."""
    agent_dir = agents_dir / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    config = agent_dir / "config.yaml"
    config.write_text(
        f"name: {name}\nrole: {role}\nprompt: Test prompt\nskills: []\n",
        encoding="utf-8",
    )
    return config


class TestAgentSyncServiceInit:
    """Verify constructor and basic attributes."""

    def test_stores_bridge_and_agents_dir(self, bridge: MagicMock, agents_dir: Path) -> None:
        svc = AgentSyncService(bridge=bridge, agents_dir=agents_dir)
        assert svc._bridge is bridge
        assert svc._agents_dir == agents_dir


class TestSyncAgentRegistry:
    """Test the sync_agent_registry method — happy path and edge cases."""

    @patch("mc.contexts.agents.sync._write_back_convex_agents")
    @patch("mc.contexts.agents.sync.validate_agent_file")
    @patch("mc.contexts.agents.sync.ensure_low_agent")
    @patch("mc.contexts.agents.sync.ensure_nanobot_agent")
    def test_syncs_valid_agents(
        self,
        mock_ensure_nanobot: MagicMock,
        mock_ensure_low: MagicMock,
        mock_validate: MagicMock,
        mock_write_back: MagicMock,
        service: AgentSyncService,
        agents_dir: Path,
        bridge: MagicMock,
    ) -> None:
        """Valid agent YAML files are synced to Convex."""
        from mc.types import AgentData

        _write_agent_yaml(agents_dir, "test-agent")
        agent_data = AgentData(
            name="test-agent",
            display_name="Test Agent",
            role="Test Agent",
            prompt="Test prompt",
        )
        mock_validate.return_value = agent_data

        synced, errors = service.sync_agent_registry(default_model="anthropic/claude-sonnet-4-5")
        assert len(synced) == 1
        assert synced[0].name == "test-agent"
        assert errors == {}
        bridge.sync_agent.assert_called_once()

    @patch("mc.contexts.agents.sync._config_default_model", return_value="anthropic/default")
    @patch("mc.contexts.agents.sync._write_back_convex_agents")
    @patch("mc.contexts.agents.sync.validate_agent_file")
    @patch("mc.contexts.agents.sync.ensure_low_agent")
    @patch("mc.contexts.agents.sync.ensure_nanobot_agent")
    def test_reports_validation_errors(
        self,
        mock_ensure_nanobot: MagicMock,
        mock_ensure_low: MagicMock,
        mock_validate: MagicMock,
        mock_write_back: MagicMock,
        mock_default_model: MagicMock,
        service: AgentSyncService,
        agents_dir: Path,
    ) -> None:
        """Invalid agent YAML files produce error entries."""
        _write_agent_yaml(agents_dir, "bad-agent")
        mock_validate.return_value = ["Missing required field: role"]

        synced, errors = service.sync_agent_registry()
        assert len(synced) == 0
        assert "bad-agent" in errors

    @patch("mc.contexts.agents.sync._config_default_model", return_value="anthropic/default")
    @patch("mc.contexts.agents.sync._write_back_convex_agents")
    @patch("mc.contexts.agents.sync.validate_agent_file")
    @patch("mc.contexts.agents.sync.ensure_low_agent")
    @patch("mc.contexts.agents.sync.ensure_nanobot_agent")
    def test_deactivates_removed_agents(
        self,
        mock_ensure_nanobot: MagicMock,
        mock_ensure_low: MagicMock,
        mock_validate: MagicMock,
        mock_write_back: MagicMock,
        mock_default_model: MagicMock,
        service: AgentSyncService,
        agents_dir: Path,
        bridge: MagicMock,
    ) -> None:
        """Agents whose YAML files are removed get deactivated."""
        from mc.types import AgentData

        _write_agent_yaml(agents_dir, "only-agent")
        mock_validate.return_value = AgentData(
            name="only-agent", display_name="Only Agent", role="r", prompt="p"
        )

        service.sync_agent_registry()
        bridge.deactivate_agents_except.assert_called_once()
        call_args = bridge.deactivate_agents_except.call_args[0]
        assert "only-agent" in call_args[0]


class TestCleanupDeletedAgents:
    """Test cleanup_deleted_agents — archives and removes local folders."""

    def test_archives_and_removes_deleted_agent_folder(
        self, service: AgentSyncService, agents_dir: Path, bridge: MagicMock
    ) -> None:
        """Deleted agents have their local data archived then removed."""
        agent_dir = agents_dir / "old-agent"
        agent_dir.mkdir()
        (agent_dir / "memory").mkdir()
        (agent_dir / "memory" / "MEMORY.md").write_text("test memory")

        bridge.list_deleted_agents.return_value = [{"name": "old-agent"}]

        service.cleanup_deleted_agents()

        bridge.archive_agent_data.assert_called_once()
        assert not agent_dir.exists()

    def test_skips_agent_without_local_folder(
        self, service: AgentSyncService, bridge: MagicMock
    ) -> None:
        """Agents with no local folder are silently skipped (idempotent)."""
        bridge.list_deleted_agents.return_value = [{"name": "nonexistent"}]

        service.cleanup_deleted_agents()
        bridge.archive_agent_data.assert_not_called()

    def test_does_not_delete_on_archive_failure(
        self, service: AgentSyncService, agents_dir: Path, bridge: MagicMock
    ) -> None:
        """If archiving fails, the local folder is NOT deleted."""
        agent_dir = agents_dir / "fragile-agent"
        agent_dir.mkdir()
        (agent_dir / "memory").mkdir()
        (agent_dir / "memory" / "MEMORY.md").write_text("keep me")

        bridge.list_deleted_agents.return_value = [{"name": "fragile-agent"}]
        bridge.archive_agent_data.side_effect = RuntimeError("Convex down")

        service.cleanup_deleted_agents()
        assert agent_dir.exists()  # Not deleted


class TestSyncModelTiers:
    """Test sync_model_tiers — model tier sync logic."""

    @patch(
        "mc.contexts.agents.sync.list_available_models",
        return_value=[
            "anthropic/claude-opus-4-5",
            "anthropic/claude-sonnet-4-5",
            "anthropic/claude-haiku-4-5",
        ],
    )
    def test_seeds_default_tiers_when_none_exist(
        self, mock_models: MagicMock, service: AgentSyncService, bridge: MagicMock
    ) -> None:
        """When no model_tiers setting exists, seeds defaults."""
        bridge.query.return_value = None

        service.sync_model_tiers()

        # Should set connected_models and model_tiers
        assert bridge.mutation.call_count == 2

    @patch(
        "mc.contexts.agents.sync.list_available_models",
        return_value=[
            "anthropic/claude-sonnet-4-5",
        ],
    )
    def test_migrates_stale_tier_values(
        self, mock_models: MagicMock, service: AgentSyncService, bridge: MagicMock
    ) -> None:
        """Tiers pointing to unavailable models get migrated."""
        existing = {"standard-high": "old/nonexistent-model", "standard-low": None}
        bridge.query.return_value = json.dumps(existing)

        service.sync_model_tiers()

        # connected_models set + model_tiers updated
        assert bridge.mutation.call_count >= 2


class TestSyncEmbeddingModel:
    """Test sync_embedding_model — reads/sets embedding env var."""

    def test_sets_env_var_when_model_configured(
        self, service: AgentSyncService, bridge: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sets NANOBOT_MEMORY_EMBEDDING_MODEL when configured."""
        bridge.query.return_value = "text-embedding-3-small"
        monkeypatch.delenv("NANOBOT_MEMORY_EMBEDDING_MODEL", raising=False)

        service.sync_embedding_model()
        assert os.environ.get("NANOBOT_MEMORY_EMBEDDING_MODEL") == "text-embedding-3-small"

    def test_clears_env_var_when_no_model(
        self, service: AgentSyncService, bridge: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Clears NANOBOT_MEMORY_EMBEDDING_MODEL when no model configured."""
        monkeypatch.setenv("NANOBOT_MEMORY_EMBEDDING_MODEL", "old-model")
        bridge.query.return_value = None

        service.sync_embedding_model()
        assert "NANOBOT_MEMORY_EMBEDDING_MODEL" not in os.environ


class TestSyncSkills:
    """Test sync_skills delegation."""

    @patch("mc.contexts.agents.sync.sync_skills_impl")
    def test_delegates_to_sync_skills_impl(
        self, mock_sync: MagicMock, service: AgentSyncService, bridge: MagicMock
    ) -> None:
        """sync_skills delegates to the standalone sync function."""
        mock_sync.return_value = ["skill-a", "skill-b"]

        result = service.sync_skills()
        assert result == ["skill-a", "skill-b"]
        mock_sync.assert_called_once()


class TestProjectionProtection:
    """Test that AgentSyncService does NOT overwrite projection-backed agents."""

    @patch("mc.contexts.agents.sync._write_back_convex_agents")
    @patch("mc.contexts.agents.sync.validate_agent_file")
    @patch("mc.contexts.agents.sync.ensure_low_agent")
    @patch("mc.contexts.agents.sync.ensure_nanobot_agent")
    def test_skips_upsert_for_projection_backed_agent(
        self,
        mock_ensure_nanobot: MagicMock,
        mock_ensure_low: MagicMock,
        mock_validate: MagicMock,
        mock_write_back: MagicMock,
        service: AgentSyncService,
        agents_dir: Path,
        bridge: MagicMock,
    ) -> None:
        """A compiled projection-backed agent must NOT be overwritten by local YAML."""
        from mc.types import AgentData

        _write_agent_yaml(agents_dir, "compiled-agent")
        agent_data = AgentData(
            name="compiled-agent",
            display_name="Compiled Agent",
            role="Developer",
            prompt="Local YAML prompt.",
        )
        mock_validate.return_value = agent_data

        # Simulate that Convex has a projection-backed agent doc via bulk list
        compiled_doc = {
            "name": "compiled-agent",
            "compiled_from_spec_id": "spec-id-abc",
            "compiled_at": "2025-01-01T00:00:00Z",
        }
        bridge.list_agents.return_value = [compiled_doc]
        bridge.get_agent_by_name.return_value = compiled_doc

        synced, _errors = service.sync_agent_registry(default_model="anthropic/claude-sonnet-4-5")

        # Should still appear in synced (for reporting), but NOT call sync_agent
        bridge.sync_agent.assert_not_called()
        # The projection-backed agent must still be included in the returned synced list
        assert len(synced) == 1
        assert synced[0].name == "compiled-agent"
        # The bulk list_agents call must have been used (no N+1 per-agent query needed)
        bridge.list_agents.assert_called()

    @patch("mc.contexts.agents.sync._write_back_convex_agents")
    @patch("mc.contexts.agents.sync.validate_agent_file")
    @patch("mc.contexts.agents.sync.ensure_low_agent")
    @patch("mc.contexts.agents.sync.ensure_nanobot_agent")
    def test_allows_upsert_for_legacy_agent(
        self,
        mock_ensure_nanobot: MagicMock,
        mock_ensure_low: MagicMock,
        mock_validate: MagicMock,
        mock_write_back: MagicMock,
        service: AgentSyncService,
        agents_dir: Path,
        bridge: MagicMock,
    ) -> None:
        """An uncompiled legacy agent (no compiledFromSpecId) is synced normally."""
        from mc.types import AgentData

        _write_agent_yaml(agents_dir, "legacy-agent")
        agent_data = AgentData(
            name="legacy-agent",
            display_name="Legacy Agent",
            role="Developer",
            prompt="Legacy prompt.",
        )
        mock_validate.return_value = agent_data

        # No projection metadata
        bridge.get_agent_by_name.return_value = {
            "name": "legacy-agent",
            "compiled_from_spec_id": None,
        }

        _synced, _errors = service.sync_agent_registry(default_model="anthropic/claude-sonnet-4-5")

        bridge.sync_agent.assert_called_once()

    @patch("mc.contexts.agents.sync._write_back_convex_agents")
    @patch("mc.contexts.agents.sync.validate_agent_file")
    @patch("mc.contexts.agents.sync.ensure_low_agent")
    @patch("mc.contexts.agents.sync.ensure_nanobot_agent")
    def test_allows_upsert_for_new_agent_not_in_convex(
        self,
        mock_ensure_nanobot: MagicMock,
        mock_ensure_low: MagicMock,
        mock_validate: MagicMock,
        mock_write_back: MagicMock,
        service: AgentSyncService,
        agents_dir: Path,
        bridge: MagicMock,
    ) -> None:
        """A brand-new agent not yet in Convex is synced normally."""
        from mc.types import AgentData

        _write_agent_yaml(agents_dir, "new-agent")
        agent_data = AgentData(
            name="new-agent",
            display_name="New Agent",
            role="Developer",
            prompt="New prompt.",
        )
        mock_validate.return_value = agent_data

        # Not in Convex at all
        bridge.get_agent_by_name.return_value = None

        _synced, _errors = service.sync_agent_registry(default_model="anthropic/claude-sonnet-4-5")

        bridge.sync_agent.assert_called_once()


class TestWriteBackProjectionProtection:
    """Test that write-back materializes config.yaml/SOUL.md from projection."""

    def test_write_back_still_works_for_projection_backed_agent(self, tmp_path: Path) -> None:
        """Write-back should still materialize config.yaml from a projection-backed agent."""
        from mc.runtime.gateway import _write_back_convex_agents

        mock_bridge = MagicMock()
        mock_bridge.list_agents.return_value = [
            {
                "name": "compiled-agent",
                "role": "Developer",
                "prompt": "Compiled prompt.",
                "compiled_from_spec_id": "spec-id-abc",
                "compiled_at": "2099-01-01T00:00:00Z",
                "last_active_at": "2099-01-01T00:00:00+00:00",
            }
        ]

        _write_back_convex_agents(mock_bridge, tmp_path)

        # Write-back SHOULD still be called for projection-backed agents
        mock_bridge.write_agent_config.assert_called_once()
        call_args = mock_bridge.write_agent_config.call_args[0]
        assert call_args[0]["name"] == "compiled-agent"
