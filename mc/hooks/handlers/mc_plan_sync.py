"""MC Plan Sync — reports plan detection and step completion to Mission Control.

Discovers MC connection from .mcp.json in the CC workspace, then uses
SyncIPCClient to call report_progress on the MC IPC server.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from ..handler import BaseHandler

logger = logging.getLogger(__name__)


class MCPlanSyncHandler(BaseHandler):
    """Syncs plan events to Mission Control via IPC."""

    events = [("PostToolUse", "Write"), ("TaskCompleted", None)]

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
                    env = (
                        config
                        .get("mcpServers", {})
                        .get("nanobot", {})
                        .get("env", {})
                    )
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
        # Placeholder — implemented in Task 4
        return None

    def _handle_task_completed(self, mc_ctx: dict[str, Any]) -> str | None:
        # Placeholder — implemented in Task 5
        return None
