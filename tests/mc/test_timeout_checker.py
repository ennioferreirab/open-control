"""Unit tests for timeout detection and escalation (Story 7.2)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from mc.runtime.timeout_checker import (
    DEFAULT_INTER_AGENT_TIMEOUT_MINUTES,
    DEFAULT_TASK_TIMEOUT_MINUTES,
    TimeoutChecker,
    _format_duration,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bridge() -> MagicMock:
    """Create a mock ConvexBridge."""
    bridge = MagicMock()
    bridge.query.return_value = None
    bridge.mutation.return_value = None
    bridge.create_activity.return_value = None
    bridge.send_message.return_value = None
    return bridge


def _make_task(
    task_id: str = "task_1",
    title: str = "Test Task",
    status: str = "in_progress",
    updated_at: datetime | None = None,
    task_timeout: float | None = None,
    inter_agent_timeout: float | None = None,
    reviewers: list[str] | None = None,
) -> dict:
    """Create a mock task dict."""
    if updated_at is None:
        updated_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    return {
        "id": task_id,
        "title": title,
        "status": status,
        "updated_at": updated_at.isoformat(),
        "task_timeout": task_timeout,
        "inter_agent_timeout": inter_agent_timeout,
        "reviewers": reviewers,
    }


# ---------------------------------------------------------------------------
# Test: _format_duration
# ---------------------------------------------------------------------------

class TestFormatDuration:
    def test_minutes_only(self) -> None:
        assert _format_duration(timedelta(minutes=15)) == "15m"

    def test_hours_and_minutes(self) -> None:
        assert _format_duration(timedelta(hours=2, minutes=30)) == "2h 30m"

    def test_zero(self) -> None:
        assert _format_duration(timedelta(0)) == "0m"

    def test_exactly_one_hour(self) -> None:
        assert _format_duration(timedelta(hours=1)) == "1h 0m"


# ---------------------------------------------------------------------------
# Test: Stalled task detection
# ---------------------------------------------------------------------------

class TestStalledTaskDetection:
    """AC #1: Flag tasks in 'in_progress' that exceed the timeout."""

    @pytest.mark.asyncio
    async def test_flags_stalled_task(self) -> None:
        """A task exceeding the default timeout gets flagged."""
        bridge = _make_bridge()
        checker = TimeoutChecker(bridge)

        stalled_task = _make_task(
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=35),
        )

        # No settings configured (use defaults)
        bridge.query.side_effect = lambda fn, args=None: {
            "settings:get": None,
            "tasks:listByStatus": [stalled_task] if args and args.get("status") == "in_progress" else [],
        }.get(fn, None)

        await checker.check_timeouts()

        # Verify activity event was created
        bridge.create_activity.assert_called_once()
        call_args = bridge.create_activity.call_args
        assert call_args[0][0] == "system_error"
        assert "stalled" in call_args[0][1].lower()
        assert "Test Task" in call_args[0][1]

        # Verify system message was sent to thread
        bridge.send_message.assert_called_once()
        msg_args = bridge.send_message.call_args
        assert msg_args[0][0] == "task_1"  # task_id
        assert "stalled" in msg_args[0][3].lower()

        # Verify markStalled mutation was called
        bridge.mutation.assert_called_once()
        mut_args = bridge.mutation.call_args
        assert mut_args[0][0] == "tasks:markStalled"

    @pytest.mark.asyncio
    async def test_does_not_flag_fresh_task(self) -> None:
        """A task within the timeout should not be flagged."""
        bridge = _make_bridge()
        checker = TimeoutChecker(bridge)

        fresh_task = _make_task(
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )

        bridge.query.side_effect = lambda fn, args=None: {
            "settings:get": None,
            "tasks:listByStatus": [fresh_task] if args and args.get("status") == "in_progress" else [],
        }.get(fn, None)

        await checker.check_timeouts()

        bridge.create_activity.assert_not_called()
        bridge.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_duplicate_alerts(self) -> None:
        """AC #9 (6.4): Already-flagged tasks should not be alerted again."""
        bridge = _make_bridge()
        checker = TimeoutChecker(bridge)

        stalled_task = _make_task(
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=45),
        )

        bridge.query.side_effect = lambda fn, args=None: {
            "settings:get": None,
            "tasks:listByStatus": [stalled_task] if args and args.get("status") == "in_progress" else [],
        }.get(fn, None)

        # First check — should flag
        await checker.check_timeouts()
        assert bridge.create_activity.call_count == 1

        # Second check — should NOT flag again
        await checker.check_timeouts()
        assert bridge.create_activity.call_count == 1  # Still 1


# ---------------------------------------------------------------------------
# Test: Per-task timeout override
# ---------------------------------------------------------------------------

class TestPerTaskTimeoutOverride:
    """AC #6: Per-task timeout overrides global default."""

    @pytest.mark.asyncio
    async def test_per_task_timeout_respected(self) -> None:
        """A task with a custom timeout of 60 min should not be flagged at 35 min."""
        bridge = _make_bridge()
        checker = TimeoutChecker(bridge)

        # 35 min elapsed, but per-task timeout is 60 min
        task = _make_task(
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=35),
            task_timeout=60,
        )

        bridge.query.side_effect = lambda fn, args=None: {
            "settings:get": None,
            "tasks:listByStatus": [task] if args and args.get("status") == "in_progress" else [],
        }.get(fn, None)

        await checker.check_timeouts()

        bridge.create_activity.assert_not_called()

    @pytest.mark.asyncio
    async def test_per_task_timeout_triggers_when_exceeded(self) -> None:
        """A task with a custom timeout of 10 min should be flagged at 15 min."""
        bridge = _make_bridge()
        checker = TimeoutChecker(bridge)

        task = _make_task(
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=15),
            task_timeout=10,
        )

        bridge.query.side_effect = lambda fn, args=None: {
            "settings:get": None,
            "tasks:listByStatus": [task] if args and args.get("status") == "in_progress" else [],
        }.get(fn, None)

        await checker.check_timeouts()

        bridge.create_activity.assert_called_once()


# ---------------------------------------------------------------------------
# Test: Global settings from Convex
# ---------------------------------------------------------------------------

class TestGlobalSettings:
    """AC #5, #8: Timeout values read from settings table."""

    @pytest.mark.asyncio
    async def test_uses_global_setting(self) -> None:
        """When global setting is 20 min, task at 25 min should be flagged."""
        bridge = _make_bridge()
        checker = TimeoutChecker(bridge)

        task = _make_task(
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=25),
        )

        def mock_query(fn, args=None):
            if fn == "settings:get":
                key = args.get("key") if args else None
                if key == "task_timeout_minutes":
                    return "20"
                if key == "inter_agent_timeout_minutes":
                    return "10"
            if fn == "tasks:listByStatus":
                if args and args.get("status") == "in_progress":
                    return [task]
                return []
            return None

        bridge.query.side_effect = mock_query

        await checker.check_timeouts()

        bridge.create_activity.assert_called_once()

    @pytest.mark.asyncio
    async def test_defaults_when_no_settings(self) -> None:
        """AC #5: When no settings exist, use hardcoded defaults (30 min)."""
        bridge = _make_bridge()
        checker = TimeoutChecker(bridge)

        # 25 min — less than default 30 min
        task = _make_task(
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=25),
        )

        bridge.query.side_effect = lambda fn, args=None: {
            "settings:get": None,
            "tasks:listByStatus": [task] if args and args.get("status") == "in_progress" else [],
        }.get(fn, None)

        await checker.check_timeouts()

        # Should NOT flag — 25 min < 30 min default
        bridge.create_activity.assert_not_called()


# ---------------------------------------------------------------------------
# Test: Review escalation
# ---------------------------------------------------------------------------

class TestReviewEscalation:
    """AC #3, #4: Review requests exceeding inter-agent timeout are escalated."""

    @pytest.mark.asyncio
    async def test_escalates_timed_out_review(self) -> None:
        """A review task with reviewers exceeding the timeout gets escalated."""
        bridge = _make_bridge()
        checker = TimeoutChecker(bridge)

        review_task = _make_task(
            task_id="review_1",
            title="Review Task",
            status="review",
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=15),
            reviewers=["reviewer-agent"],
        )

        bridge.query.side_effect = lambda fn, args=None: {
            "settings:get": None,
            "tasks:listByStatus": (
                [review_task] if args and args.get("status") == "review" else []
            ),
        }.get(fn, None)

        await checker.check_timeouts()

        # Activity event for escalation
        bridge.create_activity.assert_called_once()
        call_args = bridge.create_activity.call_args
        assert call_args[0][0] == "system_error"
        assert "timed out" in call_args[0][1].lower()
        assert "escalating" in call_args[0][1].lower()

        # Thread message
        bridge.send_message.assert_called_once()
        msg_args = bridge.send_message.call_args
        assert msg_args[0][0] == "review_1"
        assert "escalating" in msg_args[0][3].lower()

    @pytest.mark.asyncio
    async def test_no_escalation_for_review_without_reviewers(self) -> None:
        """A review task without reviewers should not be escalated."""
        bridge = _make_bridge()
        checker = TimeoutChecker(bridge)

        review_task = _make_task(
            task_id="review_2",
            status="review",
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=15),
            reviewers=None,
        )

        bridge.query.side_effect = lambda fn, args=None: {
            "settings:get": None,
            "tasks:listByStatus": (
                [review_task] if args and args.get("status") == "review" else []
            ),
        }.get(fn, None)

        await checker.check_timeouts()

        bridge.create_activity.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_duplicate_escalation(self) -> None:
        """Already-escalated reviews should not be escalated again."""
        bridge = _make_bridge()
        checker = TimeoutChecker(bridge)

        review_task = _make_task(
            task_id="review_3",
            title="Review Dup",
            status="review",
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            reviewers=["agent-a"],
        )

        bridge.query.side_effect = lambda fn, args=None: {
            "settings:get": None,
            "tasks:listByStatus": (
                [review_task] if args and args.get("status") == "review" else []
            ),
        }.get(fn, None)

        await checker.check_timeouts()
        assert bridge.create_activity.call_count == 1

        await checker.check_timeouts()
        assert bridge.create_activity.call_count == 1  # Still 1

    @pytest.mark.asyncio
    async def test_per_task_inter_agent_timeout_override(self) -> None:
        """Per-task inter_agent_timeout overrides global default."""
        bridge = _make_bridge()
        checker = TimeoutChecker(bridge)

        # 8 min elapsed, per-task override is 20 min — should NOT escalate
        review_task = _make_task(
            task_id="review_4",
            status="review",
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=8),
            reviewers=["agent-a"],
            inter_agent_timeout=20,
        )

        bridge.query.side_effect = lambda fn, args=None: {
            "settings:get": None,
            "tasks:listByStatus": (
                [review_task] if args and args.get("status") == "review" else []
            ),
        }.get(fn, None)

        await checker.check_timeouts()

        bridge.create_activity.assert_not_called()


# ---------------------------------------------------------------------------
# Test: start() loop behavior
# ---------------------------------------------------------------------------

class TestStartLoop:
    """AC #7: Timeout checking runs as a periodic check."""

    @pytest.mark.asyncio
    async def test_start_runs_check_and_sleeps(self) -> None:
        """The start() method runs check_timeouts then sleeps."""
        bridge = _make_bridge()
        checker = TimeoutChecker(bridge)

        call_count = 0

        async def mock_check():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError()

        checker.check_timeouts = mock_check  # type: ignore[assignment]

        with patch("mc.runtime.timeout_checker.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(asyncio.CancelledError):
                await checker.start()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_start_continues_on_exception(self) -> None:
        """The start() method catches exceptions and continues."""
        bridge = _make_bridge()
        checker = TimeoutChecker(bridge)

        call_count = 0

        async def mock_check():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient error")
            if call_count >= 3:
                raise asyncio.CancelledError()

        checker.check_timeouts = mock_check  # type: ignore[assignment]

        with patch("mc.runtime.timeout_checker.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(asyncio.CancelledError):
                await checker.start()

        assert call_count == 3  # Continued past the error
