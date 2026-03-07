"""Runtime composition roots and public entrypoints for Mission Control."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "TaskOrchestrator": ("mc.runtime.orchestrator", "TaskOrchestrator"),
    "TimeoutChecker": ("mc.runtime.timeout_checker", "TimeoutChecker"),
    "generate_title_via_low_agent": (
        "mc.runtime.orchestrator",
        "generate_title_via_low_agent",
    ),
    "main": ("mc.runtime.gateway", "main"),
    "run_gateway": ("mc.runtime.gateway", "run_gateway"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name)
    return getattr(module, attr_name)
