"""Claude Code Workspace Manager.

Prepares per-agent workspaces for Claude Code execution:
  - Creates directory structure (memory/, sessions/)
  - Generates CLAUDE.md with agent identity and MCP tools guide
  - Maps skill symlinks into .claude/skills/
  - Generates .mcp.json pointing at the mc.mcp_bridge subprocess
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from mc.types import AgentData, WorkspaceContext

logger = logging.getLogger(__name__)

# Path to the vendor nanobot skills directory (builtin skills).
# Try to import the canonical constant from upstream; fall back to the
# path computed from __file__ so this module keeps working if the
# vendor package layout changes.
try:
    from nanobot.agent.skills import BUILTIN_SKILLS_DIR as _VENDOR_SKILLS_DIR  # type: ignore[import]
except ImportError:  # pragma: no cover – vendor package not on path
    _VENDOR_SKILLS_DIR = Path(__file__).parent.parent / "vendor" / "nanobot" / "nanobot" / "skills"

_MCP_TOOLS_GUIDE = """\
## Available MCP Tools (nanobot server)

Use these tools via the `mcp__nanobot__` prefix:

- **mcp__nanobot__ask_user** — Ask the human user a question and wait for a reply.
- **mcp__nanobot__send_message** — Send a message to another agent or to the task thread.
- **mcp__nanobot__delegate_task** — Delegate a subtask to a specialist agent.
- **mcp__nanobot__ask_agent** — Ask a specific agent a question and get a reply.
- **mcp__nanobot__report_progress** — Report task progress back to Mission Control.

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


class CCWorkspaceManager:
    """Prepares Claude Code agent workspaces."""

    def __init__(
        self,
        workspace_root: Path | None = None,
        vendor_skills_dir: Path | None = None,
    ) -> None:
        self._root = workspace_root or Path.home() / ".nanobot"
        self._vendor_skills = vendor_skills_dir or _VENDOR_SKILLS_DIR

    def prepare(self, agent_name: str, agent_config: AgentData, task_id: str) -> WorkspaceContext:
        """Set up the workspace directory for an agent and return its context.

        Creates directory structure, generates CLAUDE.md, maps skill symlinks,
        and writes the MCP config JSON.

        Args:
            agent_name: Unique agent identifier (used for paths and socket name).
            agent_config: Agent configuration data including prompt, soul, and skills.
            task_id: The Convex task _id being executed.

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

        self._generate_claude_md(workspace, agent_config)
        self._map_skills(workspace, agent_config.skills)

        # H3: Validate socket path length (macOS limit ~104 chars)
        socket_path = f"/tmp/mc-{agent_name}.sock"
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

    def _generate_claude_md(self, workspace: Path, config: AgentData) -> None:
        """Write CLAUDE.md with agent identity and MCP tools guide."""
        lines: list[str] = []

        # Agent identity section
        lines.append("# Agent Identity\n")
        lines.append(f"**Name**: {config.name}")
        lines.append(f"**Role**: {config.role}")
        if config.display_name:
            lines.append(f"**Display name**: {config.display_name}")
        lines.append("")

        if config.prompt:
            lines.append("## System Prompt\n")
            lines.append(config.prompt.strip())
            lines.append("")

        # H1: Project conventions section (AC1 requirement)
        lines.append(_DEFAULT_CONVENTIONS)

        # MCP tools guide
        lines.append(_MCP_TOOLS_GUIDE)

        # Soul (personality / long-term memory)
        if config.soul:
            lines.append("## Soul\n")
            lines.append(config.soul.strip())
            lines.append("")

        content = "\n".join(lines)
        (workspace / "CLAUDE.md").write_text(content, encoding="utf-8")

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

        for skill_name in skills:
            # C2: Validate skill name to prevent path traversal
            if "/" in skill_name or skill_name.startswith("."):
                logger.warning("Skipping invalid skill name: %s", skill_name)
                continue

            target = self._find_skill(workspace, skill_name)
            if target is None:
                logger.warning("Skill '%s' not found in any search location — skipping", skill_name)
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
                    "args": ["run", "python", "-m", "mc.mcp_bridge"],
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
