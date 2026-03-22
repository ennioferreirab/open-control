"""Unit tests for claude_code.workspace.CCWorkspaceManager."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from claude_code.types import WorkspaceContext
from claude_code.workspace import CCWorkspaceManager

from mc.types import AgentData

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


def _write_nanobot_config(home: Path, data: dict) -> None:
    config_path = home / ".nanobot" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(data), encoding="utf-8")


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
        assert "mcp__mc__ask_user" in content
        assert "mcp__mc__send_message" in content
        assert "mcp__mc__delegate_task" in content
        assert "mcp__mc__ask_agent" in content

    def test_claude_md_contains_ask_user_warning(self, tmp_path: Path) -> None:
        """The IMPORTANT warning about AskUserQuestion must be present."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare("test-agent", agent, "task123")

        content = ctx.claude_md.read_text()
        assert "structured questions array" in content
        assert "free-text fallback" in content

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

    def test_prepare_writes_claude_hook_settings_for_interactive_sessions(
        self, tmp_path: Path
    ) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()

        ctx = manager.prepare(
            "test-agent",
            agent,
            "task123",
            interactive_session_id="interactive_session:claude",
        )

        settings_path = ctx.cwd / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        hooks = settings["hooks"]

        assert "SessionStart" in hooks
        assert "Stop" in hooks
        assert "PermissionRequest" in hooks
        command = hooks["Stop"][0]["hooks"][0]["command"]
        assert "claude_code.hook_bridge" in command
        assert "MC_INTERACTIVE_SESSION_ID=interactive_session:claude" in command


# ---------------------------------------------------------------------------
# Task 2: Operator visibility for the transitional Claude step path (Story 28.0c)
# ---------------------------------------------------------------------------


class TestSessionObservability:
    """Pin that a running Claude interactive session is observable/intervenable.

    These tests document the visibility contract for the transitional runtime
    path (pre-provider-CLI). Story 28.2 is the canonical cutover.
    """

    def test_session_is_observable_via_hook_settings_when_session_id_is_present(
        self, tmp_path: Path
    ) -> None:
        """When interactive_session_id is provided, all lifecycle hooks are wired.

        This ensures Mission Control can observe the session lifecycle (start, stop,
        permission requests, tool use) and intervene via the hook bridge.
        """
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()

        ctx = manager.prepare(
            "test-agent",
            agent,
            "task123",
            interactive_session_id="interactive_session:claude-code:agent:step:step-1:step",
        )

        settings_path = ctx.cwd / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        hooks = settings["hooks"]

        # All observable lifecycle events must be present.
        assert "SessionStart" in hooks, "SessionStart hook required for session observability"
        assert "Stop" in hooks, "Stop hook required for session lifecycle tracking"
        assert "PermissionRequest" in hooks, "PermissionRequest hook enables intervention"
        assert "UserPromptSubmit" in hooks, "UserPromptSubmit hook required for activity feed"
        assert "PreToolUse" in hooks, "PreToolUse hook required for tool activity visibility"
        assert "PostToolUse" in hooks, "PostToolUse hook required for tool result visibility"

    def test_session_hook_command_embeds_session_id_for_routing(self, tmp_path: Path) -> None:
        """The hook command must embed the session ID so events are routed to the right session."""
        session_id = "interactive_session:claude-code:myagent:step:step-42:step"
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()

        ctx = manager.prepare(
            "myagent",
            agent,
            "task-99",
            interactive_session_id=session_id,
        )

        settings_path = ctx.cwd / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        hooks = settings["hooks"]

        # Every hook command must embed the session ID for correct event routing.
        session_hook_command = hooks["SessionStart"][0]["hooks"][0]["command"]
        assert f"MC_INTERACTIVE_SESSION_ID={session_id}" in session_hook_command
        stop_hook_command = hooks["Stop"][0]["hooks"][0]["command"]
        assert f"MC_INTERACTIVE_SESSION_ID={session_id}" in stop_hook_command

    def test_session_hook_command_embeds_task_id_for_routing(self, tmp_path: Path) -> None:
        """The hook command must embed task_id so the bridge can route events back to the task."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()

        ctx = manager.prepare(
            "test-agent",
            agent,
            "task-abc-123",
            interactive_session_id="interactive_session:claude",
        )

        settings_path = ctx.cwd / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        hooks = settings["hooks"]

        hook_command = hooks["SessionStart"][0]["hooks"][0]["command"]
        assert "TASK_ID=task-abc-123" in hook_command

    def test_session_without_interactive_id_produces_empty_hooks(self, tmp_path: Path) -> None:
        """When no interactive_session_id is given, no hooks are wired.

        Headless step execution (non-interactive) does not require lifecycle hooks
        since supervision goes through the IPC socket directly.
        """
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()

        ctx = manager.prepare(
            "test-agent",
            agent,
            "task123",
            interactive_session_id=None,
        )

        settings_path = ctx.cwd / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        hooks = settings["hooks"]

        assert hooks == {}, (
            "Without interactive_session_id, hooks must be empty — "
            "lifecycle tracking is only required for interactive sessions."
        )

    def test_mcp_socket_path_is_embedded_in_hook_command(self, tmp_path: Path) -> None:
        """The IPC socket path must appear in the hook command for the bridge to connect."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()

        ctx = manager.prepare(
            "test-agent",
            agent,
            "task123",
            interactive_session_id="interactive_session:claude",
        )

        settings_path = ctx.cwd / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        hooks = settings["hooks"]

        hook_command = hooks["SessionStart"][0]["hooks"][0]["command"]
        # The socket path must be embedded so the hook bridge knows where to connect.
        assert "MC_SOCKET_PATH=/tmp/mc-test-agent-task123.sock" in hook_command


# ---------------------------------------------------------------------------
# Skills mapping (AC2)
# ---------------------------------------------------------------------------


class TestSkillsMapping:
    def test_skill_copied_for_existing_skill(self, tmp_path: Path) -> None:
        """A copy is created in .claude/skills/ for a skill found in workspace/skills/."""
        # Create a mock skill in the workspace skills directory
        workspace = tmp_path / "agents" / "test-agent"
        skill_dir = workspace / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# My Skill")

        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent(skills=["my-skill"])
        manager.prepare("test-agent", agent, "task123")

        dest = workspace / ".claude" / "skills" / "my-skill"
        assert dest.is_dir()
        assert not dest.is_symlink(), "Must be a real copy, not a symlink"
        assert (dest / "SKILL.md").read_text() == "# My Skill"

    def test_global_skill_dir_used_as_fallback(self, tmp_path: Path) -> None:
        """Skills in root/workspace/skills/ are used when not in agent workspace."""
        global_skill_dir = tmp_path / "workspace" / "skills" / "global-skill"
        global_skill_dir.mkdir(parents=True)
        (global_skill_dir / "SKILL.md").write_text("# Global Skill")

        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent(skills=["global-skill"])
        ctx = manager.prepare("test-agent", agent, "task123")

        dest = ctx.cwd / ".claude" / "skills" / "global-skill"
        assert dest.is_dir()
        assert (dest / "SKILL.md").read_text() == "# Global Skill"

    def test_vendor_skills_dir_injectable(self, tmp_path: Path) -> None:
        """vendor_skills_dir constructor parameter is used as the builtin skills fallback."""
        vendor_dir = tmp_path / "vendor-skills"
        vendor_skill = vendor_dir / "vendor-skill"
        vendor_skill.mkdir(parents=True)
        (vendor_skill / "SKILL.md").write_text("# Vendor Skill")

        manager = CCWorkspaceManager(workspace_root=tmp_path, vendor_skills_dir=vendor_dir)
        agent = _make_agent(skills=["vendor-skill"])
        ctx = manager.prepare("test-agent", agent, "task123")

        dest = ctx.cwd / ".claude" / "skills" / "vendor-skill"
        assert dest.is_dir()
        assert (dest / "SKILL.md").read_text() == "# Vendor Skill"

    def test_legacy_symlinks_cleaned_up(self, tmp_path: Path) -> None:
        """Pre-existing symlinks in .claude/skills/ are removed (migration from old code)."""
        workspace = tmp_path / "agents" / "test-agent"
        skills_dir = workspace / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        # Create a legacy symlink (broken or not — both get removed)
        broken_link = skills_dir / "nonexistent-skill"
        broken_link.symlink_to(tmp_path / "does-not-exist")
        assert broken_link.is_symlink()

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

    def test_idempotent_skill_copies(self, tmp_path: Path) -> None:
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

        dest = ctx.cwd / ".claude" / "skills" / "my-skill"
        assert dest.is_dir()
        assert (dest / "SKILL.md").read_text() == "# My Skill"

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
        assert "openmc" in data["mcpServers"]
        server = data["mcpServers"]["openmc"]

        assert server["command"] == "uv"
        assert server["args"] == ["run", "python", "-m", "mc.runtime.mcp.bridge"]
        assert "env" in server

    def test_mcp_json_env_vars(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare("my-agent", agent, "task-abc")

        data = json.loads(ctx.mcp_config.read_text())
        env = data["mcpServers"]["openmc"]["env"]

        assert env["MC_SOCKET_PATH"] == "/tmp/mc-my-agent-task-abc.sock"
        assert env["AGENT_NAME"] == "my-agent"
        assert env["TASK_ID"] == "task-abc"

    def test_mcp_json_includes_interactive_session_id_when_present(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare(
            "my-agent",
            agent,
            "task-abc",
            interactive_session_id="interactive_session:claude",
        )

        data = json.loads(ctx.mcp_config.read_text())
        env = data["mcpServers"]["openmc"]["env"]

        assert env["MC_INTERACTIVE_SESSION_ID"] == "interactive_session:claude"

    def test_mcp_json_includes_explicit_memory_workspace(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        board_workspace = tmp_path / "boards" / "default" / "agents" / "my-agent"
        board_workspace.mkdir(parents=True, exist_ok=True)
        (board_workspace / "memory").mkdir()
        (board_workspace / "sessions").mkdir()

        with patch(
            "mc.infrastructure.boards.resolve_board_workspace", return_value=board_workspace
        ):
            ctx = manager.prepare(
                "my-agent",
                agent,
                "task-abc",
                board_name="default",
                memory_mode="with_history",
            )

        data = json.loads(ctx.mcp_config.read_text())
        env = data["mcpServers"]["openmc"]["env"]

        expected_memory_workspace = tmp_path / "agents" / "my-agent"
        assert env["MEMORY_WORKSPACE"] == str(expected_memory_workspace)
        assert env["BOARD_NAME"] == "default"

    def test_claude_md_loads_memory_from_effective_shared_workspace(self, tmp_path: Path) -> None:
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        board_workspace = tmp_path / "boards" / "default" / "agents" / "my-agent"
        board_workspace.mkdir(parents=True, exist_ok=True)
        (board_workspace / "memory").mkdir()
        (board_workspace / "sessions").mkdir()

        shared_memory_dir = tmp_path / "agents" / "my-agent" / "memory"
        shared_memory_dir.mkdir(parents=True, exist_ok=True)
        (shared_memory_dir / "MEMORY.md").write_text(
            "Shared fact: reuse the incident rollback checklist.",
            encoding="utf-8",
        )

        with patch(
            "mc.infrastructure.boards.resolve_board_workspace", return_value=board_workspace
        ):
            ctx = manager.prepare(
                "my-agent",
                agent,
                "task-abc",
                board_name="default",
                memory_mode="with_history",
            )

        content = ctx.claude_md.read_text(encoding="utf-8")
        assert "reuse the incident rollback checklist" in content

    def test_mcp_json_includes_resolved_secret_env_vars(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        _write_nanobot_config(
            tmp_path,
            {
                "providers": {
                    "anthropic": {"apiKey": "anthropic-from-config"},
                    "openai": {"apiKey": "openai-from-config"},
                },
                "tools": {
                    "web": {
                        "search": {"apiKey": "brave-from-config"},
                    }
                },
            },
        )

        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare("my-agent", agent, "task-abc")

        data = json.loads(ctx.mcp_config.read_text())
        env = data["mcpServers"]["openmc"]["env"]

        assert env["ANTHROPIC_API_KEY"] == "anthropic-from-config"
        assert env["OPENAI_API_KEY"] == "openai-from-config"
        assert env["BRAVE_API_KEY"] == "brave-from-config"

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
        env = data["mcpServers"]["openmc"]["env"]
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

    def test_unavailable_skill_not_copied(self, tmp_path: Path) -> None:
        """A skill whose binary requirement is missing must NOT be copied."""
        vendor_dir = tmp_path / "vendor-skills"
        self._make_vendor_skill(
            vendor_dir,
            "needs-nonexistent-bin",
            '---\nmetadata: \'{"nanobot":{"requires":{"bins":["__nonexistent_binary_xyz__"]}}}\'\n---\n# Skill\n',
        )

        manager = CCWorkspaceManager(workspace_root=tmp_path, vendor_skills_dir=vendor_dir)
        agent = _make_agent(skills=["needs-nonexistent-bin"])
        ctx = manager.prepare("test-agent", agent, "task123")

        dest = ctx.cwd / ".claude" / "skills" / "needs-nonexistent-bin"
        assert not dest.exists(), "Skill must not be copied when requirements are unmet"

    def test_available_skill_copied(self, tmp_path: Path) -> None:
        """A skill with no requirements (always available) must be copied normally."""
        vendor_dir = tmp_path / "vendor-skills"
        self._make_vendor_skill(
            vendor_dir,
            "no-requirements-skill",
            "# No Requirements Skill\n\nThis skill has no special requirements.\n",
        )

        manager = CCWorkspaceManager(workspace_root=tmp_path, vendor_skills_dir=vendor_dir)
        agent = _make_agent(skills=["no-requirements-skill"])
        ctx = manager.prepare("test-agent", agent, "task123")

        dest = ctx.cwd / ".claude" / "skills" / "no-requirements-skill"
        assert dest.is_dir(), "Skill must be copied for an available skill"
        assert not dest.is_symlink(), "Must be a real copy, not a symlink"

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
            "missing-binary-skill" in msg and "unavailable" in msg for msg in warning_messages
        ), (
            f"Expected WARNING containing 'missing-binary-skill' and 'unavailable', got: {warning_messages}"
        )


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

        # Patch at the source module (mc.infrastructure.boards) rather than claude_code.workspace,
        # because workspace.py uses a deferred `from mc.infrastructure.boards import …` inside
        # prepare(), so Python re-resolves the name from mc.infrastructure.boards on every call.
        # If workspace.py ever hoists the import to module level, the target must change
        # to "claude_code.workspace.resolve_board_workspace".
        with patch(
            "mc.infrastructure.boards.resolve_board_workspace", return_value=board_workspace
        ) as mock_resolve:
            ctx = manager.prepare(
                "test-agent", agent, "task123", board_name="myboard", memory_mode="clean"
            )

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
        with patch(
            "mc.infrastructure.boards.resolve_board_workspace", return_value=board_workspace
        ) as mock_resolve:
            manager.prepare(
                "test-agent", agent, "task123", board_name="projboard", memory_mode="with_history"
            )

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
        with patch(
            "mc.infrastructure.boards.resolve_board_workspace", return_value=board_workspace
        ):
            manager.prepare("test-agent", agent, "task999", board_name="b1")

        claude_md = board_workspace / "CLAUDE.md"
        assert claude_md.exists()
        assert "Board agent prompt." in claude_md.read_text()
