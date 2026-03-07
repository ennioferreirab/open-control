"""Tests for mention_handler orientation fix (CC-12)."""
from __future__ import annotations

import inspect

import pytest


@pytest.mark.asyncio
async def test_mention_handler_no_import_error():
    """The mention handler should not raise ImportError for _maybe_inject_orientation."""
    # This test verifies the bug fix: mention_handler no longer imports
    # _maybe_inject_orientation from mc.contexts.execution.executor (it was an instance method).
    # After the fix, it uses mc.infrastructure.orientation.load_orientation instead.

    # Simply importing the module should not error
    import mc.mentions.handler

    # The module should use load_orientation, not _maybe_inject_orientation
    source = inspect.getsource(mc.mentions.handler)
    assert "_maybe_inject_orientation" not in source, \
        "mention_handler should not reference _maybe_inject_orientation"
    assert "load_orientation" in source, \
        "mention_handler should use load_orientation from mc.infrastructure.orientation"
