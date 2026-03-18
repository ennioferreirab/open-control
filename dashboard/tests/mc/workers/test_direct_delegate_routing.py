"""Tests for direct-delegate routing through InboxWorker and PlanningWorker guard."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mc.contexts.routing.router import DirectDelegationRouter, RoutingDecision
from mc.infrastructure.runtime_context import RuntimeContext
from mc.runtime.workers.inbox import InboxWorker


async def _sync_to_thread(func, *args, **kwargs):
    """Run asyncio.to_thread payloads synchronously in tests."""
    return func(*args, **kwargs)


def _make_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.update_task_status.return_value = None
    bridge.mutation.return_value = None
    bridge.create_activity.return_value = None
    bridge.patch_routing_decision.return_value = None
    bridge.list_active_registry_view.return_value = []
    bridge.get_board_by_id.return_value = None
    return bridge


def _make_ctx(bridge: MagicMock | None = None) -> RuntimeContext:
    if bridge is None:
        bridge = _make_bridge()
    return RuntimeContext(bridge=bridge, agents_dir=Path("/tmp/test-agents"))


class TestInboxWorkerDirectDelegation:
    """Tests that InboxWorker routes direct_delegate tasks via DirectDelegationRouter."""

    @pytest.mark.asyncio
    async def test_direct_delegate_task_transitions_to_assigned(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-dd-1",
            "title": "Direct delegate task",
            "description": "A task for direct delegation",
            "workMode": "direct_delegate",
            "is_manual": False,
        }

        decision = RoutingDecision(
            target_agent="agent-alpha",
            reason="Least-loaded agent",
            reason_code="least_loaded",
            registry_snapshot=[{"name": "agent-alpha", "role": "dev"}],
            routed_at="2026-01-01T00:00:00+00:00",
        )

        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch.object(
                DirectDelegationRouter,
                "route",
                return_value=decision,
            ),
        ):
            await worker.process_task(task)

        # Should transition to assigned with the resolved agent
        bridge.update_task_status.assert_called_once_with(
            "task-dd-1",
            "assigned",
            "agent-alpha",
            "Direct delegation to agent-alpha",
        )

    @pytest.mark.asyncio
    async def test_direct_delegate_task_stores_routing_metadata(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-dd-2",
            "title": "Delegated task",
            "workMode": "direct_delegate",
            "is_manual": False,
        }

        decision = RoutingDecision(
            target_agent="agent-beta",
            reason="Explicitly assigned to agent-beta",
            reason_code="explicit_assignment",
            registry_snapshot=[{"name": "agent-beta", "role": "analyst"}],
            routed_at="2026-01-01T12:00:00+00:00",
        )

        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch.object(DirectDelegationRouter, "route", return_value=decision),
        ):
            await worker.process_task(task)

        bridge.patch_routing_decision.assert_called_once_with(
            "task-dd-2",
            "lead_agent",
            {
                "target_agent": "agent-beta",
                "reason": "Explicitly assigned to agent-beta",
                "reason_code": "explicit_assignment",
                "registry_snapshot": [{"name": "agent-beta", "role": "analyst"}],
                "routed_at": "2026-01-01T12:00:00+00:00",
            },
        )

    @pytest.mark.asyncio
    async def test_direct_delegate_falls_through_to_planning_when_no_agent(self) -> None:
        """When the router returns None, the task should fall through to planning."""
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-dd-3",
            "title": "No agent available",
            "workMode": "direct_delegate",
            "is_manual": False,
        }

        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch.object(DirectDelegationRouter, "route", return_value=None),
        ):
            await worker.process_task(task)

        # Falls through to planning (no assigned_agent on task)
        bridge.update_task_status.assert_called_once_with("task-dd-3", "planning")
        bridge.patch_routing_decision.assert_not_called()

    @pytest.mark.asyncio
    async def test_workflow_task_bypasses_direct_delegation(self) -> None:
        """Workflow tasks with ai_workflow+workflow plan must NOT go through direct delegation."""
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-wf-1",
            "title": "Workflow task",
            "workMode": "ai_workflow",
            "executionPlan": {"generatedBy": "workflow", "steps": []},
            "is_manual": False,
        }

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        # Should go to review (awaitingKickoff), not direct delegation
        bridge.update_task_status.assert_called_once_with(
            "task-wf-1",
            "review",
            None,
            "Workflow plan ready for kick-off: 'Workflow task'",
            True,
        )
        bridge.patch_routing_decision.assert_not_called()

    @pytest.mark.asyncio
    async def test_routing_metadata_failure_does_not_block_assignment(self) -> None:
        """If patch_routing_decision fails, the task should still transition to assigned."""
        bridge = _make_bridge()
        bridge.patch_routing_decision.side_effect = Exception("Convex error")
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-dd-4",
            "title": "Resilient delegation",
            "workMode": "direct_delegate",
            "is_manual": False,
        }

        decision = RoutingDecision(
            target_agent="agent-gamma",
            reason="Least-loaded",
            reason_code="least_loaded",
            registry_snapshot=[],
            routed_at="2026-01-01T00:00:00+00:00",
        )

        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch.object(DirectDelegationRouter, "route", return_value=decision),
        ):
            await worker.process_task(task)

        # Still transitions to assigned despite routing metadata failure
        bridge.update_task_status.assert_called_once_with(
            "task-dd-4",
            "assigned",
            "agent-gamma",
            "Direct delegation to agent-gamma",
        )


class TestPlanningWorkerDirectDelegateGuard:
    """Tests that PlanningWorker rejects direct_delegate tasks."""

    @pytest.mark.asyncio
    async def test_planning_worker_rejects_direct_delegate(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from mc.runtime.workers.planning import PlanningWorker

        bridge = _make_bridge()
        bridge.create_task_directory.return_value = None
        ctx = _make_ctx(bridge)
        worker = PlanningWorker(
            ctx,
            plan_materializer=MagicMock(),
            step_dispatcher=MagicMock(),
        )

        task = {
            "id": "task-dd-planning",
            "title": "Should be rejected",
            "workMode": "direct_delegate",
            "is_manual": False,
        }

        with patch("mc.runtime.workers.planning.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        # Must not call list_agents or any planning machinery
        bridge.list_agents.assert_not_called()
        bridge.create_activity.assert_not_called()

    @pytest.mark.asyncio
    async def test_planning_worker_allows_regular_tasks(self) -> None:
        """Regular tasks (no workMode) should still reach the planning pipeline."""
        from unittest.mock import AsyncMock, MagicMock

        from mc.runtime.workers.planning import PlanningWorker

        bridge = _make_bridge()
        bridge.create_task_directory.return_value = None
        bridge.list_agents.return_value = []
        ctx = _make_ctx(bridge)
        worker = PlanningWorker(
            ctx,
            plan_materializer=MagicMock(),
            step_dispatcher=MagicMock(),
        )

        task = {
            "id": "task-regular",
            "title": "Normal task",
            "is_manual": False,
        }

        with (
            patch("mc.runtime.workers.planning.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.runtime.workers.planning.TaskPlanner") as mock_planner_class,
        ):
            mock_planner = MagicMock()
            mock_planner.plan_task = AsyncMock(return_value=MagicMock(steps=[], to_dict=lambda: {}))
            mock_planner_class.return_value = mock_planner
            await worker.process_task(task)

        # Regular task should invoke planning machinery (list_agents is called)
        bridge.list_agents.assert_called_once()
