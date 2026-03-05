"""Unit tests for claude_code.workspace.CCWorkspaceManager."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from claude_code.workspace import CCWorkspaceManager
from mc.types import AgentData
from claude_code.types import WorkspaceContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(
    name: str = "test-agent",
    role: str = "Tester",
    prompt: str = "You are a test agent.",
    soul: str | None = None,
    skills: list[str] | None = None,
) -> AgentData:
    return AgentData(
        name=name,
        display_name=name.replace("-", " ").title(),
        role=role,
        prompt=prompt,
        soul=soul,
        skills=skills or [],
        backend="claude-code",
    )


# ---------------------------------------------------------------------------
# WorkspaceContext structure
# ---------------------------------------------------------------------------

class TestWorkspaceContext:
    def test_correct_paths_returned(self, tmp_path: Path) -> None:
        """prepare() returns WorkspaceContext with correct paths."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare("test-agent", agent, "task123")

        expected_workspace = tmp_path / "agents" / "test-agent"
        assert ctx.cwd == expected_workspace
        assert ctx.mcp_config == expected_workspace / ".mcp.json"
        assert ctx.claude_md == expected_workspace / "CLAUDE.md"
        assert ctx.socket_path == "/tmp/mc-test-agent-task123.sock"

    def test_returns_workspace_context_type(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare("test-agent", agent, "task123")
        assert isinstance(ctx, WorkspaceContext)


# ---------------------------------------------------------------------------
# Directory structure
# ---------------------------------------------------------------------------

class TestDirectoryStructure:
    def test_creates_workspace_directory(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare("test-agent", agent, "task123")
        assert ctx.cwd.is_dir()

    def test_creates_memory_directory(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare("test-agent", agent, "task123")
        assert (ctx.cwd / "memory").is_dir()

    def test_creates_sessions_directory(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare("test-agent", agent, "task123")
        assert (ctx.cwd / "sessions").is_dir()

    def test_memory_and_sessions_preserved_on_second_prepare(self, tmp_path: Path) -> None:
        """AC5: memory/ and sessions/ directories are never touched on subsequent prepare()."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()

        ctx = manager.prepare("test-agent", agent, "task1")

        # Write sentinel files into memory/ and sessions/
        memory_file = ctx.cwd / "memory" / "test.txt"
        sessions_file = ctx.cwd / "sessions" / "session.dat"
        memory_file.write_text("preserved memory")
        sessions_file.write_text("preserved session")

        # Second prepare() must not remove these files
        manager.prepare("test-agent", agent, "task2")

        assert memory_file.exists(), "memory/test.txt was deleted by prepare()"
        assert memory_file.read_text() == "preserved memory"
        assert sessions_file.exists(), "sessions/session.dat was deleted by prepare()"
        assert sessions_file.read_text() == "preserved session"


# ---------------------------------------------------------------------------
# CLAUDE.md generation (AC1)
# ---------------------------------------------------------------------------

class TestClaudeMdGeneration:
    def test_claude_md_contains_agent_prompt(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent(prompt="You are a specialized test agent.")
        ctx = manager.prepare("test-agent", agent, "task123")

        content = ctx.claude_md.read_text()
        assert "You are a specialized test agent." in content

    def test_claude_md_contains_mcp_tools_guide(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare("test-agent", agent, "task123")

        content = ctx.claude_md.read_text()
        assert "mcp__nanobot__ask_user" in content
        assert "mcp__nanobot__send_message" in content
        assert "mcp__nanobot__delegate_task" in content
        assert "mcp__nanobot__ask_agent" in content
        assert "mcp__nanobot__report_progress" in content

    def test_claude_md_contains_ask_user_warning(self, tmp_path: Path) -> None:
        """The IMPORTANT warning about AskUserQuestion must be present."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare("test-agent", agent, "task123")

        content = ctx.claude_md.read_text()
        assert "AskUserQuestion" in content
        assert "does NOT work" in content

    def test_claude_md_contains_conventions_section(self, tmp_path: Path) -> None:
        """AC1: CLAUDE.md must include a Project Conventions section."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare("test-agent", agent, "task123")

        content = ctx.claude_md.read_text()
        assert "## Project Conventions" in content

    def test_claude_md_contains_soul_when_present(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent(soul="## Soul\n\nI am deeply thoughtful.")
        ctx = manager.prepare("test-agent", agent, "task123")

        content = ctx.claude_md.read_text()
        assert "I am deeply thoughtful." in content

    def test_claude_md_no_soul_section_when_absent(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent(soul=None)
        ctx = manager.prepare("test-agent", agent, "task123")

        content = ctx.claude_md.read_text()
        # Soul content block must not appear when soul is absent
        assert "## Soul" not in content
        assert ctx.claude_md.exists()
        assert agent.name in content

    def test_claude_md_contains_agent_identity(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent(name="my-agent", role="Senior Developer")
        ctx = manager.prepare("my-agent", agent, "task123")

        content = ctx.claude_md.read_text()
        assert "my-agent" in content
        assert "Senior Developer" in content

    def test_claude_md_overwritten_on_second_call(self, tmp_path: Path) -> None:
        """CLAUDE.md is overwritten if it already exists."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent1 = _make_agent(prompt="First prompt.")
        manager.prepare("test-agent", agent1, "task1")

        agent2 = _make_agent(prompt="Second prompt.")
        ctx = manager.prepare("test-agent", agent2, "task2")

        content = ctx.claude_md.read_text()
        assert "Second prompt." in content
        assert "First prompt." not in content


# ---------------------------------------------------------------------------
# Skills mapping (AC2)
# ---------------------------------------------------------------------------

class TestSkillsMapping:
    def test_symlink_created_for_existing_skill(self, tmp_path: Path) -> None:
        """A symlink is created in .claude/skills/ for a skill found in workspace/skills/."""
        # Create a mock skill in the workspace skills directory
        workspace = tmp_path / "agents" / "test-agent"
        skill_dir = workspace / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# My Skill")

        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent(skills=["my-skill"])
        manager.prepare("test-agent", agent, "task123")

        link = workspace / ".claude" / "skills" / "my-skill"
        assert link.is_symlink()
        assert link.resolve() == skill_dir.resolve()

    def test_global_skill_dir_used_as_fallback(self, tmp_path: Path) -> None:
        """Skills in root/workspace/skills/ are used when not in agent workspace."""
        global_skill_dir = tmp_path / "workspace" / "skills" / "global-skill"
        global_skill_dir.mkdir(parents=True)
        (global_skill_dir / "SKILL.md").write_text("# Global Skill")

        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent(skills=["global-skill"])
        ctx = manager.prepare("test-agent", agent, "task123")

        link = ctx.cwd / ".claude" / "skills" / "global-skill"
        assert link.is_symlink()

    def test_vendor_skills_dir_injectable(self, tmp_path: Path) -> None:
        """vendor_skills_dir constructor parameter is used as the builtin skills fallback."""
        vendor_dir = tmp_path / "vendor-skills"
        vendor_skill = vendor_dir / "vendor-skill"
        vendor_skill.mkdir(parents=True)
        (vendor_skill / "SKILL.md").write_text("# Vendor Skill")

        manager = CCWorkspaceManager(workspace_root=tmp_path, vendor_skills_dir=vendor_dir)
        agent = _make_agent(skills=["vendor-skill"])
        ctx = manager.prepare("test-agent", agent, "task123")

        link = ctx.cwd / ".claude" / "skills" / "vendor-skill"
        assert link.is_symlink()

    def test_broken_symlinks_cleaned_up(self, tmp_path: Path) -> None:
        """Pre-existing broken symlinks in .claude/skills/ are removed."""
        workspace = tmp_path / "agents" / "test-agent"
        skills_dir = workspace / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        # Create a broken symlink
        broken_link = skills_dir / "nonexistent-skill"
        broken_link.symlink_to(tmp_path / "does-not-exist")
        assert broken_link.is_symlink()
        assert not broken_link.resolve().exists()

        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent(skills=[])
        manager.prepare("test-agent", agent, "task123")

        assert not broken_link.exists()

    def test_missing_skill_logged_as_warning_not_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A skill that cannot be found is logged as WARNING, not raised as exception."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent(skills=["nonexistent-skill"])

        with caplog.at_level(logging.WARNING, logger="claude_code.workspace"):
            # Should NOT raise
            ctx = manager.prepare("test-agent", agent, "task123")

        assert ctx is not None
        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("nonexistent-skill" in msg for msg in warning_messages)

    def test_idempotent_skill_symlinks(self, tmp_path: Path) -> None:
        """Running prepare() twice with same skills doesn't error."""
        workspace = tmp_path / "agents" / "test-agent"
        skill_dir = workspace / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# My Skill")

        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent(skills=["my-skill"])

        manager.prepare("test-agent", agent, "task1")
        # Second call must not raise
        ctx = manager.prepare("test-agent", agent, "task2")

        link = ctx.cwd / ".claude" / "skills" / "my-skill"
        assert link.is_symlink()

    def test_invalid_skill_name_with_slash_skipped(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """C2: Skill names with '/' are rejected with a warning."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent(skills=["../../etc/passwd"])

        with caplog.at_level(logging.WARNING, logger="claude_code.workspace"):
            ctx = manager.prepare("test-agent", agent, "task123")

        assert ctx is not None
        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("../../etc/passwd" in msg for msg in warning_messages)
        # No symlink must have been created
        skills_dir = ctx.cwd / ".claude" / "skills"
        assert not any(skills_dir.iterdir()) if skills_dir.exists() else True

    def test_invalid_skill_name_with_dot_prefix_skipped(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """C2: Skill names starting with '.' are rejected with a warning."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent(skills=[".hidden-skill"])

        with caplog.at_level(logging.WARNING, logger="claude_code.workspace"):
            ctx = manager.prepare("test-agent", agent, "task123")

        assert ctx is not None
        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any(".hidden-skill" in msg for msg in warning_messages)


# ---------------------------------------------------------------------------
# MCP config generation (AC3)
# ---------------------------------------------------------------------------

class TestMcpConfigGeneration:
    def test_mcp_json_written(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare("test-agent", agent, "task123")
        assert ctx.mcp_config.exists()

    def test_mcp_json_structure(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare("my-agent", agent, "task-abc")

        data = json.loads(ctx.mcp_config.read_text())

        assert "mcpServers" in data
        assert "nanobot" in data["mcpServers"]
        server = data["mcpServers"]["nanobot"]

        assert server["command"] == "uv"
        assert server["args"] == ["run", "python", "-m", "claude_code.mcp_bridge"]
        assert "env" in server

    def test_mcp_json_env_vars(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare("my-agent", agent, "task-abc")

        data = json.loads(ctx.mcp_config.read_text())
        env = data["mcpServers"]["nanobot"]["env"]

        assert env["MC_SOCKET_PATH"] == "/tmp/mc-my-agent-task-abc.sock"
        assert env["AGENT_NAME"] == "my-agent"
        assert env["TASK_ID"] == "task-abc"

    def test_mcp_json_valid_json(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare("test-agent", agent, "task123")

        # json.loads will raise if invalid
        data = json.loads(ctx.mcp_config.read_text())
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Input validation (C1, H3)
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_invalid_agent_name_with_slash_raises(self, tmp_path: Path) -> None:
        """C1: agent_name containing '/' must raise ValueError."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        with pytest.raises(ValueError, match="Invalid agent name"):
            manager.prepare("../../etc/passwd", agent, "task123")

    def test_invalid_agent_name_dot_prefix_raises(self, tmp_path: Path) -> None:
        """C1: agent_name starting with '.' must raise ValueError."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        with pytest.raises(ValueError, match="Invalid agent name"):
            manager.prepare(".hidden", agent, "task123")

    def test_empty_agent_name_raises(self, tmp_path: Path) -> None:
        """C1: Empty agent_name must raise ValueError."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        with pytest.raises(ValueError, match="Invalid agent name"):
            manager.prepare("", agent, "task123")

    def test_socket_path_too_long_raises(self, tmp_path: Path) -> None:
        """H3: Agent name that produces a socket path >104 chars must raise ValueError."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        # "/tmp/mc-" is 8 chars, "-task123" is 8 chars, ".sock" is 5 chars,
        # total overhead = 21.  Need >104 total, so name must be >83 chars.
        long_name = "a" * 85
        with pytest.raises(ValueError, match="Socket path too long"):
            manager.prepare(long_name, agent, "task123")


# ---------------------------------------------------------------------------
# Idempotent preparation
# ---------------------------------------------------------------------------

class TestIdempotentPreparation:
    def test_prepare_twice_no_errors(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()

        ctx1 = manager.prepare("test-agent", agent, "task1")
        ctx2 = manager.prepare("test-agent", agent, "task2")

        assert ctx1.cwd == ctx2.cwd
        assert ctx2.claude_md.exists()
        assert ctx2.mcp_config.exists()

    def test_mcp_json_updated_on_second_call(self, tmp_path: Path) -> None:
        """The task_id in .mcp.json reflects the most recent prepare() call."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()

        manager.prepare("test-agent", agent, "task-first")
        ctx = manager.prepare("test-agent", agent, "task-second")

        data = json.loads(ctx.mcp_config.read_text())
        env = data["mcpServers"]["nanobot"]["env"]
        assert env["TASK_ID"] == "task-second"


# ---------------------------------------------------------------------------
# Skill availability check (via SkillsLoader)
# ---------------------------------------------------------------------------

class TestSkillAvailabilityCheck:
    """Verify that _map_skills() skips unavailable skills detected by SkillsLoader."""

    def _make_vendor_skill(self, vendor_dir: Path, skill_name: str, skill_md_content: str) -> Path:
        """Helper: create a skill directory under vendor_dir with given SKILL.md content."""
        skill_dir = vendor_dir / skill_name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(skill_md_content)
        return skill_dir

    def test_unavailable_skill_not_symlinked(self, tmp_path: Path) -> None:
        """A skill whose binary requirement is missing must NOT have its symlink created."""
        vendor_dir = tmp_path / "vendor-skills"
        self._make_vendor_skill(
            vendor_dir,
            "needs-nonexistent-bin",
            '---\nmetadata: \'{"nanobot":{"requires":{"bins":["__nonexistent_binary_xyz__"]}}}\'\n---\n# Skill\n',
        )

        manager = CCWorkspaceManager(workspace_root=tmp_path, vendor_skills_dir=vendor_dir)
        agent = _make_agent(skills=["needs-nonexistent-bin"])
        ctx = manager.prepare("test-agent", agent, "task123")

        link = ctx.cwd / ".claude" / "skills" / "needs-nonexistent-bin"
        assert not link.exists(), "Symlink must not be created for an unavailable skill"
        assert not link.is_symlink(), "Broken symlink must not be created for an unavailable skill"

    def test_available_skill_still_symlinked(self, tmp_path: Path) -> None:
        """A skill with no requirements (always available) must have its symlink created normally."""
        vendor_dir = tmp_path / "vendor-skills"
        self._make_vendor_skill(
            vendor_dir,
            "no-requirements-skill",
            "# No Requirements Skill\n\nThis skill has no special requirements.\n",
        )

        manager = CCWorkspaceManager(workspace_root=tmp_path, vendor_skills_dir=vendor_dir)
        agent = _make_agent(skills=["no-requirements-skill"])
        ctx = manager.prepare("test-agent", agent, "task123")

        link = ctx.cwd / ".claude" / "skills" / "no-requirements-skill"
        assert link.is_symlink(), "Symlink must be created for an available skill"

    def test_unavailable_skill_logged_as_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Skipping an unavailable skill must produce a WARNING log with the skill name and 'unavailable'."""
        vendor_dir = tmp_path / "vendor-skills"
        self._make_vendor_skill(
            vendor_dir,
            "missing-binary-skill",
            '---\nmetadata: \'{"nanobot":{"requires":{"bins":["__nonexistent_binary_xyz__"]}}}\'\n---\n# Skill\n',
        )

        manager = CCWorkspaceManager(workspace_root=tmp_path, vendor_skills_dir=vendor_dir)
        agent = _make_agent(skills=["missing-binary-skill"])

        with caplog.at_level(logging.WARNING, logger="claude_code.workspace"):
            manager.prepare("test-agent", agent, "task123")

        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "missing-binary-skill" in msg and "unavailable" in msg
            for msg in warning_messages
        ), f"Expected WARNING containing 'missing-binary-skill' and 'unavailable', got: {warning_messages}"


class TestBoardScopedWorkspace:
    """Tests for board-scoped workspace isolation."""

    def test_board_scoped_workspace_uses_board_path(self, tmp_path: Path) -> None:
        """When board_name is provided, workspace root is under boards/{board}/agents/{agent}/."""
        from unittest.mock import patch

        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()

        board_workspace = tmp_path / "boards" / "myboard" / "agents" / "test-agent"
        board_workspace.mkdir(parents=True, exist_ok=True)
        (board_workspace / "memory").mkdir()
        (board_workspace / "sessions").mkdir()

        # Patch at the source module (mc.board_utils) rather than claude_code.workspace,
        # because workspace.py uses a deferred `from mc.board_utils import …` inside
        # prepare(), so Python re-resolves the name from mc.board_utils on every call.
        # If workspace.py ever hoists the import to module level, the target must change
        # to "claude_code.workspace.resolve_board_workspace".
        with patch("mc.board_utils.resolve_board_workspace", return_value=board_workspace) as mock_resolve:
            ctx = manager.prepare("test-agent", agent, "task123", board_name="myboard", memory_mode="clean")

        mock_resolve.assert_called_once_with("myboard", "test-agent", mode="clean")
        assert ctx.cwd == board_workspace

    def test_no_board_uses_global_path(self, tmp_path: Path) -> None:
        """Without board_name, workspace stays at agents/{agent}/."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare("test-agent", agent, "task123")
        assert ctx.cwd == tmp_path / "agents" / "test-agent"

    def test_with_history_mode_passed_to_board_utils(self, tmp_path: Path) -> None:
        """memory_mode='with_history' is forwarded to resolve_board_workspace."""
        from unittest.mock import patch

        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()

        board_workspace = tmp_path / "boards" / "projboard" / "agents" / "test-agent"
        board_workspace.mkdir(parents=True, exist_ok=True)
        (board_workspace / "memory").mkdir()
        (board_workspace / "sessions").mkdir()

        # See patch-target note in test_board_scoped_workspace_uses_board_path.
        with patch("mc.board_utils.resolve_board_workspace", return_value=board_workspace) as mock_resolve:
            manager.prepare("test-agent", agent, "task123", board_name="projboard", memory_mode="with_history")

        mock_resolve.assert_called_once_with("projboard", "test-agent", mode="with_history")

    def test_board_workspace_generates_claude_md(self, tmp_path: Path) -> None:
        """Board-scoped workspace still generates CLAUDE.md correctly."""
        from unittest.mock import patch

        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent(prompt="Board agent prompt.")

        board_workspace = tmp_path / "boards" / "b1" / "agents" / "test-agent"
        board_workspace.mkdir(parents=True, exist_ok=True)
        (board_workspace / "memory").mkdir()
        (board_workspace / "sessions").mkdir()

        # See patch-target note in test_board_scoped_workspace_uses_board_path.
        with patch("mc.board_utils.resolve_board_workspace", return_value=board_workspace):
            ctx = manager.prepare("test-agent", agent, "task999", board_name="b1")

        claude_md = board_workspace / "CLAUDE.md"
        assert claude_md.exists()
        assert "Board agent prompt." in claude_md.read_text()
