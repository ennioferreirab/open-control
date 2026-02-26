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
        self._polling_tasks: dict[str, asyncio.Task[None]] = {}

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

    async def execute(
        self, title: str, description: str, assigned_agent: str | None = None, **kwargs: Any
    ) -> str:
        """Create the task in Convex and start a polling loop to wait for completion."""
        if not self._bridge:
            self._init_bridge()
            if not self._bridge:
                return "Error: Mission Control is not configured or reachable. Cannot delegate."

        try:
            # Create the task in Convex
            task_args: dict[str, Any] = {
                "title": title,
                "description": description,
            }
            if assigned_agent:
                task_args["assignedAgent"] = assigned_agent

            task_id = await asyncio.to_thread(self._bridge.mutation, "tasks:create", task_args)
            if not task_id:
                return "Error: Failed to create task in Mission Control."

            origin = {
                "channel": self._origin_channel,
                "chat_id": self._origin_chat_id,
            }

            # Start background polling
            bg_task = asyncio.create_task(self._poll_task_completion(task_id, title, origin))
            self._polling_tasks[task_id] = bg_task
            bg_task.add_done_callback(lambda _: self._polling_tasks.pop(task_id, None))

            return f"Task '{title}' has been successfully delegated to Mission Control (ID: {task_id}). You will receive a system message when it completes. Do not wait for it, proceed with conversation."

        except Exception as e:
            logger.exception("Failed to delegate task to MC")
            return f"Error: Failed to delegate task: {e}"

    async def _poll_task_completion(self, task_id: str, title: str, origin: dict[str, str]) -> None:
        """Poll Convex periodically until the task status is completed or failed."""
        if not self._bridge:
            return

        try:
            while True:
                task = await asyncio.to_thread(
                    self._bridge.query, "tasks:getById", {"task_id": task_id}
                )
                if not task:
                    await self._announce(
                        task_id,
                        title,
                        "Task was deleted from Mission Control before completion.",
                        origin,
                        "error",
                    )
                    return

                status = task.get("status")
                if status == "completed":
                    # Fetch final artifacts/messages
                    messages = await asyncio.to_thread(
                        self._bridge.query, "messages:listByTask", {"taskId": task_id}
                    )

                    # Try to extract the final result
                    final_result = "Task completed."
                    if messages:
                        # Find the last message that is not an activity/error
                        for msg in reversed(messages):
                            if msg.get("type") in ("agent_message", "tool_result") and msg.get(
                                "content"
                            ):
                                final_result = msg["content"]
                                break

                    await self._announce(task_id, title, final_result, origin, "ok")
                    return
                elif status in ("failed", "crashed", "deleted"):
                    await self._announce(
                        task_id, title, f"Task ended with status: {status}", origin, "error"
                    )
                    return

                await asyncio.sleep(5)  # Poll every 5 seconds
        except Exception as e:
            logger.exception("Error polling MC task {}", task_id)
            await self._announce(task_id, title, f"Polling failed: {e}", origin, "error")

    async def _announce(
        self, task_id: str, title: str, result: str, origin: dict[str, str], status: str
    ) -> None:
        """Announce the result back to the main agent bus."""
        status_text = "completed successfully" if status == "ok" else "failed"

        announce_content = f"""[Mission Control Task '{title}' {status_text}]

Result from Mission Control:
{result}

Summarize this naturally for the user. Keep it brief. Do not mention technical details like task IDs."""

        msg = InboundMessage(
            channel="system",
            sender_id="mc_delegate",
            chat_id=origin["chat_id"],
            content=announce_content,
        )

        await self._bus.publish_inbound(msg)
        logger.debug(
            "MC Task [{}] announced result to {}:{}", task_id, origin["channel"], origin["chat_id"]
        )
