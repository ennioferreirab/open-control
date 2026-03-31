"""Message repository -- posting and queries for task thread messages."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mc.bridge.overflow import safe_string_for_convex
from mc.infrastructure.runtime_home import get_tasks_dir

if TYPE_CHECKING:
    from mc.bridge.client import BridgeClientProtocol

logger = logging.getLogger(__name__)


def _content_digest(*parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _resolve_overflow_dir(task_id: str) -> Path | None:
    """Return the task overflow directory used for oversized thread content."""
    try:
        return get_tasks_dir() / task_id / "output" / "_overflow"
    except Exception:
        return None


def _safe_message_content(task_id: str, content: str) -> str:
    """Cap message content to the Convex safe limit with filesystem overflow."""
    return safe_string_for_convex(
        content,
        field_name="content",
        task_id=task_id,
        overflow_dir=_resolve_overflow_dir(task_id),
    )


class MessageRepository:
    """Data access methods for message entities in Convex."""

    def __init__(self, client: BridgeClientProtocol):
        self._client = client

    def get_task_messages(self, task_id: str) -> list[dict[str, Any]]:
        """Fetch all thread messages for a task, in chronological order."""
        result = self._client.query("messages:listByTask", {"task_id": task_id})
        return result if isinstance(result, list) else []

    def get_recent_user_messages(
        self, since_timestamp: str, *, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Fetch all user messages created since the given ISO timestamp."""
        args: dict[str, Any] = {"since_timestamp": since_timestamp}
        if limit is not None:
            args["limit"] = limit
        result = self._client.query(
            "messages:listRecentUserMessages",
            args,
        )
        return result if isinstance(result, list) else []

    def send_message(
        self,
        task_id: str,
        author_name: str,
        author_type: str,
        content: str,
        message_type: str,
        msg_type: str | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        """Send a task-scoped message with retry and logging.

        Args:
            task_id: Convex task _id.
            author_name: Display name of the message author.
            author_type: AuthorType value ("agent", "user", or "system").
            content: Message body.
            message_type: Legacy MessageType value for existing UI styling.
            msg_type: Optional ThreadMessageType value for unified thread (Story 2.4).
                      When provided, stored as the `type` field on the message.
                      When omitted, the `type` field is not set (backward compatible).
        """
        safe_content = _safe_message_content(task_id, content)
        args: dict[str, Any] = {
            "task_id": task_id,
            "author_name": author_name,
            "author_type": author_type,
            "content": safe_content,
            "message_type": message_type,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if msg_type is not None:
            args["type"] = msg_type
        args["idempotency_key"] = idempotency_key or (
            f"py:message:{task_id}:{author_name}:{message_type}:{msg_type or 'none'}:"
            f"{_content_digest(content, args['timestamp'])}"
        )
        result = self._client.mutation("messages:create", args)
        self._log_state_transition("message", f"Message sent by {author_name} on task {task_id}")
        return result

    def post_step_completion(
        self,
        task_id: str,
        step_id: str,
        agent_name: str,
        content: str,
        artifacts: list[dict[str, Any]] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        """Post a step-completion message to the unified task thread.

        Calls messages:postStepCompletion Convex mutation. The bridge's
        key-conversion will translate snake_case args to camelCase automatically.

        Args:
            task_id: Convex task _id.
            step_id: Convex step _id linking the message to the specific step.
            agent_name: Name of the agent that completed the step.
            content: Completion message body (summary of what was done).
            artifacts: Optional list of artifact dicts with keys:
                       path, action ("created"|"modified"|"deleted"),
                       description (optional), diff (optional).
        """
        safe_content = _safe_message_content(task_id, content)
        args: dict[str, Any] = {
            "task_id": task_id,
            "step_id": step_id,
            "agent_name": agent_name,
            "content": safe_content,
        }
        if artifacts:
            args["artifacts"] = artifacts
        args["idempotency_key"] = idempotency_key or (
            f"py:step-completion:{task_id}:{step_id}:{agent_name}:{_content_digest(content, artifacts)}"
        )
        result = self._client.mutation("messages:postStepCompletion", args)
        self._log_state_transition(
            "message",
            f"Step completion posted by {agent_name} on task {task_id}",
        )
        return result

    def post_orchestrator_agent_message(
        self,
        task_id: str,
        content: str,
        msg_type: str,
        plan_review: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        """Post an Orchestrator Agent chat message to the unified task thread.

        Calls messages:postOrchestratorAgentMessage Convex mutation.

        Args:
            task_id: Convex task _id.
            content: Message body (chat message).
            msg_type: ThreadMessageType value -- "orchestrator_agent_chat".
        """
        safe_content = _safe_message_content(task_id, content)
        args: dict[str, Any] = {
            "task_id": task_id,
            "content": safe_content,
            "type": msg_type,
        }
        if plan_review is not None:
            args["plan_review"] = plan_review
        args["idempotency_key"] = idempotency_key or (
            f"py:orchestrator-agent:{task_id}:{msg_type}:{_content_digest(content, plan_review)}"
        )
        result = self._client.mutation("messages:postOrchestratorAgentMessage", args)
        self._log_state_transition(
            "message",
            f"Orchestrator agent message ({msg_type}) posted on task {task_id}",
        )
        return result

    def post_system_error(
        self,
        task_id: str,
        content: str,
        step_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        """Post a system error message to the task thread.

        Args:
            task_id: Convex task _id.
            content: Error message body.
            step_id: Optional step _id that triggered the error.
        """
        safe_content = _safe_message_content(task_id, content)
        args: dict[str, Any] = {
            "task_id": task_id,
            "author_name": "System",
            "author_type": "system",
            "content": safe_content,
            "message_type": "system_event",
            "type": "system_error",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if step_id is not None:
            args["step_id"] = step_id
        args["idempotency_key"] = idempotency_key or (
            f"py:system-error:{task_id}:{step_id or 'none'}:{_content_digest(content, args['timestamp'])}"
        )
        result = self._client.mutation("messages:create", args)
        self._log_state_transition("message", f"System error posted on task {task_id}")
        return result

    @staticmethod
    def _log_state_transition(entity_type: str, description: str) -> None:
        """Log a state transition to local stdout via logging."""
        timestamp = datetime.now(UTC).isoformat()
        logger.info("[MC] %s %s: %s", timestamp, entity_type, description)
