"""Review context public API."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["ReviewHandler"]


def __getattr__(name: str) -> Any:
    if name != "ReviewHandler":
        raise AttributeError(name)
    module = import_module("mc.contexts.review.handler")
    return getattr(module, name)
