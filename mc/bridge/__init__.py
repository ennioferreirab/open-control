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

import logging
import os  # noqa: F401 -- re-exported for patch compatibility
import re  # noqa: F401 -- re-exported for patch compatibility
import time
from datetime import UTC, datetime, timezone  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Any

from convex import ConvexClient

from mc.bridge.adapter import _BridgeClientAdapter
from mc.bridge.facade_mixins import BridgeRepositoryFacadeMixin
from mc.bridge.idempotency import ensure_idempotency_key
from mc.bridge.key_conversion import (  # noqa: F401
    _convert_keys_to_camel,
    _convert_keys_to_snake,
    _to_camel_case,
    _to_snake_case,
)
from mc.bridge.repositories.agents import AgentRepository
from mc.bridge.repositories.boards import BoardRepository
from mc.bridge.repositories.chats import ChatRepository
from mc.bridge.repositories.messages import MessageRepository
from mc.bridge.repositories.settings import SettingsRepository
from mc.bridge.repositories.specs import SpecsRepository
from mc.bridge.repositories.steps import StepRepository
from mc.bridge.repositories.tasks import TaskRepository
from mc.bridge.retry import (
    BACKOFF_BASE_SECONDS,
    MAX_RETRIES,
)
from mc.bridge.subscriptions import SubscriptionManager
from mc.types import task_safe_id  # noqa: F401

logger = logging.getLogger(__name__)


class ConvexBridge(BridgeRepositoryFacadeMixin):
    """Bridge between nanobot Python runtime and Convex backend."""

    def __init__(self, deployment_url: str, admin_key: str | None = None):
        self._client = ConvexClient(deployment_url)
        if admin_key:
            self._client.set_admin_auth(admin_key)
        else:
            logger.warning(
                "ConvexBridge initialized WITHOUT admin key — "
                "internal mutations will fail. Set CONVEX_ADMIN_KEY."
            )
        logger.info("ConvexBridge connected to %s", deployment_url)
        self._init_repositories()

    def _init_repositories(self) -> None:
        """Initialize all repository sub-modules."""
        adapter = _BridgeClientAdapter(self)
        self._bridge_client = adapter
        self._tasks = TaskRepository(adapter)
        self._steps = StepRepository(adapter)
        self._messages = MessageRepository(adapter)
        self._agents = AgentRepository(adapter)
        self._boards = BoardRepository(adapter)
        self._chats = ChatRepository(adapter)
        self._settings = SettingsRepository(adapter)
        self._specs = SpecsRepository(adapter)
        self._subscriptions = SubscriptionManager(adapter)

    def _ensure_repos(self) -> None:
        """Ensure repositories exist for object.__new__ test instances."""
        if not hasattr(self, "_bridge_client"):
            self._init_repositories()

    def query(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        camel_args = _convert_keys_to_camel(args) if args else {}
        logger.debug("query %s args=%s", function_name, camel_args)
        result = self._client.query(function_name, camel_args)
        return _convert_keys_to_snake(result)

    def mutation(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        return self._mutation_with_retry(function_name, args)

    def _mutation_with_retry(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        camel_args = _convert_keys_to_camel(args) if args else {}
        camel_args = ensure_idempotency_key(function_name, camel_args)
        last_exception = None
        max_attempts = MAX_RETRIES + 1

        for attempt in range(1, max_attempts + 1):
            try:
                logger.debug("mutation %s attempt %d args=%s", function_name, attempt, camel_args)
                result = self._client.mutation(function_name, camel_args)
                if attempt > 1:
                    logger.info(
                        "Mutation %s succeeded on attempt %d/%d",
                        function_name,
                        attempt,
                        max_attempts,
                    )
                return _convert_keys_to_snake(result) if result else result
            except Exception as e:
                last_exception = e
                if attempt < max_attempts:
                    delay = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        "Mutation %s failed (attempt %d/%d), retrying in %ds: %s",
                        function_name,
                        attempt,
                        max_attempts,
                        delay,
                        e,
                    )
                    time.sleep(delay)

        logger.error(
            "Mutation %s failed after %d attempts. Args: %s. Error: %s",
            function_name,
            max_attempts,
            camel_args,
            last_exception,
        )
        self._write_error_activity(function_name, str(last_exception))
        assert last_exception is not None
        raise last_exception

    def _write_error_activity(self, mutation_name: str, error_message: str) -> None:
        try:
            timestamp = datetime.now(UTC).isoformat()
            self._client.mutation(
                "activities:create",
                {
                    "eventType": "system_error",
                    "description": (
                        f"Mutation {mutation_name} failed after {MAX_RETRIES + 1} "
                        f"attempts ({MAX_RETRIES} retries): {error_message}"
                    ),
                    "timestamp": timestamp,
                },
            )
        except Exception as e:
            logger.error("Failed to write error activity event (best-effort): %s", e)

    def _log_state_transition(self, entity_type: str, description: str) -> None:
        timestamp = datetime.now(UTC).isoformat()
        logger.info("[MC] %s %s: %s", timestamp, entity_type, description)

    def close(self) -> None:
        logger.info("ConvexBridge closing connection")
        close_fn = getattr(self._client, "close", None)
        if close_fn is not None:
            close_fn()
