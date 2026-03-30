"""MC Plan Sync — reports plan detection and step completion to Mission Control.

Discovers MC connection from .mcp.json in the CC workspace, then uses
SyncIPCClient to call report_progress on the MC IPC server.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, ClassVar

from ..config import get_config, get_project_root
from ..handler import BaseHandler
from ..ipc_sync import SyncIPCClient
from .plan_tracker import compute_parallel_groups, is_plan_file, parse_plan_tasks

logger = logging.getLogger(__name__)


class MCPlanSyncHandler(BaseHandler):
    """Syncs plan events to Mission Control via IPC."""

    events: ClassVar[list[tuple[str, str | None]]] = [
        ("PostToolUse", "Write"),
        ("TaskCompleted", None),
    ]

    def handle(self) -> str | None:
        mc_ctx = self._discover_mc_context()
        if not mc_ctx:
            return None  # Not in MC-managed session

        event = self.payload.get("hook_event_name", "")
        if event == "PostToolUse":
            return self._handle_plan_write(mc_ctx)
        elif event == "TaskCompleted":
            return self._handle_task_completed(mc_ctx)
        return None

    def _discover_mc_context(self) -> dict[str, Any] | None:
        """Try to find MC connection info from env vars or .mcp.json.

        Returns dict with socket_path, agent_name, task_id, or None.
        """
        # 1. Environment variables (explicit override)
        socket_path = os.environ.get("MC_SOCKET_PATH")
        if socket_path and Path(socket_path).exists():
            return {
                "socket_path": socket_path,
                "agent_name": os.environ.get("AGENT_NAME", "agent"),
                "task_id": os.environ.get("TASK_ID"),
            }

        # 2. Read .mcp.json from CC workspace (cwd)
        cwd = self.payload.get("cwd", "")
        if cwd:
            mcp_json = Path(cwd) / ".mcp.json"
            if mcp_json.is_file():
                try:
                    config = json.loads(mcp_json.read_text())
                    # Find the first MCP server that has MC_SOCKET_PATH
                    servers = config.get("mcpServers", {})
                    env = {}
                    for srv in servers.values():
                        if isinstance(srv, dict) and "env" in srv:
                            candidate = srv["env"]
                            if isinstance(candidate, dict) and candidate.get("MC_SOCKET_PATH"):
                                env = candidate
                                break
                    sp = env.get("MC_SOCKET_PATH")
                    if sp and Path(sp).exists():
                        return {
                            "socket_path": sp,
                            "agent_name": env.get("AGENT_NAME", "agent"),
                            "task_id": env.get("TASK_ID"),
                        }
                except (json.JSONDecodeError, OSError):
                    pass

        return None

    def _handle_plan_write(self, mc_ctx: dict[str, Any]) -> str | None:
        """Parse plan from written file and report structure to MC."""
        tool_input = self.payload.get("tool_input", {})
        file_path = tool_input.get("file_path", "")

        if not file_path or not is_plan_file(file_path):
            return None

        content = tool_input.get("content", "")
        if not content:
            try:
                content = Path(file_path).read_text()
            except OSError:
                return None

        tasks = parse_plan_tasks(content)
        if not tasks:
            return None

        steps = compute_parallel_groups(tasks)
        total = len(steps)

        # Build human-readable summary
        groups: dict[int, list[int]] = {}
        for s in steps:
            groups.setdefault(s["parallel_group"], []).append(s["id"])
        group_desc = ", ".join(
            f"group {g}: [{','.join(str(i) for i in ids)}]" for g, ids in sorted(groups.items())
        )
        task_word = "task" if total == 1 else "tasks"
        summary = (
            f"Plan detected: {total} {task_word} in {len(groups)} parallel group(s). {group_desc}"
        )

        # Report to MC (non-fatal)
        try:
            ipc = SyncIPCClient(mc_ctx["socket_path"])
            ipc.request(
                "report_progress",
                {
                    "message": summary,
                    "agent_name": mc_ctx["agent_name"],
                    "task_id": mc_ctx.get("task_id"),
                },
            )
        except (ConnectionError, OSError) as exc:
            logger.debug("MC plan sync: IPC failed (non-fatal): %s", exc)

        return summary

    def _handle_task_completed(self, mc_ctx: dict[str, Any]) -> str | None:
        """Match completed task to a plan step and report progress to MC."""
        subject = self.payload.get("task_subject", "") or self.payload.get("task", {}).get(
            "subject", ""
        )
        if not subject:
            return None

        # Try numeric ID match
        m = re.search(r"Task\s+(\d+)", subject)
        task_id = int(m.group(1)) if m else None

        config = get_config()
        root = get_project_root()
        tracker_dir = root / config.tracker_dir

        if not tracker_dir.is_dir():
            return None

        for tracker_path in sorted(tracker_dir.glob("*.json")):
            try:
                data = json.loads(tracker_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            matched_step = None
            for step in data.get("steps", []):
                if task_id is not None and step["id"] == task_id:
                    matched_step = step
                    break
                elif task_id is None and step["name"].lower() in subject.lower():
                    matched_step = step
                    break

            if matched_step is None or matched_step["status"] == "completed":
                continue

            # Build progress summary
            done_ids = {s["id"] for s in data["steps"] if s["status"] == "completed"}
            done_ids.add(matched_step["id"])
            total = len(data["steps"])
            done_count = len(done_ids)

            unblocked = []
            for s in data["steps"]:
                if (
                    s["status"] == "pending"
                    and s["id"] != matched_step["id"]
                    and s["blocked_by"]
                    and all(b in done_ids for b in s["blocked_by"])
                ):
                    unblocked.append(f"Task {s['id']}")

            summary = (
                f"Step {matched_step['id']} '{matched_step['name']}' completed. "
                f"Progress: {done_count}/{total} done."
            )
            if unblocked:
                summary += f" Now unblocked: {', '.join(unblocked)}"

            # Report to MC (non-fatal)
            try:
                ipc = SyncIPCClient(mc_ctx["socket_path"])
                ipc.request(
                    "report_progress",
                    {
                        "message": summary,
                        "agent_name": mc_ctx["agent_name"],
                        "task_id": mc_ctx.get("task_id"),
                    },
                )
            except (ConnectionError, OSError) as exc:
                logger.debug("MC plan sync: IPC failed (non-fatal): %s", exc)

            return summary

        return None
