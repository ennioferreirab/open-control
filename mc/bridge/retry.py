"""Retry logic and error handling for Convex mutations.

Provides exponential backoff retry for mutation calls and best-effort
error activity logging on exhaustion.

NOTE: The retry logic in this module is intentionally duplicated in
ConvexBridge._mutation_with_retry() (mc/bridge/__init__.py) to preserve
backward compatibility with existing test patches that target
``mc.bridge.time.sleep`` and ``mc.bridge.os.makedirs``. Bug fixes to
the retry algorithm must be applied in both places until the legacy
patch surface is removed (planned for Story 19.1).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from convex import ConvexClient

from mc.bridge.key_conversion import _convert_keys_to_camel, _convert_keys_to_snake

logger = logging.getLogger(__name__)

MAX_RETRIES = 3  # Number of retries AFTER the initial attempt (4 total attempts)
BACKOFF_BASE_SECONDS = 1  # Delays: 1s, 2s, 4s


def mutation_with_retry(
    client: ConvexClient,
    function_name: str,
    args: dict[str, Any] | None = None,
) -> Any:
    """Call a Convex mutation with retry and exponential backoff.

    Retries up to MAX_RETRIES times on failure. On exhaustion, logs error
    and makes a best-effort attempt to write a system_error activity event.

    Args:
        client: The raw ConvexClient instance.
        function_name: Convex function in colon notation.
        args: Optional arguments dict (snake_case keys -- converted to camelCase).

    Raises:
        Exception: Re-raises the last exception after retry exhaustion.
    """
    camel_args = _convert_keys_to_camel(args) if args else {}
    last_exception = None
    max_attempts = MAX_RETRIES + 1  # initial attempt + retries

    for attempt in range(1, max_attempts + 1):
        try:
            logger.debug("mutation %s attempt %d args=%s", function_name, attempt, camel_args)
            result = client.mutation(function_name, camel_args)
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
    _write_error_activity(client, function_name, str(last_exception))
    raise last_exception


def _write_error_activity(client: ConvexClient, mutation_name: str, error_message: str) -> None:
    """Best-effort write of a system_error activity event to Convex.

    Called after retry exhaustion. If this write also fails,
    the error is silently logged -- no cascading exceptions.
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        client.mutation(
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
