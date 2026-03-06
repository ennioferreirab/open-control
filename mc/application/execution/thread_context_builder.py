"""Unified thread context assembly.

Wraps the existing mc.thread_context.ThreadContextBuilder to provide
a shared interface for both task and step context building. Mention
context and assigned-agent context share the same builder.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_thread_context(
    messages: list[dict[str, Any]],
    *,
    max_messages: int = 20,
    predecessor_step_ids: list[str] | None = None,
) -> str:
    """Build thread context string using the shared ThreadContextBuilder.

    Delegates to mc.thread_context.ThreadContextBuilder.build(), which
    handles both legacy (task) and step-aware (with predecessors) modes.

    This is the single entry point for all thread context assembly --
    tasks, steps, mentions, and CC execution all use this function.

    Args:
        messages: Thread messages in chronological order (snake_case keys).
        max_messages: Truncation window size (default 20).
        predecessor_step_ids: Step IDs of direct blockedBy predecessors.
            When provided, their completion messages are always included.

    Returns:
        Formatted context string, or "" if no relevant context.
    """
    from mc.thread_context import ThreadContextBuilder

    return ThreadContextBuilder().build(
        messages,
        max_messages=max_messages,
        predecessor_step_ids=predecessor_step_ids,
    )
