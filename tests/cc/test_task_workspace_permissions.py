"""Reproduce: task workspace permission failures in the instagram-post-squad-v3 workflow.

Simulates the 2-step task segment:
  Step 9: Post Designer ("Cria a direção visual") → writes visual direction output
  Step 10: Image Generator ("Gera imagens e slides") → reads direction, generates images

Current problems observed in production (live tab):
  1. CC sandbox restricts agent to project root (/app), blocking /workspace/ access
  2. Ephemeral CWD (/tmp/mc-workspaces/) has no .git — CC falls back to /app as project root
  3. CLI command doesn't include --allowed-directory for workspace or /tmp paths
  4. settings.json permissions don't explicitly grant access to ephemeral workspace paths
  5. Step 10 agent tries to read from persistent /workspace/tasks/ path instead of ephemeral task/

This test file ONLY demonstrates the problems. It does NOT fix them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from claude_code.types import ClaudeCodeOpts, WorkspaceContext
from claude_code.workspace import CCWorkspaceManager, sync_workspace_back

from mc.types import AgentData

# ---------------------------------------------------------------------------
# Fixtures — agent configs matching the real squad
# ---------------------------------------------------------------------------


def _post_designer_agent() -> AgentData:
    """Post Designer agent — Step 9: Cria a direção visual."""
    return AgentData(
        name="post-designer",
        display_name="Post Designer",
        role=(
            "Designs Instagram post directions and generation prompts from "
            "approved post specs and brand constraints."
        ),
        prompt=(
            "You are the Post Designer. Read the approved post specification "
            "from your task attachments and create a detailed visual direction "
            "document. Save the visual direction to task/output/visual_direction.md"
        ),
        skills=[],
        backend="claude-code",
    )


def _image_generator_agent() -> AgentData:
    """Image Generator agent — Step 10: Gera imagens e slides."""
    return AgentData(
        name="image-generator",
        display_name="Image Generator",
        role=(
            "Generates still images, carousel slides, and design assets from "
            "approved visual directions while ignoring reel/video tasks."
        ),
        prompt=(
            "You are the Image Generator. Read the visual direction from your "
            "task attachments and generate images. Use the generate-image skill "
            "to create images. Save all outputs to task/output/"
        ),
        skills=["generate-image"],
        backend="claude-code",
    )


def _make_task_attachments(workspace_root: Path, task_id: str) -> Path:
    """Simulate a task with attachments (logo, post spec) on the persistent volume."""
    from mc.types import task_safe_id

    safe_id = task_safe_id(task_id)
    task_dir = workspace_root / "tasks" / safe_id
    attachments = task_dir / "attachments"
    attachments.mkdir(parents=True, exist_ok=True)

    # Simulate files that exist on the real persistent volume
    (attachments / "logo_adrena-removebg-preview.png").write_bytes(
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # minimal PNG-like header
    )
    (attachments / "post_spec.md").write_text(
        "# Post Spec\n\n"
        "- Format: Carrossel 5 slides\n"
        "- Template: A\n"
        "- Brand: Adrena\n"
        "- Aspect ratio: 1:1\n",
        encoding="utf-8",
    )
    return task_dir


# ---------------------------------------------------------------------------
# Test class: Full 2-step workflow simulation
# ---------------------------------------------------------------------------


class TestInstagramPostSquadPermissions:
    """Simulate Step 9 → Step 10 of instagram-post-squad-v3 and show permission gaps."""

    TASK_ID = "n9760zrfdcd80svyvftybjahp183spr6"  # real Convex ID from production

    def test_step9_workspace_files_are_accessible_locally(self, tmp_path: Path) -> None:
        """Step 9 (Post Designer): ephemeral workspace has task files copied correctly.

        This passes — the copy to ephemeral CWD works. But the agent will fail
        when it tries to access the PERSISTENT path instead.
        """
        _make_task_attachments(tmp_path, self.TASK_ID)
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _post_designer_agent()

        ctx = manager.prepare("post-designer", agent, self.TASK_ID)

        # Files are correctly copied to ephemeral workspace
        local_attachments = ctx.cwd / "task" / "attachments"
        assert local_attachments.is_dir()
        assert (local_attachments / "logo_adrena-removebg-preview.png").exists()
        assert (local_attachments / "post_spec.md").exists()

        # Output directory exists and is writable
        local_output = ctx.cwd / "task" / "output"
        assert local_output.is_dir()
        (local_output / "test_write.txt").write_text("writable")
        assert (local_output / "test_write.txt").read_text() == "writable"

    def test_step9_claude_md_points_to_ephemeral_task_dir(self, tmp_path: Path) -> None:
        """CLAUDE.md correctly references ephemeral task paths — not /workspace/ paths.

        The guidance is correct, but the agent often ignores it and tries
        the persistent /workspace/tasks/ path instead (observed in live tab).
        """
        _make_task_attachments(tmp_path, self.TASK_ID)
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _post_designer_agent()

        ctx = manager.prepare("post-designer", agent, self.TASK_ID)
        claude_md = ctx.claude_md.read_text(encoding="utf-8")

        # CLAUDE.md should reference the ephemeral task directory
        ephemeral_task_dir = str(ctx.cwd / "task")
        assert ephemeral_task_dir in claude_md, (
            f"CLAUDE.md should reference ephemeral task dir {ephemeral_task_dir}"
        )
        assert f"{ephemeral_task_dir}/attachments/" in claude_md
        assert f"{ephemeral_task_dir}/output/" in claude_md

        # CLAUDE.md should NOT contain the persistent /workspace/ path
        persistent_path = f"/workspace/tasks/{self.TASK_ID}"
        assert persistent_path not in claude_md, (
            f"CLAUDE.md must NOT reference persistent path {persistent_path} — "
            "agents cannot access /workspace/ from the CC sandbox"
        )

    def test_step9_settings_do_not_grant_access_to_workspace_paths(self, tmp_path: Path) -> None:
        """BUG: settings.json permissions don't explicitly allow the ephemeral workspace path.

        The settings use bare tool names (Read, Write, Bash(*)) which should
        allow any path, but CC's internal sandbox still restricts Bash to the
        project root directory. The project root is /app (where .git lives),
        NOT the ephemeral workspace.
        """
        _make_task_attachments(tmp_path, self.TASK_ID)
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _post_designer_agent()

        ctx = manager.prepare("post-designer", agent, self.TASK_ID)
        settings = json.loads((ctx.cwd / ".claude" / "settings.json").read_text())

        # Settings disable the sandbox — correct intent
        assert settings["sandbox"]["enabled"] is False

        # Permissions use bare tool names — correct intent
        allow = settings["permissions"]["allow"]
        assert "Bash(*)" in allow
        assert "Read" in allow
        assert "Write" in allow

        # BUG: No explicit allowed directories are configured.
        # CC's Bash tool has its own directory restriction separate from
        # the permission system. Even with Bash(*), it restricts to the
        # "project root" — which it determines by looking for .git upward
        # from CWD. The ephemeral workspace at /tmp/mc-workspaces/ has no
        # .git, so CC falls back to whatever it considers the project root.
        #
        # In the Docker container, this is /app (where the codebase .git lives).
        # Result: ls /workspace/tasks/... → BLOCKED (allowed: /app)

        # Verify: the ephemeral CWD has NO .git directory
        assert not (ctx.cwd / ".git").exists(), (
            "Ephemeral workspace should NOT have .git — "
            "this means CC cannot determine project root from CWD"
        )

        # Verify: the settings don't include any path-scoped permissions
        # that would help CC know about the workspace paths
        for rule in allow:
            assert "/tmp/mc-workspaces" not in rule, (
                "No permission rule grants access to ephemeral workspace paths"
            )
            assert "/workspace" not in rule, (
                "No permission rule grants access to persistent /workspace/ paths"
            )

    def test_step9_cli_command_missing_allowed_directory(self, tmp_path: Path) -> None:
        """BUG: The CC CLI command doesn't include --allowed-directory for workspace paths.

        The interactive adapter builds a CLI command without --allowed-directory,
        so CC has no way to know that the agent should be able to access
        /tmp/mc-workspaces/ or /workspace/ paths.
        """
        from mc.contexts.interactive.adapters.claude_code import ClaudeCodeInteractiveAdapter

        agent = _image_generator_agent()

        # Build the command that the interactive adapter would generate
        adapter = ClaudeCodeInteractiveAdapter(
            bridge=None,
            workspace_manager=CCWorkspaceManager(workspace_root=tmp_path),
            cli_path="claude",
        )

        # Construct a minimal workspace context to test _build_command
        ephemeral_cwd = tmp_path / "ephemeral"
        ephemeral_cwd.mkdir()
        ws_ctx = WorkspaceContext(
            cwd=ephemeral_cwd,
            mcp_config=ephemeral_cwd / ".mcp.json",
            claude_md=ephemeral_cwd / "CLAUDE.md",
            socket_path="/tmp/mc-image-generator-test.sock",
        )

        cmd = adapter._build_command(agent, ws_ctx, resume_session_id=None)

        # BUG: No --allowed-directory flag in the command
        assert "--allowed-directory" not in cmd, (
            "CONFIRMED BUG: CLI command has no --allowed-directory flag. "
            "CC cannot access task workspace paths from the Bash sandbox."
        )

        # The command does have --permission-mode bypassPermissions
        assert "--permission-mode" in cmd
        idx = cmd.index("--permission-mode")
        assert cmd[idx + 1] == "bypassPermissions"

    def test_step9_output_syncs_to_persistent_before_step10(self, tmp_path: Path) -> None:
        """Step 9 output must be synced back so Step 10 can read it.

        This works correctly — sync_workspace_back copies output to persistent path.
        """
        _make_task_attachments(tmp_path, self.TASK_ID)
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _post_designer_agent()

        ctx = manager.prepare("post-designer", agent, self.TASK_ID)

        # Simulate Step 9 writing output
        local_output = ctx.cwd / "task" / "output"
        (local_output / "visual_direction.md").write_text(
            "# Visual Direction\n\n"
            "Dark editorial extreme sports photography.\n"
            "1:1 square composition, teal accent lighting.\n",
            encoding="utf-8",
        )

        # Sync back to persistent volume
        sync_workspace_back(ctx)

        # Verify output is on persistent path
        from mc.types import task_safe_id

        safe_id = task_safe_id(self.TASK_ID)
        persistent_output = tmp_path / "tasks" / safe_id / "output"
        assert (persistent_output / "visual_direction.md").exists()

    def test_step10_receives_step9_output_as_attachment(self, tmp_path: Path) -> None:
        """Step 10 workspace must contain Step 9's output for the agent to read.

        BUG: The current workspace preparation copies from tasks/{id}/attachments/
        only. Step 9's output goes to tasks/{id}/output/. Step 10 does NOT
        automatically receive step 9's output in its task/attachments/ directory.

        The Image Generator agent would need to read from task/output/ from the
        PREVIOUS step, but:
        1. It only gets its own fresh ephemeral workspace
        2. task/attachments/ only has the original task attachments (logo, spec)
        3. task/output/ is empty (fresh for this step's output)
        4. Step 9's visual_direction.md is NOT available anywhere in step 10's workspace
        """
        from mc.types import task_safe_id

        safe_id = task_safe_id(self.TASK_ID)

        # First: simulate Step 9 completed and synced its output
        _make_task_attachments(tmp_path, self.TASK_ID)
        step9_output = tmp_path / "tasks" / safe_id / "output"
        step9_output.mkdir(parents=True, exist_ok=True)
        (step9_output / "visual_direction.md").write_text(
            "# Visual Direction\nDark editorial style.\n",
            encoding="utf-8",
        )

        # Now: prepare Step 10 workspace
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _image_generator_agent()
        ctx = manager.prepare("image-generator", agent, self.TASK_ID)

        # Step 10's ephemeral workspace has the original attachments
        local_attachments = ctx.cwd / "task" / "attachments"
        assert (local_attachments / "logo_adrena-removebg-preview.png").exists()
        assert (local_attachments / "post_spec.md").exists()

        # BUG: Step 9's output is NOT in step 10's workspace
        # The visual_direction.md from step 9 is missing
        local_output = ctx.cwd / "task" / "output"
        assert not (local_output / "visual_direction.md").exists(), (
            "CONFIRMED: Step 10 does NOT receive Step 9's output. "
            "The visual_direction.md is missing from the ephemeral workspace."
        )

        # The output IS on the persistent path, but the agent can't reach it
        # from the CC sandbox (observed: "blocked, allowed: /app")
        persistent_output = tmp_path / "tasks" / safe_id / "output"
        assert (persistent_output / "visual_direction.md").exists(), (
            "Step 9's output exists on persistent path but is unreachable from CC sandbox"
        )

    def test_step10_output_dir_accessible_but_persistent_path_blocked(self, tmp_path: Path) -> None:
        """The ephemeral output dir is writable, but the persistent /workspace/ path is not.

        Demonstrates the gap: the agent's CLAUDE.md says "write to task/output/"
        but in production the agent ignores this and tries /workspace/tasks/{id}/output/
        which the CC sandbox blocks.
        """
        _make_task_attachments(tmp_path, self.TASK_ID)
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _image_generator_agent()
        ctx = manager.prepare("image-generator", agent, self.TASK_ID)

        claude_md = ctx.claude_md.read_text(encoding="utf-8")

        # Agent CAN write to ephemeral task/output/ (relative to CWD)
        local_output = ctx.cwd / "task" / "output"
        assert local_output.is_dir()
        assert os.access(local_output, os.W_OK)

        # CLAUDE.md tells the agent the correct path
        assert "task/output/" in claude_md or str(local_output) in claude_md

        # But the agent's CWD is under /tmp/ which has no .git
        # CC determines project root from .git traversal
        # In Docker: /tmp → no .git → falls back to /app (container .git)
        # Result: Bash tool restricts to /app, blocking /tmp/mc-workspaces/ too
        cwd_path = ctx.cwd
        git_found = False
        check = cwd_path
        while check != check.parent:
            if (check / ".git").exists():
                git_found = True
                break
            check = check.parent

        assert not git_found, (
            "CONFIRMED: No .git found above ephemeral CWD. "
            "CC cannot determine project root from the workspace path. "
            "In Docker, CC falls back to /app as project root, "
            "blocking Bash access to /tmp/mc-workspaces/ and /workspace/."
        )

    def test_step10_generate_image_skill_path_resolution(self, tmp_path: Path) -> None:
        """The generate-image skill uses relative paths from CWD.

        When the agent runs:
          uv run python .claude/skills/generate-image/scripts/generate_image.py --output output/img.png

        This resolves relative to the Bash CWD. If CC's Bash CWD is the
        ephemeral workspace, it works. If CC overrides CWD to /app (project root),
        the script path and output path both break.
        """
        # Create the skill in workspace so it can be mapped
        skill_dir = tmp_path / "workspace" / "skills" / "generate-image"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: generate-image\n"
            "description: Generate images via OpenRouter\n"
            "---\n\n"
            "# Generate Image\n"
            "Run: uv run python .claude/skills/generate-image/scripts/generate_image.py\n",
            encoding="utf-8",
        )
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "generate_image.py").write_text("# placeholder", encoding="utf-8")

        _make_task_attachments(tmp_path, self.TASK_ID)
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _image_generator_agent()
        ctx = manager.prepare("image-generator", agent, self.TASK_ID)

        # Skill IS correctly copied to ephemeral workspace
        skill_script = (
            ctx.cwd / ".claude" / "skills" / "generate-image" / "scripts" / "generate_image.py"
        )
        assert skill_script.exists(), "Skill script must be in ephemeral workspace"

        # The skill uses RELATIVE paths like "output/generated.png"
        # This only works if Bash CWD = ephemeral workspace
        # If CC overrides Bash CWD to /app, the relative path resolves to /app/output/
        # which doesn't exist and isn't writable by the agent
        relative_output = ctx.cwd / "output"  # where "output/img.png" would resolve
        task_output = ctx.cwd / "task" / "output"  # where output SHOULD go

        # The skill's default --output is "output/generated.png" (relative)
        # but the task output directory is at "task/output/" (different path)
        assert not relative_output.exists(), (
            "output/ at CWD root does not exist — skill default --output path "
            "would need to be task/output/ to match the workspace layout"
        )
        assert task_output.exists(), (
            "task/output/ exists — but the skill's default path doesn't point here"
        )


class TestWorkspacePermissionSettings:
    """Verify the settings.json permission model is insufficient for task execution."""

    def test_settings_lack_explicit_directory_allowlist(self, tmp_path: Path) -> None:
        """settings.json has no directory allowlist — relies entirely on CC's project root.

        In the Docker container, the project root is /app (the codebase).
        The task workspace is at /tmp/mc-workspaces/ (ephemeral) and
        /workspace/tasks/ (persistent). Neither is under /app.
        """
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _image_generator_agent()
        _make_task_attachments(tmp_path, "task-test-perms")
        ctx = manager.prepare("image-generator", agent, "task-test-perms")

        settings = json.loads((ctx.cwd / ".claude" / "settings.json").read_text())

        # The settings try to be permissive but miss directory-level control
        assert settings["sandbox"]["enabled"] is False
        assert "Bash(*)" in settings["permissions"]["allow"]

        # No allowedDirectories or similar field exists
        assert "allowedDirectories" not in settings
        assert "allowed_directories" not in settings

        # The permission rules are tool-level, not path-level
        for rule in settings["permissions"]["allow"]:
            assert not rule.startswith("/"), (
                f"Permission rule '{rule}' is a tool pattern, not a path pattern"
            )

    def test_headless_provider_cli_also_missing_allowed_directory(self, tmp_path: Path) -> None:
        """The headless ProviderCli command also lacks --allowed-directory.

        Both interactive (tmux TUI) and headless (-p flag) paths share
        the same permission gap.
        """
        from mc.contexts.interactive.adapters.claude_code import ClaudeCodeInteractiveAdapter

        agent = _image_generator_agent()
        agent.claude_code_opts = ClaudeCodeOpts(
            permission_mode="bypassPermissions",
        )

        adapter = ClaudeCodeInteractiveAdapter(
            bridge=None,
            workspace_manager=CCWorkspaceManager(workspace_root=tmp_path),
            cli_path="claude",
        )

        ws_ctx = WorkspaceContext(
            cwd=tmp_path / "ephemeral",
            mcp_config=tmp_path / "ephemeral" / ".mcp.json",
            claude_md=tmp_path / "ephemeral" / "CLAUDE.md",
            socket_path="/tmp/mc-test.sock",
        )

        cmd = adapter._build_command(agent, ws_ctx, resume_session_id=None)

        # Verify the gap: no directory-level flags
        assert "--allowed-directory" not in cmd
        assert "--add-dir" not in cmd

        # The CWD is passed separately via tmux -c, not in the CLI command
        # CC determines project root by .git traversal from CWD, not from flags
        for flag in cmd:
            assert not flag.startswith("/tmp/mc-workspaces"), (
                "No workspace path appears in the CLI command"
            )


class TestCrossStepOutputSharing:
    """Verify that outputs from step N are available to step N+1."""

    TASK_ID = "n9760zrfdcd80svyvftybjahp183spr6"

    def test_step_output_not_included_in_next_step_attachments(self, tmp_path: Path) -> None:
        """BUG: workspace.prepare() copies attachments/ but NOT output/ from prior steps.

        Step 9 writes visual_direction.md to task/output/.
        After sync_workspace_back(), it lands on persistent tasks/{id}/output/.
        Step 10's workspace.prepare() copies tasks/{id}/attachments/ → ephemeral.
        It does NOT copy tasks/{id}/output/ → ephemeral.
        Step 10 cannot read step 9's output.
        """
        from mc.types import task_safe_id

        safe_id = task_safe_id(self.TASK_ID)

        # Setup: task with attachments + prior step output
        _make_task_attachments(tmp_path, self.TASK_ID)

        prior_output = tmp_path / "tasks" / safe_id / "output"
        prior_output.mkdir(parents=True, exist_ok=True)
        (prior_output / "visual_direction.md").write_text("Dark editorial style.")
        (prior_output / "color_palette.json").write_text('{"primary": "#0A0A0A"}')

        # Step 10: prepare workspace
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _image_generator_agent()
        ctx = manager.prepare("image-generator", agent, self.TASK_ID)

        # Attachments are copied ✓
        assert (ctx.cwd / "task" / "attachments" / "post_spec.md").exists()

        # Prior step output is NOT copied ✗
        assert not (ctx.cwd / "task" / "output" / "visual_direction.md").exists()
        assert not (ctx.cwd / "task" / "output" / "color_palette.json").exists()

        # The output directory exists but is empty (fresh for this step)
        output_files = list((ctx.cwd / "task" / "output").iterdir())
        assert output_files == [], f"Step 10's output dir should be empty but has: {output_files}"

    def test_persistent_output_exists_but_unreachable_from_sandbox(self, tmp_path: Path) -> None:
        """The prior step's output IS on the persistent path but the sandbox blocks access.

        This exactly matches the production behavior seen in the live tab:
        agent runs `ls /workspace/tasks/{id}/output/` → BLOCKED (allowed: /app)
        """
        from mc.types import task_safe_id

        safe_id = task_safe_id(self.TASK_ID)

        # Setup persistent output
        _make_task_attachments(tmp_path, self.TASK_ID)
        prior_output = tmp_path / "tasks" / safe_id / "output"
        prior_output.mkdir(parents=True, exist_ok=True)
        (prior_output / "visual_direction.md").write_text("Visual direction content")

        # Prepare step 10 workspace
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _image_generator_agent()
        ctx = manager.prepare("image-generator", agent, self.TASK_ID)

        # The persistent path has the data
        assert (prior_output / "visual_direction.md").exists()

        # But the ephemeral workspace does NOT have it
        assert not (ctx.cwd / "task" / "output" / "visual_direction.md").exists()

        # The agent would need to access:
        #   /workspace/tasks/{safe_id}/output/visual_direction.md  (persistent)
        # But CC sandbox allows only: /app (project root from .git)
        #
        # Even the ephemeral CWD (/tmp/mc-workspaces/image-generator-{suffix}/)
        # is outside /app, so Bash commands fail there too.

        # Verify: the persistent path is different from the ephemeral path
        persistent_output_path = str(prior_output)
        ephemeral_output_path = str(ctx.cwd / "task" / "output")
        assert persistent_output_path != ephemeral_output_path, (
            "Persistent and ephemeral output paths are different — "
            "agent gets ephemeral (empty), persistent (has data) is blocked"
        )
