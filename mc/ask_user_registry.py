"""Global registry of active MCSocketServer instances for ask_user reply routing.

When a CC agent calls ask_user, the MCSocketServer creates a Future and waits.
This registry allows the AskUserReplyWatcher to find the correct server instance
and deliver user replies via deliver_user_reply().
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from claude_code.ipc_server import MCSocketServer

logger = logging.getLogger(__name__)


class AskUserRegistry:
    """Thread-safe registry mapping task_id → MCSocketServer.

    Lifecycle:
    - register() when IPC server starts (before CC execution)
    - unregister() when IPC server stops (in finally block)
    - get() / deliver_reply() used by AskUserReplyWatcher
    """

    def __init__(self) -> None:
        self._servers: dict[str, MCSocketServer] = {}

    def register(self, task_id: str, server: MCSocketServer) -> None:
        """Register an IPC server for a task."""
        self._servers[task_id] = server
        logger.debug("[ask_user_registry] Registered server for task %s", task_id)

    def unregister(self, task_id: str) -> None:
        """Remove an IPC server registration."""
        removed = self._servers.pop(task_id, None)
        if removed:
            logger.debug("[ask_user_registry] Unregistered server for task %s", task_id)

    def get(self, task_id: str) -> MCSocketServer | None:
        """Look up the IPC server for a task."""
        return self._servers.get(task_id)

    def has_pending_ask(self, task_id: str) -> bool:
        """Check if a task has an active ask_user waiting for a reply."""
        server = self._servers.get(task_id)
        if not server:
            return False
        request_id = server._task_to_request.get(task_id)
        if not request_id:
            return False
        return request_id in server._pending_ask

    def active_task_ids(self) -> set[str]:
        """Return task_ids that currently have a pending ask_user."""
        return {tid for tid in self._servers if self.has_pending_ask(tid)}

    def deliver_reply(self, task_id: str, answer: str) -> bool:
        """Deliver a user reply to the waiting ask_user Future.

        Returns True if delivered, False if no server/pending ask found.
        """
        server = self._servers.get(task_id)
        if not server:
            return False
        server.deliver_user_reply(task_id, answer)
        logger.info("[ask_user_registry] Delivered reply for task %s", task_id)
        return True
