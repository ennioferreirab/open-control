"""Board repository -- board-related queries and mutations."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.bridge.client import BridgeClientProtocol

logger = logging.getLogger(__name__)


class BoardRepository:
    """Data access methods for board entities in Convex."""

    def __init__(self, client: "BridgeClientProtocol"):
        self._client = client

    def get_board_by_id(self, board_id: str) -> dict[str, Any] | None:
        """Fetch a board by its Convex _id.

        Args:
            board_id: Convex board _id string.

        Returns:
            Board dict with snake_case keys, or None if not found.
        """
        return self._client.query("boards:getById", {"board_id": board_id})

    def get_default_board(self) -> dict[str, Any] | None:
        """Fetch the current default board."""
        return self._client.query("boards:getDefault", {})

    def ensure_default_board(self) -> Any:
        """Ensure a default board exists in Convex.

        Creates it if none exists. Idempotent -- safe to call on every startup.

        Returns:
            The default board's _id.
        """
        result = self._client.mutation("boards:ensureDefaultBoard", {})
        self._log_state_transition("board", "Ensured default board exists")
        return result

    @staticmethod
    def _log_state_transition(entity_type: str, description: str) -> None:
        """Log a state transition to local stdout via logging."""
        timestamp = datetime.now(UTC).isoformat()
        logger.info("[MC] %s %s: %s", timestamp, entity_type, description)
