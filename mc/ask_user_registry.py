"""Global registry of active AskUserHandler instances for ask_user reply routing.

When a backend calls ask_user, the AskUserHandler creates a Future and waits.
This registry allows the AskUserReplyWatcher to find the correct handler instance
and deliver user replies via deliver_user_reply().
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.ask_user_handler import AskUserHandler

logger = logging.getLogger(__name__)


class AskUserRegistry:
    """Thread-safe registry mapping task_id → AskUserHandler.

    Lifecycle:
    - register() when ask_user handler is initialized
    - unregister() when task execution ends
    - get() / deliver_reply() used by AskUserReplyWatcher

    Note: If multiple CC steps for the same task_id run concurrently and both
    call ask_user, only the last-registered handler receives replies. This is
    acceptable because concurrent ask_user from the same task is rare.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, AskUserHandler] = {}

    def register(self, task_id: str, handler: AskUserHandler) -> None:
        """Register an ask_user handler for a task."""
        self._handlers[task_id] = handler
        logger.debug("[ask_user_registry] Registered handler for task %s", task_id)

    def unregister(self, task_id: str) -> None:
        """Remove an ask_user handler registration."""
        removed = self._handlers.pop(task_id, None)
        if removed:
            logger.debug("[ask_user_registry] Unregistered handler for task %s", task_id)

    def get(self, task_id: str) -> AskUserHandler | None:
        """Look up the ask_user handler for a task."""
        return self._handlers.get(task_id)

    def has_pending_ask(self, task_id: str) -> bool:
        """Check if a task has an active ask_user waiting for a reply."""
        handler = self._handlers.get(task_id)
        if not handler:
            return False
        return handler.has_pending_ask(task_id)

    def active_task_ids(self) -> set[str]:
        """Return task_ids that currently have a pending ask_user."""
        return {tid for tid in self._handlers if self.has_pending_ask(tid)}

    def deliver_reply(self, task_id: str, answer: str) -> bool:
        """Deliver a user reply to the waiting ask_user Future.

        Returns True if delivered, False if no handler/pending ask found.
        """
        handler = self._handlers.get(task_id)
        if not handler:
            return False
        if not handler.has_pending_ask(task_id):
            return False
        handler.deliver_user_reply(task_id, answer)
        logger.info("[ask_user_registry] Delivered reply for task %s", task_id)
        return True
