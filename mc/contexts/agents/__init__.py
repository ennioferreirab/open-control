"""Agent management context."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "AgentSyncService": ("mc.contexts.agents.sync", "AgentSyncService"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name)
    return getattr(module, attr_name)
