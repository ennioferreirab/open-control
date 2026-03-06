"""Chat repository -- chat message queries and mutations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.bridge.client import BridgeClient

logger = logging.getLogger(__name__)


class ChatRepository:
    """Data access methods for chat messages in Convex."""

    def __init__(self, client: "BridgeClient"):
        self._client = client

    def get_pending_chat_messages(self) -> list[dict[str, Any]]:
        """Fetch all pending chat messages from Convex.

        Returns:
            List of chat dicts with snake_case keys.
        """
        result = self._client.query("chats:listPending")
        return result if isinstance(result, list) else []

    def send_chat_response(
        self, agent_name: str, content: str, author_name: str | None = None
    ) -> Any:
        """Send an agent response to a chat conversation.

        Args:
            agent_name: Name of the responding agent.
            content: The agent's response text.
            author_name: Display name for the agent (defaults to agent_name).
        """
        return self._client.mutation(
            "chats:send",
            {
                "agent_name": agent_name,
                "author_name": author_name or agent_name,
                "author_type": "agent",
                "content": content,
                "status": "done",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    def mark_chat_processing(self, chat_id: str) -> Any:
        """Mark a chat message as processing.

        Args:
            chat_id: Convex _id of the chat message.
        """
        return self._client.mutation(
            "chats:updateStatus",
            {"chat_id": chat_id, "status": "processing"},
        )

    def mark_chat_done(self, chat_id: str) -> Any:
        """Mark a chat message as done.

        Args:
            chat_id: Convex _id of the chat message.
        """
        return self._client.mutation(
            "chats:updateStatus",
            {"chat_id": chat_id, "status": "done"},
        )
