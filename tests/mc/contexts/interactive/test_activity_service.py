"""Tests for SessionActivityService event buffer and flush logic."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from mc.contexts.interactive.activity_service import (
    BATCH_SIZE_THRESHOLD,
    SessionActivityService,
)


def _make_service() -> tuple[SessionActivityService, MagicMock]:
    """Create a service with a mock bridge."""
    bridge = MagicMock()
    service = SessionActivityService(bridge=bridge)
    return service, bridge


class TestEventBuffer:
    """Verify buffer and flush behavior."""

    def test_events_are_buffered_not_sent_immediately(self) -> None:
        """A single append_event should buffer, not call mutation."""
        service, bridge = _make_service()
        # Reset flush timer to future so time threshold doesn't trigger
        service._last_flush_time = time.monotonic() + 100

        service.append_event(
            "session-1",
            kind="tool_use",
            agent_name="agent",
            provider="provider",
        )

        # No mutation called yet (event is buffered)
        bridge.mutation.assert_not_called()
        assert len(service._event_buffer) == 1

    def test_flush_sends_single_event_directly(self) -> None:
        """Explicit flush of a single event uses the singular append mutation."""
        service, bridge = _make_service()
        service._last_flush_time = time.monotonic() + 100

        service.append_event(
            "session-1",
            kind="tool_use",
            agent_name="agent",
            provider="provider",
        )
        service.flush()

        bridge.mutation.assert_called_once()
        call_args = bridge.mutation.call_args
        assert call_args[0][0] == "sessionActivityLog:append"
        assert len(service._event_buffer) == 0

    def test_flush_sends_batch_for_multiple_events(self) -> None:
        """Explicit flush of multiple events uses the batch mutation."""
        service, bridge = _make_service()
        service._last_flush_time = time.monotonic() + 100

        for i in range(5):
            service.append_event(
                "session-1",
                kind=f"event-{i}",
                agent_name="agent",
                provider="provider",
            )

        service.flush()

        bridge.mutation.assert_called_once()
        call_args = bridge.mutation.call_args
        assert call_args[0][0] == "sessionActivityLog:appendBatch"
        events = call_args[0][1]["events"]
        assert len(events) == 5
        assert len(service._event_buffer) == 0

    def test_auto_flush_at_batch_size_threshold(self) -> None:
        """Buffer auto-flushes when reaching BATCH_SIZE_THRESHOLD."""
        service, bridge = _make_service()

        for i in range(BATCH_SIZE_THRESHOLD):
            service.append_event(
                "session-1",
                kind=f"event-{i}",
                agent_name="agent",
                provider="provider",
            )

        # Should have auto-flushed
        assert bridge.mutation.call_count == 1
        assert len(service._event_buffer) == 0

    def test_time_based_flush(self) -> None:
        """Buffer flushes when time threshold is exceeded on next append."""
        service, bridge = _make_service()
        # Set last flush time to the past
        service._last_flush_time = time.monotonic() - 1.0

        service.append_event(
            "session-1",
            kind="event-1",
            agent_name="agent",
            provider="provider",
        )

        # Should have auto-flushed due to time threshold
        assert bridge.mutation.call_count == 1
        assert len(service._event_buffer) == 0

    def test_flush_noop_when_empty(self) -> None:
        """Flush does nothing when buffer is empty."""
        service, bridge = _make_service()
        service.flush()
        bridge.mutation.assert_not_called()

    def test_append_result_triggers_flush(self) -> None:
        """append_result flushes remaining buffered events."""
        service, bridge = _make_service()
        service._last_flush_time = time.monotonic() + 100

        # Buffer some events
        service.append_event(
            "session-1",
            kind="tool_use",
            agent_name="agent",
            provider="provider",
        )

        # append_result should cause a flush
        service.append_result(
            "session-1",
            agent_name="agent",
            provider="provider",
            success=True,
            content="Done",
        )

        # Both events should be flushed (the tool_use + the result)
        assert bridge.mutation.call_count >= 1
        assert len(service._event_buffer) == 0

    def test_upsert_session_ended_triggers_flush(self) -> None:
        """upsert_session with ended status flushes buffered events."""
        service, _bridge = _make_service()
        service._last_flush_time = time.monotonic() + 100

        # Buffer an event
        service.append_event(
            "session-1",
            kind="tool_use",
            agent_name="agent",
            provider="provider",
        )

        # End the session
        service.upsert_session(
            "session-1",
            agent_name="agent",
            provider="provider",
            surface="tmux",
            task_id="task-1",
            status="ended",
        )

        # Buffer should be flushed
        assert len(service._event_buffer) == 0

    def test_no_bridge_skips_flush(self) -> None:
        """Service without a bridge does not error on flush."""
        service = SessionActivityService(bridge=None)
        service.append_event(
            "session-1",
            kind="event",
            agent_name="agent",
            provider="provider",
        )
        # Should not raise
        service.flush()
