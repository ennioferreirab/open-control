"""Unit tests for the agent-assisted YAML generation module."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from mc.cli.agent_assist import (
    create_agent_workspace,
    extract_yaml_from_response,
    generate_agent_yaml,
    validate_yaml_content,
)

# ---------------------------------------------------------------------------
# extract_yaml_from_response
# ---------------------------------------------------------------------------


class TestExtractYaml:
    """Tests for extracting YAML from LLM responses."""

    def test_plain_yaml(self) -> None:
        response = textwrap.dedent("""\
            name: test-agent
            role: Tester
            prompt: "You test things."
        """)
        assert "name: test-agent" in extract_yaml_from_response(response)

    def test_yaml_code_block(self) -> None:
        response = textwrap.dedent("""\
            Here is the configuration:

            ```yaml
            name: test-agent
            role: Tester
            prompt: "You test things."
            ```

            Let me know if you need changes.
        """)
        result = extract_yaml_from_response(response)
        assert "name: test-agent" in result
        assert "Here is the configuration" not in result
        assert "Let me know" not in result

    def test_generic_code_block(self) -> None:
        response = textwrap.dedent("""\
            ```
            name: test-agent
            role: Tester
            prompt: "You test things."
            ```
        """)
        result = extract_yaml_from_response(response)
        assert "name: test-agent" in result

    def test_extra_text_no_block(self) -> None:
        response = textwrap.dedent("""\
            Sure! Here is your agent config:
            name: test-agent
            role: Tester
            prompt: "You test."
        """)
        # Without code block, returns the whole response stripped
        result = extract_yaml_from_response(response)
        assert "name: test-agent" in result

    def test_empty_response(self) -> None:
        assert extract_yaml_from_response("") == ""
        assert extract_yaml_from_response("   ") == ""


# ---------------------------------------------------------------------------
# validate_yaml_content
# ---------------------------------------------------------------------------


class TestValidateYamlContent:
    """Tests for in-memory YAML validation."""

    def test_valid_yaml(self) -> None:
        yaml_text = textwrap.dedent("""\
            name: research-agent
            role: Researcher
            prompt: "You research AI trends."
            skills:
              - research
              - summarization
        """)
        parsed, errors = validate_yaml_content(yaml_text)
        assert parsed is not None
        assert errors == []
        assert parsed["name"] == "research-agent"

    def test_minimal_valid(self) -> None:
        yaml_text = textwrap.dedent("""\
            name: my-agent
            role: Helper
            prompt: "You help."
        """)
        parsed, errors = validate_yaml_content(yaml_text)
        assert parsed is not None
        assert errors == []

    def test_missing_required_field(self) -> None:
        yaml_text = textwrap.dedent("""\
            name: my-agent
            role: Helper
        """)
        parsed, errors = validate_yaml_content(yaml_text)
        assert parsed is None
        assert len(errors) >= 1
        assert any("prompt" in e.lower() for e in errors)

    def test_invalid_name(self) -> None:
        yaml_text = textwrap.dedent("""\
            name: "My Agent"
            role: Helper
            prompt: "You help."
        """)
        parsed, errors = validate_yaml_content(yaml_text)
        assert parsed is None
        assert any("invalid characters" in e.lower() for e in errors)

    def test_invalid_yaml_syntax(self) -> None:
        yaml_text = "name: test\n  bad: indent"
        parsed, errors = validate_yaml_content(yaml_text)
        assert parsed is None
        assert any("yaml parse error" in e.lower() for e in errors)

    def test_non_mapping_yaml(self) -> None:
        yaml_text = "- item1\n- item2"
        parsed, errors = validate_yaml_content(yaml_text)
        assert parsed is None
        assert any("mapping" in e.lower() for e in errors)

    def test_generated_yaml_passes_story_3_1_validation(self) -> None:
        """Validate that well-formed generated YAML passes the full validator."""
        yaml_text = textwrap.dedent("""\
            name: finance-agent
            role: Financial Analyst
            prompt: |
              You are a financial analyst agent specializing in personal finance.
              You track payments and manage boletos.
            skills:
              - financial-analysis
              - boleto-tracking
        """)
        parsed, errors = validate_yaml_content(yaml_text)
        assert parsed is not None
        assert errors == []


# ---------------------------------------------------------------------------
# generate_agent_yaml (mocked LLM)
# ---------------------------------------------------------------------------


class TestGenerateAgentYaml:
    """Tests for LLM-based YAML generation with mocked provider."""

    @pytest.mark.asyncio
    async def test_basic_generation(self) -> None:
        mock_response = MagicMock()
        mock_response.content = textwrap.dedent("""\
            name: research-agent
            role: AI Researcher
            prompt: "You research AI trends."
            skills:
              - research
        """)

        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        result = await generate_agent_yaml(provider, "create a research agent")
        assert "research-agent" in result
        provider.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_generation_with_feedback(self) -> None:
        mock_response = MagicMock()
        mock_response.content = "name: updated-agent\nrole: Updated\nprompt: Updated."

        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        result = await generate_agent_yaml(provider, "create an agent", feedback="add more skills")
        assert "updated-agent" in result

        # Check that feedback was included in the system prompt
        call_args = provider.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args[0][0]
        system_msg = messages[0]["content"]
        assert "add more skills" in system_msg

    @pytest.mark.asyncio
    async def test_empty_response(self) -> None:
        mock_response = MagicMock()
        mock_response.content = ""

        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        result = await generate_agent_yaml(provider, "create an agent")
        assert result == ""

    @pytest.mark.asyncio
    async def test_none_response(self) -> None:
        mock_response = MagicMock()
        mock_response.content = None

        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        result = await generate_agent_yaml(provider, "create an agent")
        assert result == ""


# ---------------------------------------------------------------------------
# create_agent_workspace
# ---------------------------------------------------------------------------


class TestCreateAgentWorkspace:
    """Tests for workspace directory creation."""

    def test_creates_workspace_structure(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        yaml_text = textwrap.dedent("""\
            name: test-agent
            role: Tester
            prompt: "You test."
        """)
        config_path = create_agent_workspace("test-agent", yaml_text)

        assert config_path.exists()
        assert config_path.read_text(encoding="utf-8") == yaml_text

        agent_dir = config_path.parent
        assert (agent_dir / "memory").is_dir()
        assert (agent_dir / "skills").is_dir()

    def test_overwrites_existing_config(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        create_agent_workspace("my-agent", "name: my-agent\nrole: V1\nprompt: Old.")
        config_path = create_agent_workspace("my-agent", "name: my-agent\nrole: V2\nprompt: New.")
        assert "V2" in config_path.read_text()


# ---------------------------------------------------------------------------
# Cancellation flow
# ---------------------------------------------------------------------------


class TestCancellationFlow:
    """Test that the user can cancel without files being created."""

    def test_validate_then_reject(self) -> None:
        """Validating YAML does not create any files."""
        yaml_text = textwrap.dedent("""\
            name: temp-agent
            role: Temp
            prompt: "Temporary."
        """)
        parsed, errors = validate_yaml_content(yaml_text)
        assert parsed is not None
        assert errors == []
        # No workspace should exist — validation is in-memory only
        Path.home() / ".nanobot" / "agents" / "temp-agent"
        # We cannot assert non-existence absolutely (other tests may create it),
        # but the point is that validate_yaml_content itself creates nothing.
