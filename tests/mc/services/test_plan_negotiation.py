"""Tests for PlanNegotiationSupervisor — Story 17.2, Task 4."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.services.plan_negotiation import PlanNegotiationSupervisor


@pytest.fixture
def bridge() -> MagicMock:
    """Create a mock ConvexBridge with async_subscribe support."""
    b = MagicMock()
    b.async_subscribe = MagicMock(return_value=asyncio.Queue())
    b.query = MagicMock(return_value=None)
    return b


@pytest.fixture
def supervisor(bridge: MagicMock) -> PlanNegotiationSupervisor:
    """Create a PlanNegotiationSupervisor instance."""
    return PlanNegotiationSupervisor(bridge=bridge)


class TestPlanNegotiationSupervisorInit:
    """Verify constructor and basic attributes."""

    def test_stores_bridge(self, bridge: MagicMock) -> None:
        svc = PlanNegotiationSupervisor(bridge=bridge)
        assert svc._bridge is bridge

    def test_tracks_active_negotiations(self, supervisor: PlanNegotiationSupervisor) -> None:
        assert len(supervisor._active_negotiation_ids) == 0


class TestSpawnLoopIfNeeded:
    """Test _spawn_loop_if_needed — spawns negotiation loops for tasks."""

    @pytest.mark.asyncio
    async def test_spawns_loop_for_new_task(
        self, supervisor: PlanNegotiationSupervisor
    ) -> None:
        """Spawns a negotiation loop for a task not yet tracked."""
        with patch(
            "mc.services.plan_negotiation.start_plan_negotiation_loop",
            new_callable=AsyncMock,
        ):
            await supervisor._spawn_loop_if_needed("task-1")
            assert "task-1" in supervisor._active_negotiation_ids

    @pytest.mark.asyncio
    async def test_does_not_duplicate_loop(
        self, supervisor: PlanNegotiationSupervisor
    ) -> None:
        """Does not spawn a second loop for a task already tracked."""
        supervisor._active_negotiation_ids.add("task-1")

        with patch(
            "mc.services.plan_negotiation.start_plan_negotiation_loop",
            new_callable=AsyncMock,
        ):
            await supervisor._spawn_loop_if_needed("task-1")
            # Loop should NOT be spawned again


class TestProcessBatch:
    """Test process_batch — filters tasks and spawns loops."""

    @pytest.mark.asyncio
    async def test_spawns_for_review_with_awaiting_kickoff(
        self, supervisor: PlanNegotiationSupervisor
    ) -> None:
        """Spawns for tasks in 'review' with awaiting_kickoff=True."""
        batch = [
            {"id": "task-1", "status": "review", "awaiting_kickoff": True},
        ]
        with patch.object(
            supervisor, "_spawn_loop_if_needed", new_callable=AsyncMock
        ) as mock_spawn:
            await supervisor.process_batch(batch)
            mock_spawn.assert_called_once_with("task-1")

    @pytest.mark.asyncio
    async def test_spawns_for_in_progress(
        self, supervisor: PlanNegotiationSupervisor
    ) -> None:
        """Spawns for tasks in 'in_progress'."""
        batch = [
            {"id": "task-2", "status": "in_progress"},
        ]
        with patch.object(
            supervisor, "_spawn_loop_if_needed", new_callable=AsyncMock
        ) as mock_spawn:
            await supervisor.process_batch(batch)
            mock_spawn.assert_called_once_with("task-2")

    @pytest.mark.asyncio
    async def test_skips_non_negotiable_tasks(
        self, supervisor: PlanNegotiationSupervisor
    ) -> None:
        """Skips tasks in non-negotiable statuses."""
        batch = [
            {"id": "task-3", "status": "done"},
            {"id": "task-4", "status": "review", "awaiting_kickoff": False},
        ]
        with patch.object(
            supervisor, "_spawn_loop_if_needed", new_callable=AsyncMock
        ) as mock_spawn:
            await supervisor.process_batch(batch)
            mock_spawn.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_cron_requeued_tasks(
        self, supervisor: PlanNegotiationSupervisor
    ) -> None:
        """Cron-requeued tasks are skipped and removed from the set."""
        supervisor._cron_requeued_ids.add("task-5")
        batch = [
            {"id": "task-5", "status": "in_progress"},
        ]
        with patch.object(
            supervisor, "_spawn_loop_if_needed", new_callable=AsyncMock
        ) as mock_spawn:
            await supervisor.process_batch(batch)
            mock_spawn.assert_not_called()
            assert "task-5" not in supervisor._cron_requeued_ids

    @pytest.mark.asyncio
    async def test_skips_empty_or_error_batches(
        self, supervisor: PlanNegotiationSupervisor
    ) -> None:
        """Empty batches and error dicts are handled gracefully."""
        with patch.object(
            supervisor, "_spawn_loop_if_needed", new_callable=AsyncMock
        ) as mock_spawn:
            await supervisor.process_batch(None)
            await supervisor.process_batch({"_error": True, "message": "fail"})
            mock_spawn.assert_not_called()


class TestMarkCronRequeued:
    """Test the cron_requeued_ids management."""

    def test_mark_and_check_cron_requeued(
        self, supervisor: PlanNegotiationSupervisor
    ) -> None:
        supervisor.mark_cron_requeued("task-99")
        assert "task-99" in supervisor._cron_requeued_ids
