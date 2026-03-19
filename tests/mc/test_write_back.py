"""Tests for agent config write-back — Story 8.2, Task 7."""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import MagicMock

import yaml

from mc.bridge import ConvexBridge


def _make_bridge_with_write(deployment_url: str = "https://test.convex.cloud") -> ConvexBridge:
    """Create a ConvexBridge with mocked client for testing write_agent_config."""
    bridge = object.__new__(ConvexBridge)
    bridge._client = MagicMock()
    return bridge


class TestWriteAgentConfig:
    """Test ConvexBridge.write_agent_config() writes YAML correctly."""

    def test_writes_yaml_file(self, tmp_path: Path) -> None:
        """write_agent_config should create a config.yaml in the agent dir."""
        bridge = _make_bridge_with_write()
        agent_data = {
            "name": "test-agent",
            "display_name": "Test Agent",
            "role": "Developer",
            "prompt": "You are a developer.",
            "skills": ["github", "memory"],
            "model": "claude-sonnet-4-6",
        }

        bridge.write_agent_config(agent_data, tmp_path)

        config_path = tmp_path / "test-agent" / "config.yaml"
        assert config_path.exists()
        content = yaml.safe_load(config_path.read_text())
        assert content["name"] == "test-agent"
        assert content["role"] == "Developer"
        assert content["prompt"] == "You are a developer."
        assert content["skills"] == ["github", "memory"]
        assert content["model"] == "claude-sonnet-4-6"
        assert content["display_name"] == "Test Agent"

    def test_creates_agent_directory(self, tmp_path: Path) -> None:
        """Should create the agent directory if it doesn't exist."""
        bridge = _make_bridge_with_write()
        agent_data = {"name": "new-agent", "role": "Tester", "prompt": "Test."}

        bridge.write_agent_config(agent_data, tmp_path)

        assert (tmp_path / "new-agent").is_dir()
        assert (tmp_path / "new-agent" / "config.yaml").is_file()

    def test_omits_empty_optional_fields(self, tmp_path: Path) -> None:
        """Model and display_name should be omitted when not provided."""
        bridge = _make_bridge_with_write()
        agent_data = {
            "name": "minimal-agent",
            "role": "Worker",
            "prompt": "Work hard.",
        }

        bridge.write_agent_config(agent_data, tmp_path)

        content = yaml.safe_load((tmp_path / "minimal-agent" / "config.yaml").read_text())
        assert "model" not in content
        assert "display_name" not in content

    def test_overwrites_existing_config(self, tmp_path: Path) -> None:
        """Should overwrite existing config.yaml with new data."""
        bridge = _make_bridge_with_write()
        agent_dir = tmp_path / "old-agent"
        agent_dir.mkdir()
        (agent_dir / "config.yaml").write_text("name: old-agent\nrole: Old Role\nprompt: Old.\n")

        agent_data = {
            "name": "old-agent",
            "role": "New Role",
            "prompt": "New prompt.",
            "skills": ["coding"],
        }

        bridge.write_agent_config(agent_data, tmp_path)

        content = yaml.safe_load((agent_dir / "config.yaml").read_text())
        assert content["role"] == "New Role"
        assert content["prompt"] == "New prompt."
        assert content["skills"] == ["coding"]

    def test_yaml_format_snake_case(self, tmp_path: Path) -> None:
        """YAML output should use snake_case field names."""
        bridge = _make_bridge_with_write()
        agent_data = {
            "name": "test-agent",
            "display_name": "Test Agent",
            "role": "Dev",
            "prompt": "Hi.",
        }

        bridge.write_agent_config(agent_data, tmp_path)

        raw = (tmp_path / "test-agent" / "config.yaml").read_text()
        assert "display_name:" in raw
        # Should not contain camelCase keys
        assert "displayName" not in raw


class TestWriteBackConvexAgents:
    """Test _write_back_convex_agents() in gateway.py."""

    def test_writes_back_when_convex_is_newer(self, tmp_path: Path) -> None:
        """If Convex lastActiveAt > local mtime, should write back."""
        from mc.runtime.gateway import _write_back_convex_agents

        # Create a local config.yaml with old mtime
        agent_dir = tmp_path / "my-agent"
        agent_dir.mkdir()
        config_path = agent_dir / "config.yaml"
        config_path.write_text("name: my-agent\nrole: Old Role\nprompt: Old.\n")
        # Set mtime to the past
        old_time = time.time() - 3600
        os.utime(config_path, (old_time, old_time))

        # Mock bridge returns agent with future timestamp
        mock_bridge = MagicMock()
        mock_bridge.list_agents.return_value = [
            {
                "name": "my-agent",
                "display_name": "My Agent",
                "role": "New Role",
                "prompt": "New prompt.",
                "skills": ["github"],
                "model": "claude-sonnet-4-6",
                "last_active_at": "2099-01-01T00:00:00+00:00",
            }
        ]
        mock_bridge.get_agent_memory_backup.return_value = None

        _write_back_convex_agents(mock_bridge, tmp_path)

        # Should have called write_agent_config
        mock_bridge.write_agent_config.assert_called_once()
        call_args = mock_bridge.write_agent_config.call_args[0]
        assert call_args[0]["name"] == "my-agent"
        assert call_args[1] == tmp_path

    def test_skips_when_local_is_newer(self, tmp_path: Path) -> None:
        """If local mtime > Convex lastActiveAt, should NOT write back."""
        from mc.runtime.gateway import _write_back_convex_agents

        agent_dir = tmp_path / "my-agent"
        agent_dir.mkdir()
        config_path = agent_dir / "config.yaml"
        config_path.write_text("name: my-agent\nrole: Current\nprompt: Current.\n")

        mock_bridge = MagicMock()
        mock_bridge.list_agents.return_value = [
            {
                "name": "my-agent",
                "role": "Stale",
                "prompt": "Stale.",
                "last_active_at": "2000-01-01T00:00:00+00:00",
            }
        ]
        mock_bridge.get_agent_memory_backup.return_value = None

        _write_back_convex_agents(mock_bridge, tmp_path)

        mock_bridge.write_agent_config.assert_not_called()

    def test_creates_new_agent_dir_from_convex(self, tmp_path: Path) -> None:
        """If agent exists in Convex but not locally, should create it."""
        from mc.runtime.gateway import _write_back_convex_agents

        mock_bridge = MagicMock()
        mock_bridge.list_agents.return_value = [
            {
                "name": "cloud-agent",
                "role": "Cloud Worker",
                "prompt": "Work in the cloud.",
                "last_active_at": "2099-01-01T00:00:00+00:00",
            }
        ]
        mock_bridge.get_agent_memory_backup.return_value = None

        _write_back_convex_agents(mock_bridge, tmp_path)

        mock_bridge.write_agent_config.assert_called_once()

    def test_handles_list_agents_failure(self, tmp_path: Path) -> None:
        """Should not crash if list_agents fails."""
        from mc.runtime.gateway import _write_back_convex_agents

        mock_bridge = MagicMock()
        mock_bridge.list_agents.side_effect = Exception("Network error")

        # Should not raise
        _write_back_convex_agents(mock_bridge, tmp_path)

    def test_skips_agent_without_last_active_at(self, tmp_path: Path) -> None:
        """Agents without lastActiveAt should be skipped."""
        from mc.runtime.gateway import _write_back_convex_agents

        mock_bridge = MagicMock()
        mock_bridge.list_agents.return_value = [
            {"name": "no-timestamp-agent", "role": "Worker", "prompt": "Hi."}
        ]
        mock_bridge.get_agent_memory_backup.return_value = None

        _write_back_convex_agents(mock_bridge, tmp_path)

        mock_bridge.write_agent_config.assert_not_called()
