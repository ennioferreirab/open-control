"""MCP bridge server — runs as a separate stdio subprocess.

Launched by: python -m claude_code.mcp_bridge
Or via:      uv run python -m claude_code.mcp_bridge

Environment variables:
    MC_SOCKET_PATH  Path to the Unix socket served by MCSocketServer (required).
    AGENT_NAME      Name of the calling agent (default: "agent").
    TASK_ID         Convex task _id context (optional).

This module MUST NOT import ConvexBridge, MessageBus, or any heavy MC deps.
All MC operations are proxied via MCSocketClient over the Unix socket.
"""

from __future__ import annotations

import asyncio
import os
import sys

# ---------------------------------------------------------------------------
# Environment — M2: read env vars lazily at first use, not at module level
# ---------------------------------------------------------------------------

def _get_socket_path() -> str:
    return os.environ.get("MC_SOCKET_PATH", "/tmp/mc-agent.sock")


def _get_agent_name() -> str:
    return os.environ.get("AGENT_NAME", "agent")


def _get_task_id() -> str | None:
    return os.environ.get("TASK_ID") or None


def _get_board_name() -> str | None:
    return os.environ.get("BOARD_NAME") or None


def _resolve_memory_workspace():
    """Resolve the memory workspace path for search_memory, board-aware."""
    from pathlib import Path
    agent_name = _get_agent_name()
    board_name = _get_board_name()
    if board_name:
        return Path.home() / ".nanobot" / "boards" / board_name / "agents" / agent_name
    return Path.home() / ".nanobot" / "agents" / agent_name


# Module-level aliases kept for backward compatibility with tests that patch them.
# These are still read lazily via the functions above in production use.
MC_SOCKET_PATH: str = os.environ.get("MC_SOCKET_PATH", "/tmp/mc-agent.sock")
AGENT_NAME: str = os.environ.get("AGENT_NAME", "agent")
TASK_ID: str | None = os.environ.get("TASK_ID") or None

# ---------------------------------------------------------------------------
# MCP server setup
# ---------------------------------------------------------------------------

from mcp.server import Server
from mcp.server.stdio import stdio_server

server: Server = Server("nanobot")

# Lazy IPC client — created once in _get_ipc()
_ipc_client = None


def _get_ipc():
    """Return the singleton IPC client, creating it if needed."""
    global _ipc_client
    if _ipc_client is None:
        from claude_code.ipc_client import MCSocketClient

        _ipc_client = MCSocketClient(_get_socket_path())
    return _ipc_client


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

from mcp.types import TextContent, Tool


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return all tools exposed by this MCP bridge."""
    return [
        Tool(
            name="ask_user",
            description=(
                "Ask the user a question and wait for their reply. "
                "Use when you need clarification or a decision from the human."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The question to ask."},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of answer choices.",
                    },
                },
                "required": ["question"],
            },
        ),
        Tool(
            name="send_message",
            description=(
                "Send a message to the user or a channel. "
                "Use to proactively communicate progress or results."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Message body."},
                    "channel": {"type": "string", "description": "Target channel (optional)."},
                    "chat_id": {"type": "string", "description": "Target chat/user ID (optional)."},
                    "media": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of file paths to attach (images, audio, documents).",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="delegate_task",
            description=(
                "Delegate a task to Mission Control. "
                "Creates an async task assigned to another agent."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "What needs to be done."},
                    "agent": {
                        "type": "string",
                        "description": "Agent to assign the task to (optional).",
                    },
                    "priority": {
                        "type": "string",
                        "description": "Task priority: low/medium/high (optional).",
                    },
                },
                "required": ["description"],
            },
        ),
        Tool(
            name="ask_agent",
            description=(
                "Ask another agent a question and wait for their response. "
                "Use for clarification or specialist opinion. Depth limit: 2."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string", "description": "Name of the agent to ask."},
                    "question": {"type": "string", "description": "The question to ask."},
                },
                "required": ["agent_name", "question"],
            },
        ),
        Tool(
            name="report_progress",
            description="Report task progress to Mission Control.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Progress description."},
                    "percentage": {
                        "type": "integer",
                        "description": "Completion percentage 0-100 (optional).",
                        "minimum": 0,
                        "maximum": 100,
                    },
                },
                "required": ["message"],
            },
        ),
        Tool(
            name="cron",
            description="Schedule reminders and recurring tasks. Actions: add, list, remove.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["add", "list", "remove"], "description": "Action to perform."},
                    "message": {"type": "string", "description": "Reminder message (required for add)."},
                    "every_seconds": {"type": "integer", "description": "Interval in seconds (for recurring tasks)."},
                    "cron_expr": {"type": "string", "description": "Cron expression like '0 9 * * *'."},
                    "tz": {"type": "string", "description": "IANA timezone for cron expressions."},
                    "at": {"type": "string", "description": "ISO datetime for one-time execution."},
                    "job_id": {"type": "string", "description": "Job ID (required for remove)."},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="search_memory",
            description=(
                "Search agent memory and history for relevant past events, decisions, "
                "and facts. Uses hybrid BM25 keyword + optional vector search."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query — keywords or natural language question.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5).",
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch a tool call to the MC IPC server."""
    ipc = _get_ipc()

    # H1: Wrap all IPC calls in ConnectionError handler
    if name == "ask_user":
        try:
            result = await ipc.request(
                "ask_user",
                {
                    "question": arguments["question"],
                    "options": arguments.get("options"),
                    "agent_name": AGENT_NAME,
                    "task_id": TASK_ID,
                },
            )
        except ConnectionError:
            return [TextContent(
                type="text",
                text="Mission Control not reachable. Is the gateway running?",
            )]
        return [TextContent(type="text", text=result.get("answer", ""))]

    elif name == "send_message":
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
            return [TextContent(
                type="text",
                text="Mission Control not reachable. Is the gateway running?",
            )]
        return [TextContent(type="text", text=result.get("status", "Message sent"))]

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
            return [TextContent(
                type="text",
                text="Mission Control not reachable. Is the gateway running?",
            )]
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [
            TextContent(
                type="text",
                text=f"Task created: {result.get('task_id')} (status: {result.get('status')})",
            )
        ]

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
            return [TextContent(
                type="text",
                text="Mission Control not reachable. Is the gateway running?",
            )]
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=result.get("response", ""))]

    elif name == "report_progress":
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
            return [TextContent(
                type="text",
                text="Mission Control not reachable. Is the gateway running?",
            )]
        return [TextContent(type="text", text=result.get("status", "Progress reported"))]

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
            return [TextContent(type="text", text="Mission Control not reachable. Is the gateway running?")]
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=result.get("result", "Done"))]

    elif name == "search_memory":
        query = arguments.get("query", "")
        top_k = arguments.get("top_k", 5)
        try:
            from mc.memory.store import HybridMemoryStore
            workspace = _resolve_memory_workspace()
            memory_dir = workspace / "memory"
            if not memory_dir.exists():
                return [TextContent(type="text", text="No memory directory found.")]
            store = HybridMemoryStore(workspace)
            results = store.search(query, top_k=top_k)
            if not results:
                return [TextContent(type="text", text="No matching memories found.")]
            return [TextContent(type="text", text=results)]
        except ImportError:
            return [TextContent(type="text", text="Memory search not available (mc.memory not installed).")]
        except Exception as e:
            return [TextContent(type="text", text=f"Memory search error: {e}")]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _run() -> None:
    """Start the MCP stdio server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(_run())
