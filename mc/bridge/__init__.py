"""
ConvexBridge -- Single integration point between nanobot AsyncIO runtime and Convex.

This is the ONLY module in the nanobot codebase that imports the `convex` Python SDK.
All other modules interact with Convex exclusively through this bridge.

This package facade re-exports the entire public API for backward compatibility.
The implementation is split across sub-modules:
- mc.bridge.client -- raw Convex client wrapper
- mc.bridge.retry -- retry/backoff logic
- mc.bridge.key_conversion -- camelCase/snake_case conversion
- mc.bridge.subscriptions -- polling/subscription logic
- mc.bridge.repositories.* -- data access by entity type
"""

from __future__ import annotations

import asyncio  # noqa: F811 -- used in type annotation
import logging
import os  # noqa: F401 -- re-exported for patch compatibility
import re  # noqa: F401 -- re-exported for patch compatibility
import time  # noqa: F401 -- re-exported for patch compatibility
from datetime import datetime, timezone  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Any, Iterator

from convex import ConvexClient  # noqa: F401 -- re-exported for patch compatibility

# Re-export key conversion utilities (used by tests and external code)
from mc.bridge.key_conversion import (  # noqa: F401
    _convert_keys_to_camel,
    _convert_keys_to_snake,
    _to_camel_case,
    _to_snake_case,
)

# Import repository and subscription classes
from mc.bridge.repositories.agents import AgentRepository
from mc.bridge.repositories.boards import BoardRepository
from mc.bridge.repositories.chats import ChatRepository
from mc.bridge.repositories.messages import MessageRepository
from mc.bridge.repositories.steps import StepRepository
from mc.bridge.repositories.tasks import TaskRepository

# Re-export retry constants
from mc.bridge.retry import (  # noqa: F401
    BACKOFF_BASE_SECONDS,
    MAX_RETRIES,
)
from mc.bridge.subscriptions import SubscriptionManager
from mc.types import task_safe_id  # noqa: F401

logger = logging.getLogger(__name__)


class ConvexBridge:
    """Bridge between nanobot Python runtime and Convex backend.

    This class is a facade that delegates to specialized sub-modules
    while maintaining the original public API for backward compatibility.
    """

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

        # Initialize sub-modules using a lightweight adapter
        self._init_repositories()

    def _init_repositories(self) -> None:
        """Initialize all repository sub-modules.

        Separated from __init__ to support lazy initialization when
        ConvexBridge is created via object.__new__ (bypassing __init__).
        """
        adapter = _BridgeClientAdapter(self)
        self._bridge_client = adapter
        self._tasks = TaskRepository(adapter)
        self._steps = StepRepository(adapter)
        self._messages = MessageRepository(adapter)
        self._agents = AgentRepository(adapter)
        self._boards = BoardRepository(adapter)
        self._chats = ChatRepository(adapter)
        self._subscriptions = SubscriptionManager(adapter)

    def _ensure_repos(self) -> None:
        """Ensure repositories are initialized (handles object.__new__ case).

        When ConvexBridge is created via object.__new__() (bypassing __init__),
        repositories need to be lazily initialized. This supports:
        - Normal construction via __init__ (repos already initialized)
        - object.__new__ with _client set manually (test pattern)
        - object.__new__ with mutation/query set as MagicMock (test pattern)
        """
        if not hasattr(self, "_bridge_client"):
            self._init_repositories()

    # ── Core client methods ──────────────────────────────────────────

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
                logger.debug(
                    "mutation %s attempt %d args=%s", function_name, attempt, camel_args
                )
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

    # ── Task methods (delegated to TaskRepository) ───────────────────

    def update_task_status(
        self,
        task_id: str,
        status: str,
        agent_name: str | None = None,
        description: str | None = None,
        awaiting_kickoff: bool | None = None,
    ) -> Any:
        """Update a task's status with retry and logging."""
        self._ensure_repos()
        return self._tasks.update_task_status(
            task_id, status, agent_name, description, awaiting_kickoff
        )

    def update_execution_plan(self, task_id: str, plan: dict[str, Any]) -> Any:
        """Update the executionPlan field on a task document."""
        self._ensure_repos()
        return self._tasks.update_execution_plan(task_id, plan)

    def kick_off_task(self, task_id: str, step_count: int) -> Any:
        """Transition a task to the running state after materialization."""
        self._ensure_repos()
        return self._tasks.kick_off_task(task_id, step_count)

    def approve_and_kick_off(
        self, task_id: str, execution_plan: dict[str, Any] | None = None
    ) -> Any:
        """Approve plan and kick off a supervised task."""
        self._ensure_repos()
        return self._tasks.approve_and_kick_off(task_id, execution_plan)

    def create_task_directory(self, task_id: str) -> None:
        """Create the filesystem directory structure for a task."""
        self._ensure_repos()
        self._tasks.create_task_directory(task_id)

    def sync_task_output_files(
        self, task_id: str, task_data: dict, agent_name: str = "agent"
    ) -> None:
        """Scan output/ directory and sync file manifest in Convex."""
        self._ensure_repos()
        self._tasks.sync_task_output_files(task_id, task_data, agent_name)

    def sync_output_files_to_parent(
        self, source_task_id: str, parent_task_id: str, agent_name: str = "agent"
    ) -> None:
        """Sync output files from a cron-triggered task to its parent task."""
        self._ensure_repos()
        self._tasks.sync_output_files_to_parent(
            source_task_id, parent_task_id, agent_name
        )

    # ── Step methods (delegated to StepRepository) ───────────────────

    def create_step(self, step_data: dict[str, Any]) -> str:
        """Create a single step record in Convex."""
        self._ensure_repos()
        return self._steps.create_step(step_data)

    def batch_create_steps(
        self,
        task_id: str,
        steps: list[dict[str, Any]],
    ) -> list[str]:
        """Create multiple step records atomically via Convex."""
        self._ensure_repos()
        return self._steps.batch_create_steps(task_id, steps)

    def update_step_status(
        self,
        step_id: str,
        status: str,
        error_message: str | None = None,
    ) -> Any:
        """Update a step's lifecycle status via steps:updateStatus."""
        self._ensure_repos()
        return self._steps.update_step_status(step_id, status, error_message)

    def get_steps_by_task(self, task_id: str) -> list[dict[str, Any]]:
        """Fetch all steps for a task ordered by step.order."""
        self._ensure_repos()
        return self._steps.get_steps_by_task(task_id)

    def check_and_unblock_dependents(self, step_id: str) -> list[str]:
        """Unblock dependents for a completed step."""
        self._ensure_repos()
        return self._steps.check_and_unblock_dependents(step_id)

    # ── Message methods (delegated to MessageRepository) ─────────────

    def get_task_messages(self, task_id: str) -> list[dict[str, Any]]:
        """Fetch all thread messages for a task, in chronological order."""
        self._ensure_repos()
        return self._messages.get_task_messages(task_id)

    def send_message(
        self,
        task_id: str,
        author_name: str,
        author_type: str,
        content: str,
        message_type: str,
        msg_type: str | None = None,
    ) -> Any:
        """Send a task-scoped message with retry and logging."""
        self._ensure_repos()
        return self._messages.send_message(
            task_id, author_name, author_type, content, message_type, msg_type
        )

    def post_step_completion(
        self,
        task_id: str,
        step_id: str,
        agent_name: str,
        content: str,
        artifacts: list[dict[str, Any]] | None = None,
    ) -> Any:
        """Post a step-completion message to the unified task thread."""
        self._ensure_repos()
        return self._messages.post_step_completion(
            task_id, step_id, agent_name, content, artifacts
        )

    def post_lead_agent_message(
        self,
        task_id: str,
        content: str,
        msg_type: str,
    ) -> Any:
        """Post a Lead Agent plan or chat message to the unified task thread."""
        self._ensure_repos()
        return self._messages.post_lead_agent_message(task_id, content, msg_type)

    def get_recent_user_messages(self, since_timestamp: str) -> list[dict[str, Any]]:
        """Fetch all user messages created since the given ISO timestamp."""
        self._ensure_repos()
        return self._messages.get_recent_user_messages(since_timestamp)

    def post_system_error(
        self,
        task_id: str,
        content: str,
        step_id: str | None = None,
    ) -> Any:
        """Post a system error message to the task thread."""
        self._ensure_repos()
        return self._messages.post_system_error(task_id, content, step_id)

    # ── Agent methods (delegated to AgentRepository) ─────────────────

    def sync_agent(self, agent_data: Any) -> Any:
        """Upsert an agent in Convex by name."""
        self._ensure_repos()
        return self._agents.sync_agent(agent_data)

    def list_agents(self) -> list[dict[str, Any]]:
        """List all agents from Convex."""
        self._ensure_repos()
        return self._agents.list_agents()

    def get_agent_by_name(self, name: str) -> dict[str, Any] | None:
        """Fetch a single agent from Convex by name."""
        self._ensure_repos()
        return self._agents.get_agent_by_name(name)

    def list_deleted_agents(self) -> list[dict[str, Any]]:
        """List all soft-deleted agents from Convex."""
        self._ensure_repos()
        return self._agents.list_deleted_agents()

    def archive_agent_data(
        self,
        name: str,
        memory_content: str | None,
        history_content: str | None,
        session_data: str | None,
    ) -> None:
        """Archive local agent files to Convex before deleting the local folder."""
        self._ensure_repos()
        self._agents.archive_agent_data(name, memory_content, history_content, session_data)

    def get_agent_archive(self, name: str) -> dict[str, Any] | None:
        """Fetch archived memory/history/session data for an agent."""
        self._ensure_repos()
        return self._agents.get_agent_archive(name)

    def clear_agent_archive(self, name: str) -> None:
        """Clear archived memory/history/session fields from the agent's Convex document."""
        self._ensure_repos()
        self._agents.clear_agent_archive(name)

    def deactivate_agents_except(self, active_names: list[str]) -> Any:
        """Set status to 'idle' for all agents NOT in the provided list."""
        self._ensure_repos()
        return self._agents.deactivate_agents_except(active_names)

    def update_agent_status(
        self,
        agent_name: str,
        status: str,
        description: str | None = None,
    ) -> Any:
        """Update an agent's status with retry and logging."""
        self._ensure_repos()
        return self._agents.update_agent_status(agent_name, status, description)

    def write_agent_config(
        self, agent_data: dict[str, Any], agents_dir: Path
    ) -> None:
        """Write an agent's config back to local YAML."""
        self._ensure_repos()
        self._agents.write_agent_config(agent_data, agents_dir)

    # ── Board methods (delegated to BoardRepository) ─────────────────

    def get_board_by_id(self, board_id: str) -> dict[str, Any] | None:
        """Fetch a board by its Convex _id."""
        self._ensure_repos()
        return self._boards.get_board_by_id(board_id)

    def ensure_default_board(self) -> Any:
        """Ensure a default board exists in Convex."""
        self._ensure_repos()
        return self._boards.ensure_default_board()

    # ── Chat methods (delegated to ChatRepository) ───────────────────

    def get_pending_chat_messages(self) -> list[dict[str, Any]]:
        """Fetch all pending chat messages from Convex."""
        self._ensure_repos()
        return self._chats.get_pending_chat_messages()

    def send_chat_response(
        self, agent_name: str, content: str, author_name: str | None = None
    ) -> Any:
        """Send an agent response to a chat conversation."""
        self._ensure_repos()
        return self._chats.send_chat_response(agent_name, content, author_name)

    def mark_chat_processing(self, chat_id: str) -> Any:
        """Mark a chat message as processing."""
        self._ensure_repos()
        return self._chats.mark_chat_processing(chat_id)

    def mark_chat_done(self, chat_id: str) -> Any:
        """Mark a chat message as done."""
        self._ensure_repos()
        return self._chats.mark_chat_done(chat_id)

    # ── Subscription methods (delegated to SubscriptionManager) ──────

    def subscribe(
        self, function_name: str, args: dict[str, Any] | None = None
    ) -> Iterator[Any]:
        """Subscribe to a Convex query for real-time updates."""
        self._ensure_repos()
        return self._subscriptions.subscribe(function_name, args)

    def async_subscribe(
        self,
        function_name: str,
        args: dict[str, Any] | None = None,
        poll_interval: float = 2.0,
    ) -> "asyncio.Queue[Any]":
        """Subscribe to a Convex query, returning an asyncio.Queue."""
        self._ensure_repos()
        return self._subscriptions.async_subscribe(function_name, args, poll_interval)

    # ── Activity (shared infrastructure, not in a repository) ────────

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

    # ── Close ────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the Convex client connection."""
        logger.info("ConvexBridge closing connection")
        if hasattr(self._client, "close"):
            self._client.close()


class _BridgeClientAdapter:
    """Adapter that makes ConvexBridge look like BridgeClient for repositories.

    This allows repositories to use the same interface whether they are
    wired through the ConvexBridge facade or through the standalone
    BridgeClient. The adapter delegates query/mutation/subscribe calls
    back to the ConvexBridge instance.

    Also handles the case where ConvexBridge was created via object.__new__()
    in tests, where _client may not exist but query/mutation are set directly.
    """

    def __init__(self, bridge: ConvexBridge):
        self._bridge = bridge

    @property
    def raw_client(self) -> Any:
        """Access the underlying ConvexClient (if available)."""
        return getattr(self._bridge, "_client", None)

    def query(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        """Delegate to ConvexBridge.query."""
        return self._bridge.query(function_name, args)

    def mutation(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        """Delegate to ConvexBridge.mutation."""
        return self._bridge.mutation(function_name, args)

    def subscribe(
        self, function_name: str, args: dict[str, Any] | None = None
    ) -> Iterator[Any]:
        """Delegate to ConvexBridge._client.subscribe (raw iterator)."""
        client = getattr(self._bridge, "_client", None)
        if client is None:
            return
        camel_args = _convert_keys_to_camel(args) if args else {}
        for result in client.subscribe(function_name, camel_args):
            yield _convert_keys_to_snake(result)

    def close(self) -> None:
        """Delegate to ConvexBridge.close."""
        self._bridge.close()
