"""Claude Code Workspace Manager.

Prepares per-agent workspaces for Claude Code execution:
  - Creates directory structure (memory/, sessions/)
  - Generates CLAUDE.md with agent identity and MCP tools guide
  - Maps skill symlinks into .claude/skills/
  - Generates .mcp.json pointing at the claude_code.mcp_bridge subprocess
"""

from __future__ import annotations

import json
import logging
import platform
import time
from datetime import datetime
from pathlib import Path

from mc.types import AgentData
from claude_code.types import WorkspaceContext

logger = logging.getLogger(__name__)

# Path to the vendor nanobot skills directory (builtin skills).
# Try to import the canonical constant from upstream; fall back to the
# path computed from __file__ so this module keeps working if the
# vendor package layout changes.
try:
    from nanobot.agent.skills import BUILTIN_SKILLS_DIR as _VENDOR_SKILLS_DIR  # type: ignore[import]
except ImportError:  # pragma: no cover – vendor package not on path
    _VENDOR_SKILLS_DIR = Path(__file__).parent.parent.parent / "nanobot" / "nanobot" / "skills"

_MCP_TOOLS_GUIDE = """\
## Available MCP Tools (nanobot server)

Use these tools via the `mcp__nanobot__` prefix:

- **mcp__nanobot__ask_user** — Ask the human user a question and wait for their reply.
- **mcp__nanobot__send_message** — Send a message to another agent or to the task thread.
- **mcp__nanobot__delegate_task** — Delegate a subtask to a specialist agent.
- **mcp__nanobot__ask_agent** — Ask a specific agent a question and get a reply.
- **mcp__nanobot__report_progress** — Report task progress back to Mission Control.
- **mcp__nanobot__cron** — Schedule reminders and recurring tasks (add/list/remove).
- **mcp__nanobot__search_memory** — Search agent memory and history for relevant past events and decisions.

### CRITICAL: User Interaction Rules

**NEVER** guess, assume, or fabricate user input. If a task requires information from the user:

1. Call `mcp__nanobot__ask_user` with your question.
2. The call BLOCKS until the user replies — wait for it.
3. Only then proceed to the next question or action.

Examples of when you MUST use `mcp__nanobot__ask_user`:
- Running a questionnaire or wizard (ask each question one at a time, wait for reply)
- Confirming a destructive action before executing it
- Gathering required parameters that were not provided in the task

> **IMPORTANT**: `AskUserQuestion` does NOT work. You MUST use `mcp__nanobot__ask_user` instead.
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


class CCWorkspaceManager:
    """Prepares Claude Code agent workspaces."""

    def __init__(
        self,
        workspace_root: Path | None = None,
        vendor_skills_dir: Path | None = None,
    ) -> None:
        self._root = workspace_root or Path.home() / ".nanobot"
        self._vendor_skills = vendor_skills_dir or _VENDOR_SKILLS_DIR

    def prepare(
        self,
        agent_name: str,
        agent_config: AgentData,
        task_id: str,
        orientation: str | None = None,
        task_prompt: str | None = None,
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

        Returns:
            WorkspaceContext with all resolved paths.

        Raises:
            ValueError: If agent_name is invalid (path traversal protection) or
                        if the resulting socket path exceeds the OS limit.
        """
        # C1: Validate agent_name to prevent path traversal
        if not agent_name or "/" in agent_name or agent_name.startswith("."):
            raise ValueError(f"Invalid agent name: {agent_name!r}")

        workspace = self._root / "agents" / agent_name
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "memory").mkdir(exist_ok=True)
        (workspace / "sessions").mkdir(exist_ok=True)

        # Skills must be mapped BEFORE generating CLAUDE.md so the skills
        # summary in _generate_claude_md() can reference the mapped symlinks.
        self._map_skills(workspace, agent_config.skills)
        self._generate_claude_md(workspace, agent_config, orientation=orientation,
                                 task_prompt=task_prompt)

        # H3: Validate socket path length (macOS limit ~104 chars)
        # Include first 8 chars of task_id to prevent socket clobber when the
        # same agent runs concurrent tasks (HIGH-2 fix).
        socket_path = f"/tmp/mc-{agent_name}-{task_id[:8]}.sock"
        if len(socket_path) > _MAX_SOCKET_PATH_LEN:
            raise ValueError(
                f"Socket path too long ({len(socket_path)} chars, max {_MAX_SOCKET_PATH_LEN}): {socket_path}"
            )
        self._generate_mcp_json(workspace, agent_name, task_id, socket_path)

        return WorkspaceContext(
            cwd=workspace,
            mcp_config=workspace / ".mcp.json",
            claude_md=workspace / "CLAUDE.md",
            socket_path=socket_path,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_claude_md(
        self, workspace: Path, config: AgentData, orientation: str | None = None,
        task_prompt: str | None = None,
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

        # 1. Agent identity section
        identity_lines: list[str] = []
        identity_lines.append("# Agent Identity\n")
        identity_lines.append(f"**Name**: {config.name}")
        identity_lines.append(f"**Role**: {config.role}")
        if config.display_name:
            identity_lines.append(f"**Display name**: {config.display_name}")
        parts.append("\n".join(identity_lines))

        # 2. Workspace guidance
        parts.append(self._workspace_guidance(workspace))

        # 3. Runtime context
        parts.append(self._runtime_context())

        # 4. System Prompt
        if config.prompt:
            parts.append(f"## System Prompt\n\n{config.prompt.strip()}")

        # 4.5. Orientation (global agent context from MC)
        if orientation:
            parts.append(f"## Orientation\n\n{orientation}")

        # 5. Bootstrap files
        bootstrap = self._load_bootstrap_files(workspace)
        if bootstrap:
            parts.append(bootstrap)

        # 6. Memory
        memory = self._load_memory(workspace)
        if memory:
            parts.append(f"## Memory\n\n{memory}")

        # 6.5. Relevant history (hybrid search)
        if task_prompt:
            relevant = self._search_relevant_history(workspace, task_prompt)
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
        """Read {workspace}/memory/MEMORY.md and return its content.

        Args:
            workspace: The agent-specific workspace directory.

        Returns:
            Memory content string or None if empty/missing.
        """
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

    def _workspace_guidance(self, workspace: Path) -> str:
        """Build workspace guidance section.

        Args:
            workspace: The agent-specific workspace directory.

        Returns:
            Workspace guidance section string.
        """
        ws = str(workspace.expanduser().resolve())
        return (
            f"## Workspace\n\n"
            f"Your workspace is at: {ws}\n"
            f"- Long-term memory: {ws}/memory/MEMORY.md\n"
            f"- Custom skills: .claude/skills/{{skill-name}}/SKILL.md\n"
        )

    def _map_skills(self, workspace: Path, skills: list[str]) -> None:
        """Create symlinks under .claude/skills/ for each requested skill.

        Search order (first match wins):
          1. workspace/skills/<skill_name>
          2. self._root/workspace/skills/<skill_name>
          3. vendor builtin: vendor/nanobot/nanobot/skills/<skill_name>
        """
        skills_dir = workspace / ".claude" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)

        # Clean up existing broken symlinks
        for entry in skills_dir.iterdir():
            if entry.is_symlink() and not entry.resolve().exists():
                logger.debug("Removing broken symlink: %s", entry)
                entry.unlink()

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

        for skill_name in skills:
            # C2: Validate skill name to prevent path traversal
            if "/" in skill_name or skill_name.startswith("."):
                logger.warning("Skipping invalid skill name: %s", skill_name)
                continue

            target = self._find_skill(workspace, skill_name)
            if target is None:
                logger.warning("Skill '%s' not found in any search location — skipping", skill_name)
                continue

            if _loader and not _loader.is_skill_available(skill_name):
                missing = _loader.get_missing_requirements(skill_name) or "unknown"
                logger.warning(
                    "Skill '%s' is unavailable (missing: %s) — skipping symlink",
                    skill_name, missing,
                )
                continue

            link_path = skills_dir / skill_name
            # Remove stale symlink pointing elsewhere before re-creating
            if link_path.is_symlink():
                if link_path.resolve() == target.resolve():
                    continue  # Already correct
                link_path.unlink()
            elif link_path.exists():
                logger.warning(
                    "Skill path '%s' exists as a non-symlink — skipping symlink creation",
                    link_path,
                )
                continue

            link_path.symlink_to(target)
            logger.debug("Mapped skill '%s' → %s", skill_name, target)

    def _find_skill(self, workspace: Path, skill_name: str) -> Path | None:
        """Return the first existing skill directory for *skill_name*, or None."""
        candidates = [
            workspace / "skills" / skill_name,
            self._root / "workspace" / "skills" / skill_name,
            self._vendor_skills / skill_name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _generate_mcp_json(
        self,
        workspace: Path,
        agent_name: str,
        task_id: str,
        socket_path: str,
    ) -> None:
        """Write .mcp.json that configures the nanobot MCP server subprocess."""
        config: dict = {
            "mcpServers": {
                "nanobot": {
                    "command": "uv",
                    "args": ["run", "python", "-m", "claude_code.mcp_bridge"],
                    "env": {
                        "MC_SOCKET_PATH": socket_path,
                        "AGENT_NAME": agent_name,
                        "TASK_ID": task_id,
                    },
                }
            }
        }
        (workspace / ".mcp.json").write_text(
            json.dumps(config, indent=2), encoding="utf-8"
        )
