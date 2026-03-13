"""Agent management context."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "AgentSyncService": ("mc.contexts.agents.sync", "AgentSyncService"),
    "AuthoringPhase": ("mc.contexts.agents.authoring_assist", "AuthoringPhase"),
    "AuthoringResponse": ("mc.contexts.agents.authoring_assist", "AuthoringResponse"),
    "SpecDraftPatch": ("mc.contexts.agents.authoring_assist", "SpecDraftPatch"),
    "generate_agent_assist_response": (
        "mc.contexts.agents.authoring_assist",
        "generate_agent_assist_response",
    ),
    "generate_squad_assist_response": (
        "mc.contexts.agents.authoring_assist",
        "generate_squad_assist_response",
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
