"""Tests for CC-7: Context Parity — CC backend CLAUDE.md enrichment.

Tests verify that CCWorkspaceManager._generate_claude_md() produces a rich
context matching the nanobot ContextBuilder's output, including bootstrap
files, memory, skills summary, runtime metadata, and workspace guidance.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

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


def _prepare_and_read(tmp_path: Path, agent: AgentData, *, agent_name: str = "test-agent") -> str:
    """Helper: call prepare() and return the generated CLAUDE.md content."""
    manager = CCWorkspaceManager(workspace_root=tmp_path)
    ctx = manager.prepare(agent_name, agent, "task123")
    return ctx.claude_md.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Bootstrap files
# ---------------------------------------------------------------------------


class TestBootstrapFilesLoading:
    def test_bootstrap_files_loaded_from_workspace(self, tmp_path: Path) -> None:
        """AC: Bootstrap files in the agent workspace appear in CLAUDE.md."""
        # Pre-create the agent workspace directory so we can place files there
        agent_workspace = tmp_path / "agents" / "test-agent"
        agent_workspace.mkdir(parents=True, exist_ok=True)

        (agent_workspace / "AGENTS.md").write_text("Agent roster content", encoding="utf-8")
        (agent_workspace / "USER.md").write_text("User profile content", encoding="utf-8")

        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        assert "Agent roster content" in content, "AGENTS.md content missing from CLAUDE.md"
        assert "User profile content" in content, "USER.md content missing from CLAUDE.md"

    def test_bootstrap_fallback_to_global(self, tmp_path: Path) -> None:
        """AC: Bootstrap files in global workspace are used when not in agent workspace."""
        # Place TOOLS.md only in the GLOBAL workspace
        global_workspace = tmp_path / "workspace"
        global_workspace.mkdir(parents=True, exist_ok=True)
        (global_workspace / "TOOLS.md").write_text("Global tools guide", encoding="utf-8")

        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        assert "Global tools guide" in content, (
            "TOOLS.md global fallback content missing from CLAUDE.md"
        )

    def test_bootstrap_agent_overrides_global(self, tmp_path: Path) -> None:
        """Agent-local bootstrap files take priority over global workspace files."""
        agent_workspace = tmp_path / "agents" / "test-agent"
        agent_workspace.mkdir(parents=True, exist_ok=True)
        (agent_workspace / "USER.md").write_text("Agent-local user profile", encoding="utf-8")

        global_workspace = tmp_path / "workspace"
        global_workspace.mkdir(parents=True, exist_ok=True)
        (global_workspace / "USER.md").write_text("Global user profile", encoding="utf-8")

        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        assert "Agent-local user profile" in content
        assert "Global user profile" not in content

    def test_identity_md_loaded(self, tmp_path: Path) -> None:
        """IDENTITY.md from workspace is included in CLAUDE.md."""
        agent_workspace = tmp_path / "agents" / "test-agent"
        agent_workspace.mkdir(parents=True, exist_ok=True)
        (agent_workspace / "IDENTITY.md").write_text("Extended agent identity", encoding="utf-8")

        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        assert "Extended agent identity" in content

    def test_soul_md_excluded_from_bootstrap(self, tmp_path: Path) -> None:
        """SOUL.md must NOT be loaded via bootstrap — only via config.soul."""
        agent_workspace = tmp_path / "agents" / "test-agent"
        agent_workspace.mkdir(parents=True, exist_ok=True)
        (agent_workspace / "SOUL.md").write_text(
            "SOUL via file — should be ignored", encoding="utf-8"
        )

        # Agent has no soul configured via config.soul
        agent = _make_agent(soul=None)
        content = _prepare_and_read(tmp_path, agent)

        # The SOUL.md file content should NOT appear
        assert "SOUL via file — should be ignored" not in content

    def test_missing_bootstrap_files_skipped_gracefully(self, tmp_path: Path) -> None:
        """No bootstrap files present — CLAUDE.md is still generated without error."""
        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        # File should still be created with core sections
        assert "# Agent Identity" in content


# ---------------------------------------------------------------------------
# Memory injection
# ---------------------------------------------------------------------------


class TestMemoryInjection:
    def test_memory_injected(self, tmp_path: Path) -> None:
        """AC: memory/MEMORY.md content appears under ## Memory in CLAUDE.md."""
        agent_workspace = tmp_path / "agents" / "test-agent"
        (agent_workspace / "memory").mkdir(parents=True, exist_ok=True)
        (agent_workspace / "memory" / "MEMORY.md").write_text(
            "Important facts to remember.", encoding="utf-8"
        )

        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        assert "## Memory" in content
        assert "Important facts to remember." in content

    def test_empty_memory_skipped(self, tmp_path: Path) -> None:
        """AC: Empty memory/MEMORY.md does NOT produce a ## Memory section."""
        agent_workspace = tmp_path / "agents" / "test-agent"
        (agent_workspace / "memory").mkdir(parents=True, exist_ok=True)
        (agent_workspace / "memory" / "MEMORY.md").write_text("", encoding="utf-8")

        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        assert "## Memory" not in content

    def test_missing_memory_file_skipped(self, tmp_path: Path) -> None:
        """Missing memory/MEMORY.md does NOT produce a ## Memory section."""
        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        assert "## Memory" not in content

    def test_whitespace_only_memory_skipped(self, tmp_path: Path) -> None:
        """Whitespace-only memory/MEMORY.md does NOT produce a ## Memory section."""
        agent_workspace = tmp_path / "agents" / "test-agent"
        (agent_workspace / "memory").mkdir(parents=True, exist_ok=True)
        (agent_workspace / "memory" / "MEMORY.md").write_text("   \n\n   ", encoding="utf-8")

        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        assert "## Memory" not in content


# ---------------------------------------------------------------------------
# Skills summary
# ---------------------------------------------------------------------------


class TestSkillsSummary:
    def test_skills_summary_generated(self, tmp_path: Path) -> None:
        """AC: Skills section appears in CLAUDE.md when a skill is mapped."""
        # Create a skill in the agent workspace's skills directory
        agent_workspace = tmp_path / "agents" / "test-agent"
        skill_dir = agent_workspace / "skills" / "my-skill"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "---\ndescription: My awesome skill\n---\n\n# My Skill\nDoes things.",
            encoding="utf-8",
        )

        agent = _make_agent(skills=["my-skill"])
        content = _prepare_and_read(tmp_path, agent)

        assert "## Skills" in content
        assert "my-skill" in content

    def test_skills_summary_includes_configured_skill_name(self, tmp_path: Path) -> None:
        """Configured skill name appears in skills summary."""
        agent_workspace = tmp_path / "agents" / "test-agent"
        skill_dir = agent_workspace / "skills" / "custom-skill"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "---\ndescription: Custom skill for testing\n---\n\n# Custom Skill",
            encoding="utf-8",
        )

        agent = _make_agent(skills=["custom-skill"])
        content = _prepare_and_read(tmp_path, agent)

        # The skills section should appear and include the custom skill name
        assert "## Skills" in content
        assert "custom-skill" in content

    def test_skills_not_found_warning_but_no_crash(self, tmp_path: Path) -> None:
        """Configured skill that doesn't exist causes a warning but no crash."""
        agent = _make_agent(skills=["nonexistent-skill"])
        # Should not raise; CLAUDE.md should still be written
        content = _prepare_and_read(tmp_path, agent)
        assert "# Agent Identity" in content

    def test_skills_mapped_before_claude_md_generated(self, tmp_path: Path) -> None:
        """AC (call order): Skills are symlinked before CLAUDE.md is generated.

        Verify that when CLAUDE.md is generated, the .claude/skills/ symlinks
        already exist (i.e., _map_skills was called first).
        """
        agent_workspace = tmp_path / "agents" / "test-agent"
        skill_dir = agent_workspace / "skills" / "test-skill"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text("# Test Skill", encoding="utf-8")

        call_log: list[str] = []

        manager = CCWorkspaceManager(workspace_root=tmp_path)
        original_map_skills = manager._map_skills
        original_gen_claude_md = manager._generate_claude_md

        def patched_map_skills(workspace: Path, skills: list[str]) -> None:
            call_log.append("_map_skills")
            original_map_skills(workspace, skills)

        def patched_gen_claude_md(workspace: Path, config: AgentData, **kwargs) -> None:
            call_log.append("_generate_claude_md")
            original_gen_claude_md(workspace, config, **kwargs)

        manager._map_skills = patched_map_skills  # type: ignore[method-assign]
        manager._generate_claude_md = patched_gen_claude_md  # type: ignore[method-assign]

        agent = _make_agent(skills=["test-skill"])
        manager.prepare("test-agent", agent, "task123")

        assert call_log == ["_map_skills", "_generate_claude_md"], (
            f"Expected _map_skills before _generate_claude_md, got: {call_log}"
        )

        # Also verify the symlink is in place
        link = agent_workspace / ".claude" / "skills" / "test-skill"
        assert link.is_symlink(), "Skill symlink was not created"


# ---------------------------------------------------------------------------
# Runtime context
# ---------------------------------------------------------------------------


class TestRuntimeContext:
    def test_runtime_context_present(self, tmp_path: Path) -> None:
        """AC: ## Runtime section exists in generated CLAUDE.md."""
        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        assert "## Runtime" in content

    def test_runtime_contains_python_version(self, tmp_path: Path) -> None:
        """## Runtime section includes Python version info."""
        import platform as _platform

        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        assert _platform.python_version() in content

    def test_runtime_contains_current_time(self, tmp_path: Path) -> None:
        """## Runtime section includes a current time string."""
        from datetime import datetime

        agent = _make_agent()
        # Use the year as a proxy for "current time present"
        content = _prepare_and_read(tmp_path, agent)

        year = datetime.now().strftime("%Y")
        assert year in content


# ---------------------------------------------------------------------------
# Workspace guidance
# ---------------------------------------------------------------------------


class TestWorkspaceGuidance:
    def test_workspace_guidance_present(self, tmp_path: Path) -> None:
        """AC: ## Workspace section exists in generated CLAUDE.md."""
        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        assert "## Workspace" in content

    def test_workspace_guidance_contains_path(self, tmp_path: Path) -> None:
        """## Workspace section includes the resolved workspace path."""
        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        expected_workspace = tmp_path / "agents" / "test-agent"
        expected_ws_str = str(expected_workspace.resolve())
        assert expected_ws_str in content

    def test_workspace_guidance_contains_memory_path(self, tmp_path: Path) -> None:
        """## Workspace section references the memory/MEMORY.md path."""
        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        assert "memory/MEMORY.md" in content

    def test_workspace_guidance_contains_skills_hint(self, tmp_path: Path) -> None:
        """## Workspace section references the custom skills location."""
        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        assert ".claude/skills/" in content

    def test_workspace_guidance_contains_board_artifacts_path(self, tmp_path: Path) -> None:
        """## Workspace section references the board-scoped artifacts directory."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()

        content = manager.prepare(
            "test-agent",
            agent,
            "task123",
            board_name="default",
        ).claude_md.read_text(encoding="utf-8")

        expected = tmp_path / "boards" / "default" / "artifacts"
        assert str(expected.resolve()) in content
        assert "Board artifacts" in content


# ---------------------------------------------------------------------------
# Section ordering
# ---------------------------------------------------------------------------


class TestSectionOrdering:
    def test_identity_before_workspace(self, tmp_path: Path) -> None:
        """Agent Identity section appears before Workspace section."""
        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        identity_pos = content.index("# Agent Identity")
        workspace_pos = content.index("## Workspace")
        assert identity_pos < workspace_pos

    def test_workspace_before_runtime(self, tmp_path: Path) -> None:
        """Workspace section appears before Runtime section."""
        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        workspace_pos = content.index("## Workspace")
        runtime_pos = content.index("## Runtime")
        assert workspace_pos < runtime_pos

    def test_soul_is_last(self, tmp_path: Path) -> None:
        """Soul section must be the last major section in CLAUDE.md."""
        soul_text = "The soul of the agent."
        agent = _make_agent(soul=soul_text)
        content = _prepare_and_read(tmp_path, agent)

        soul_pos = content.index("## Soul")
        conventions_pos = content.index("## Project Conventions")
        mcp_pos = content.index("## Available MCP Tools")
        assert soul_pos > conventions_pos
        assert soul_pos > mcp_pos

    def test_system_prompt_present_and_before_conventions(self, tmp_path: Path) -> None:
        """System Prompt section appears before Project Conventions."""
        agent = _make_agent(prompt="My custom prompt text.")
        content = _prepare_and_read(tmp_path, agent)

        assert "## System Prompt" in content
        prompt_pos = content.index("## System Prompt")
        conventions_pos = content.index("## Project Conventions")
        assert prompt_pos < conventions_pos


# ---------------------------------------------------------------------------
# Regression: existing tests still pass (integration smoke test)
# ---------------------------------------------------------------------------


class TestContextParityRegression:
    def test_all_original_sections_still_present(self, tmp_path: Path) -> None:
        """All sections from the original CLAUDE.md generation must still be present."""
        agent = _make_agent(
            soul="Wise and thoughtful.",
            prompt="Specialized test agent.",
        )
        content = _prepare_and_read(tmp_path, agent)

        # Original sections
        assert "# Agent Identity" in content
        assert "test-agent" in content
        assert "Tester" in content
        assert "## System Prompt" in content
        assert "Specialized test agent." in content
        assert "## Project Conventions" in content
        assert "mcp__mc__ask_user" in content
        assert "structured questions array" in content
        assert "free-text fallback" in content
        assert "## Soul" in content
        assert "Wise and thoughtful." in content

        # New sections
        assert "## Runtime" in content
        assert "## Workspace" in content


# ---------------------------------------------------------------------------
# Orientation section (CC-9)
# ---------------------------------------------------------------------------


class TestOrientationSection:
    def test_orientation_included_when_provided(self, tmp_path: Path) -> None:
        """Orientation text appears as ## Orientation in CLAUDE.md."""
        agent = _make_agent()
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        ctx = manager.prepare("test-agent", agent, "task123", orientation="You work for Acme Corp.")
        content = ctx.claude_md.read_text(encoding="utf-8")

        assert "## Orientation" in content
        assert "You work for Acme Corp." in content

    def test_orientation_omitted_when_none(self, tmp_path: Path) -> None:
        """No ## Orientation section when orientation is None."""
        agent = _make_agent()
        content = _prepare_and_read(tmp_path, agent)

        assert "## Orientation" not in content

    def test_orientation_between_prompt_and_bootstrap(self, tmp_path: Path) -> None:
        """Orientation section appears after System Prompt and before bootstrap files."""
        agent_workspace = tmp_path / "agents" / "test-agent"
        agent_workspace.mkdir(parents=True, exist_ok=True)
        (agent_workspace / "AGENTS.md").write_text("Agent roster", encoding="utf-8")

        agent = _make_agent(prompt="My prompt")
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        ctx = manager.prepare("test-agent", agent, "task123", orientation="Orientation text")
        content = ctx.claude_md.read_text(encoding="utf-8")

        prompt_pos = content.index("## System Prompt")
        orientation_pos = content.index("## Orientation")
        bootstrap_pos = content.index("## AGENTS.md")

        assert prompt_pos < orientation_pos < bootstrap_pos

    def test_orientation_empty_string_not_included(self, tmp_path: Path) -> None:
        """Empty orientation string should not produce an Orientation section."""
        agent = _make_agent()
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        ctx = manager.prepare("test-agent", agent, "task123", orientation="")
        content = ctx.claude_md.read_text(encoding="utf-8")

        assert "## Orientation" not in content


class TestAlwaysOnSkills:
    """Tests for CC-12: always-on skills injection into CLAUDE.md."""

    def test_always_skills_included_when_available(self, tmp_path: Path) -> None:
        """Always-on skills content appears in CLAUDE.md when skills are found."""
        agent = _make_agent(name="skill-agent")
        manager = CCWorkspaceManager(workspace_root=tmp_path)

        with patch.object(
            manager, "_build_always_skills_content", return_value="Always skill content here"
        ):
            ctx = manager.prepare("skill-agent", agent, "task123")
            content = ctx.claude_md.read_text(encoding="utf-8")

        assert "## Active Skills" in content
        assert "Always skill content here" in content

    def test_always_skills_empty_when_none(self, tmp_path: Path) -> None:
        """No Active Skills section when no always-on skills exist."""
        agent = _make_agent(name="no-skill-agent")
        manager = CCWorkspaceManager(workspace_root=tmp_path)

        with patch.object(manager, "_build_always_skills_content", return_value=""):
            ctx = manager.prepare("no-skill-agent", agent, "task123")
            content = ctx.claude_md.read_text(encoding="utf-8")

        assert "## Active Skills" not in content

    def test_always_skills_import_error_graceful(self, tmp_path: Path) -> None:
        """ImportError in SkillsLoader is handled gracefully (returns empty)."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)

        with patch("nanobot.agent.skills.SkillsLoader", side_effect=ImportError("no module")):
            result = manager._build_always_skills_content(tmp_path / "agents" / "test")

        assert result == ""
