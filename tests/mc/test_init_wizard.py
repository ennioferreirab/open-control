"""Tests for the init wizard business logic and CLI command."""

import shutil
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from nanobot.cli.commands import app
from mc.cli.init_wizard import (
    LEAD_AGENT_CONFIG,
    PRESETS,
    AgentPlan,
    CreationResult,
    agent_exists,
    build_lead_agent_yaml,
    build_preset_yaml,
    create_agents,
    lead_agent_exists,
)

runner = CliRunner()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_agents_dir(tmp_path):
    """Redirect AGENTS_DIR to a temp directory for isolation."""
    agents = tmp_path / "agents"
    agents.mkdir()
    with (
        patch("mc.cli.init_wizard.AGENTS_DIR", agents),
        patch("mc.cli.agent_assist.Path") as mock_path_cls,
    ):
        # Also patch create_agent_workspace's home so it writes to tmp
        mock_path_cls.home.return_value = tmp_path
        # Keep the rest of Path working normally by forwarding attribute access
        mock_path_cls.side_effect = Path
        yield agents


@pytest.fixture
def tmp_agents_dir_simple(tmp_path):
    """Simpler fixture that only patches the existence checks."""
    agents = tmp_path / "agents"
    agents.mkdir()
    with patch("mc.cli.init_wizard.AGENTS_DIR", agents):
        yield agents


# ---------------------------------------------------------------------------
# YAML generation tests
# ---------------------------------------------------------------------------


class TestBuildLeadAgentYaml:
    def test_valid_yaml(self):
        text = build_lead_agent_yaml()
        data = yaml.safe_load(text)
        assert data["name"] == "lead-agent"
        assert data["role"] == "Lead Agent — Orchestrator"
        assert "prompt" in data
        assert isinstance(data["skills"], list)
        assert len(data["skills"]) > 0

    def test_matches_config_dict(self):
        text = build_lead_agent_yaml()
        data = yaml.safe_load(text)
        assert data == LEAD_AGENT_CONFIG

    def test_passes_agent_validation(self):
        from mc.cli.agent_assist import validate_yaml_content

        text = build_lead_agent_yaml()
        parsed, errors = validate_yaml_content(text)
        assert errors == []
        assert parsed is not None
        assert parsed["name"] == "lead-agent"


class TestBuildPresetYaml:
    @pytest.mark.parametrize("preset", PRESETS, ids=[p.name for p in PRESETS])
    def test_valid_yaml(self, preset):
        text = build_preset_yaml(preset)
        data = yaml.safe_load(text)
        assert data["name"] == preset.name
        assert data["role"] == preset.role
        assert data["prompt"] == preset.prompt
        assert data["skills"] == list(preset.skills)

    @pytest.mark.parametrize("preset", PRESETS, ids=[p.name for p in PRESETS])
    def test_passes_agent_validation(self, preset):
        from mc.cli.agent_assist import validate_yaml_content

        text = build_preset_yaml(preset)
        parsed, errors = validate_yaml_content(text)
        assert errors == [], f"Validation failed for {preset.name}: {errors}"
        assert parsed is not None

    def test_preset_names_unique(self):
        names = [p.name for p in PRESETS]
        assert len(names) == len(set(names)), "Duplicate preset names found"

    def test_preset_names_not_lead(self):
        for p in PRESETS:
            assert p.name != "lead-agent", "Preset must not shadow lead-agent"


# ---------------------------------------------------------------------------
# Existence checks
# ---------------------------------------------------------------------------


class TestAgentExists:
    def test_returns_false_when_missing(self, tmp_agents_dir_simple):
        assert agent_exists("nonexistent") is False

    def test_returns_true_when_present(self, tmp_agents_dir_simple):
        agent_dir = tmp_agents_dir_simple / "my-agent"
        agent_dir.mkdir()
        (agent_dir / "config.yaml").write_text("name: my-agent\n")
        assert agent_exists("my-agent") is True

    def test_lead_agent_exists_false(self, tmp_agents_dir_simple):
        assert lead_agent_exists() is False

    def test_lead_agent_exists_true(self, tmp_agents_dir_simple):
        lead_dir = tmp_agents_dir_simple / "lead-agent"
        lead_dir.mkdir()
        (lead_dir / "config.yaml").write_text("name: lead-agent\n")
        assert lead_agent_exists() is True


# ---------------------------------------------------------------------------
# create_agents
# ---------------------------------------------------------------------------


class TestCreateAgents:
    def test_skip_plan(self, tmp_agents_dir_simple):
        plans = [
            AgentPlan(
                name="skipped",
                role="Test",
                yaml_text="",
                source="test",
                skip=True,
                skip_reason="test skip",
            )
        ]
        results = create_agents(plans)
        assert len(results) == 1
        assert results[0].success is True
        assert "skipped" in results[0].error

    def test_create_single_agent(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        yaml_text = build_lead_agent_yaml()

        with (
            patch("mc.cli.init_wizard.AGENTS_DIR", agents_dir),
            patch("mc.cli.init_wizard.create_agent_workspace") as mock_create,
        ):
            config_path = agents_dir / "lead-agent" / "config.yaml"
            # Simulate workspace creation
            (agents_dir / "lead-agent").mkdir(parents=True)
            config_path.write_text(yaml_text)
            mock_create.return_value = config_path

            plans = [
                AgentPlan(
                    name="lead-agent",
                    role="Lead",
                    yaml_text=yaml_text,
                    source="lead",
                )
            ]
            results = create_agents(plans)
            assert len(results) == 1
            assert results[0].success is True
            assert results[0].path == str(config_path)

    def test_create_failure_returns_error(self, tmp_agents_dir_simple):
        with patch("mc.cli.init_wizard.create_agent_workspace", side_effect=OSError("disk full")):
            plans = [
                AgentPlan(
                    name="fail-agent",
                    role="Test",
                    yaml_text="name: fail-agent\n",
                    source="test",
                )
            ]
            results = create_agents(plans)
            assert len(results) == 1
            assert results[0].success is False
            assert "disk full" in results[0].error

    def test_mixed_results(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        good_yaml = build_preset_yaml(PRESETS[0])

        # Prepare valid agent on disk
        (agents_dir / "developer").mkdir(parents=True)
        config_path = agents_dir / "developer" / "config.yaml"
        config_path.write_text(good_yaml)

        def mock_create(name, yaml_text):
            if name == "developer":
                return config_path
            raise OSError("fail")

        with (
            patch("mc.cli.init_wizard.AGENTS_DIR", agents_dir),
            patch("mc.cli.init_wizard.create_agent_workspace", side_effect=mock_create),
        ):
            plans = [
                AgentPlan(name="developer", role="Dev", yaml_text=good_yaml, source="preset"),
                AgentPlan(name="bad-agent", role="Bad", yaml_text="name: bad\n", source="test"),
            ]
            results = create_agents(plans)
            assert results[0].success is True
            assert results[1].success is False


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestInitCLI:
    def test_help(self):
        result = runner.invoke(app, ["mc", "init", "--help"])
        assert result.exit_code == 0
        assert "setup wizard" in result.stdout.lower() or "wizard" in result.stdout.lower()

    def test_lead_only(self, tmp_path):
        """--skip-presets --skip-custom --yes creates only the lead-agent."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        with (
            patch("mc.cli.AGENTS_DIR", agents_dir),
            patch("mc.cli.init_wizard.AGENTS_DIR", agents_dir),
            patch("mc.cli._sync_to_convex"),
            patch("mc.cli.init_wizard.create_agent_workspace") as mock_create,
        ):
            # Set up workspace creation to actually write the file
            def do_create(name, yaml_text):
                d = agents_dir / name
                d.mkdir(parents=True, exist_ok=True)
                (d / "config.yaml").write_text(yaml_text)
                return d / "config.yaml"

            mock_create.side_effect = do_create

            result = runner.invoke(app, ["mc", "init", "--skip-presets", "--skip-custom", "--yes"])
            assert result.exit_code == 0
            assert "lead-agent" in result.stdout
            mock_create.assert_called_once()
            assert mock_create.call_args[0][0] == "lead-agent"

    def test_lead_exists_skips(self, tmp_path):
        """If lead-agent already exists, step 1 skips it."""
        agents_dir = tmp_path / "agents"
        lead_dir = agents_dir / "lead-agent"
        lead_dir.mkdir(parents=True)
        (lead_dir / "config.yaml").write_text(build_lead_agent_yaml())

        with (
            patch("mc.cli.AGENTS_DIR", agents_dir),
            patch("mc.cli.init_wizard.AGENTS_DIR", agents_dir),
            patch("mc.cli.init_wizard.create_agent_workspace") as mock_create,
        ):
            result = runner.invoke(app, ["mc", "init", "--skip-presets", "--skip-custom", "--yes"])
            assert result.exit_code == 0
            assert "already exists" in result.stdout
            # Nothing to create → exit 0 with "Nothing to create"
            assert "nothing to create" in result.stdout.lower()
            mock_create.assert_not_called()

    def test_yes_creates_all_presets(self, tmp_path):
        """--yes auto-selects all presets that don't exist."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        created_names = []

        def do_create(name, yaml_text):
            created_names.append(name)
            d = agents_dir / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "config.yaml").write_text(yaml_text)
            return d / "config.yaml"

        with (
            patch("mc.cli.AGENTS_DIR", agents_dir),
            patch("mc.cli.init_wizard.AGENTS_DIR", agents_dir),
            patch("mc.cli._sync_to_convex"),
            patch("mc.cli.init_wizard.create_agent_workspace", side_effect=do_create),
        ):
            result = runner.invoke(app, ["mc", "init", "--skip-custom", "--yes"])
            assert result.exit_code == 0
            # Should create lead + all 5 presets
            assert "lead-agent" in created_names
            for p in PRESETS:
                assert p.name in created_names
