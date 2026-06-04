"""Agent-run plumbing extracted from the task executor."""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Native tool names that overlap with the Phase 1 MCP surface and must be
# hidden in MC runtime so the model sees only one canonical surface.
# ---------------------------------------------------------------------------
_MC_OVERLAPPING_NATIVE_TOOLS = frozenset({"ask_user", "delegate_task", "message", "cron"})


def _build_mc_mcp_servers(
    task_id: str | None = None,
    agent_name: str | None = None,
) -> dict:
    """Build the mcp_servers config for the repo-owned MC MCP bridge.

    The bridge is launched as a Python subprocess (stdio transport) so that
    the model sees the canonical Phase 1 MC tool surface.
    """

    env: dict[str, str] = {}
    if task_id:
        env["TASK_ID"] = task_id
    if agent_name:
        env["AGENT_NAME"] = agent_name
    convex_url = os.environ.get("CONVEX_URL")
    convex_admin_key = os.environ.get("CONVEX_ADMIN_KEY")
    if convex_url:
        env["CONVEX_URL"] = convex_url
    if convex_admin_key:
        env["CONVEX_ADMIN_KEY"] = convex_admin_key

    config: dict[str, Any] = {
        "command": sys.executable,
        "args": ["-m", "mc.runtime.mcp.bridge"],
    }
    if env:
        config["env"] = env

    return {"mc": config}


@dataclass(slots=True)
class AgentRunResult:
    content: str
    is_error: bool = False
    error_message: str | None = None


def _coerce_agent_run_result(value: Any) -> AgentRunResult:
    """Normalize old string results and structured loop results to one shape."""
    if isinstance(value, AgentRunResult):
        return value
    if isinstance(value, str):
        return AgentRunResult(content=value)
    content = getattr(value, "content", "") or ""
    is_error = bool(getattr(value, "is_error", False))
    error_message = getattr(value, "error_message", None)
    return AgentRunResult(
        content=content,
        is_error=is_error,
        error_message=error_message,
    )
