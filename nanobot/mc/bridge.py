"""
ConvexBridge — Single integration point between nanobot AsyncIO runtime and Convex.

This is the ONLY module in the nanobot codebase that imports the `convex` Python SDK.
All other modules interact with Convex exclusively through this bridge.
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from convex import ConvexClient

logger = logging.getLogger(__name__)

MAX_RETRIES = 3  # Number of retries AFTER the initial attempt (4 total attempts)
BACKOFF_BASE_SECONDS = 1  # Delays: 1s, 2s, 4s


def _to_camel_case(snake_str: str) -> str:
    """Convert a snake_case string to camelCase. Preserves _prefixed Convex fields."""
    if snake_str.startswith("_"):
        return snake_str
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def _to_snake_case(camel_str: str) -> str:
    """Convert a camelCase string to snake_case. Handles Convex _prefixed fields."""
    if camel_str.startswith("_"):
        # Strip leading underscore, convert rest
        # _id -> id, _creationTime -> creation_time
        inner = camel_str[1:]
        s1 = re.sub(r"([A-Z])", r"_\1", inner)
        return s1.lower().lstrip("_")
    s1 = re.sub(r"([A-Z])", r"_\1", camel_str)
    return s1.lower().lstrip("_")


def _convert_keys_to_camel(data: Any) -> Any:
    """Recursively convert all dict keys from snake_case to camelCase."""
    if isinstance(data, dict):
        return {_to_camel_case(k): _convert_keys_to_camel(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_convert_keys_to_camel(item) for item in data]
    return data


def _convert_keys_to_snake(data: Any) -> Any:
    """Recursively convert all dict keys from camelCase to snake_case."""
    if isinstance(data, dict):
        return {_to_snake_case(k): _convert_keys_to_snake(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_convert_keys_to_snake(item) for item in data]
    return data


class ConvexBridge:
    """Bridge between nanobot Python runtime and Convex backend."""

    def __init__(self, deployment_url: str, admin_key: str | None = None):
        """
        Initialize the Convex bridge.

        Args:
            deployment_url: Convex deployment URL (e.g., "https://example.convex.cloud")
            admin_key: Optional admin key for server-side auth
        """
        self._client = ConvexClient(deployment_url)
        if admin_key:
            self._client.set_admin_auth(admin_key)
        logger.info("ConvexBridge connected to %s", deployment_url)

    def query(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        """
        Call a Convex query function.

        Args:
            function_name: Convex function in colon notation (e.g., "tasks:list")
            args: Optional arguments dict (snake_case keys — converted to camelCase)

        Returns:
            Query result with camelCase keys converted to snake_case
        """
        camel_args = _convert_keys_to_camel(args) if args else {}
        logger.debug("query %s args=%s", function_name, camel_args)
        result = self._client.query(function_name, camel_args)
        return _convert_keys_to_snake(result)

    def mutation(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        """
        Call a Convex mutation function with retry.

        Args:
            function_name: Convex function in colon notation (e.g., "tasks:create")
            args: Optional arguments dict (snake_case keys — converted to camelCase)

        Returns:
            Mutation result (if any) with camelCase keys converted to snake_case
        """
        return self._mutation_with_retry(function_name, args)

    def _mutation_with_retry(
        self, function_name: str, args: dict[str, Any] | None = None
    ) -> Any:
        """
        Call a Convex mutation with retry and exponential backoff.

        Retries up to MAX_RETRIES times on failure. On exhaustion, logs error
        and makes a best-effort attempt to write a system_error activity event.

        Raises:
            Exception: Re-raises the last exception after retry exhaustion.
        """
        camel_args = _convert_keys_to_camel(args) if args else {}
        last_exception = None
        max_attempts = MAX_RETRIES + 1  # initial attempt + retries

        for attempt in range(1, max_attempts + 1):
            try:
                logger.debug("mutation %s attempt %d args=%s", function_name, attempt, camel_args)
                result = self._client.mutation(function_name, camel_args)
                if attempt > 1:
                    logger.info(
                        "Mutation %s succeeded on attempt %d/%d",
                        function_name, attempt, max_attempts,
                    )
                return _convert_keys_to_snake(result) if result else result
            except Exception as e:
                last_exception = e
                if attempt < max_attempts:
                    delay = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        "Mutation %s failed (attempt %d/%d), retrying in %ds: %s",
                        function_name, attempt, max_attempts, delay, e,
                    )
                    time.sleep(delay)

        logger.error(
            "Mutation %s failed after %d attempts. Args: %s. Error: %s",
            function_name, max_attempts, camel_args, last_exception,
        )
        self._write_error_activity(function_name, str(last_exception))
        raise last_exception

    def _write_error_activity(self, mutation_name: str, error_message: str) -> None:
        """
        Best-effort write of a system_error activity event to Convex.

        Called after retry exhaustion. If this write also fails,
        the error is silently logged -- no cascading exceptions.
        """
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            self._client.mutation("activities:create", {
                "eventType": "system_error",
                "description": (
                    f"Mutation {mutation_name} failed after {MAX_RETRIES + 1} "
                    f"attempts ({MAX_RETRIES} retries): {error_message}"
                ),
                "timestamp": timestamp,
            })
        except Exception as e:
            logger.error("Failed to write error activity event (best-effort): %s", e)

    def _log_state_transition(self, entity_type: str, description: str) -> None:
        """Log a state transition to local stdout via logging."""
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info("[MC] %s %s: %s", timestamp, entity_type, description)

    def update_task_status(
        self,
        task_id: str,
        status: str,
        agent_name: str | None = None,
        description: str | None = None,
    ) -> Any:
        """Update a task's status with retry and logging."""
        mutation_args: dict[str, Any] = {"task_id": task_id, "status": status}
        if agent_name is not None:
            mutation_args["agent_name"] = agent_name
        result = self._mutation_with_retry(
            "tasks:updateStatus",
            mutation_args,
        )
        desc = description or f"Task status changed to {status}"
        if agent_name:
            desc += f" by {agent_name}"
        self._log_state_transition("task", desc)
        return result

    def update_agent_status(
        self,
        agent_name: str,
        status: str,
        description: str | None = None,
    ) -> Any:
        """Update an agent's status with retry and logging."""
        result = self._mutation_with_retry(
            "agents:updateStatus",
            {"agent_name": agent_name, "status": status},
        )
        self._log_state_transition(
            "agent",
            description or f"Agent '{agent_name}' status changed to {status}",
        )
        return result

    def create_activity(
        self,
        event_type: str,
        description: str,
        task_id: str | None = None,
        agent_name: str | None = None,
    ) -> Any:
        """Create an activity event with retry and logging."""
        args: dict[str, Any] = {
            "event_type": event_type,
            "description": description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if task_id:
            args["task_id"] = task_id
        if agent_name:
            args["agent_name"] = agent_name
        result = self._mutation_with_retry("activities:create", args)
        self._log_state_transition("activity", description)
        return result

    def create_task_directory(self, task_id: str) -> None:
        """Create the filesystem directory structure for a task.

        Creates:
            ~/.nanobot/tasks/{safe_task_id}/attachments/
            ~/.nanobot/tasks/{safe_task_id}/output/

        Idempotent — no error if directories already exist.
        On OSError, logs an activity event and continues (does not raise).

        Args:
            task_id: Convex task _id (e.g. "jd7abc123xyz").
        """
        safe_task_id = re.sub(r"[^\w\-]", "_", task_id)
        task_dir = Path.home() / ".nanobot" / "tasks" / safe_task_id
        for subdir in ("attachments", "output"):
            path = task_dir / subdir
            try:
                os.makedirs(path, exist_ok=True)
                logger.debug("Created task directory: %s", path)
            except OSError as exc:
                error_msg = f"Failed to create task directory {path}: {exc}"
                logger.error(error_msg)
                try:
                    self.create_activity(
                        "system_error",
                        error_msg,
                        task_id=task_id,
                    )
                except Exception as activity_exc:
                    logger.error(
                        "Failed to log directory creation error as activity: %s",
                        activity_exc,
                    )

    def send_message(
        self,
        task_id: str,
        author_name: str,
        author_type: str,
        content: str,
        message_type: str,
    ) -> Any:
        """Send a task-scoped message with retry and logging."""
        result = self._mutation_with_retry(
            "messages:create",
            {
                "task_id": task_id,
                "author_name": author_name,
                "author_type": author_type,
                "content": content,
                "message_type": message_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        self._log_state_transition(
            "message", f"Message sent by {author_name} on task {task_id}"
        )
        return result

    def update_execution_plan(self, task_id: str, plan: dict[str, Any]) -> Any:
        """Update the executionPlan field on a task document.

        Args:
            task_id: Convex task _id.
            plan: Serialized execution plan dict (camelCase keys).

        Returns:
            Mutation result (if any).
        """
        # Plan dict already has camelCase keys from ExecutionPlan.to_dict(),
        # so pass it directly without snake->camel conversion on the plan body.
        return self._mutation_with_retry(
            "tasks:updateExecutionPlan",
            {"task_id": task_id, "execution_plan": plan},
        )

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
        return self.mutation("agents:upsertByName", args)

    def list_agents(self) -> list[dict[str, Any]]:
        """List all agents from Convex.

        Returns:
            List of agent dicts with snake_case keys.
        """
        result = self.query("agents:list")
        if result is None:
            return []
        return result

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

    def write_agent_config(self, agent_data: dict[str, Any], agents_dir: Path) -> None:
        """Write an agent's config back to local YAML.

        Used for Convex → local write-back when dashboard edits are newer
        than the local file.

        Args:
            agent_data: Agent dict with snake_case keys (from Convex query).
            agents_dir: Path to the agents directory (e.g. ~/.nanobot/agents/).
        """
        import yaml

        from nanobot.mc.agent_assist import ensure_soul_md

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

        config_path.write_text(
            yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        logger.info("Wrote agent config to %s", config_path)

        # Generate SOUL.md if not already present (preserves user edits)
        role = agent_data.get("role", "Agent")
        ensure_soul_md(agent_dir, name, role, soul)

    def sync_task_output_files(self, task_id: str, task_data: dict, agent_name: str = "agent") -> None:
        """Scan output/ directory and sync file manifest in Convex.

        - Adds new output files not yet in the manifest
        - Replaces the output section if stale entries exist
        - Creates activity event if new files were found
        """
        import mimetypes

        EXT_MIME: dict[str, str] = {
            "pdf": "application/pdf", "md": "text/markdown", "markdown": "text/markdown",
            "html": "text/html", "htm": "text/html", "txt": "text/plain",
            "csv": "text/csv", "json": "application/json", "yaml": "text/yaml",
            "yml": "text/yaml", "xml": "application/xml", "py": "text/x-python",
            "ts": "text/typescript", "tsx": "text/typescript", "js": "text/javascript",
            "jsx": "text/javascript", "go": "text/x-go", "rs": "text/x-rust",
            "sh": "text/x-sh", "bash": "text/x-sh",
        }

        safe_id = re.sub(r"[^\w\-]", "_", task_id)
        output_dir = Path.home() / ".nanobot" / "tasks" / safe_id / "output"

        if not output_dir.exists():
            return

        # Scan filesystem
        now = datetime.utcnow().isoformat() + "Z"
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

    def close(self) -> None:
        """Close the Convex client connection."""
        logger.info("ConvexBridge closing connection")
        if hasattr(self._client, "close"):
            self._client.close()
