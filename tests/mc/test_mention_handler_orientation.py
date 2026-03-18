"""Tests for mention_handler orientation fix (CC-12)."""

from __future__ import annotations

import inspect

import pytest


@pytest.mark.asyncio
async def test_mention_handler_no_import_error():
    """The mention handler should not raise ImportError for _maybe_inject_orientation."""
    # This test verifies the bug fix: mention_handler no longer imports
    # _maybe_inject_orientation from mc.contexts.execution.executor (it was an instance method).
    # After the refactor, orientation injection is handled by ContextBuilder.

    # Simply importing the module should not error
    import mc.contexts.conversation.mentions.handler

    # The module should not reference the old broken import
    source = inspect.getsource(mc.contexts.conversation.mentions.handler)
    assert "_maybe_inject_orientation" not in source, (
        "mention_handler should not reference _maybe_inject_orientation"
    )
