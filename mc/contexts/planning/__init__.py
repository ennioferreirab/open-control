"""Planning context public API."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "AUTO_TITLE_PROMPT": (
        "mc.contexts.planning.title_generation",
        "AUTO_TITLE_PROMPT",
    ),
    "PlanMaterializer": (
        "mc.contexts.planning.materializer",
        "PlanMaterializer",
    ),
    "generate_title_via_low_agent": (
        "mc.contexts.planning.title_generation",
        "generate_title_via_low_agent",
    ),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name)
    return getattr(module, attr_name)
