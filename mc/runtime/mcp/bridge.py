"""Repo-owned MC MCP stdio bridge — runs as a separate stdio subprocess.

Launched by: python -m mc.runtime.mcp.bridge
Or via:      uv run python -m mc.runtime.mcp.bridge

Environment variables:
    MC_SOCKET_PATH  Path to the Unix socket served by MCSocketServer (required).
    AGENT_NAME      Name of the calling agent (default: "agent").
    TASK_ID         Convex task _id context (optional).

This bridge exposes the canonical Phase 1 MC tool surface and forwards tool
calls to the existing MC IPC/runtime handlers via the Unix socket.

Tool names are semantic and transport-agnostic (AC3).  Namespace identity is
carried by the MCP server identity, not by tool name suffixes.
"""

from __future__ import annotations

import asyncio
import os

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mc.runtime.mcp.tool_specs import PHASE1_TOOLS

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
# Tool listing — uses the canonical Phase 1 surface
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the canonical Phase 1 MC tools exposed by this bridge."""
    return PHASE1_TOOLS


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

    elif name == "report_progress":
        service = _get_interaction_service()
        context = _build_interaction_context("mc")
        if service is not None and context is not None:
            await asyncio.to_thread(
                service.report_progress,
                context=context,
                message=arguments["message"],
                percentage=arguments.get("percentage"),
            )
            return [TextContent(type="text", text="Progress reported")]
        try:
            result = await ipc.request(
                "report_progress",
                {
                    "message": arguments["message"],
                    "percentage": arguments.get("percentage"),
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
        return [TextContent(type="text", text=result.get("status", "Progress reported"))]

    elif name == "record_final_result":
        service = _get_interaction_service()
        context = _build_interaction_context("mc")
        if service is not None and context is not None:
            await asyncio.to_thread(
                service.record_final_result,
                context=context,
                content=arguments["content"],
                source="mc-mcp",
            )
            return [TextContent(type="text", text="Final result recorded")]
        try:
            result = await ipc.request(
                "record_final_result",
                {
                    "content": arguments["content"],
                    "session_id": _get_interactive_session_id(),
                    "agent_name": _get_agent_name(),
                    "task_id": _get_task_id(),
                    "source": "mc-mcp",
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
        return [TextContent(type="text", text=result.get("status", "Final result recorded"))]

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
