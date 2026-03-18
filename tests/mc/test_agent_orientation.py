"""Tests for MC Agent Skills-First Orientation.

Covers TaskExecutor._maybe_inject_orientation():
1. orientation injected for non-lead agents when file exists
2. orientation NOT injected for lead-agent
3. graceful no-op when orientation file is missing
4. orientation comes before agent's own prompt
5. orientation alone becomes prompt when agent has no config prompt
"""

from unittest.mock import MagicMock, patch


def _make_executor(bridge=None):
    from mc.contexts.execution.executor import TaskExecutor

    return TaskExecutor(bridge or MagicMock())


class TestMaybeInjectOrientation:
    def test_orientation_injected_for_non_lead_agent(self, tmp_path):
        """Orientation content is prepended for non-lead agents."""
        mc_dir = tmp_path / ".nanobot" / "mc"
        mc_dir.mkdir(parents=True)
        (mc_dir / "agent-orientation.md").write_text("use your skills", encoding="utf-8")
        executor = _make_executor()
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = executor._maybe_inject_orientation("youtube-summarizer", "agent prompt")
        assert result is not None
        assert "use your skills" in result
        assert "agent prompt" in result

    def test_orientation_not_injected_for_lead_agent(self, tmp_path):
        """lead-agent is exempt from the global orientation."""
        mc_dir = tmp_path / ".nanobot" / "mc"
        mc_dir.mkdir(parents=True)
        (mc_dir / "agent-orientation.md").write_text("use your skills", encoding="utf-8")
        executor = _make_executor()
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = executor._maybe_inject_orientation("lead-agent", "lead-agent prompt")
        assert result == "lead-agent prompt"
        assert "use your skills" not in (result or "")

    def test_no_error_when_orientation_file_missing(self, tmp_path):
        """No orientation file -> returns original prompt unchanged, no exception."""
        executor = _make_executor()
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = executor._maybe_inject_orientation("some-agent", "my prompt")
        assert result == "my prompt"

    def test_orientation_prepended_before_agent_prompt(self, tmp_path):
        """Orientation must come BEFORE the agent's own prompt."""
        mc_dir = tmp_path / ".nanobot" / "mc"
        mc_dir.mkdir(parents=True)
        (mc_dir / "agent-orientation.md").write_text("ORIENTATION", encoding="utf-8")
        executor = _make_executor()
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = executor._maybe_inject_orientation("agent", "AGENT_PROMPT")
        assert result is not None
        assert result.index("ORIENTATION") < result.index("AGENT_PROMPT")

    def test_orientation_becomes_prompt_when_no_agent_prompt(self, tmp_path):
        """If agent has no config.yaml prompt, orientation alone becomes the prompt."""
        mc_dir = tmp_path / ".nanobot" / "mc"
        mc_dir.mkdir(parents=True)
        (mc_dir / "agent-orientation.md").write_text("rules", encoding="utf-8")
        executor = _make_executor()
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = executor._maybe_inject_orientation("agent", None)
        assert result == "rules"

    def test_empty_orientation_file_returns_prompt_unchanged(self, tmp_path):
        """Empty orientation file -> returns original prompt unchanged."""
        mc_dir = tmp_path / ".nanobot" / "mc"
        mc_dir.mkdir(parents=True)
        (mc_dir / "agent-orientation.md").write_text("", encoding="utf-8")
        executor = _make_executor()
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = executor._maybe_inject_orientation("worker", "my prompt")
        assert result == "my prompt"

    def test_whitespace_only_orientation_file_returns_prompt_unchanged(self, tmp_path):
        """Whitespace-only orientation file -> returns original prompt unchanged."""
        mc_dir = tmp_path / ".nanobot" / "mc"
        mc_dir.mkdir(parents=True)
        (mc_dir / "agent-orientation.md").write_text("   \n\n  ", encoding="utf-8")
        executor = _make_executor()
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = executor._maybe_inject_orientation("worker", "my prompt")
        assert result == "my prompt"

    def test_empty_string_agent_prompt_treated_as_no_prompt(self, tmp_path):
        """Empty string agent_prompt is falsy — orientation alone becomes the prompt."""
        mc_dir = tmp_path / ".nanobot" / "mc"
        mc_dir.mkdir(parents=True)
        (mc_dir / "agent-orientation.md").write_text("rules", encoding="utf-8")
        executor = _make_executor()
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = executor._maybe_inject_orientation("worker", "")
        assert result == "rules"

    def test_exact_separator_format(self, tmp_path):
        """Verify the exact separator format: orientation + \\n\\n---\\n\\n + agent prompt."""
        mc_dir = tmp_path / ".nanobot" / "mc"
        mc_dir.mkdir(parents=True)
        (mc_dir / "agent-orientation.md").write_text("O", encoding="utf-8")
        executor = _make_executor()
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = executor._maybe_inject_orientation("worker", "P")
        assert result == "O\n\n---\n\nP"
