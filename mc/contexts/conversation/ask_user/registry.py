"""Global registry of active AskUserHandler instances for ask_user reply routing."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mc.contexts.conversation.ask_user.handler import AskUserHandler

logger = logging.getLogger(__name__)


class AskUserRegistry:
    """Thread-safe registry mapping task_id to AskUserHandler."""

    def __init__(self) -> None:
        self._handlers: dict[str, AskUserHandler] = {}
        self._change_version = 0
        self._change_event: asyncio.Event = asyncio.Event()

    def _notify_change(self) -> None:
        self._change_version += 1
        self._change_event.set()
        self._change_event = asyncio.Event()

    def register(self, task_id: str, handler: AskUserHandler) -> None:
        handler.set_state_change_callback(self._notify_change)
        self._handlers[task_id] = handler
        logger.debug("[ask_user_registry] Registered handler for task %s", task_id)
        self._notify_change()

    def unregister(self, task_id: str) -> None:
        removed = self._handlers.pop(task_id, None)
        if removed:
            removed.set_state_change_callback(None)
            logger.debug("[ask_user_registry] Unregistered handler for task %s", task_id)
            self._notify_change()

    def get(self, task_id: str) -> AskUserHandler | None:
        return self._handlers.get(task_id)

    def has_pending_ask(self, task_id: str) -> bool:
        handler = self._handlers.get(task_id)
        if not handler:
            return False
        return handler.has_pending_ask(task_id)

    def active_task_ids(self) -> set[str]:
        return {task_id for task_id in self._handlers if self.has_pending_ask(task_id)}

    def deliver_reply(self, task_id: str, answer: str) -> bool:
        handler = self._handlers.get(task_id)
        if not handler:
            return False
        if not handler.has_pending_ask(task_id):
            return False
        handler.deliver_user_reply(task_id, answer)
        logger.info("[ask_user_registry] Delivered reply for task %s", task_id)
        return True

    async def wait_for_change(self, last_seen_version: int) -> int:
        """Block until the active ask registry changes."""
        while self._change_version == last_seen_version:
            event = self._change_event
            await event.wait()
        return self._change_version

    @property
    def change_version(self) -> int:
        """Current monotonic registry change version."""
        return self._change_version
