"""
ConvexBridge — Single integration point between nanobot AsyncIO runtime and Convex.

This is the ONLY module in the nanobot codebase that imports the `convex` Python SDK.
All other modules interact with Convex exclusively through this bridge.

Subscription polling, agent sync/archive, file sync, and write-back operations
live in ``mc.bridge_subscriptions`` and are mixed into ConvexBridge automatically.
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from convex import ConvexClient
from mc.bridge_subscriptions import ConvexBridgeSubscriptionsMixin
from mc.types import task_safe_id

logger = logging.getLogger(__name__)

MAX_RETRIES = 3  # Number of retries AFTER the initial attempt (4 total attempts)
BACKOFF_BASE_SECONDS = 1  # Delays: 1s, 2s, 4s


def _to_camel_case(snake_str: str) -> str:
    """Convert a snake_case string to camelCase. Preserves _prefixed Convex fields."""
    if snake_str.startswith("_"):
        return snake_str
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def _to_snake_case(camel_str: str) -> str:
    """Convert a camelCase string to snake_case. Handles Convex _prefixed fields."""
    if camel_str.startswith("_"):
        # Strip leading underscore, convert rest
        # _id -> id, _creationTime -> creation_time
        inner = camel_str[1:]
        s1 = re.sub(r"([A-Z])", r"_\1", inner)
        return s1.lower().lstrip("_")
    s1 = re.sub(r"([A-Z])", r"_\1", camel_str)
    return s1.lower().lstrip("_")


def _convert_keys_to_camel(data: Any) -> Any:
    """Recursively convert all dict keys from snake_case to camelCase."""
    if isinstance(data, dict):
        return {_to_camel_case(k): _convert_keys_to_camel(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_convert_keys_to_camel(item) for item in data]
    return data


def _convert_keys_to_snake(data: Any) -> Any:
    """Recursively convert all dict keys from camelCase to snake_case."""
    if isinstance(data, dict):
        return {_to_snake_case(k): _convert_keys_to_snake(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_convert_keys_to_snake(item) for item in data]
    return data


class ConvexBridge(ConvexBridgeSubscriptionsMixin):
    """Bridge between nanobot Python runtime and Convex backend."""

    def __init__(self, deployment_url: str, admin_key: str | None = None):
        """
        Initialize the Convex bridge.

        Args:
            deployment_url: Convex deployment URL (e.g., "https://example.convex.cloud")
            admin_key: Optional admin key for server-side auth
        """
        self._client = ConvexClient(deployment_url)
        if admin_key:
            self._client.set_admin_auth(admin_key)
        else:
            logger.warning(
                "ConvexBridge initialized WITHOUT admin key — "
                "internal mutations will fail. Set CONVEX_ADMIN_KEY."
            )
        logger.info("ConvexBridge connected to %s", deployment_url)

    def query(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        """
        Call a Convex query function.

        Args:
            function_name: Convex function in colon notation (e.g., "tasks:list")
            args: Optional arguments dict (snake_case keys — converted to camelCase)

        Returns:
            Query result with camelCase keys converted to snake_case
        """
        camel_args = _convert_keys_to_camel(args) if args else {}
        logger.debug("query %s args=%s", function_name, camel_args)
        result = self._client.query(function_name, camel_args)
        return _convert_keys_to_snake(result)

    def mutation(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        """
        Call a Convex mutation function with retry.

        Args:
            function_name: Convex function in colon notation (e.g., "tasks:create")
            args: Optional arguments dict (snake_case keys — converted to camelCase)

        Returns:
            Mutation result (if any) with camelCase keys converted to snake_case
        """
        return self._mutation_with_retry(function_name, args)

    def _mutation_with_retry(
        self, function_name: str, args: dict[str, Any] | None = None
    ) -> Any:
        """
        Call a Convex mutation with retry and exponential backoff.

        Retries up to MAX_RETRIES times on failure. On exhaustion, logs error
        and makes a best-effort attempt to write a system_error activity event.

        Raises:
            Exception: Re-raises the last exception after retry exhaustion.
        """
        camel_args = _convert_keys_to_camel(args) if args else {}
        last_exception = None
        max_attempts = MAX_RETRIES + 1  # initial attempt + retries

        for attempt in range(1, max_attempts + 1):
            try:
                logger.debug("mutation %s attempt %d args=%s", function_name, attempt, camel_args)
                result = self._client.mutation(function_name, camel_args)
                if attempt > 1:
                    logger.info(
                        "Mutation %s succeeded on attempt %d/%d",
                        function_name, attempt, max_attempts,
                    )
                return _convert_keys_to_snake(result) if result else result
            except Exception as e:
                last_exception = e
                if attempt < max_attempts:
                    delay = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        "Mutation %s failed (attempt %d/%d), retrying in %ds: %s",
                        function_name, attempt, max_attempts, delay, e,
                    )
                    time.sleep(delay)

        logger.error(
            "Mutation %s failed after %d attempts. Args: %s. Error: %s",
            function_name, max_attempts, camel_args, last_exception,
        )
        self._write_error_activity(function_name, str(last_exception))
        raise last_exception

    def _write_error_activity(self, mutation_name: str, error_message: str) -> None:
        """
        Best-effort write of a system_error activity event to Convex.

        Called after retry exhaustion. If this write also fails,
        the error is silently logged -- no cascading exceptions.
        """
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            self._client.mutation("activities:create", {
                "eventType": "system_error",
                "description": (
                    f"Mutation {mutation_name} failed after {MAX_RETRIES + 1} "
                    f"attempts ({MAX_RETRIES} retries): {error_message}"
                ),
                "timestamp": timestamp,
            })
        except Exception as e:
            logger.error("Failed to write error activity event (best-effort): %s", e)

    def _log_state_transition(self, entity_type: str, description: str) -> None:
        """Log a state transition to local stdout via logging."""
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info("[MC] %s %s: %s", timestamp, entity_type, description)

    def update_task_status(
        self,
        task_id: str,
        status: str,
        agent_name: str | None = None,
        description: str | None = None,
        awaiting_kickoff: bool | None = None,
    ) -> Any:
        """Update a task's status with retry and logging."""
        mutation_args: dict[str, Any] = {"task_id": task_id, "status": status}
        if agent_name is not None:
            mutation_args["agent_name"] = agent_name
        if awaiting_kickoff is not None:
            mutation_args["awaiting_kickoff"] = awaiting_kickoff
        result = self._mutation_with_retry(
            "tasks:updateStatus",
            mutation_args,
        )
        desc = description or f"Task status changed to {status}"
        if agent_name:
            desc += f" by {agent_name}"
        self._log_state_transition("task", desc)
        return result

    def update_agent_status(
        self,
        agent_name: str,
        status: str,
        description: str | None = None,
    ) -> Any:
        """Update an agent's status with retry and logging."""
        result = self._mutation_with_retry(
            "agents:updateStatus",
            {"agent_name": agent_name, "status": status},
        )
        self._log_state_transition(
            "agent",
            description or f"Agent '{agent_name}' status changed to {status}",
        )
        return result

    def create_activity(
        self,
        event_type: str,
        description: str,
        task_id: str | None = None,
        agent_name: str | None = None,
    ) -> Any:
        """Create an activity event with retry and logging."""
        args: dict[str, Any] = {
            "event_type": event_type,
            "description": description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if task_id:
            args["task_id"] = task_id
        if agent_name:
            args["agent_name"] = agent_name
        result = self._mutation_with_retry("activities:create", args)
        self._log_state_transition("activity", description)
        return result

    def create_task_directory(self, task_id: str) -> None:
        """Create the filesystem directory structure for a task.

        Creates:
            ~/.nanobot/tasks/{safe_task_id}/attachments/
            ~/.nanobot/tasks/{safe_task_id}/output/

        Idempotent — no error if directories already exist.
        On OSError, logs an activity event and continues (does not raise).

        Args:
            task_id: Convex task _id (e.g. "jd7abc123xyz").
        """
        safe_task_id = task_safe_id(task_id)
        task_dir = Path.home() / ".nanobot" / "tasks" / safe_task_id
        for subdir in ("attachments", "output"):
            path = task_dir / subdir
            try:
                os.makedirs(path, exist_ok=True)
                logger.debug("Created task directory: %s", path)
            except OSError as exc:
                error_msg = f"Failed to create task directory {path}: {exc}"
                logger.error(error_msg)
                try:
                    self.create_activity(
                        "system_error",
                        error_msg,
                        task_id=task_id,
                    )
                except Exception as activity_exc:
                    logger.error(
                        "Failed to log directory creation error as activity: %s",
                        activity_exc,
                    )

    def get_task_messages(self, task_id: str) -> list[dict[str, Any]]:
        """Fetch all thread messages for a task, in chronological order."""
        result = self.query("messages:listByTask", {"task_id": task_id})
        return result if isinstance(result, list) else []

    def send_message(
        self,
        task_id: str,
        author_name: str,
        author_type: str,
        content: str,
        message_type: str,
        msg_type: str | None = None,
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
        args: dict[str, Any] = {
            "task_id": task_id,
            "author_name": author_name,
            "author_type": author_type,
            "content": content,
            "message_type": message_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if msg_type is not None:
            args["type"] = msg_type
        result = self._mutation_with_retry("messages:create", args)
        self._log_state_transition(
            "message", f"Message sent by {author_name} on task {task_id}"
        )
        return result

    def post_step_completion(
        self,
        task_id: str,
        step_id: str,
        agent_name: str,
        content: str,
        artifacts: list[dict[str, Any]] | None = None,
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
        args: dict[str, Any] = {
            "task_id": task_id,
            "step_id": step_id,
            "agent_name": agent_name,
            "content": content,
        }
        if artifacts:
            args["artifacts"] = artifacts
        result = self._mutation_with_retry("messages:postStepCompletion", args)
        self._log_state_transition(
            "message",
            f"Step completion posted by {agent_name} on task {task_id}",
        )
        return result

    def post_lead_agent_message(
        self,
        task_id: str,
        content: str,
        msg_type: str,
    ) -> Any:
        """Post a Lead Agent plan or chat message to the unified task thread.

        Calls messages:postLeadAgentMessage Convex mutation.

        Args:
            task_id: Convex task _id.
            content: Message body (plan text or chat message).
            msg_type: ThreadMessageType value — either "lead_agent_plan"
                      or "lead_agent_chat".
        """
        args: dict[str, Any] = {
            "task_id": task_id,
            "content": content,
            "type": msg_type,
        }
        result = self._mutation_with_retry("messages:postLeadAgentMessage", args)
        self._log_state_transition(
            "message",
            f"Lead agent message ({msg_type}) posted on task {task_id}",
        )
        return result

    def update_execution_plan(self, task_id: str, plan: dict[str, Any]) -> Any:
        """Update the executionPlan field on a task document.

        Args:
            task_id: Convex task _id.
            plan: Serialized execution plan dict (camelCase keys).

        Returns:
            Mutation result (if any).
        """
        # Plan dict already has camelCase keys from ExecutionPlan.to_dict(),
        # so pass it directly without snake->camel conversion on the plan body.
        return self._mutation_with_retry(
            "tasks:updateExecutionPlan",
            {"task_id": task_id, "execution_plan": plan},
        )

    def create_step(self, step_data: dict[str, Any]) -> str:
        """Create a single step record in Convex.

        Args:
            step_data: Step payload using snake_case keys.

        Returns:
            Convex step _id.
        """
        result = self._mutation_with_retry("steps:create", step_data)
        if not isinstance(result, str):
            raise RuntimeError("steps:create did not return a step id")
        return result

    def batch_create_steps(
        self,
        task_id: str,
        steps: list[dict[str, Any]],
    ) -> list[str]:
        """Create multiple step records atomically via Convex.

        Args:
            task_id: Parent task _id.
            steps: Step payload list using snake_case keys.

        Returns:
            List of created step _id values in insertion order.
        """
        result = self._mutation_with_retry(
            "steps:batchCreate",
            {"task_id": task_id, "steps": steps},
        )
        if result is None:
            return []
        if not isinstance(result, list):
            raise RuntimeError("steps:batchCreate did not return a list of step ids")
        return [str(step_id) for step_id in result]

    def kick_off_task(self, task_id: str, step_count: int) -> Any:
        """Transition a task to the running state after materialization."""
        result = self._mutation_with_retry(
            "tasks:kickOff",
            {"task_id": task_id, "step_count": step_count},
        )
        self._log_state_transition(
            "task", f"Task {task_id} kicked off with {step_count} steps"
        )
        return result

    def approve_and_kick_off(
        self, task_id: str, execution_plan: dict[str, Any] | None = None
    ) -> Any:
        """Approve plan and kick off a supervised task.

        Calls the atomic Convex mutation that saves the (optionally edited)
        execution plan, transitions review (awaitingKickoff) -> in_progress,
        and creates an activity event.
        """
        args: dict[str, Any] = {"task_id": task_id}
        if execution_plan is not None:
            args["execution_plan"] = execution_plan
        result = self._mutation_with_retry("tasks:approveAndKickOff", args)
        self._log_state_transition(
            "task", f"Task {task_id} approved and kicked off"
        )
        return result

    def post_system_error(
        self,
        task_id: str,
        content: str,
        step_id: str | None = None,
    ) -> Any:
        """Post a system error message to the task thread.

        Args:
            task_id: Convex task _id.
            content: Error message body.
            step_id: Optional step _id that triggered the error.
        """
        args: dict[str, Any] = {
            "task_id": task_id,
            "author_name": "System",
            "author_type": "system",
            "content": content,
            "message_type": "system_event",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if step_id is not None:
            args["step_id"] = step_id
        result = self._mutation_with_retry("messages:create", args)
        self._log_state_transition(
            "message", f"System error posted on task {task_id}"
        )
        return result

    def update_step_status(
        self,
        step_id: str,
        status: str,
        error_message: str | None = None,
    ) -> Any:
        """Update a step's lifecycle status via steps:updateStatus."""
        args: dict[str, Any] = {"step_id": step_id, "status": status}
        if error_message is not None:
            args["error_message"] = error_message

        result = self._mutation_with_retry("steps:updateStatus", args)
        self._log_state_transition(
            "step", f"Step {step_id} status changed to {status}"
        )
        return result

    def get_steps_by_task(self, task_id: str) -> list[dict[str, Any]]:
        """Fetch all steps for a task ordered by step.order."""
        result = self.query("steps:getByTask", {"task_id": task_id})
        return result if isinstance(result, list) else []

    def check_and_unblock_dependents(self, step_id: str) -> list[str]:
        """Unblock dependents for a completed step.

        Returns:
            List of newly unblocked step IDs.
        """
        result = self._mutation_with_retry(
            "steps:checkAndUnblockDependents",
            {"step_id": step_id},
        )
        if not isinstance(result, list):
            return []
        return [str(unblocked_id) for unblocked_id in result]

    def get_board_by_id(self, board_id: str) -> dict[str, Any] | None:
        """Fetch a board by its Convex _id.

        Args:
            board_id: Convex board _id string.

        Returns:
            Board dict with snake_case keys, or None if not found.
        """
        return self.query("boards:getById", {"board_id": board_id})

    def ensure_default_board(self) -> Any:
        """Ensure a default board exists in Convex.

        Creates it if none exists. Idempotent — safe to call on every startup.

        Returns:
            The default board's _id.
        """
        result = self.mutation("boards:ensureDefaultBoard", {})
        self._log_state_transition("board", "Ensured default board exists")
        return result

    # ── Chat helpers (Story 10.2) ──────────────────────────────────────

    def get_pending_chat_messages(self) -> list[dict[str, Any]]:
        """Fetch all pending chat messages from Convex.

        Returns:
            List of chat dicts with snake_case keys.
        """
        result = self.query("chats:listPending")
        return result if isinstance(result, list) else []

    def send_chat_response(self, agent_name: str, content: str, author_name: str | None = None) -> Any:
        """Send an agent response to a chat conversation.

        Args:
            agent_name: Name of the responding agent.
            content: The agent's response text.
            author_name: Display name for the agent (defaults to agent_name).
        """
        return self._mutation_with_retry(
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
        return self._mutation_with_retry(
            "chats:updateStatus",
            {"chat_id": chat_id, "status": "processing"},
        )

    def mark_chat_done(self, chat_id: str) -> Any:
        """Mark a chat message as done.

        Args:
            chat_id: Convex _id of the chat message.
        """
        return self._mutation_with_retry(
            "chats:updateStatus",
            {"chat_id": chat_id, "status": "done"},
        )

    def close(self) -> None:
        """Close the Convex client connection."""
        logger.info("ConvexBridge closing connection")
        if hasattr(self._client, "close"):
            self._client.close()
