"""Key conversion utilities for camelCase <-> snake_case transformation.

Used by the Convex bridge to convert between Python snake_case conventions
and Convex/JavaScript camelCase conventions.
"""

from __future__ import annotations

import re
from typing import Any


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
