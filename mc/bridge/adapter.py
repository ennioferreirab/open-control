"""Bridge adapter shared by the ConvexBridge repositories."""

from __future__ import annotations

from typing import Any, Iterator

from mc.bridge.key_conversion import _convert_keys_to_camel, _convert_keys_to_snake


class _BridgeClientAdapter:
    """Adapter that makes ConvexBridge look like BridgeClient for repositories."""

    def __init__(self, bridge: Any):
        self._bridge = bridge

    @property
    def raw_client(self) -> Any:
        return getattr(self._bridge, "_client", None)

    def query(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        return self._bridge.query(function_name, args)

    def mutation(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        return self._bridge.mutation(function_name, args)

    def subscribe(self, function_name: str, args: dict[str, Any] | None = None) -> Iterator[Any]:
        client = getattr(self._bridge, "_client", None)
        if client is None:
            return iter(())

        def _iter() -> Iterator[Any]:
            camel_args = _convert_keys_to_camel(args) if args else {}
            for result in client.subscribe(function_name, camel_args):
                yield _convert_keys_to_snake(result)

        return _iter()

    def close(self) -> None:
        self._bridge.close()
