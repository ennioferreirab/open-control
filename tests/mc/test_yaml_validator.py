"""Unit tests for the YAML Agent Validator."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from mc.types import AgentData
from mc.yaml_validator import (
    validate_agent_file,
    validate_agents_dir,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(tmp_path: Path, filename: str, content: str) -> Path:
    """Write a YAML string to a file and return its path."""
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Valid config tests
# ---------------------------------------------------------------------------

class TestValidConfigs:
    """Tests for valid agent YAML configurations."""

    def test_full_config_returns_agent_data(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "agent.yaml", """\
            name: dev-agent
            role: Senior Developer
            prompt: "You are a senior developer."
            skills:
              - code-review
              - debugging
            model: claude-sonnet-4-6
            display_name: Dev Agent
        """)
        result = validate_agent_file(path)
        assert isinstance(result, AgentData)
        assert result.name == "dev-agent"
        assert result.role == "Senior Developer"
        assert result.prompt == "You are a senior developer."
        assert result.skills == ["code-review", "debugging"]
        assert result.model == "claude-sonnet-4-6"
        assert result.display_name == "Dev Agent"
        assert result.status == "idle"

    def test_minimal_config_returns_agent_data_with_defaults(
        self, tmp_path: Path
    ) -> None:
        path = _write_yaml(tmp_path, "agent.yaml", """\
            name: my-agent
            role: Assistant
            prompt: "You help with tasks."
        """)
        result = validate_agent_file(path)
        assert isinstance(result, AgentData)
        assert result.name == "my-agent"
        assert result.skills == []
        assert result.model is None
        assert result.display_name == "My Agent"

    def test_display_name_auto_generated_from_name(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "agent.yaml", """\
            name: code-review-bot
            role: Reviewer
            prompt: "You review code."
        """)
        result = validate_agent_file(path)
        assert isinstance(result, AgentData)
        assert result.display_name == "Code Review Bot"

    def test_display_name_with_underscores(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "agent.yaml", """\
            name: my-agent
            role: Helper
            prompt: "Help."
            display_name: null
        """)
        result = validate_agent_file(path)
        assert isinstance(result, AgentData)
        assert result.display_name == "My Agent"


# ---------------------------------------------------------------------------
# Missing required field tests
# ---------------------------------------------------------------------------

class TestMissingRequired:
    """Tests for missing required fields."""

    def test_missing_name(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "agent.yaml", """\
            role: Developer
            prompt: "You code."
        """)
        result = validate_agent_file(path)
        assert isinstance(result, list)
        assert any("name" in e.lower() for e in result)

    def test_missing_role(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "agent.yaml", """\
            name: dev-agent
            prompt: "You code."
        """)
        result = validate_agent_file(path)
        assert isinstance(result, list)
        assert any("role" in e.lower() for e in result)

    def test_missing_prompt(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "agent.yaml", """\
            name: dev-agent
            role: Developer
        """)
        result = validate_agent_file(path)
        assert isinstance(result, list)
        assert any("prompt" in e.lower() for e in result)


# ---------------------------------------------------------------------------
# Wrong type tests
# ---------------------------------------------------------------------------

class TestWrongTypes:
    """Tests for fields with wrong types."""

    def test_skills_string_instead_of_list(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "agent.yaml", """\
            name: dev-agent
            role: Developer
            prompt: "You code."
            skills: coding
        """)
        result = validate_agent_file(path)
        assert isinstance(result, list)
        assert any("skills" in e.lower() for e in result)

    def test_name_invalid_characters(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "agent.yaml", """\
            name: "My Agent"
            role: Developer
            prompt: "You code."
        """)
        result = validate_agent_file(path)
        assert isinstance(result, list)
        assert any("invalid characters" in e.lower() for e in result)

    def test_name_uppercase(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "agent.yaml", """\
            name: DevAgent
            role: Developer
            prompt: "You code."
        """)
        result = validate_agent_file(path)
        assert isinstance(result, list)
        assert any("invalid characters" in e.lower() for e in result)


# ---------------------------------------------------------------------------
# Multi-error collection tests
# ---------------------------------------------------------------------------

class TestMultiError:
    """Tests that multiple errors are collected in a single pass."""

    def test_multiple_missing_fields(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "agent.yaml", """\
            skills: 123
        """)
        result = validate_agent_file(path)
        assert isinstance(result, list)
        assert len(result) >= 2, f"Expected >=2 errors, got {len(result)}: {result}"

    def test_missing_role_and_invalid_skills(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "agent.yaml", """\
            name: dev-agent
            prompt: "You code."
            skills: not-a-list
        """)
        result = validate_agent_file(path)
        assert isinstance(result, list)
        assert len(result) >= 2
        error_text = " ".join(result).lower()
        assert "role" in error_text
        assert "skills" in error_text


# ---------------------------------------------------------------------------
# YAML parse error tests
# ---------------------------------------------------------------------------

class TestYamlParseErrors:
    """Tests for malformed YAML files."""

    def test_malformed_yaml(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "agent.yaml", """\
            name: dev-agent
            role: Developer
              bad-indent: oops
        """)
        result = validate_agent_file(path)
        assert isinstance(result, list)
        assert any("yaml parse error" in e.lower() for e in result)

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "agent.yaml"
        path.write_text("", encoding="utf-8")
        result = validate_agent_file(path)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_file_not_found(self, tmp_path: Path) -> None:
        path = tmp_path / "nonexistent.yaml"
        result = validate_agent_file(path)
        assert isinstance(result, list)
        assert any("not found" in e.lower() for e in result)


# ---------------------------------------------------------------------------
# Directory validation tests
# ---------------------------------------------------------------------------

class TestDirectoryValidation:
    """Tests for validate_agents_dir."""

    def test_mixed_valid_and_invalid(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path, "good1.yaml", """\
            name: agent-one
            role: Tester
            prompt: "You test."
        """)
        _write_yaml(tmp_path, "good2.yml", """\
            name: agent-two
            role: Builder
            prompt: "You build."
        """)
        _write_yaml(tmp_path, "bad.yaml", """\
            name: "Invalid Name!"
            role: Breaker
            prompt: "Oops."
        """)

        valid, errors = validate_agents_dir(tmp_path)
        assert len(valid) == 2
        assert "bad.yaml" in errors
        names = {a.name for a in valid}
        assert names == {"agent-one", "agent-two"}

    def test_empty_directory(self, tmp_path: Path) -> None:
        valid, errors = validate_agents_dir(tmp_path)
        assert valid == []
        assert errors == {}

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope"
        valid, errors = validate_agents_dir(missing)
        assert valid == []
        assert errors == {}

    def test_ignores_non_yaml_files(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path, "good.yaml", """\
            name: agent-one
            role: Tester
            prompt: "You test."
        """)
        (tmp_path / "readme.md").write_text("# Not YAML", encoding="utf-8")
        (tmp_path / "config.json").write_text("{}", encoding="utf-8")

        valid, errors = validate_agents_dir(tmp_path)
        assert len(valid) == 1
        assert errors == {}
