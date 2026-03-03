"""Tool to delegate tasks to Mission Control (Convex)."""

import asyncio
import os
from typing import Any, TYPE_CHECKING

from loguru import logger

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge


class McDelegateTool(Tool):
    """Tool to delegate a task to the Mission Control board."""

    def __init__(self, source_agent: str | None = None) -> None:
        self._bridge: "ConvexBridge | None" = None
        self._source_agent = source_agent
        self._init_bridge()

    def set_source_agent(self, name: str) -> None:
        """Set the calling agent's name (used to prevent circular delegation)."""
        self._source_agent = name


    def _init_bridge(self) -> None:
        try:
            from mc.gateway import _resolve_convex_url
            from mc.bridge import ConvexBridge

            url = _resolve_convex_url()
            if url:
                admin_key = os.environ.get("CONVEX_ADMIN_KEY")
                self._bridge = ConvexBridge(url, admin_key)
        except Exception as e:
            logger.debug("Failed to initialize ConvexBridge for McDelegateTool: {}", e)

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

        # Prevent circular self-delegation
        if assigned_agent and self._source_agent and assigned_agent == self._source_agent:
            logger.warning(
                "Blocked self-delegation: agent '%s' tried to delegate to itself",
                self._source_agent,
            )
            return (
                f"Error: You ({self._source_agent}) cannot delegate a task to yourself. "
                "Either execute the task directly using your tools, or delegate to a different agent."
            )


        try:
            task_args: dict[str, Any] = {
                "title": title,
                "description": description,
            }
            if assigned_agent:
                task_args["assignedAgent"] = assigned_agent
            if self._source_agent:
                task_args["sourceAgent"] = self._source_agent


            task_id = await asyncio.to_thread(self._bridge.mutation, "tasks:create", task_args)
            if not task_id:
                return "Error: Failed to create task in Mission Control."

            return f"Task '{title}' has been successfully delegated to Mission Control (ID: {task_id}). A system heartbeat will notify you with the results once the agent finishes."

        except Exception as e:
            logger.exception("Failed to delegate task to MC")
            return f"Error: Failed to delegate task: {e}"