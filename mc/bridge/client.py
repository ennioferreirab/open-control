"""Raw Convex client wrapper -- connection, auth, raw query/mutation calls.

This module owns the ConvexClient instance and provides the low-level
query, mutation, and subscribe operations with key conversion.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator

from convex import ConvexClient

from mc.bridge.key_conversion import _convert_keys_to_camel, _convert_keys_to_snake
from mc.bridge.retry import mutation_with_retry

logger = logging.getLogger(__name__)


class BridgeClient:
    """Low-level Convex client wrapper with key conversion and retry."""

    def __init__(self, deployment_url: str, admin_key: str | None = None):
        """Initialize the Convex bridge client.

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

    @property
    def raw_client(self) -> ConvexClient:
        """Access the underlying ConvexClient (for subscription helpers)."""
        return self._client

    def query(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        """Call a Convex query function.

        Args:
            function_name: Convex function in colon notation (e.g., "tasks:list")
            args: Optional arguments dict (snake_case keys -- converted to camelCase)

        Returns:
            Query result with camelCase keys converted to snake_case
        """
        camel_args = _convert_keys_to_camel(args) if args else {}
        logger.debug("query %s args=%s", function_name, camel_args)
        result = self._client.query(function_name, camel_args)
        return _convert_keys_to_snake(result)

    def mutation(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        """Call a Convex mutation function with retry.

        Args:
            function_name: Convex function in colon notation (e.g., "tasks:create")
            args: Optional arguments dict (snake_case keys -- converted to camelCase)

        Returns:
            Mutation result (if any) with camelCase keys converted to snake_case
        """
        return mutation_with_retry(self._client, function_name, args)

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
        for result in self._client.subscribe(function_name, camel_args):
            yield _convert_keys_to_snake(result)

    def close(self) -> None:
        """Close the Convex client connection."""
        logger.info("ConvexBridge closing connection")
        if hasattr(self._client, "close"):
            self._client.close()
