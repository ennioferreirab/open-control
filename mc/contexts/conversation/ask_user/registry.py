"""Global registry of active AskUserHandler instances for ask_user reply routing."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mc.contexts.conversation.ask_user.handler import AskUserHandler

logger = logging.getLogger(__name__)


class AskUserRegistry:
    """Thread-safe registry mapping task_id to AskUserHandler."""

    def __init__(self) -> None:
        self._handlers: dict[str, AskUserHandler] = {}

    def register(self, task_id: str, handler: AskUserHandler) -> None:
        self._handlers[task_id] = handler
        logger.debug("[ask_user_registry] Registered handler for task %s", task_id)

    def unregister(self, task_id: str) -> None:
        removed = self._handlers.pop(task_id, None)
        if removed:
            logger.debug("[ask_user_registry] Unregistered handler for task %s", task_id)

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
