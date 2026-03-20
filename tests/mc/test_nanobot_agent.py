"""Tests for Story 1.3: Nanobot agent as system fallback."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from mc.bridge import ConvexBridge
from mc.types import AgentData


def _make_agent(name: str, skills: list[str] | None = None) -> AgentData:
    return AgentData(
        name=name,
        display_name=name,
        role="tester",
        skills=skills or [],
    )


class TestEnsureNanobotAgent:
    @patch(
        "mc.infrastructure.agent_bootstrap._fetch_bot_identity",
        return_value={"name": "Bento", "role": "General-Purpose Assistant"},
    )
    def test_creates_directory_and_config_when_missing(self, mock_identity, tmp_path: Path) -> None:
        from mc.runtime.gateway import NANOBOT_AGENT_NAME, ensure_nanobot_agent

        ensure_nanobot_agent(tmp_path)

        agent_dir = tmp_path / NANOBOT_AGENT_NAME
        config_path = agent_dir / "config.yaml"
        assert agent_dir.is_dir()
        assert (agent_dir / "memory").is_dir()
        assert (agent_dir / "skills").is_dir()
        assert config_path.is_file()

        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert config["name"] == "nanobot"
        assert config["role"] == "General-Purpose Assistant"
        assert config["is_system"] is True
        assert config["skills"] == []

    @patch(
        "mc.infrastructure.agent_bootstrap._fetch_bot_identity",
        return_value={"name": "Bento", "role": "General-Purpose Assistant"},
    )
    def test_is_idempotent_and_preserves_existing_config(
        self, mock_identity, tmp_path: Path
    ) -> None:
        from mc.runtime.gateway import NANOBOT_AGENT_NAME, ensure_nanobot_agent

        agent_dir = tmp_path / NANOBOT_AGENT_NAME
        agent_dir.mkdir(parents=True)
        config_path = agent_dir / "config.yaml"
        existing = (
            "name: nanobot\nrole: Custom Role\nis_system: false\nprompt: custom\nskills: []\n"
        )
        config_path.write_text(existing, encoding="utf-8")

        ensure_nanobot_agent(tmp_path)

        assert config_path.read_text(encoding="utf-8") == existing


class TestSyncAgentRegistryNanobotAgent:
    def test_sync_includes_nanobot_agent_with_is_system_true(self, tmp_path: Path) -> None:
        from mc.runtime.gateway import sync_agent_registry

        mock_bridge = MagicMock()

        with (
            patch("mc.infrastructure.agent_bootstrap._cleanup_deleted_agents"),
            patch("mc.infrastructure.agent_bootstrap._write_back_convex_agents"),
        ):
            synced, errors = sync_agent_registry(
                mock_bridge,
                tmp_path,
                default_model="anthropic/claude-haiku-4-5",
            )

        assert errors == {}
        assert any(a.name == "nanobot" and a.is_system for a in synced)
        # sync_agent is called at least twice: once for low-agent (Step 0) and
        # once for nanobot (during YAML sync).
        assert mock_bridge.sync_agent.call_count >= 2
        synced_names = [c[0][0].name for c in mock_bridge.sync_agent.call_args_list]
        assert "nanobot" in synced_names
        nanobot_agent = next(
            c[0][0] for c in mock_bridge.sync_agent.call_args_list if c[0][0].name == "nanobot"
        )
        assert nanobot_agent.is_system is True
        mock_bridge.deactivate_agents_except.assert_called_once()
        active_names = mock_bridge.deactivate_agents_except.call_args[0][0]
        assert "nanobot" in active_names


class TestBridgeSyncAgentSystemFlag:
    def test_sync_agent_passes_is_system_arg_when_true(self) -> None:
        bridge = object.__new__(ConvexBridge)
        bridge.mutation = MagicMock(return_value=None)

        agent = AgentData(
            name="nanobot",
            display_name="Bento",
            role="General-Purpose Assistant",
            prompt="hello",
            soul="# Soul",
            skills=[],
            model="anthropic/claude-haiku-4-5",
            is_system=True,
        )

        bridge.sync_agent(agent)

        args = bridge.mutation.call_args[0][1]
        assert args["name"] == "nanobot"
        assert args["is_system"] is True
