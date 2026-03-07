"""Execution context public API."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "CCExecutorMixin": (
        "mc.contexts.execution.cc_executor",
        "CCExecutorMixin",
    ),
    "StepDispatcher": (
        "mc.contexts.execution.step_dispatcher",
        "StepDispatcher",
    ),
    "TaskExecutor": ("mc.contexts.execution.executor", "TaskExecutor"),
    "build_task_message": (
        "mc.contexts.execution.executor",
        "build_task_message",
    ),
    "execute_step_via_cc": (
        "mc.contexts.execution.cc_step_runner",
        "execute_step_via_cc",
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
