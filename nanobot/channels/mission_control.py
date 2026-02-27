"""Mission Control channel — bridges outbound messages to Convex task threads."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from loguru import logger

from nanobot.channels.base import BaseChannel
from nanobot.bus.events import OutboundMessage

if TYPE_CHECKING:
    from nanobot.bus.queue import MessageBus


class MissionControlChannel(BaseChannel):
    """Channel that delivers messages to Convex via the ConvexBridge.

    When ``send()`` is called:
    - If ``msg.chat_id`` resolves to an existing task, post to its thread.
    - Otherwise, create a new task with the message content as title.
    """

    name: str = "mc"

    def __init__(self, config: Any, bus: "MessageBus", bridge: Any | None = None):
        super().__init__(config, bus)
        self._bridge = bridge

    async def start(self) -> None:
        """MC channel has no inbound listener — keep alive until stopped."""
        self._running = True
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        """Send an outbound message to Convex."""
        if not self._bridge:
            logger.warning("[mc-channel] No bridge configured — message dropped")
            return

        task_id = msg.chat_id
        try:
            task = await asyncio.to_thread(
                self._bridge.query, "tasks:getById", {"task_id": task_id}
            )
        except Exception:
            logger.warning("[mc-channel] Failed to query task %s", task_id)
            task = None

        if task:
            try:
                await asyncio.to_thread(
                    self._bridge.send_message,
                    task_id,
                    "Cron",
                    "system",
                    msg.content,
                    "system",
                )
                logger.info("[mc-channel] Posted to task thread %s", task_id)
            except Exception:
                logger.exception("[mc-channel] Failed to post to task %s", task_id)
        else:
            try:
                await asyncio.to_thread(
                    self._bridge.mutation,
                    "tasks:create",
                    {"title": msg.content[:200]},
                )
                logger.info("[mc-channel] Created new task for message")
            except Exception:
                logger.exception("[mc-channel] Failed to create task")
