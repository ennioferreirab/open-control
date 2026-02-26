"""Tool to delegate tasks to Mission Control (Convex)."""

import asyncio
import os
from typing import Any, TYPE_CHECKING

from loguru import logger

from nanobot.agent.tools.base import Tool
from nanobot.bus.events import InboundMessage

if TYPE_CHECKING:
    from nanobot.bus.queue import MessageBus
    from nanobot.mc.bridge import ConvexBridge


class McDelegateTool(Tool):
    """
    Tool to delegate a task to the Mission Control board.

    The task runs asynchronously on the MC backend, and the result is
    announced back to the main agent when complete.
    """

    def __init__(self, bus: "MessageBus"):
        self._bus = bus
        self._origin_channel = "cli"
        self._origin_chat_id = "direct"
        self._bridge: "ConvexBridge | None" = None

        self._init_bridge()

    def _init_bridge(self) -> None:
        try:
            from nanobot.mc.gateway import _resolve_convex_url
            from nanobot.mc.bridge import ConvexBridge

            url = _resolve_convex_url()
            if url:
                admin_key = os.environ.get("CONVEX_ADMIN_KEY")
                self._bridge = ConvexBridge(url, admin_key)
        except Exception as e:
            logger.debug("Failed to initialize ConvexBridge for McDelegateTool: {}", e)

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the origin context for announcements."""
        self._origin_channel = channel
        self._origin_chat_id = chat_id

    @property
    def name(self) -> str:
        return "delegate_task"

    @property
    def description(self) -> str:
        return (
            "Delegate a task to the Mission Control board. "
            "Use this to assign tasks to specialized agents (e.g. secretary, lead-agent). "
            "Mission control will handle the execution and notify you here when it is complete. "
            "IMPORTANT: This is asynchronous. Do NOT wait for the result. Say something like 'I have delegated the task to Mission Control.' and end your turn."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title of the task (e.g., 'Summarize email')",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of what needs to be done",
                },
                "assigned_agent": {
                    "type": "string",
                    "description": "Name of the agent to assign (e.g., 'secretary', 'lead-agent'). Leave empty to let the system decide.",
                },
            },
            "required": ["title", "description"],
        }

    async def execute(self, title: str, description: str, assigned_agent: str | None = None, **kwargs: Any) -> str:
        """Create the task in Convex and instruct the main agent."""
        if not self._bridge:
            self._init_bridge()
            if not self._bridge:
                return "Error: Mission Control is not configured or reachable. Cannot delegate."

        try:
            task_args: dict[str, Any] = {
                "title": title,
                "description": description,
            }
            if assigned_agent:
                task_args["assignedAgent"] = assigned_agent
                
            task_id = await asyncio.to_thread(self._bridge.mutation, "tasks:create", task_args)
            if not task_id:
                return "Error: Failed to create task in Mission Control."

            return f"Task '{title}' has been successfully delegated to Mission Control (ID: {task_id}). A system heartbeat will notify you with the results once the agent finishes."

        except Exception as e:
            logger.exception("Failed to delegate task to MC")
            return f"Error: Failed to delegate task: {e}"