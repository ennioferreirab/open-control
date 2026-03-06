"""
ConvexBridge subscription and sync mixin.

Extracts subscription polling, agent sync/archive, file sync, and
write-back operations into a dedicated mixin class.  ConvexBridge
inherits from this mixin so all methods remain accessible on the
bridge instance — no external callers need to change.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from mc.types import task_safe_id

logger = logging.getLogger(__name__)


class ConvexBridgeSubscriptionsMixin:
    """Mixin providing subscription, sync, and write-back methods.

    All methods assume ``self`` is a ``ConvexBridge`` instance (with
    ``query``, ``mutation``, ``_mutation_with_retry``,
    ``_log_state_transition``, ``create_activity``, and ``_client``
    attributes).
    """

    # ── Subscriptions ────────────────────────────────────────────────

    def subscribe(
        self, function_name: str, args: dict[str, Any] | None = None
    ) -> Iterator[Any]:
        """
        Subscribe to a Convex query for real-time updates.

        Args:
            function_name: Convex query in colon notation (e.g., "tasks:list")
            args: Optional arguments dict (snake_case keys — converted to camelCase)

        Yields:
            Updated results with camelCase keys converted to snake_case
        """
        from mc.bridge import _convert_keys_to_camel, _convert_keys_to_snake

        camel_args = _convert_keys_to_camel(args) if args else {}
        logger.debug("subscribe %s args=%s", function_name, camel_args)
        for result in self._client.subscribe(function_name, camel_args):
            yield _convert_keys_to_snake(result)

    def async_subscribe(
        self,
        function_name: str,
        args: dict[str, Any] | None = None,
        poll_interval: float = 2.0,
    ) -> "asyncio.Queue[Any]":
        """Subscribe to a Convex query, returning an asyncio.Queue.

        Uses a polling strategy: periodically queries Convex and pushes
        results into an asyncio.Queue when data changes.  This avoids
        the thread-safety issues with the Convex Python SDK's blocking
        subscription iterator and ``call_soon_threadsafe``.

        Args:
            function_name: Convex query in colon notation.
            args: Optional arguments dict (snake_case keys).
            poll_interval: Seconds between polls. Defaults to 2.0.

        Returns:
            An asyncio.Queue that yields query results on each change.
        """
        import asyncio

        queue: asyncio.Queue[Any] = asyncio.Queue()

        async def _poll() -> None:
            last_result: Any = None
            consecutive_errors = 0
            max_errors = 10
            while True:
                try:
                    result = await asyncio.to_thread(
                        self.query, function_name, args
                    )
                    consecutive_errors = 0
                    if result != last_result:
                        queue.put_nowait(result)
                        last_result = result
                except Exception as exc:
                    consecutive_errors += 1
                    if consecutive_errors >= max_errors:
                        logger.error(
                            "Poll %s failed %d times consecutively: %s",
                            function_name, max_errors, exc,
                        )
                        queue.put_nowait(
                            {"_error": True, "message": str(exc)}
                        )
                        return
                    logger.warning(
                        "Poll %s error (attempt %d/%d): %s",
                        function_name, consecutive_errors, max_errors, exc,
                    )
                await asyncio.sleep(poll_interval)

        asyncio.get_running_loop().create_task(_poll())
        return queue

    # ── Agent sync / archive ─────────────────────────────────────────

    def list_agents(self) -> list[dict[str, Any]]:
        """List all agents from Convex.

        Returns:
            List of agent dicts with snake_case keys.
        """
        result = self.query("agents:list")
        if result is None:
            return []
        return result

    def get_agent_by_name(self, name: str) -> dict[str, Any] | None:
        """Fetch a single agent from Convex by name.

        Returns the agent dict with snake_case keys, or None if not found.
        """
        return self.query("agents:getByName", {"name": name})

    def sync_agent(self, agent_data: Any) -> Any:
        """Upsert an agent in Convex by name.

        Args:
            agent_data: An AgentData instance with name, display_name, role, prompt, soul, skills, model.

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
        return self.mutation("agents:upsertByName", args)

    def list_deleted_agents(self) -> list[dict[str, Any]]:
        """List all soft-deleted agents from Convex.

        Returns:
            List of agent dicts with snake_case keys (all have deletedAt set).
        """
        result = self.query("agents:listDeleted")
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
        self.mutation("agents:archiveAgentData", args)

    def get_agent_archive(self, name: str) -> dict[str, Any] | None:
        """Fetch archived memory/history/session data for an agent.

        Returns:
            Dict with keys memory_content, history_content, session_data (each str | None),
            or None if agent has no archived data.
        """
        return self.query("agents:getArchive", {"agent_name": name})

    def clear_agent_archive(self, name: str) -> None:
        """Clear archived memory/history/session fields from the agent's Convex document.

        Called after _restore_archived_files succeeds to free storage space and
        prevent stale data from being re-archived if the agent is deleted again.
        """
        self.mutation("agents:clearAgentArchive", {"agent_name": name})

    def deactivate_agents_except(self, active_names: list[str]) -> Any:
        """Set status to 'idle' for all agents NOT in the provided list.

        Args:
            active_names: Names of agents that should remain active.

        Returns:
            Mutation result (if any).
        """
        return self.mutation(
            "agents:deactivateExcept",
            {"active_names": active_names},
        )

    # ── Write-back / config sync ─────────────────────────────────────

    def write_agent_config(self, agent_data: dict[str, Any], agents_dir: Path) -> None:
        """Write an agent's config back to local YAML.

        Used for Convex -> local write-back when dashboard edits are newer
        than the local file.

        Args:
            agent_data: Agent dict with snake_case keys (from Convex query).
            agents_dir: Path to the agents directory (e.g. ~/.nanobot/agents/).
        """
        import yaml

        from mc.agent_assist import ensure_soul_md

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

    # ── File sync ────────────────────────────────────────────────────

    def sync_task_output_files(self, task_id: str, task_data: dict, agent_name: str = "agent") -> None:
        """Scan output/ directory and sync file manifest in Convex.

        - Adds new output files not yet in the manifest
        - Replaces the output section if stale entries exist
        - Creates activity event if new files were found
        """
        EXT_MIME: dict[str, str] = {
            "pdf": "application/pdf", "md": "text/markdown", "markdown": "text/markdown",
            "html": "text/html", "htm": "text/html", "txt": "text/plain",
            "csv": "text/csv", "json": "application/json", "yaml": "text/yaml",
            "yml": "text/yaml", "xml": "application/xml", "py": "text/x-python",
            "ts": "text/typescript", "tsx": "text/typescript", "js": "text/javascript",
            "jsx": "text/javascript", "go": "text/x-go", "rs": "text/x-rust",
            "sh": "text/x-sh", "bash": "text/x-sh",
        }

        safe_id = task_safe_id(task_id)
        output_dir = Path.home() / ".nanobot" / "tasks" / safe_id / "output"

        if not output_dir.exists():
            return

        # Scan filesystem
        now = datetime.now(timezone.utc).isoformat()
        fs_files: list[dict] = []
        try:
            for entry in output_dir.iterdir():
                if entry.is_file():
                    ext = entry.suffix.lstrip(".").lower()
                    mime = EXT_MIME.get(ext, "application/octet-stream")
                    fs_files.append({
                        "name": entry.name,
                        "type": mime,
                        "size": entry.stat().st_size,
                        "subfolder": "output",
                        "uploaded_at": now,
                    })
        except OSError as exc:
            logger.error("[bridge] Failed to scan output dir %s: %s", output_dir, exc)
            return

        # Compare with existing manifest
        existing_output = {
            f["name"] for f in (task_data.get("files") or [])
            if f.get("subfolder") == "output"
        }
        fs_names = {f["name"] for f in fs_files}

        new_files = [f for f in fs_files if f["name"] not in existing_output]
        stale_names = existing_output - fs_names

        if not new_files and not stale_names:
            return  # nothing to do

        # Update Convex — replace full output section
        try:
            self._mutation_with_retry("tasks:updateTaskOutputFiles", {
                "task_id": task_id,
                "output_files": fs_files,
            })
            logger.info("[bridge] Synced %d output file(s) for task %s", len(fs_files), task_id)
        except Exception as exc:
            logger.error("[bridge] Failed to sync output files for task %s: %s", task_id, exc)
            return

        if stale_names:
            logger.warning(
                "[bridge] Manifest reconciliation: removed %d orphaned entries for task %s",
                len(stale_names), task_id,
            )

        # Activity event for new files
        if new_files:
            file_names = ", ".join(f["name"] for f in new_files)
            msg = f"{agent_name} produced {len(new_files)} output file(s): {file_names}"
            try:
                self.create_activity("agent_output", msg, task_id=task_id)
            except Exception as exc:
                logger.error("[bridge] Failed to create output file activity: %s", exc)

    def sync_output_files_to_parent(
        self, source_task_id: str, parent_task_id: str, agent_name: str = "agent"
    ) -> None:
        """Sync output files from a cron-triggered task to its parent task.

        Fetches files from the source task's output/ directory and appends
        any new filenames (append-only) to the parent task's output section.
        """
        EXT_MIME: dict[str, str] = {
            "pdf": "application/pdf", "md": "text/markdown", "markdown": "text/markdown",
            "html": "text/html", "htm": "text/html", "txt": "text/plain",
            "csv": "text/csv", "json": "application/json", "yaml": "text/yaml",
            "yml": "text/yaml", "xml": "application/xml", "py": "text/x-python",
            "ts": "text/typescript", "tsx": "text/typescript", "js": "text/javascript",
            "jsx": "text/javascript", "go": "text/x-go", "rs": "text/x-rust",
            "sh": "text/x-sh", "bash": "text/x-sh",
        }
        safe_source_id = re.sub(r"[^\w\-]", "_", source_task_id)
        source_output_dir = Path.home() / ".nanobot" / "tasks" / safe_source_id / "output"
        if not source_output_dir.exists():
            return
        now = datetime.utcnow().isoformat() + "Z"
        source_files: list[dict] = []
        try:
            for entry in source_output_dir.iterdir():
                if entry.is_file():
                    ext = entry.suffix.lstrip(".").lower()
                    mime = EXT_MIME.get(ext, "application/octet-stream")
                    source_files.append({
                        "name": entry.name, "type": mime,
                        "size": entry.stat().st_size, "subfolder": "output", "uploaded_at": now,
                    })
        except OSError as exc:
            logger.error("[bridge] Failed to scan source output dir %s: %s", source_output_dir, exc)
            return
        if not source_files:
            return
        try:
            parent_task = self.query("tasks:getById", {"task_id": parent_task_id})
            parent_files = (parent_task or {}).get("files") or []
        except Exception:
            logger.warning("[bridge] Could not fetch parent task %s", parent_task_id)
            parent_files = []
        existing_output = [f for f in parent_files if f.get("subfolder") == "output"]
        existing_names = {f["name"] for f in existing_output}
        truly_new = [f for f in source_files if f["name"] not in existing_names]
        if not truly_new:
            return
        merged_output = existing_output + truly_new
        try:
            self._mutation_with_retry("tasks:updateTaskOutputFiles", {
                "task_id": parent_task_id, "output_files": merged_output,
            })
            logger.info("[bridge] Synced %d file(s) from cron task %s to parent %s",
                        len(truly_new), source_task_id, parent_task_id)
        except Exception as exc:
            logger.error("[bridge] Failed to sync to parent %s: %s", parent_task_id, exc)
            return
        if truly_new:
            file_names = ", ".join(f["name"] for f in truly_new)
            try:
                self.create_activity("agent_output",
                    f"{agent_name} produced {len(truly_new)} file(s) via cron: {file_names}",
                    task_id=parent_task_id)
            except Exception:
                pass
