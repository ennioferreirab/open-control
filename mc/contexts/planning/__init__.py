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
    "STANDARD_TOOLS": ("mc.contexts.planning.planner", "STANDARD_TOOLS"),
    "SYSTEM_PROMPT": ("mc.contexts.planning.planner", "SYSTEM_PROMPT"),
    "TaskPlanner": ("mc.contexts.planning.planner", "TaskPlanner"),
    "USER_PROMPT_TEMPLATE": (
        "mc.contexts.planning.planner",
        "USER_PROMPT_TEMPLATE",
    ),
    "generate_title_via_low_agent": (
        "mc.contexts.planning.title_generation",
        "generate_title_via_low_agent",
    ),
    "handle_plan_negotiation": (
        "mc.contexts.planning.negotiation",
        "handle_plan_negotiation",
    ),
    "start_plan_negotiation_loop": (
        "mc.contexts.planning.negotiation",
        "start_plan_negotiation_loop",
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
