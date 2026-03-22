"""Agent repository -- agent sync, queries, and config management."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.bridge.client import BridgeClientProtocol

logger = logging.getLogger(__name__)


class AgentRepository:
    """Data access methods for agent entities in Convex."""

    def __init__(self, client: BridgeClientProtocol):
        self._client = client

    def sync_agent(self, agent_data: Any) -> Any:
        """Upsert an agent in Convex by name.

        Args:
            agent_data: An AgentData instance with name, display_name, role,
                        prompt, soul, skills, model.

        Returns:
            Mutation result (if any).
        """
        args: dict[str, Any] = {
            "name": agent_data.name,
            "display_name": agent_data.display_name,
            "role": agent_data.role,
            "skills": agent_data.skills,
            "model": agent_data.model,
        }
        if agent_data.prompt:
            args["prompt"] = agent_data.prompt
        if agent_data.soul:
            args["soul"] = agent_data.soul
        if agent_data.is_system:
            args["is_system"] = True
        if agent_data.backend != "nanobot":
            args["backend"] = agent_data.backend
        if agent_data.interactive_provider is not None:
            args["interactive_provider"] = agent_data.interactive_provider
        cc_opts = agent_data.claude_code_opts
        if cc_opts is not None:
            cc_payload: dict[str, Any] = {}
            if cc_opts.permission_mode is not None:
                cc_payload["permission_mode"] = cc_opts.permission_mode
            if cc_opts.max_budget_usd is not None:
                cc_payload["max_budget_usd"] = cc_opts.max_budget_usd
            if cc_opts.max_turns is not None:
                cc_payload["max_turns"] = cc_opts.max_turns
            if cc_payload:
                args["claude_code_opts"] = cc_payload
        return self._client.mutation("agents:upsertByName", args)

    def list_agents(self) -> list[dict[str, Any]]:
        """List all agents from Convex.

        Returns:
            List of agent dicts with snake_case keys.
        """
        result = self._client.query("agents:list")
        if result is None:
            return []
        return result

    def get_agent_by_name(self, name: str) -> dict[str, Any] | None:
        """Fetch a single agent from Convex by name.

        Returns the agent dict with snake_case keys, or None if not found.
        """
        return self._client.query("agents:getByName", {"name": name})

    def list_active_registry_view(self) -> list[dict[str, Any]]:
        """Return the active delegatable agent roster with role, skills, squads, and metrics.

        Returns:
            List of registry view dicts. Each entry contains agentId, name,
            displayName, role, skills, squads, enabled, status, tasksExecuted,
            stepsExecuted, lastTaskExecutedAt, lastStepExecutedAt, and lastActiveAt.
        """
        result = self._client.query("agents:listActiveRegistryView")
        if result is None:
            return []
        return result

    def list_deleted_agents(self) -> list[dict[str, Any]]:
        """List all soft-deleted agents from Convex.

        Returns:
            List of agent dicts with snake_case keys (all have deletedAt set).
        """
        result = self._client.query("agents:listDeleted")
        if result is None:
            return []
        return result

    def backup_agent_memory(
        self,
        name: str,
        boards_data: list[dict[str, Any]],
        global_data: dict[str, str | None] | None = None,
    ) -> None:
        """Back up agent memory to Convex (board-scoped + optional global).

        Args:
            name: Agent name.
            boards_data: List of dicts with board_name, memory_content, history_content.
            global_data: Optional dict with memory_content, history_content for global workspace (nanobot only).
        """
        args: dict[str, Any] = {
            "agent_name": name,
            "boards": boards_data,
        }
        if global_data:
            if global_data.get("memory_content") is not None:
                args["global_memory_content"] = global_data["memory_content"]
            if global_data.get("history_content") is not None:
                args["global_history_content"] = global_data["history_content"]
        self._client.mutation("agents:upsertMemoryBackup", args)

    def get_agent_memory_backup(self, name: str) -> dict[str, Any] | None:
        """Fetch memory backup data for an agent.

        Returns:
            Dict with boards array and optional global fields, or None if no backup.
        """
        return self._client.query("agents:getMemoryBackup", {"agent_name": name})

    def deactivate_agents_except(self, active_names: list[str]) -> Any:
        """Set status to 'idle' for all agents NOT in the provided list.

        Args:
            active_names: Names of agents that should remain active.

        Returns:
            Mutation result (if any).
        """
        return self._client.mutation(
            "agents:deactivateExcept",
            {"active_names": active_names},
        )

    def update_agent_status(
        self,
        agent_name: str,
        status: str,
        description: str | None = None,
    ) -> Any:
        """Update an agent's status with retry and logging."""
        result = self._client.mutation(
            "agents:updateStatus",
            {"agent_name": agent_name, "status": status},
        )
        self._log_state_transition(
            "agent",
            description or f"Agent '{agent_name}' status changed to {status}",
        )
        return result

    def write_agent_config(self, agent_data: dict[str, Any], agents_dir: Path) -> None:
        """Write an agent's config back to local YAML.

        Used for Convex -> local write-back when dashboard edits are newer
        than the local file.

        Args:
            agent_data: Agent dict with snake_case keys (from Convex query).
            agents_dir: Path to the agents directory (e.g. ~/.nanobot/agents/).
        """
        import yaml

        from mc.cli.agent_assist import ensure_soul_md

        name = agent_data["name"]
        agent_dir = agents_dir / name
        agent_dir.mkdir(parents=True, exist_ok=True)
        for subdir in ("memory", "skills"):
            p = agent_dir / subdir
            # Remove broken symlinks left over from previous runs
            if p.is_symlink() and not p.exists():
                p.unlink()
            p.mkdir(exist_ok=True)
        config_path = agent_dir / "config.yaml"

        config: dict[str, Any] = {
            "name": name,
            "role": agent_data.get("role", ""),
            "prompt": agent_data.get("prompt", ""),
        }

        skills = agent_data.get("skills")
        if skills:
            config["skills"] = skills

        model = agent_data.get("model")
        if model:
            config["model"] = model

        display_name = agent_data.get("display_name")
        if display_name:
            config["display_name"] = display_name

        soul = agent_data.get("soul")
        if soul:
            config["soul"] = soul

        backend = agent_data.get("backend")
        if backend and backend != "nanobot":
            config["backend"] = backend
        interactive_provider = agent_data.get("interactive_provider")
        if interactive_provider:
            config["interactive_provider"] = interactive_provider

        claude_code = agent_data.get("claude_code_opts") or agent_data.get("claude_code")
        if claude_code and isinstance(claude_code, dict):
            config["claude_code"] = claude_code

        config_path.write_text(
            yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        logger.info("Wrote agent config to %s", config_path)

        # Generate SOUL.md if not already present (preserves user edits)
        role = agent_data.get("role", "Agent")
        ensure_soul_md(agent_dir, name, role, soul)

    @staticmethod
    def _log_state_transition(entity_type: str, description: str) -> None:
        """Log a state transition to local stdout via logging."""
        timestamp = datetime.now(UTC).isoformat()
        logger.info("[MC] %s %s: %s", timestamp, entity_type, description)
