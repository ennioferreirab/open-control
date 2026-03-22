"""DEPRECATED — thin wrapper that re-exports from the canonical MC MCP bridge.

All MCP tools are now served by ``mc.runtime.mcp.bridge``.  This module
exists only for backward compatibility with code that imports from
``claude_code.mcp_bridge`` (e.g. existing tests).

To run the MCP server directly::

    python -m mc.runtime.mcp.bridge
"""

from __future__ import annotations

import warnings

warnings.warn(
    "claude_code.mcp_bridge is deprecated — use mc.runtime.mcp.bridge instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the canonical bridge so existing imports keep working.
from mc.runtime.mcp.bridge import (  # noqa: F401, E402
    AGENT_NAME,
    MC_SOCKET_PATH,
    TASK_ID,
    _build_interaction_context,
    _get_agent_name,
    _get_board_name,
    _get_convex,
    _get_convex_admin_key,
    _get_convex_url,
    _get_ipc,
    _get_interaction_service,
    _get_interactive_session_id,
    _get_memory_workspace,
    _get_socket_path,
    _get_step_id,
    _get_task_id,
    _resolve_memory_workspace,
    _run,
    call_tool,
    list_tools,
    server,
)

if __name__ == "__main__":
    import asyncio

    asyncio.run(_run())
