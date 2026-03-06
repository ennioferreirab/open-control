"""Subscription and polling logic for Convex real-time updates.

Provides both blocking iterator-based subscriptions and async polling
via asyncio.Queue.
"""

from __future__ import annotations

import asyncio  # noqa: F811 -- used in type annotation and runtime
import logging
from typing import TYPE_CHECKING, Any, Iterator

from mc.bridge.key_conversion import _convert_keys_to_camel, _convert_keys_to_snake

if TYPE_CHECKING:
    from mc.bridge.client import BridgeClient

logger = logging.getLogger(__name__)


class SubscriptionManager:
    """Manages Convex subscriptions and async polling."""

    def __init__(self, client: "BridgeClient"):
        self._client = client

    def subscribe(
        self, function_name: str, args: dict[str, Any] | None = None
    ) -> Iterator[Any]:
        """Subscribe to a Convex query for real-time updates.

        Args:
            function_name: Convex query in colon notation (e.g., "tasks:list")
            args: Optional arguments dict (snake_case keys -- converted to camelCase)

        Yields:
            Updated results with camelCase keys converted to snake_case
        """
        camel_args = _convert_keys_to_camel(args) if args else {}
        logger.debug("subscribe %s args=%s", function_name, camel_args)
        for result in self._client.raw_client.subscribe(function_name, camel_args):
            yield _convert_keys_to_snake(result)

    def async_subscribe(
        self,
        function_name: str,
        args: dict[str, Any] | None = None,
        poll_interval: float = 2.0,
    ) -> "asyncio.Queue[Any]":
        """Subscribe to a Convex query, returning an asyncio.Queue.

        Uses a polling strategy: periodically queries Convex and pushes
        results into an asyncio.Queue when data changes.  This avoids
        the thread-safety issues with the Convex Python SDK's blocking
        subscription iterator and ``call_soon_threadsafe``.

        Args:
            function_name: Convex query in colon notation.
            args: Optional arguments dict (snake_case keys).
            poll_interval: Seconds between polls. Defaults to 2.0.

        Returns:
            An asyncio.Queue that yields query results on each change.
        """
        import asyncio

        queue: asyncio.Queue[Any] = asyncio.Queue()

        async def _poll() -> None:
            last_result: Any = None
            consecutive_errors = 0
            max_errors = 10
            while True:
                try:
                    result = await asyncio.to_thread(
                        self._client.query, function_name, args
                    )
                    consecutive_errors = 0
                    if result != last_result:
                        queue.put_nowait(result)
                        last_result = result
                except Exception as exc:
                    consecutive_errors += 1
                    if consecutive_errors >= max_errors:
                        logger.error(
                            "Poll %s failed %d times consecutively: %s",
                            function_name, max_errors, exc,
                        )
                        queue.put_nowait(
                            {"_error": True, "message": str(exc)}
                        )
                        return
                    logger.warning(
                        "Poll %s error (attempt %d/%d): %s",
                        function_name, consecutive_errors, max_errors, exc,
                    )
                await asyncio.sleep(poll_interval)

        asyncio.get_running_loop().create_task(_poll())
        return queue
