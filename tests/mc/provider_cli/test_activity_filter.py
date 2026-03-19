"""Tests for the unified provider CLI activity filter."""

from __future__ import annotations

import pytest

from mc.contexts.provider_cli.activity_filter import should_suppress_activity_event
from mc.contexts.provider_cli.types import ParsedCliEvent

# ---------------------------------------------------------------------------
# Claude Code noise subtypes — should be suppressed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "subtype",
    ["task_progress", "task_started", "task_notification"],
)
def test_suppresses_claude_code_noise_subtypes(subtype: str) -> None:
    event = ParsedCliEvent(
        kind="system_event",
        text=subtype,
        metadata={
            "source_type": "system",
            "source_subtype": subtype,
        },
    )
    assert should_suppress_activity_event(event) is True


def test_suppresses_via_subtype_key_fallback() -> None:
    """The filter checks 'subtype' when 'source_subtype' is absent."""
    event = ParsedCliEvent(
        kind="system_event",
        text="task_progress",
        metadata={
            "source_type": "system",
            "subtype": "task_progress",
        },
    )
    assert should_suppress_activity_event(event) is True


# ---------------------------------------------------------------------------
# Events that must NOT be suppressed
# ---------------------------------------------------------------------------


def test_allows_hook_started_system_event() -> None:
    event = ParsedCliEvent(
        kind="system_event",
        text="SessionStart:startup",
        metadata={
            "source_type": "system",
            "source_subtype": "hook_started",
        },
    )
    assert should_suppress_activity_event(event) is False


def test_allows_hook_response_system_event() -> None:
    event = ParsedCliEvent(
        kind="system_event",
        text="SessionStart:startup",
        metadata={
            "source_type": "system",
            "source_subtype": "hook_response",
        },
    )
    assert should_suppress_activity_event(event) is False


def test_allows_init_system_event() -> None:
    event = ParsedCliEvent(
        kind="session_id",
        text="abc-123",
        metadata={
            "source_type": "system",
            "source_subtype": "init",
        },
    )
    assert should_suppress_activity_event(event) is False


def test_allows_tool_use_events() -> None:
    event = ParsedCliEvent(
        kind="tool_use",
        text="Read",
        metadata={
            "source_type": "tool_use",
            "tool_name": "Read",
        },
    )
    assert should_suppress_activity_event(event) is False


def test_allows_text_events() -> None:
    event = ParsedCliEvent(
        kind="text",
        text="Hello, I'll help you with that.",
        metadata={"source_type": "assistant"},
    )
    assert should_suppress_activity_event(event) is False


def test_allows_result_events() -> None:
    event = ParsedCliEvent(
        kind="result",
        text="Task completed successfully.",
        metadata={"source_type": "result", "source_subtype": "success"},
    )
    assert should_suppress_activity_event(event) is False


def test_allows_error_events() -> None:
    event = ParsedCliEvent(
        kind="error",
        text="Something went wrong",
        metadata={"source_type": "result", "source_subtype": "error"},
    )
    assert should_suppress_activity_event(event) is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_handles_none_metadata() -> None:
    event = ParsedCliEvent(kind="text", text="hello", metadata=None)
    assert should_suppress_activity_event(event) is False


def test_handles_empty_metadata() -> None:
    event = ParsedCliEvent(kind="system_event", text="unknown", metadata={})
    assert should_suppress_activity_event(event) is False


def test_system_source_with_unknown_subtype_passes() -> None:
    """Future system subtypes we haven't classified should pass through."""
    event = ParsedCliEvent(
        kind="system_event",
        text="some_future_subtype",
        metadata={
            "source_type": "system",
            "source_subtype": "some_future_subtype",
        },
    )
    assert should_suppress_activity_event(event) is False
