"""Task repository -- CRUD and queries for task entities."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mc.types import task_safe_id

if TYPE_CHECKING:
    from mc.bridge.client import BridgeClient

logger = logging.getLogger(__name__)


class TaskRepository:
    """Data access methods for task entities in Convex."""

    def __init__(self, client: "BridgeClient"):
        self._client = client

    def update_task_status(
        self,
        task_id: str,
        status: str,
        agent_name: str | None = None,
        description: str | None = None,
        awaiting_kickoff: bool | None = None,
    ) -> Any:
        """Update a task's status with retry and logging."""
        mutation_args: dict[str, Any] = {"task_id": task_id, "status": status}
        if agent_name is not None:
            mutation_args["agent_name"] = agent_name
        if awaiting_kickoff is not None:
            mutation_args["awaiting_kickoff"] = awaiting_kickoff
        result = self._client.mutation(
            "tasks:updateStatus",
            mutation_args,
        )
        desc = description or f"Task status changed to {status}"
        if agent_name:
            desc += f" by {agent_name}"
        self._log_state_transition("task", desc)
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
        return self._client.mutation(
            "tasks:updateExecutionPlan",
            {"task_id": task_id, "execution_plan": plan},
        )

    def kick_off_task(self, task_id: str, step_count: int) -> Any:
        """Transition a task to the running state after materialization."""
        result = self._client.mutation(
            "tasks:kickOff",
            {"task_id": task_id, "step_count": step_count},
        )
        self._log_state_transition("task", f"Task {task_id} kicked off with {step_count} steps")
        return result

    def approve_and_kick_off(
        self, task_id: str, execution_plan: dict[str, Any] | None = None
    ) -> Any:
        """Approve plan and kick off a supervised task.

        Calls the atomic Convex mutation that saves the (optionally edited)
        execution plan, transitions review (awaitingKickoff) -> in_progress,
        and creates an activity event.
        """
        args: dict[str, Any] = {"task_id": task_id}
        if execution_plan is not None:
            args["execution_plan"] = execution_plan
        result = self._client.mutation("tasks:approveAndKickOff", args)
        self._log_state_transition("task", f"Task {task_id} approved and kicked off")
        return result

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Fetch a single task by id."""
        return self._client.query("tasks:getById", {"task_id": task_id})

    def create_task_directory(self, task_id: str) -> None:
        """Create the filesystem directory structure for a task.

        Creates:
            ~/.nanobot/tasks/{safe_task_id}/attachments/
            ~/.nanobot/tasks/{safe_task_id}/output/

        Idempotent -- no error if directories already exist.
        On OSError, logs an activity event and continues (does not raise).

        Args:
            task_id: Convex task _id (e.g. "jd7abc123xyz").
        """
        safe_task_id = task_safe_id(task_id)
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
                    self._client.mutation(
                        "activities:create",
                        {
                            "event_type": "system_error",
                            "description": error_msg,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "task_id": task_id,
                        },
                    )
                except Exception as activity_exc:
                    logger.error(
                        "Failed to log directory creation error as activity: %s",
                        activity_exc,
                    )

    def sync_task_output_files(
        self, task_id: str, task_data: dict, agent_name: str = "agent"
    ) -> None:
        """Scan output/ directory and sync file manifest in Convex.

        - Adds new output files not yet in the manifest
        - Replaces the output section if stale entries exist
        - Creates activity event if new files were found
        """
        ext_mime: dict[str, str] = {
            "pdf": "application/pdf",
            "md": "text/markdown",
            "markdown": "text/markdown",
            "html": "text/html",
            "htm": "text/html",
            "txt": "text/plain",
            "csv": "text/csv",
            "json": "application/json",
            "yaml": "text/yaml",
            "yml": "text/yaml",
            "xml": "application/xml",
            "py": "text/x-python",
            "ts": "text/typescript",
            "tsx": "text/typescript",
            "js": "text/javascript",
            "jsx": "text/javascript",
            "go": "text/x-go",
            "rs": "text/x-rust",
            "sh": "text/x-sh",
            "bash": "text/x-sh",
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
                    mime = ext_mime.get(ext, "application/octet-stream")
                    fs_files.append(
                        {
                            "name": entry.name,
                            "type": mime,
                            "size": entry.stat().st_size,
                            "subfolder": "output",
                            "uploaded_at": now,
                        }
                    )
        except OSError as exc:
            logger.error("[bridge] Failed to scan output dir %s: %s", output_dir, exc)
            return

        # Compare with existing manifest
        existing_output = {
            f["name"] for f in (task_data.get("files") or []) if f.get("subfolder") == "output"
        }
        fs_names = {f["name"] for f in fs_files}

        new_files = [f for f in fs_files if f["name"] not in existing_output]
        stale_names = existing_output - fs_names

        if not new_files and not stale_names:
            return  # nothing to do

        # Update Convex -- replace full output section
        try:
            self._client.mutation(
                "tasks:updateTaskOutputFiles",
                {
                    "task_id": task_id,
                    "output_files": fs_files,
                },
            )
            logger.info("[bridge] Synced %d output file(s) for task %s", len(fs_files), task_id)
        except Exception as exc:
            logger.error("[bridge] Failed to sync output files for task %s: %s", task_id, exc)
            return

        if stale_names:
            logger.warning(
                "[bridge] Manifest reconciliation: removed %d orphaned entries for task %s",
                len(stale_names),
                task_id,
            )

        # Activity event for new files
        if new_files:
            file_names = ", ".join(f["name"] for f in new_files)
            msg = f"{agent_name} produced {len(new_files)} output file(s): {file_names}"
            try:
                self._client.mutation(
                    "activities:create",
                    {
                        "event_type": "agent_output",
                        "description": msg,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "task_id": task_id,
                    },
                )
            except Exception as exc:
                logger.error("[bridge] Failed to create output file activity: %s", exc)

    def sync_output_files_to_parent(
        self, source_task_id: str, parent_task_id: str, agent_name: str = "agent"
    ) -> None:
        """Sync output files from a cron-triggered task to its parent task.

        Fetches files from the source task's output/ directory and appends
        any new filenames (append-only) to the parent task's output section.
        """
        ext_mime: dict[str, str] = {
            "pdf": "application/pdf",
            "md": "text/markdown",
            "markdown": "text/markdown",
            "html": "text/html",
            "htm": "text/html",
            "txt": "text/plain",
            "csv": "text/csv",
            "json": "application/json",
            "yaml": "text/yaml",
            "yml": "text/yaml",
            "xml": "application/xml",
            "py": "text/x-python",
            "ts": "text/typescript",
            "tsx": "text/typescript",
            "js": "text/javascript",
            "jsx": "text/javascript",
            "go": "text/x-go",
            "rs": "text/x-rust",
            "sh": "text/x-sh",
            "bash": "text/x-sh",
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
                    mime = ext_mime.get(ext, "application/octet-stream")
                    source_files.append(
                        {
                            "name": entry.name,
                            "type": mime,
                            "size": entry.stat().st_size,
                            "subfolder": "output",
                            "uploaded_at": now,
                        }
                    )
        except OSError as exc:
            logger.error("[bridge] Failed to scan source output dir %s: %s", source_output_dir, exc)
            return
        if not source_files:
            return
        try:
            parent_task = self._client.query("tasks:getById", {"task_id": parent_task_id})
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
            self._client.mutation(
                "tasks:updateTaskOutputFiles",
                {
                    "task_id": parent_task_id,
                    "output_files": merged_output,
                },
            )
            logger.info(
                "[bridge] Synced %d file(s) from cron task %s to parent %s",
                len(truly_new),
                source_task_id,
                parent_task_id,
            )
        except Exception as exc:
            logger.error("[bridge] Failed to sync to parent %s: %s", parent_task_id, exc)
            return
        if truly_new:
            file_names = ", ".join(f["name"] for f in truly_new)
            try:
                self._client.mutation(
                    "activities:create",
                    {
                        "event_type": "agent_output",
                        "description": (
                            f"{agent_name} produced {len(truly_new)} file(s) via cron: {file_names}"
                        ),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "task_id": parent_task_id,
                    },
                )
            except Exception:
                pass

    @staticmethod
    def _log_state_transition(entity_type: str, description: str) -> None:
        """Log a state transition to local stdout via logging."""
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info("[MC] %s %s: %s", timestamp, entity_type, description)
