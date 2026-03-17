"""Unit tests for CLI agent commands (Story 3.4)."""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from mc.cli import mc_app, _get_agent_status_color

runner = CliRunner()


# ── _get_agent_status_color tests ────────────────────────────────────


class TestGetAgentStatusColor:
    def test_active(self):
        assert _get_agent_status_color("active") == "blue"

    def test_idle(self):
        assert _get_agent_status_color("idle") == "dim"

    def test_crashed(self):
        assert _get_agent_status_color("crashed") == "red"

    def test_unknown_status(self):
        assert _get_agent_status_color("something_else") == "white"


# ── agents --help test ───────────────────────────────────────────────


class TestAgentsHelp:
    def test_agents_help(self):
        result = runner.invoke(mc_app, ["agents", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "create" in result.output
        assert "Manage Mission Control agents" in result.output

    def test_agents_no_args_shows_help(self):
        result = runner.invoke(mc_app, ["agents"])
        assert "list" in result.output
        assert "create" in result.output


# ── agents list tests ────────────────────────────────────────────────


class TestAgentsList:
    def test_list_no_agents_dir(self, tmp_path):
        with patch("mc.cli.AGENTS_DIR", tmp_path / "nonexistent"):
            result = runner.invoke(mc_app, ["agents", "list"])
        assert result.exit_code == 0
        assert "No agents found" in result.output
        assert "nanobot mc agents create" in result.output

    def test_list_empty_dir(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        with patch("mc.cli.AGENTS_DIR", agents_dir):
            result = runner.invoke(mc_app, ["agents", "list"])
        assert result.exit_code == 0
        assert "No agents found" in result.output

    def test_list_displays_agents(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agent1 = agents_dir / "dev-agent"
        agent1.mkdir(parents=True)
        (agent1 / "config.yaml").write_text(
            "name: dev-agent\nrole: Developer\nprompt: You code.\nskills:\n  - coding\n  - testing\nmodel: gpt-4\n"
        )
        agent2 = agents_dir / "researcher"
        agent2.mkdir()
        (agent2 / "config.yaml").write_text(
            "name: researcher\nrole: Research Analyst\nprompt: You research.\n"
        )

        with patch("mc.cli.AGENTS_DIR", agents_dir):
            result = runner.invoke(mc_app, ["agents", "list"])

        assert result.exit_code == 0
        assert "Registered Agents" in result.output
        assert "dev-agent" in result.output
        assert "Developer" in result.output
        assert "coding, testing" in result.output
        assert "gpt-4" in result.output
        assert "researcher" in result.output
        assert "Research Analyst" in result.output

    def test_list_skips_invalid_yaml(self, tmp_path):
        agents_dir = tmp_path / "agents"
        good = agents_dir / "good-agent"
        good.mkdir(parents=True)
        (good / "config.yaml").write_text("name: good-agent\nrole: Dev\nprompt: You dev.\n")
        bad = agents_dir / "bad-agent"
        bad.mkdir()
        (bad / "config.yaml").write_text("invalid: yaml: content: [")

        with patch("mc.cli.AGENTS_DIR", agents_dir):
            result = runner.invoke(mc_app, ["agents", "list"])

        assert result.exit_code == 0
        assert "good-agent" in result.output

    def test_list_skips_dirs_without_config(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agent = agents_dir / "no-config"
        agent.mkdir(parents=True)

        with patch("mc.cli.AGENTS_DIR", agents_dir):
            result = runner.invoke(mc_app, ["agents", "list"])

        assert result.exit_code == 0
        assert "No agents found" in result.output


# ── agents create tests ──────────────────────────────────────────────


@patch("mc.cli._sync_to_convex")
class TestAgentsCreate:
    def test_create_agent(self, mock_sync, tmp_path):
        agents_dir = tmp_path / "agents"
        with patch("mc.cli.AGENTS_DIR", agents_dir):
            result = runner.invoke(
                mc_app,
                ["agents", "create"],
                input="test-agent\nDeveloper\ncoding,testing\nYou are a dev.\n\ngpt-4\n",
            )

        assert result.exit_code == 0
        assert "Agent 'test-agent' created" in result.output

        # Verify directory structure
        agent_dir = agents_dir / "test-agent"
        assert agent_dir.is_dir()
        assert (agent_dir / "config.yaml").is_file()
        assert (agent_dir / "memory").is_dir()
        assert (agent_dir / "skills").is_dir()
        assert (agent_dir / "memory" / "MEMORY.md").is_file()

    def test_create_agent_yaml_valid(self, mock_sync, tmp_path):
        agents_dir = tmp_path / "agents"
        with patch("mc.cli.AGENTS_DIR", agents_dir):
            result = runner.invoke(
                mc_app,
                ["agents", "create"],
                input="my-agent\nResearcher\nresearch\nYou research things.\n\n\n",
            )

        assert result.exit_code == 0
        config_path = agents_dir / "my-agent" / "config.yaml"

        # Validate using the same validator
        from mc.infrastructure.agents.yaml_validator import validate_agent_file

        validation_result = validate_agent_file(config_path)
        assert not isinstance(validation_result, list), f"Validation failed: {validation_result}"
        assert validation_result.name == "my-agent"
        assert validation_result.role == "Researcher"

    def test_create_agent_no_model(self, mock_sync, tmp_path):
        agents_dir = tmp_path / "agents"
        with patch("mc.cli.AGENTS_DIR", agents_dir):
            result = runner.invoke(
                mc_app,
                ["agents", "create"],
                input="no-model\nDev\n\nDo stuff.\n\n\n",
            )

        assert result.exit_code == 0
        import yaml

        config = yaml.safe_load((agents_dir / "no-model" / "config.yaml").read_text())
        assert "model" not in config

    def test_create_agent_invalid_name_retry(self, mock_sync, tmp_path):
        agents_dir = tmp_path / "agents"
        with patch("mc.cli.AGENTS_DIR", agents_dir):
            result = runner.invoke(
                mc_app,
                ["agents", "create"],
                input="INVALID NAME!\nvalid-name\nDev\n\nDo stuff.\n\n\n",
            )

        assert result.exit_code == 0
        assert "Invalid name" in result.output
        assert (agents_dir / "valid-name" / "config.yaml").is_file()
