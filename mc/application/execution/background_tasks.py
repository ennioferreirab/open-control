"""Shared background-task tracking for execution flows.

This module is the stable API for fire-and-forget tasks spawned by the
execution runtime. It keeps compatibility with the legacy executor task
registry so existing tests and cleanup helpers continue to work.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

_background_tasks_ref: set[asyncio.Task[Any]] | None = None
_deduplicated_background_tasks: dict[str, asyncio.Task[Any]] = {}


def get_background_tasks() -> set[asyncio.Task[Any]]:
    """Return the shared background-task registry.

    The registry still aliases the legacy executor set during the
    stabilization period so old tests and code paths observe the same
    tasks while new modules depend on this stable boundary instead.
    """
    global _background_tasks_ref
    if _background_tasks_ref is None:
        from mc.contexts.execution.executor import (
            _background_tasks as legacy_background_tasks,
        )

        _background_tasks_ref = legacy_background_tasks
    return _background_tasks_ref


def track_background_task(task: asyncio.Task[Any]) -> asyncio.Task[Any]:
    """Register a task and remove it automatically when finished."""
    background_tasks = get_background_tasks()
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return task


def create_background_task(coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
    """Create and track a background task in one call."""
    return track_background_task(asyncio.create_task(coro))


def create_deduplicated_background_task(
    key: str,
    coro: Coroutine[Any, Any, Any],
) -> asyncio.Task[Any]:
    """Create one tracked background task per logical key."""
    existing = _deduplicated_background_tasks.get(key)
    if existing is not None and not existing.done():
        coro.close()
        return existing

    task = create_background_task(coro)
    _deduplicated_background_tasks[key] = task

    def _cleanup(done_task: asyncio.Task[Any]) -> None:
        current = _deduplicated_background_tasks.get(key)
        if current is done_task:
            _deduplicated_background_tasks.pop(key, None)

    task.add_done_callback(_cleanup)
    return task
