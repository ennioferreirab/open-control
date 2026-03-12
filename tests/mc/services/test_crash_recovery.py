"""Tests for CrashRecoveryService — Story 17.2, Task 3."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mc.contexts.execution.crash_recovery import MAX_AUTO_RETRIES, CrashRecoveryService


@pytest.fixture
def bridge() -> MagicMock:
    """Create a mock ConvexBridge."""
    b = MagicMock()
    b.update_task_status = MagicMock()
    b.send_message = MagicMock()
    return b


@pytest.fixture
def service(bridge: MagicMock) -> CrashRecoveryService:
    """Create a CrashRecoveryService instance."""
    return CrashRecoveryService(bridge=bridge)


class TestCrashRecoveryInit:
    """Verify constructor."""

    def test_stores_bridge(self, bridge: MagicMock) -> None:
        svc = CrashRecoveryService(bridge=bridge)
        assert svc._bridge is bridge

    def test_retry_counts_empty_initially(self, service: CrashRecoveryService) -> None:
        assert service.get_retry_count("any-task") == 0


class TestHandleAgentCrash:
    """Test handle_agent_crash — retry and crash semantics."""

    @pytest.mark.asyncio
    async def test_first_crash_retries(
        self, service: CrashRecoveryService, bridge: MagicMock
    ) -> None:
        """First crash triggers auto-retry (retrying -> in_progress)."""
        error = RuntimeError("Agent crashed")
        await service.handle_agent_crash("test-agent", "task-1", error)

        # Should transition to retrying, then to in_progress
        assert bridge.update_task_status.call_count == 2
        first_call = bridge.update_task_status.call_args_list[0]
        assert first_call[0][1] == "retrying"  # first transition

        second_call = bridge.update_task_status.call_args_list[1]
        assert second_call[0][1] == "in_progress"  # re-dispatch

    @pytest.mark.asyncio
    async def test_first_crash_posts_error_message(
        self, service: CrashRecoveryService, bridge: MagicMock
    ) -> None:
        """First crash posts an error message to the task thread."""
        error = ValueError("Bad input")
        await service.handle_agent_crash("test-agent", "task-1", error)

        bridge.send_message.assert_called_once()
        msg_content = bridge.send_message.call_args[0][3]
        assert "ValueError: Bad input" in msg_content
        assert "Auto-retrying" in msg_content

    @pytest.mark.asyncio
    async def test_second_crash_marks_as_crashed(
        self, service: CrashRecoveryService, bridge: MagicMock
    ) -> None:
        """Second crash (retry exhausted) transitions to crashed."""
        error = RuntimeError("Crash again")

        # First crash — retries
        await service.handle_agent_crash("test-agent", "task-1", error)
        bridge.reset_mock()

        # Second crash — should mark as crashed
        await service.handle_agent_crash("test-agent", "task-1", error)
        first_call = bridge.update_task_status.call_args_list[0]
        assert first_call[0][1] == "crashed"

    @pytest.mark.asyncio
    async def test_second_crash_posts_retry_failed_message(
        self, service: CrashRecoveryService, bridge: MagicMock
    ) -> None:
        """Second crash posts 'Retry failed' message."""
        error = RuntimeError("boom")
        await service.handle_agent_crash("agent", "task-1", error)
        bridge.reset_mock()

        await service.handle_agent_crash("agent", "task-1", error)
        msg_content = bridge.send_message.call_args[0][3]
        assert "Retry failed" in msg_content

    @pytest.mark.asyncio
    async def test_retry_count_increments(
        self, service: CrashRecoveryService, bridge: MagicMock
    ) -> None:
        """Retry count is tracked correctly."""
        error = RuntimeError("crash")
        assert service.get_retry_count("task-1") == 0

        await service.handle_agent_crash("agent", "task-1", error)
        assert service.get_retry_count("task-1") == 1

    @pytest.mark.asyncio
    async def test_retry_count_cleared_after_exhaust(
        self, service: CrashRecoveryService, bridge: MagicMock
    ) -> None:
        """Retry count is cleared after retry exhaustion (crashed)."""
        error = RuntimeError("crash")
        await service.handle_agent_crash("agent", "task-1", error)
        await service.handle_agent_crash("agent", "task-1", error)
        assert service.get_retry_count("task-1") == 0


class TestClearRetryCount:
    """Test clear_retry_count."""

    @pytest.mark.asyncio
    async def test_clears_existing_count(
        self, service: CrashRecoveryService, bridge: MagicMock
    ) -> None:
        error = RuntimeError("x")
        await service.handle_agent_crash("a", "task-1", error)
        assert service.get_retry_count("task-1") == 1

        service.clear_retry_count("task-1")
        assert service.get_retry_count("task-1") == 0

    def test_clears_nonexistent_count_safely(
        self, service: CrashRecoveryService
    ) -> None:
        """Clearing a count for a task that has no entry does not raise."""
        service.clear_retry_count("nonexistent")  # Should not raise


class TestMaxAutoRetries:
    """Verify the MAX_AUTO_RETRIES constant matches the original gateway.py value."""

    def test_max_auto_retries_is_one(self) -> None:
        """FR37 specifies a single auto-retry."""
        assert MAX_AUTO_RETRIES == 1
