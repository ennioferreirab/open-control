"""Agent repository -- agent sync, queries, and config management."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.bridge.client import BridgeClient

logger = logging.getLogger(__name__)


class AgentRepository:
    """Data access methods for agent entities in Convex."""

    def __init__(self, client: "BridgeClient"):
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

    def list_deleted_agents(self) -> list[dict[str, Any]]:
        """List all soft-deleted agents from Convex.

        Returns:
            List of agent dicts with snake_case keys (all have deletedAt set).
        """
        result = self._client.query("agents:listDeleted")
        if result is None:
            return []
        return result

    def archive_agent_data(
        self,
        name: str,
        memory_content: str | None,
        history_content: str | None,
        session_data: str | None,
    ) -> None:
        """Archive local agent files to Convex before deleting the local folder.

        Args:
            name: Agent name.
            memory_content: Contents of MEMORY.md, or None if not present.
            history_content: Contents of HISTORY.md, or None if not present.
            session_data: Contents of session JSONL file(s), or None if not present.
        """
        args: dict[str, Any] = {"agent_name": name}
        if memory_content is not None:
            args["memory_content"] = memory_content
        if history_content is not None:
            args["history_content"] = history_content
        if session_data is not None:
            args["session_data"] = session_data
        self._client.mutation("agents:archiveAgentData", args)

    def get_agent_archive(self, name: str) -> dict[str, Any] | None:
        """Fetch archived memory/history/session data for an agent.

        Returns:
            Dict with keys memory_content, history_content, session_data
            (each str | None), or None if agent has no archived data.
        """
        return self._client.query("agents:getArchive", {"agent_name": name})

    def clear_agent_archive(self, name: str) -> None:
        """Clear archived memory/history/session fields from the agent's Convex document.

        Called after _restore_archived_files succeeds to free storage space and
        prevent stale data from being re-archived if the agent is deleted again.
        """
        self._client.mutation("agents:clearAgentArchive", {"agent_name": name})

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

    def write_agent_config(
        self, agent_data: dict[str, Any], agents_dir: Path
    ) -> None:
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
        (agent_dir / "memory").mkdir(exist_ok=True)
        (agent_dir / "skills").mkdir(exist_ok=True)
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

        claude_code = agent_data.get("claude_code_opts") or agent_data.get(
            "claude_code"
        )
        if claude_code and isinstance(claude_code, dict):
            config["claude_code"] = claude_code

        config_path.write_text(
            yaml.dump(
                config, default_flow_style=False, allow_unicode=True, sort_keys=False
            ),
            encoding="utf-8",
        )
        logger.info("Wrote agent config to %s", config_path)

        # Generate SOUL.md if not already present (preserves user edits)
        role = agent_data.get("role", "Agent")
        ensure_soul_md(agent_dir, name, role, soul)

    @staticmethod
    def _log_state_transition(entity_type: str, description: str) -> None:
        """Log a state transition to local stdout via logging."""
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info("[MC] %s %s: %s", timestamp, entity_type, description)
