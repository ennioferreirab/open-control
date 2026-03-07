"""Tests for roster_builder module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mc.application.execution.roster_builder import (
    inject_orientation,
    resolve_tier,
    sync_agent_from_convex,
)


class TestSyncAgentFromConvex:
    """Tests for sync_agent_from_convex."""

    def test_none_convex_agent_returns_original(self) -> None:
        prompt, model, skills = sync_agent_from_convex(
            "test-agent", "yaml prompt", "gpt-4", ["code"], None
        )
        assert prompt == "yaml prompt"
        assert model == "gpt-4"
        assert skills == ["code"]

    def test_convex_prompt_overrides_yaml(self) -> None:
        convex = {"prompt": "convex prompt"}
        prompt, _, _ = sync_agent_from_convex(
            "test-agent", "yaml prompt", None, None, convex
        )
        assert prompt == "convex prompt"

    def test_convex_model_overrides_yaml(self) -> None:
        convex = {"model": "gpt-5"}
        _, model, _ = sync_agent_from_convex(
            "test-agent", None, "gpt-4", None, convex
        )
        assert model == "gpt-5"

    def test_convex_skills_overrides_yaml(self) -> None:
        convex = {"skills": ["write", "review"]}
        _, _, skills = sync_agent_from_convex(
            "test-agent", None, None, ["code"], convex
        )
        assert skills == ["write", "review"]

    def test_variable_interpolation(self) -> None:
        convex = {
            "prompt": "Hello {{name}}, your role is {{role}}",
            "variables": [
                {"name": "name", "value": "Alice"},
                {"name": "role", "value": "developer"},
            ],
        }
        prompt, _, _ = sync_agent_from_convex(
            "test-agent", None, None, None, convex
        )
        assert prompt == "Hello Alice, your role is developer"

    def test_empty_variables_no_error(self) -> None:
        convex = {"prompt": "Hello {{name}}", "variables": []}
        prompt, _, _ = sync_agent_from_convex(
            "test-agent", None, None, None, convex
        )
        assert prompt == "Hello {{name}}"

    def test_convex_empty_prompt_keeps_yaml(self) -> None:
        convex = {"prompt": ""}
        prompt, _, _ = sync_agent_from_convex(
            "test-agent", "yaml prompt", None, None, convex
        )
        # Empty string is falsy, so yaml prompt is kept
        assert prompt == "yaml prompt"

    def test_convex_none_skills_keeps_yaml(self) -> None:
        convex = {}  # no "skills" key at all
        _, _, skills = sync_agent_from_convex(
            "test-agent", None, None, ["code"], convex
        )
        assert skills == ["code"]


class TestInjectOrientation:
    """Tests for inject_orientation."""

    @patch("mc.infrastructure.orientation.load_orientation")
    def test_no_orientation_returns_original(self, mock_load: MagicMock) -> None:
        mock_load.return_value = None
        result = inject_orientation("test-agent", "my prompt")
        assert result == "my prompt"

    @patch("mc.infrastructure.orientation.load_orientation")
    def test_orientation_prepended(self, mock_load: MagicMock) -> None:
        mock_load.return_value = "Global rules"
        result = inject_orientation("test-agent", "my prompt")
        assert result is not None
        assert result.startswith("Global rules")
        assert "---" in result
        assert "my prompt" in result

    @patch("mc.infrastructure.orientation.load_orientation")
    def test_orientation_with_no_prompt(self, mock_load: MagicMock) -> None:
        mock_load.return_value = "Global rules"
        result = inject_orientation("test-agent", None)
        assert result == "Global rules"


class TestResolveTier:
    """Tests for resolve_tier."""

    def test_non_tier_model_passes_through(self) -> None:
        resolver = MagicMock()
        model, reasoning = resolve_tier("gpt-4", resolver)
        assert model == "gpt-4"
        assert reasoning is None
        resolver.resolve_model.assert_not_called()

    def test_none_model_passes_through(self) -> None:
        resolver = MagicMock()
        model, reasoning = resolve_tier(None, resolver)
        assert model is None
        assert reasoning is None

    def test_tier_reference_resolved(self) -> None:
        resolver = MagicMock()
        resolver.resolve_model.return_value = "gpt-4o"
        resolver.resolve_reasoning_level.return_value = "high"
        model, reasoning = resolve_tier("tier:standard-high", resolver)
        assert model == "gpt-4o"
        assert reasoning == "high"
        resolver.resolve_model.assert_called_once_with("tier:standard-high")

    def test_tier_resolution_failure_raises(self) -> None:
        resolver = MagicMock()
        resolver.resolve_model.side_effect = ValueError("Unknown tier")
        with pytest.raises(ValueError, match="Unknown tier"):
            resolve_tier("tier:unknown", resolver)
