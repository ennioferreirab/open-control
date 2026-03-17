"""Subscription and polling logic for Convex real-time updates.

Provides both blocking iterator-based subscriptions and async polling
via asyncio.Queue.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from mc.bridge.key_conversion import _convert_keys_to_camel, _convert_keys_to_snake

if TYPE_CHECKING:
    from mc.bridge.client import BridgeClientProtocol

logger = logging.getLogger(__name__)


class SubscriptionManager:
    """Manages Convex subscriptions and async polling.

    Supports subscription dedup: when multiple callers subscribe to the same
    function+args, a single poll loop is shared and results are fanned out
    to all consumer queues.
    """

    def __init__(self, client: "BridgeClientProtocol"):
        self._client = client
        self._shared_polls: dict[tuple, tuple[asyncio.Task, list[asyncio.Queue]]] = {}  # type: ignore[type-arg]

    def subscribe(self, function_name: str, args: dict[str, Any] | None = None) -> Iterator[Any]:
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
        sleep_controller: Any | None = None,
    ) -> asyncio.Queue[Any]:
        """Subscribe to a Convex query, returning an asyncio.Queue.

        Uses a polling strategy: periodically queries Convex and pushes
        results into an asyncio.Queue when data changes.

        **Dedup:** When multiple callers subscribe to the same function+args,
        a single poll loop is shared. The first subscriber's poll_interval
        is used for all consumers of that key.

        Args:
            function_name: Convex query in colon notation.
            args: Optional arguments dict (snake_case keys).
            poll_interval: Seconds between polls. Defaults to 2.0.

        Returns:
            An asyncio.Queue that yields query results on each change.
        """
        import asyncio

        key = (function_name, self._freeze_args(args))
        queue: asyncio.Queue[Any] = asyncio.Queue()

        if key in self._shared_polls:
            task, consumers = self._shared_polls[key]
            if not task.done():
                consumers.append(queue)
                logger.debug(
                    "Dedup: reusing poll loop for %s (now %d consumers)",
                    function_name,
                    len(consumers),
                )
                return queue
            del self._shared_polls[key]

        consumers: list[asyncio.Queue] = [queue]  # type: ignore[no-redef]
        task = asyncio.get_running_loop().create_task(
            self._poll_loop(
                function_name,
                args,
                poll_interval,
                consumers,
                sleep_controller=sleep_controller,
            )
        )
        self._shared_polls[key] = (task, consumers)
        return queue

    async def _poll_loop(
        self,
        function_name: str,
        args: dict[str, Any] | None,
        poll_interval: float,
        consumers: list[asyncio.Queue[Any]],
        sleep_controller: Any | None = None,
    ) -> None:
        """Shared poll loop that fans out results to all consumer queues."""
        last_result: Any = None
        consecutive_errors = 0
        max_errors = 10
        while True:
            if (
                sleep_controller is not None
                and getattr(sleep_controller, "mode", "active") == "sleep"
            ):
                await sleep_controller.wait_for_next_cycle(poll_interval)
            try:
                result = await asyncio.to_thread(self._client.query, function_name, args)
                consecutive_errors = 0
                is_error = isinstance(result, dict) and result.get("_error") is True
                should_wake = (
                    not is_error
                    and bool(result)
                    and (
                        getattr(sleep_controller, "mode", "active") == "sleep"
                        or result != last_result
                    )
                )
                if sleep_controller is not None:
                    if should_wake:
                        await sleep_controller.record_work_found()
                    else:
                        await sleep_controller.record_idle()
                if result != last_result:
                    last_result = result
                    for q in consumers:
                        q.put_nowait(result)
            except Exception as exc:
                consecutive_errors += 1
                if consecutive_errors >= max_errors:
                    logger.error(
                        "Poll %s failed %d times consecutively: %s",
                        function_name,
                        max_errors,
                        exc,
                    )
                    error_msg = {"_error": True, "message": str(exc)}
                    for q in consumers:
                        q.put_nowait(error_msg)
                    return
                logger.warning(
                    "Poll %s error (attempt %d/%d): %s",
                    function_name,
                    consecutive_errors,
                    max_errors,
                    exc,
                )
            if sleep_controller is not None:
                await sleep_controller.wait_for_next_cycle(poll_interval)
            else:
                await asyncio.sleep(poll_interval)

    @staticmethod
    def _freeze_args(args: dict[str, Any] | None) -> tuple:
        """Convert args dict to a hashable key for dedup."""
        if not args:
            return ()
        return tuple(sorted(args.items()))
