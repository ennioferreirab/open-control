"""Convention-based handler discovery."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

from .handler import BaseHandler

_cache: list[type[BaseHandler]] | None = None


def discover_handlers() -> list[type[BaseHandler]]:
    """Auto-discover handler classes from mc/hooks/handlers/."""
    global _cache
    if _cache is not None:
        return _cache

    handlers_dir = Path(__file__).parent / "handlers"
    if not handlers_dir.is_dir():
        _cache = []
        return _cache

    result: list[type[BaseHandler]] = []
    for py_file in sorted(handlers_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        try:
            module_name = f"mc.hooks.handlers.{py_file.stem}"
            mod = importlib.import_module(module_name)
            for obj in vars(mod).values():
                if (
                    isinstance(obj, type)
                    and issubclass(obj, BaseHandler)
                    and obj is not BaseHandler
                ):
                    result.append(obj)
        except Exception:
            continue  # skip broken handler files

    _cache = result
    return _cache
