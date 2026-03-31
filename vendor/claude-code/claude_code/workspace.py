"""Claude Code Workspace Manager.

Prepares per-agent workspaces for Claude Code execution:
  - Creates directory structure (memory/, sessions/)
  - Generates CLAUDE.md with agent identity and MCP tools guide
  - Maps skill symlinks into .claude/skills/
  - Generates .mcp.json pointing at the mc.runtime.mcp.bridge subprocess
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shlex
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path

from claude_code.types import WorkspaceContext
from mc.types import AgentData

logger = logging.getLogger(__name__)

# Path to the vendor nanobot skills directory (builtin skills).
# Try to import the canonical constant from upstream; fall back to the
# path computed from __file__ so this module keeps working if the
# vendor package layout changes.
try:
    from nanobot.agent.skills import (
        BUILTIN_SKILLS_DIR as _VENDOR_SKILLS_DIR,  # type: ignore[import]
    )
except ImportError:  # pragma: no cover - vendor package not on path
    _VENDOR_SKILLS_DIR = Path(__file__).parent.parent.parent / "nanobot" / "nanobot" / "skills"

# Project root — used to anchor `uv run --project` in hook commands so that
# hooks work when executed from agent workspaces outside the project tree.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_MCP_TOOLS_GUIDE = """\
## Available MCP Tools (mc server)

Use these tools via the `mcp__mc__` prefix:

- **mcp__mc__ask_user** — Ask the human user a question or a short structured questionnaire and wait for their reply.
- **mcp__mc__send_message** — Send a message to another agent or to the task thread.
- **mcp__mc__delegate_task** — Delegate a subtask to a specialist agent.
- **mcp__mc__ask_agent** — Ask a specific agent a question and get a reply.
- **mcp__mc__cron** — Schedule reminders and recurring tasks (add/list/remove).
- **mcp__mc__search_memory** — Search agent memory and history for relevant past events and decisions.
- **mcp__mc__create_agent_spec** — Create a V2 agent specification in Mission Control.
- **mcp__mc__publish_squad_graph** — Publish a complete squad blueprint (agents + workflows) to Mission Control.

### CRITICAL: User Interaction Rules

**NEVER** guess, assume, or fabricate user input. If a task requires information from the user:

1. Call `mcp__mc__ask_user` with your question.
2. The call BLOCKS until the user replies — wait for it.
3. Only then proceed to the next question or action.

Native `AskUserQuestion` and built-in `Cron*` tools are disabled in Mission Control sessions.
Always use the `mcp__mc__*` tools instead of searching for or relying on those native variants.

Examples of when you MUST use `mcp__mc__ask_user`:
- Running a questionnaire or wizard (either one question at a time, or a short structured questions array)
- Confirming a destructive action before executing it
- Gathering required parameters that were not provided in the task

Structured questionnaire rules:
- Use the `questions` array when you need 2-3 related answers in one interaction
- Each question may include up to 3 explicit options
- The UI always offers a free-text fallback as the fourth choice
- Prefer concise headers/ids so the final reply is easy to parse

> **IMPORTANT**: Use `mcp__mc__ask_user` for both single questions and structured questions arrays.
"""


_DEFAULT_CONVENTIONS = """\
## Project Conventions

- Use `uv run python` instead of `python3`
- Use `uv run pytest` for running tests
- Follow the project's existing code patterns and style
"""

# Maximum safe Unix socket path length (macOS limit ~104 chars).
_MAX_SOCKET_PATH_LEN = 104

# Bootstrap files to load from the workspace (SOUL.md is excluded — it is
# handled via config.soul to keep the personality override at the end).
_BOOTSTRAP_FILES = ["AGENTS.md", "USER.md", "TOOLS.md", "IDENTITY.md"]


def sync_workspace_back(ctx: WorkspaceContext) -> None:
    """Sync container-local workspace data back to the persistent volume.

    Called by the execution strategy AFTER the CC agent finishes.
    Copies output files and memory changes from the ephemeral workspace
    to the persistent Docker volume paths, then cleans up the ephemeral dir.
    """
    if not ctx.sync_targets:
        return
    for target in ctx.sync_targets:
        if not target.local.is_dir():
            continue
        try:
            target.persistent.mkdir(parents=True, exist_ok=True)
            for entry in target.local.rglob("*"):
                if not entry.is_file():
                    continue
                rel = entry.relative_to(target.local)
                dest = target.persistent / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(entry, dest)
            logger.info("[sync] %s → %s", target.local, target.persistent)
        except OSError:
            logger.error("[sync] Failed %s → %s", target.local, target.persistent, exc_info=True)

    # Clean up ephemeral workspace to avoid /tmp accumulation
    if ctx.cwd.exists() and str(ctx.cwd).startswith("/tmp/mc-workspaces/"):
        shutil.rmtree(ctx.cwd, ignore_errors=True)
        logger.info("[sync] Cleaned up ephemeral workspace %s", ctx.cwd)


class CCWorkspaceManager:
    """Prepares Claude Code agent workspaces."""

    def __init__(
        self,
        workspace_root: Path | None = None,
        vendor_skills_dir: Path | None = None,
    ) -> None:
        from mc.infrastructure.runtime_home import get_runtime_home

        self._root = workspace_root or get_runtime_home()
        self._vendor_skills = vendor_skills_dir or _VENDOR_SKILLS_DIR

    def prepare(
        self,
        agent_name: str,
        agent_config: AgentData,
        task_id: str | None = None,
        orientation: str | None = None,
        task_prompt: str | None = None,
        board_name: str | None = None,
        memory_mode: str = "clean",
        memory_workspace: Path | None = None,
        interactive_session_id: str | None = None,
    ) -> WorkspaceContext:
        """Set up the workspace directory for an agent and return its context.

        Creates directory structure, generates CLAUDE.md, maps skill symlinks,
        and writes the MCP config JSON.

        Args:
            agent_name: Unique agent identifier (used for paths and socket name).
            agent_config: Agent configuration data including prompt, soul, and skills.
            task_id: The Convex task _id being executed.
            orientation: Optional global orientation text to inject into CLAUDE.md.
            task_prompt: Optional task description for relevant history search.
            board_name: Optional board name for board-scoped workspace root.
            memory_mode: Agent memory mode for board workspace ("clean" or
                "with_history").

        Returns:
            WorkspaceContext with all resolved paths.

        Raises:
            ValueError: If agent_name is invalid (path traversal protection) or
                        if the resulting socket path exceeds the OS limit.
        """
        # C1: Validate agent_name to prevent path traversal
        if not agent_name or "/" in agent_name or agent_name.startswith("."):
            raise ValueError(f"Invalid agent name: {agent_name!r}")

        explicit_memory_workspace = memory_workspace

        if board_name:
            from mc.infrastructure.boards import resolve_board_workspace

            workspace = resolve_board_workspace(board_name, agent_name, mode=memory_mode)
            from mc.artifacts import resolve_board_artifacts_workspace

            artifacts_workspace = resolve_board_artifacts_workspace(board_name, root=self._root)
            if explicit_memory_workspace is not None:
                memory_workspace = explicit_memory_workspace
                memory_workspace.mkdir(parents=True, exist_ok=True)
                (memory_workspace / "memory").mkdir(exist_ok=True)
                (memory_workspace / "sessions").mkdir(exist_ok=True)
            elif memory_mode == "clean":
                memory_workspace = workspace
            else:
                memory_workspace = self._root / "agents" / agent_name
                memory_workspace.mkdir(parents=True, exist_ok=True)
                (memory_workspace / "memory").mkdir(exist_ok=True)
                (memory_workspace / "sessions").mkdir(exist_ok=True)
            # resolve_board_workspace already creates memory/ and sessions/.
            # Keep these calls for idempotent safety.
            (workspace / "memory").mkdir(parents=True, exist_ok=True)
            (workspace / "sessions").mkdir(exist_ok=True)
        else:
            workspace = self._root / "agents" / agent_name
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "memory").mkdir(exist_ok=True)
            (workspace / "sessions").mkdir(exist_ok=True)
            if explicit_memory_workspace is not None:
                memory_workspace = explicit_memory_workspace
                memory_workspace.mkdir(parents=True, exist_ok=True)
                (memory_workspace / "memory").mkdir(exist_ok=True)
                (memory_workspace / "sessions").mkdir(exist_ok=True)
            else:
                memory_workspace = workspace
            artifacts_workspace = None

        # --- Ephemeral CWD (fully container-local) ---
        # The CC bubblewrap sandbox cannot reliably operate on Docker host
        # bind-mounts (virtiofs/osxfs).  Everything the agent touches lives in
        # /tmp/mc-workspaces/.  MC (outside the sandbox) handles sync to/from
        # the persistent bind-mount before and after execution.
        suffix = task_id[:8] if task_id else uuid.uuid4().hex[:8]
        ephemeral_cwd = Path("/tmp/mc-workspaces") / f"{agent_name}-{suffix}"
        ephemeral_cwd.mkdir(parents=True, exist_ok=True)

        from claude_code.types import SyncTarget

        sync_targets: list[SyncTarget] = []

        # --- Copy memory (not symlink — bind-mount paths break bubblewrap) ---
        for subdir in ("memory", "sessions"):
            src = memory_workspace / subdir
            dest = ephemeral_cwd / subdir
            if dest.is_symlink():
                dest.unlink()
            elif dest.exists():
                shutil.rmtree(dest)
            if src.is_dir():
                shutil.copytree(src, dest)
            else:
                dest.mkdir(parents=True, exist_ok=True)
        # Memory and sessions need sync back after execution
        sync_targets.append(SyncTarget(
            local=ephemeral_cwd / "memory",
            persistent=memory_workspace / "memory",
        ))
        sync_targets.append(SyncTarget(
            local=ephemeral_cwd / "sessions",
            persistent=memory_workspace / "sessions",
        ))

        # --- Copy task attachments + create local output dir ---
        local_task_dir: str | None = None
        if task_id:
            from mc.types import task_safe_id

            safe_id = task_safe_id(task_id)
            persistent_task_dir = self._root / "tasks" / safe_id
            local_task = ephemeral_cwd / "task"
            local_task.mkdir(exist_ok=True)
            local_task_dir = str(local_task)

            # Copy attachments into container-local path
            persistent_attach = persistent_task_dir / "attachments"
            local_attach = local_task / "attachments"
            if local_attach.exists():
                shutil.rmtree(local_attach)
            if persistent_attach.is_dir():
                shutil.copytree(persistent_attach, local_attach)
            else:
                local_attach.mkdir(parents=True, exist_ok=True)

            # Create local output dir (agent writes here)
            local_output = local_task / "output"
            local_output.mkdir(exist_ok=True)
            # Sync output back to bind-mount after execution
            persistent_output = persistent_task_dir / "output"
            persistent_output.mkdir(parents=True, exist_ok=True)
            sync_targets.append(SyncTarget(
                local=local_output,
                persistent=persistent_output,
            ))

        # --- Copy board artifacts ---
        local_artifacts_workspace: Path | None = None
        if artifacts_workspace and artifacts_workspace.is_dir():
            local_artifacts = ephemeral_cwd / "artifacts"
            if local_artifacts.exists():
                shutil.rmtree(local_artifacts)
            shutil.copytree(artifacts_workspace, local_artifacts)
            local_artifacts_workspace = local_artifacts

        # Skills must be mapped BEFORE generating CLAUDE.md so the skills
        # summary in _generate_claude_md() can reference the mapped symlinks.
        self._map_skills(ephemeral_cwd, agent_config.skills, persistent_workspace=workspace)
        self._generate_claude_md(
            ephemeral_cwd,
            agent_config,
            orientation=orientation,
            task_prompt=task_prompt,
            memory_workspace=ephemeral_cwd,
            artifacts_workspace=local_artifacts_workspace,
            task_id=task_id,
            persistent_workspace=workspace,
            local_task_dir=local_task_dir,
        )

        # H3: Validate socket path length (macOS limit ~104 chars)
        socket_suffix = suffix
        socket_path = f"/tmp/mc-{agent_name}-{socket_suffix}.sock"
        if len(socket_path) > _MAX_SOCKET_PATH_LEN:
            raise ValueError(
                f"Socket path too long ({len(socket_path)} chars, max {_MAX_SOCKET_PATH_LEN}): {socket_path}"
            )
        self._generate_mcp_json(
            ephemeral_cwd,
            agent_name,
            task_id,
            socket_path,
            board_name=board_name,
            memory_workspace=ephemeral_cwd,
            interactive_session_id=interactive_session_id,
        )
        self._generate_hook_settings(
            ephemeral_cwd,
            agent_name=agent_name,
            task_id=task_id,
            socket_path=socket_path,
            interactive_session_id=interactive_session_id,
        )

        return WorkspaceContext(
            cwd=ephemeral_cwd,
            mcp_config=ephemeral_cwd / ".mcp.json",
            claude_md=ephemeral_cwd / "CLAUDE.md",
            socket_path=socket_path,
            sync_targets=sync_targets,
            persistent_memory_workspace=memory_workspace,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_claude_md(
        self,
        workspace: Path,
        config: AgentData,
        orientation: str | None = None,
        task_prompt: str | None = None,
        memory_workspace: Path | None = None,
        artifacts_workspace: Path | None = None,
        task_id: str | None = None,
        persistent_workspace: Path | None = None,
        local_task_dir: str | None = None,
    ) -> None:
        """Write CLAUDE.md with agent identity, context, and MCP tools guide.

        Section order:
          1. Agent Identity (name, role, display_name)
          2. Workspace guidance
          3. Runtime context
          4. System Prompt (config.prompt)
          4.5. Orientation (global agent context from MC)
          5. Bootstrap files (AGENTS.md, USER.md, TOOLS.md, IDENTITY.md)
          6. Memory (MEMORY.md content)
          7. Project Conventions
          8. MCP Tools Guide
          9. Skills summary
         10. Soul (config.soul) — last for personality override
        """
        parts: list[str] = []
        effective_memory_workspace = memory_workspace or workspace

        # 1. Agent identity section
        identity_lines: list[str] = []
        identity_lines.append("# Agent Identity\n")
        identity_lines.append(f"**Name**: {config.name}")
        identity_lines.append(f"**Role**: {config.role}")
        if config.display_name:
            identity_lines.append(f"**Display name**: {config.display_name}")
        parts.append("\n".join(identity_lines))

        # 2. Workspace guidance
        task_dir = local_task_dir
        parts.append(
            self._workspace_guidance(
                workspace,
                memory_workspace=effective_memory_workspace,
                artifacts_workspace=artifacts_workspace,
                task_dir=task_dir,
            )
        )

        # 3. Runtime context
        parts.append(self._runtime_context())

        # 4. System Prompt
        if config.prompt:
            parts.append(f"## System Prompt\n\n{config.prompt.strip()}")

        # 4.5. Orientation (global agent context from MC)
        if orientation:
            parts.append(f"## Orientation\n\n{orientation}")

        # 5. Bootstrap files (search persistent workspace for agent-local files)
        bootstrap = self._load_bootstrap_files(persistent_workspace or workspace)
        if bootstrap:
            parts.append(bootstrap)

        # 6. Memory
        memory = self._load_memory(effective_memory_workspace)
        if memory:
            parts.append(f"## Memory\n\n{memory}")

        # 6.5. Relevant history (hybrid search)
        if task_prompt:
            relevant = self._search_relevant_history(effective_memory_workspace, task_prompt)
            if relevant:
                parts.append(f"## Relevant History\n\n{relevant}")

        # 7. Project conventions
        parts.append(_DEFAULT_CONVENTIONS)

        # 8. MCP tools guide
        parts.append(_MCP_TOOLS_GUIDE)

        # 8.5. Always-on skills
        always_content = self._build_always_skills_content(workspace)
        if always_content:
            parts.append(f"## Active Skills\n\n{always_content}")

        # 9. Skills summary
        skills_summary = self._build_skills_summary(workspace, config.skills)
        if skills_summary:
            parts.append(
                f"## Skills\n\n"
                f"The following skills extend your capabilities. "
                f"Skill definitions are at `.claude/skills/<skill-name>/SKILL.md`. "
                f"To use a skill, read its SKILL.md file.\n\n"
                f"{skills_summary}"
            )

        # 10. Soul (personality override — keep last)
        if config.soul:
            parts.append(f"## Soul\n\n{config.soul.strip()}")

        content = "\n\n".join(parts)
        (workspace / "CLAUDE.md").write_text(content, encoding="utf-8")

    def _read_file_with_fallback(self, workspace: Path, filename: str) -> str | None:
        """Read file from agent workspace, falling back to global workspace.

        Args:
            workspace: The agent-specific workspace directory.
            filename: The file name to look for.

        Returns:
            File content (stripped) or None if not found in either location.
        """
        agent_file = workspace / filename
        if agent_file.exists():
            return agent_file.read_text(encoding="utf-8").strip()
        global_file = self._root / "workspace" / filename
        if global_file.exists():
            return global_file.read_text(encoding="utf-8").strip()
        return None

    def _load_bootstrap_files(self, workspace: Path) -> str:
        """Load bootstrap files from workspace (agent-local, then global fallback).

        Reads AGENTS.md, USER.md, TOOLS.md, IDENTITY.md in that order.
        SOUL.md is intentionally excluded — handled via config.soul.

        Args:
            workspace: The agent-specific workspace directory.

        Returns:
            Formatted bootstrap content string, or empty string if none found.
        """
        parts: list[str] = []
        for filename in _BOOTSTRAP_FILES:
            content = self._read_file_with_fallback(workspace, filename)
            if content:
                parts.append(f"## {filename}\n\n{content}")
        return "\n\n".join(parts) if parts else ""

    def _load_memory(self, workspace: Path) -> str | None:
        """Load memory context (long-term + recent history) via HybridMemoryStore.

        Falls back to raw MEMORY.md if mc.memory is unavailable.

        Args:
            workspace: The agent-specific workspace directory.

        Returns:
            Memory context string or None if empty/missing.
        """
        try:
            from mc.memory import create_memory_store

            store = create_memory_store(workspace)
            ctx = store.get_memory_context()
            return ctx if ctx else None
        except ImportError:
            pass
        memory_file = workspace / "memory" / "MEMORY.md"
        if not memory_file.exists():
            return None
        content = memory_file.read_text(encoding="utf-8").strip()
        return content if content else None

    def _search_relevant_history(self, workspace: Path, query: str) -> str | None:
        """Search agent memory for history relevant to the task prompt.

        Uses MemoryIndex for hybrid BM25+vector search if available.

        Args:
            workspace: The agent-specific workspace directory.
            query: Task description to search for.

        Returns:
            Formatted relevant history or None if unavailable/empty.
        """
        try:
            from mc.memory.index import MemoryIndex

            index = MemoryIndex(workspace / "memory")
            index.sync()
            results = index.search(query, top_k=5)
            if not results:
                return None
            return "\n".join(f"- {r.content.strip()}" for r in results)
        except ImportError:
            return None
        except Exception:
            logger.warning("Failed to search relevant history for workspace %s", workspace)
            return None

    def _build_always_skills_content(self, workspace: Path) -> str:
        """Load always-on skills content for injection into CLAUDE.md."""
        try:
            from nanobot.agent.skills import SkillsLoader  # type: ignore[import]

            loader = SkillsLoader(workspace, global_skills_dir=self._root / "workspace" / "skills")
            always_names = loader.get_always_skills()
            if not always_names:
                return ""
            return loader.load_skills_for_context(always_names)
        except ImportError:
            return ""

    def _build_skills_summary(self, workspace: Path, skill_names: list[str]) -> str:
        """Build skills summary from mapped skill symlinks.

        Tries to use SkillsLoader from nanobot.agent.skills for rich XML output;
        falls back to a simple listing from the .claude/skills/ symlinks.

        Args:
            workspace: The agent-specific workspace directory.
            skill_names: List of skill names configured for the agent.

        Returns:
            Skills summary string, or empty string if no skills.
        """
        try:
            from nanobot.agent.skills import SkillsLoader  # type: ignore[import]

            loader = SkillsLoader(workspace, global_skills_dir=self._root / "workspace" / "skills")
            return loader.build_skills_summary(allowed_names=skill_names)
        except ImportError:
            # Fallback: simple listing from symlinks
            skills_dir = workspace / ".claude" / "skills"
            if not skills_dir.exists():
                return ""
            entries = []
            for entry in sorted(skills_dir.iterdir()):
                if entry.is_dir() or entry.is_symlink():
                    entries.append(f"- **{entry.name}**: {entry}")
            return "\n".join(entries) if entries else ""

    def _runtime_context(self) -> str:
        """Build runtime metadata section.

        Returns:
            Runtime section string with OS, architecture, Python version, and time.
        """
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = time.strftime("%Z") or "UTC"
        return f"## Runtime\n\n{runtime}, Python {platform.python_version()}\nCurrent Time: {now} ({tz})\n"

    def _workspace_guidance(
        self,
        workspace: Path,
        *,
        memory_workspace: Path | None = None,
        artifacts_workspace: Path | None = None,
        task_dir: str | None = None,
    ) -> str:
        """Build workspace guidance section.

        Args:
            workspace: The agent-specific workspace directory.
            memory_workspace: Effective memory workspace, if distinct.
            artifacts_workspace: Board artifacts workspace, if applicable.
            task_dir: Absolute path to the task directory (attachments + output).

        Returns:
            Workspace guidance section string.
        """
        ws = str(workspace.expanduser().resolve())
        memory_ws = str((memory_workspace or workspace).expanduser().resolve())
        artifacts_ws = (
            str(artifacts_workspace.expanduser().resolve())
            if artifacts_workspace is not None
            else None
        )
        artifacts_line = ""
        if artifacts_ws:
            artifacts_line = f"- Board artifacts: {artifacts_ws}\n"
        if task_dir:
            task_line = (
                f"- Task files (attachments + output): {task_dir}\n"
                f"  - Read input from: {task_dir}/attachments/\n"
                f"  - Save output to: {task_dir}/output/\n"
                f"  - **If an output file already exists, Read it before using Write to overwrite.**\n"
            )
        else:
            task_line = "- Task-specific deliverables stay in task output directories.\n"
        return (
            f"## Workspace\n\n"
            f"Your workspace is at: {ws}\n"
            f"- Long-term memory: {memory_ws}/memory/MEMORY.md\n"
            f"{artifacts_line}"
            f"{task_line}"
            f"- Custom skills: .claude/skills/{{skill-name}}/SKILL.md\n"
        )

    def _map_skills(
        self,
        workspace: Path,
        skills: list[str],
        persistent_workspace: Path | None = None,
    ) -> None:
        """Copy skill directories into .claude/skills/ for each requested skill.

        Also registers each skill as a CC slash command in .claude/commands/
        so that the Skill tool can invoke them.

        Uses real copies (not symlinks) because Claude Code's Glob tool
        does not traverse symlinked directories.

        Search order (first match wins):
          1. persistent_workspace/skills/<skill_name>  (agent-local)
          2. self._root/workspace/skills/<skill_name>  (global)
          3. vendor builtin: vendor/nanobot/nanobot/skills/<skill_name>
        """
        import shutil

        logger.info(
            "[skills] Mapping %d skill(s) for workspace %s: %s",
            len(skills),
            workspace,
            skills,
        )
        skills_dir = workspace / ".claude" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        commands_dir = workspace / ".claude" / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)

        # Clean up stale entries: remove broken symlinks from old code AND
        # directory copies for skills no longer in the agent's config.
        current_skill_set = set(skills)
        for entry in list(skills_dir.iterdir()):
            if entry.is_symlink():
                # Migrate: remove old symlinks so they get replaced by copies
                logger.debug("Removing legacy symlink: %s", entry)
                entry.unlink()
            elif entry.is_dir() and entry.name not in current_skill_set:
                shutil.rmtree(entry)
                logger.info("[skills] Removed stale skill copy: %s", entry.name)

        _loader = None
        try:
            from nanobot.agent.skills import SkillsLoader

            _loader = SkillsLoader(
                workspace,
                global_skills_dir=self._root / "workspace" / "skills",
                builtin_skills_dir=self._vendor_skills,
            )
        except ImportError:
            pass

        mapped_skills: list[str] = []

        for skill_name in skills:
            # C2: Validate skill name to prevent path traversal
            if "/" in skill_name or skill_name.startswith("."):
                logger.warning("Skipping invalid skill name: %s", skill_name)
                continue

            target = self._find_skill(workspace, skill_name, persistent_workspace)
            if target is None:
                logger.warning("Skill '%s' not found in any search location — skipping", skill_name)
                continue

            if _loader and not _loader.is_skill_available(skill_name):
                missing = _loader.get_missing_requirements(skill_name) or "unknown"
                logger.warning(
                    "Skill '%s' is unavailable (missing: %s) — skipping",
                    skill_name,
                    missing,
                )
                continue

            dest_path = skills_dir / skill_name
            # Re-copy if source is newer or dest doesn't exist
            source_mtime = target.stat().st_mtime
            if dest_path.exists():
                dest_mtime = dest_path.stat().st_mtime
                if dest_mtime >= source_mtime:
                    logger.debug("[skills] '%s' already up-to-date", skill_name)
                    mapped_skills.append(skill_name)
                    continue
                # Source is newer — remove stale copy
                shutil.rmtree(dest_path)

            shutil.copytree(target, dest_path)
            mapped_skills.append(skill_name)
            logger.info("[skills] Copied '%s' → %s", skill_name, dest_path)

        # Register each mapped skill as a CC slash command so the Skill tool
        # can invoke them (e.g. /generate-image).
        self._register_skill_commands(commands_dir, skills_dir, mapped_skills)

    def _find_skill(
        self,
        workspace: Path,
        skill_name: str,
        persistent_workspace: Path | None = None,
    ) -> Path | None:
        """Return the first existing skill directory for *skill_name*, or None."""
        candidates = [
            *([persistent_workspace / "skills" / skill_name] if persistent_workspace else []),
            workspace / "skills" / skill_name,
            self._root / "workspace" / "skills" / skill_name,
            self._vendor_skills / skill_name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def _parse_skill_frontmatter(skill_md: Path) -> tuple[str, str]:
        """Extract name and description from a SKILL.md YAML frontmatter.

        Returns:
            (name, description) tuple.  Falls back to the file's parent
            directory name and an empty description if parsing fails.
        """
        import re

        text = skill_md.read_text(encoding="utf-8", errors="replace")
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not m:
            return skill_md.parent.name, ""

        block = m.group(1)
        name = skill_md.parent.name
        description = ""
        for line in block.splitlines():
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip("'\"")
            elif line.startswith("description:"):
                description = line.split(":", 1)[1].strip().strip("'\"")
        return name, description

    def _register_skill_commands(
        self,
        commands_dir: Path,
        skills_dir: Path,
        skill_names: list[str],
    ) -> None:
        """Create a CC slash command for each workspace skill.

        Generates ``.claude/commands/{skill-name}.md`` so that
        Claude Code's ``Skill`` tool can invoke workspace skills
        via ``/skill-name``.
        """
        for skill_name in skill_names:
            skill_md = skills_dir / skill_name / "SKILL.md"
            if not skill_md.exists():
                continue

            name, description = self._parse_skill_frontmatter(skill_md)
            # The command file tells CC to load the full SKILL.md
            command_content = (
                f"---\n"
                f"name: '{name}'\n"
                f"description: '{description}'\n"
                f"---\n\n"
                f"Read and follow the full skill definition at "
                f".claude/skills/{skill_name}/SKILL.md\n"
            )
            cmd_path = commands_dir / f"{skill_name}.md"
            cmd_path.write_text(command_content, encoding="utf-8")
            logger.debug("[skills] Registered CC command for '%s'", skill_name)

    def _generate_mcp_json(
        self,
        workspace: Path,
        agent_name: str,
        task_id: str | None,
        socket_path: str,
        *,
        board_name: str | None = None,
        memory_workspace: Path | None = None,
        interactive_session_id: str | None = None,
    ) -> None:
        """Write .mcp.json that configures the MC MCP bridge subprocess."""
        from mc.infrastructure.secrets import resolve_secret_env

        env: dict[str, str] = {
            **resolve_secret_env(),
            "MC_SOCKET_PATH": socket_path,
            "AGENT_NAME": agent_name,
            # search_memory must use the exact workspace chosen by execution,
            # not reconstruct a parallel path from board metadata.
            "MEMORY_WORKSPACE": str(memory_workspace or workspace),
        }
        if task_id:
            env["TASK_ID"] = task_id
        if interactive_session_id:
            env["MC_INTERACTIVE_SESSION_ID"] = interactive_session_id
        if board_name:
            env["BOARD_NAME"] = board_name
        if os.environ.get("CONVEX_URL"):
            env["CONVEX_URL"] = os.environ["CONVEX_URL"]
        if os.environ.get("CONVEX_ADMIN_KEY"):
            env["CONVEX_ADMIN_KEY"] = os.environ["CONVEX_ADMIN_KEY"]
        config: dict = {
            "mcpServers": {
                "mc": {
                    "command": "uv",
                    "args": [
                        "run",
                        "--project",
                        str(_PROJECT_ROOT),
                        "python",
                        "-m",
                        "mc.runtime.mcp.bridge",
                    ],
                    "env": env,
                }
            }
        }
        (workspace / ".mcp.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    def _generate_hook_settings(
        self,
        workspace: Path,
        *,
        agent_name: str,
        task_id: str | None,
        socket_path: str,
        interactive_session_id: str | None,
    ) -> None:
        claude_dir = workspace / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        settings_path = claude_dir / "settings.json"

        # The Docker container IS the sandbox boundary — disable CC's
        # internal bubblewrap sandbox which is unreliable on virtiofs/osxfs
        # bind-mounts and blocks legitimate file writes from Bash subprocesses.
        #
        # Permission rules use bare tool names (no path restriction) so every
        # tool is auto-approved regardless of path.  With bypassPermissions
        # mode these are redundant but serve as documentation and fallback.
        base_settings: dict = {
            "permissions": {
                "allow": [
                    "Bash(*)",
                    "Read",
                    "Edit",
                    "Write",
                ]
            },
            # Explicitly disable — container provides isolation.
            "sandbox": {
                "enabled": False,
            },
        }

        if interactive_session_id is None:
            base_settings["hooks"] = {}
            settings_path.write_text(json.dumps(base_settings, indent=2), encoding="utf-8")
            return

        command = self._build_hook_command(
            socket_path=socket_path,
            agent_name=agent_name,
            task_id=task_id,
            interactive_session_id=interactive_session_id,
        )
        command_hook = [{"hooks": [{"type": "command", "command": command}]}]
        tool_hook = [{"matcher": "*", "hooks": [{"type": "command", "command": command}]}]
        base_settings["hooks"] = {
            "SessionStart": command_hook,
            "UserPromptSubmit": command_hook,
            "PermissionRequest": command_hook,
            "Stop": command_hook,
            "PreToolUse": tool_hook,
            "PostToolUse": tool_hook,
            "PostToolUseFailure": tool_hook,
        }
        settings_path.write_text(json.dumps(base_settings, indent=2), encoding="utf-8")

    def _build_hook_command(
        self,
        *,
        socket_path: str,
        agent_name: str,
        task_id: str | None,
        interactive_session_id: str,
    ) -> str:
        env_parts = [
            f"MC_SOCKET_PATH={shlex.quote(socket_path)}",
            f"MC_INTERACTIVE_SESSION_ID={shlex.quote(interactive_session_id)}",
            f"AGENT_NAME={shlex.quote(agent_name)}",
        ]
        if task_id:
            env_parts.append(f"TASK_ID={shlex.quote(task_id)}")
        project_flag = f"--project {shlex.quote(str(_PROJECT_ROOT))}"
        return " ".join([*env_parts, f"uv run {project_flag} python -m claude_code.hook_bridge"])
