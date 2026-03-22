"""MC MCP stdio bridge — the single MCP server for all MC tool access.

Launched by: python -m mc.runtime.mcp.bridge
Or via:      uv run python -m mc.runtime.mcp.bridge

Environment variables:
    MC_SOCKET_PATH              Path to the Unix socket served by MCSocketServer (required).
    AGENT_NAME                  Name of the calling agent (default: "agent").
    TASK_ID                     Convex task _id context (optional).
    MEMORY_WORKSPACE            Explicit memory workspace path (optional).
    BOARD_NAME                  Board name for board-scoped workspaces (optional).
    MC_INTERACTIVE_SESSION_ID   Session ID for Convex interaction service (optional).
    CONVEX_URL                  Convex deployment URL (optional).
    CONVEX_ADMIN_KEY            Convex admin key (optional).

Tool names are semantic and transport-agnostic.  Namespace identity is
carried by the MCP server identity, not by tool name suffixes.
"""

from __future__ import annotations

import asyncio
import os

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mc.runtime.mcp.tool_specs import MC_TOOLS

# ---------------------------------------------------------------------------
# Environment — read lazily at first use
# ---------------------------------------------------------------------------


def _get_socket_path() -> str:
    return os.environ.get("MC_SOCKET_PATH", "/tmp/mc-agent.sock")


def _get_agent_name() -> str:
    return os.environ.get("AGENT_NAME", "agent")


def _get_task_id() -> str | None:
    return os.environ.get("TASK_ID") or None


def _get_interactive_session_id() -> str | None:
    return os.environ.get("MC_INTERACTIVE_SESSION_ID") or None


def _get_step_id() -> str | None:
    return os.environ.get("STEP_ID") or None


def _get_board_name() -> str | None:
    return os.environ.get("BOARD_NAME") or None


def _get_memory_workspace() -> str | None:
    return os.environ.get("MEMORY_WORKSPACE") or None


def _resolve_memory_workspace():
    """Resolve the memory workspace path for search_memory, board-aware."""
    from pathlib import Path

    memory_workspace = _get_memory_workspace()
    if memory_workspace:
        return Path(memory_workspace)
    agent_name = _get_agent_name()
    board_name = _get_board_name()
    if board_name:
        return Path.home() / ".nanobot" / "boards" / board_name / "agents" / agent_name
    return Path.home() / ".nanobot" / "agents" / agent_name


def _get_convex_url() -> str | None:
    return os.environ.get("CONVEX_URL") or None


def _get_convex_admin_key() -> str | None:
    return os.environ.get("CONVEX_ADMIN_KEY") or None


def _get_interaction_session_id() -> str | None:
    return _get_interactive_session_id() or (
        f"mc:{_get_task_id()}:{_get_agent_name()}" if _get_task_id() else None
    )


# Module-level aliases kept for backward compatibility with tests that patch them.
MC_SOCKET_PATH: str = os.environ.get("MC_SOCKET_PATH", "/tmp/mc-agent.sock")
AGENT_NAME: str = os.environ.get("AGENT_NAME", "agent")
TASK_ID: str | None = os.environ.get("TASK_ID") or None

server: Server = Server("mc")

# Lazy IPC client — created once in _get_ipc()
_ipc_client = None
_convex_client = None


def _get_ipc():
    """Return the singleton IPC client, creating it if needed."""
    global _ipc_client
    if _ipc_client is None:
        from claude_code.ipc_client import MCSocketClient

        _ipc_client = MCSocketClient(_get_socket_path())
    return _ipc_client


def _get_convex():
    """Return a lightweight Convex client when runtime credentials are available."""
    global _convex_client
    if _convex_client is None:
        url = _get_convex_url()
        if not url:
            return None
        from mc.bridge.client import BridgeClient

        _convex_client = BridgeClient(url, _get_convex_admin_key())
    return _convex_client


def _get_interaction_service():
    convex = _get_convex()
    if convex is None:
        return None
    from mc.contexts.interaction.service import InteractionService

    return InteractionService(convex)


def _build_interaction_context(provider: str = "mc"):
    session_id = _get_interaction_session_id()
    task_id = _get_task_id()
    if not session_id or not task_id:
        return None
    from mc.contexts.interaction.types import InteractionContext

    return InteractionContext(
        session_id=session_id,
        task_id=task_id,
        step_id=_get_step_id(),
        agent_name=_get_agent_name(),
        provider=provider,
    )


# ---------------------------------------------------------------------------
# Tool listing — uses the canonical MC tool surface
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the canonical MC tools exposed by this bridge."""
    return MC_TOOLS


# ---------------------------------------------------------------------------
# Tool dispatch — forwards calls through the existing IPC path
# ---------------------------------------------------------------------------


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch a tool call to the MC IPC server."""
    ipc = _get_ipc()

    if name == "ask_user":
        service = _get_interaction_service()
        context = _build_interaction_context("mc")
        if service is not None and context is not None:
            answer = await asyncio.to_thread(
                service.ask_user,
                context=context,
                question=arguments.get("question"),
                options=arguments.get("options"),
                questions=arguments.get("questions"),
            )
            return [TextContent(type="text", text=answer)]
        try:
            request: dict[str, object] = {
                "agent_name": AGENT_NAME,
                "task_id": TASK_ID,
            }
            if "questions" in arguments:
                request["questions"] = arguments["questions"]
            else:
                request["question"] = arguments["question"]
                request["options"] = arguments.get("options")
            result = await ipc.request("ask_user", request)
        except ConnectionError:
            return [
                TextContent(
                    type="text",
                    text="Mission Control not reachable. Is the gateway running?",
                )
            ]
        return [TextContent(type="text", text=result.get("answer", ""))]

    elif name == "ask_agent":
        try:
            result = await ipc.request(
                "ask_agent",
                {
                    "agent_name": arguments["agent_name"],
                    "question": arguments["question"],
                    "caller_agent": AGENT_NAME,
                    "task_id": TASK_ID,
                },
            )
        except ConnectionError:
            return [
                TextContent(
                    type="text",
                    text="Mission Control not reachable. Is the gateway running?",
                )
            ]
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=result.get("response", ""))]

    elif name == "delegate_task":
        try:
            result = await ipc.request(
                "delegate_task",
                {
                    "description": arguments["description"],
                    "agent": arguments.get("agent"),
                    "priority": arguments.get("priority"),
                    "agent_name": AGENT_NAME,
                    "task_id": TASK_ID,
                },
            )
        except ConnectionError:
            return [
                TextContent(
                    type="text",
                    text="Mission Control not reachable. Is the gateway running?",
                )
            ]
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [
            TextContent(
                type="text",
                text=f"Task created: {result.get('task_id')} (status: {result.get('status')})",
            )
        ]

    elif name == "send_message":
        service = _get_interaction_service()
        context = _build_interaction_context("mc")
        if service is not None and context is not None and not arguments.get("chat_id"):
            await asyncio.to_thread(
                service.post_message,
                context=context,
                content=arguments["content"],
                channel=arguments.get("channel"),
                chat_id=arguments.get("chat_id"),
                media=arguments.get("media"),
            )
            return [TextContent(type="text", text="Message sent")]
        try:
            result = await ipc.request(
                "send_message",
                {
                    "content": arguments["content"],
                    "channel": arguments.get("channel"),
                    "chat_id": arguments.get("chat_id"),
                    "media": arguments.get("media"),
                    "agent_name": AGENT_NAME,
                    "task_id": TASK_ID,
                },
            )
        except ConnectionError:
            return [
                TextContent(
                    type="text",
                    text="Mission Control not reachable. Is the gateway running?",
                )
            ]
        return [TextContent(type="text", text=result.get("status", "Message sent"))]

    elif name == "cron":
        try:
            result = await ipc.request(
                "cron",
                {
                    "action": arguments["action"],
                    "message": arguments.get("message"),
                    "every_seconds": arguments.get("every_seconds"),
                    "cron_expr": arguments.get("cron_expr"),
                    "tz": arguments.get("tz"),
                    "at": arguments.get("at"),
                    "job_id": arguments.get("job_id"),
                    "agent_name": _get_agent_name(),
                    "task_id": _get_task_id(),
                },
            )
        except ConnectionError:
            return [
                TextContent(
                    type="text",
                    text="Mission Control not reachable. Is the gateway running?",
                )
            ]
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=result.get("result", "Done"))]

    elif name == "create_agent_spec":
        try:
            result = await ipc.request(
                "create_agent_spec",
                {
                    "name": arguments["name"],
                    "display_name": arguments.get("displayName"),
                    "role": arguments["role"],
                    "responsibilities": arguments.get("responsibilities"),
                    "non_goals": arguments.get("nonGoals"),
                    "principles": arguments.get("principles"),
                    "working_style": arguments.get("workingStyle"),
                    "quality_rules": arguments.get("qualityRules"),
                    "anti_patterns": arguments.get("antiPatterns"),
                    "output_contract": arguments.get("outputContract"),
                    "tool_policy": arguments.get("toolPolicy"),
                    "memory_policy": arguments.get("memoryPolicy"),
                    "execution_policy": arguments.get("executionPolicy"),
                    "review_policy_ref": arguments.get("reviewPolicyRef"),
                    "skills": arguments.get("skills"),
                    "model": arguments.get("model"),
                    "agent_name": _get_agent_name(),
                    "task_id": _get_task_id(),
                },
            )
        except ConnectionError:
            return [
                TextContent(
                    type="text",
                    text="Mission Control not reachable. Is the gateway running?",
                )
            ]
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=f"Agent spec created: {result.get('spec_id', 'ok')}")]

    elif name == "publish_squad_graph":
        try:
            result = await ipc.request(
                "publish_squad_graph",
                {
                    "graph": arguments,
                    "agent_name": _get_agent_name(),
                    "task_id": _get_task_id(),
                },
            )
        except ConnectionError:
            return [
                TextContent(
                    type="text",
                    text="Mission Control not reachable. Is the gateway running?",
                )
            ]
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=f"Squad published: {result.get('squad_id', 'ok')}")]

    elif name == "search_memory":
        query = arguments.get("query", "")
        top_k = arguments.get("top_k", 5)
        try:
            from mc.memory import create_memory_store

            workspace = _resolve_memory_workspace()
            memory_dir = workspace / "memory"
            if not memory_dir.exists():
                return [TextContent(type="text", text="No memory directory found.")]
            store = create_memory_store(workspace)
            results = store.search(query, top_k=top_k)
            if not results:
                return [TextContent(type="text", text="No matching memories found.")]
            return [TextContent(type="text", text=results)]
        except ImportError:
            return [
                TextContent(
                    type="text", text="Memory search not available (mc.memory not installed)."
                )
            ]
        except Exception as e:
            return [TextContent(type="text", text=f"Memory search error: {e}")]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _run() -> None:
    """Start the MC MCP stdio bridge server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(_run())
