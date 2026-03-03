"""Tests for Story 8.6: Manual tasks — orchestrator skip and type enum."""

import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from mc.types import ActivityEventType


# ---------------------------------------------------------------------------
# Task 7.1: Orchestrator skips manual tasks
# ---------------------------------------------------------------------------

class TestOrchestratorSkipsManualTasks:
    """The orchestrator must NOT route manual tasks (is_manual=True)."""

    @pytest.mark.asyncio
    async def test_manual_task_skipped_in_process_inbox(self):
        """_process_inbox_task should return early for manual tasks."""
        from mc.orchestrator import TaskOrchestrator

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.list_agents = MagicMock()

        orch = TaskOrchestrator(mock_bridge)
        task_data = {
            "id": "task_manual_1",
            "title": "Buy groceries",
            "description": None,
            "is_manual": True,
        }

        async def passthrough(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("asyncio.to_thread", side_effect=passthrough):
            await orch._process_inbox_task(task_data)

        # Should NOT call update_task_status (no routing)
        mock_bridge.update_task_status.assert_not_called()
        # Should NOT call list_agents (no scoring)
        mock_bridge.list_agents.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_manual_task_still_routed(self):
        """Tasks without is_manual should still be routed normally."""
        from mc.orchestrator import TaskOrchestrator

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.list_agents = MagicMock(return_value=[])

        orch = TaskOrchestrator(mock_bridge)
        task_data = {
            "id": "task_agent_1",
            "title": "Run tests",
            "description": None,
        }

        async def passthrough(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("asyncio.to_thread", side_effect=passthrough):
            await orch._process_inbox_task(task_data)

        # Should call update_task_status (lead agent fallback)
        mock_bridge.update_task_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_manual_task_skipped_in_routing_loop(self):
        """Manual tasks appearing in inbox subscription should be skipped."""
        from mc.orchestrator import TaskOrchestrator

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.list_agents = MagicMock(return_value=[])

        manual_task = {
            "id": "task_manual_loop",
            "title": "Manual task",
            "is_manual": True,
        }
        agent_task = {
            "id": "task_agent_loop",
            "title": "Agent task",
            "description": None,
        }

        q = asyncio.Queue()
        q.put_nowait([manual_task, agent_task])
        mock_bridge.async_subscribe = lambda fn, args: q

        orch = TaskOrchestrator(mock_bridge)

        async def passthrough(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("asyncio.to_thread", side_effect=passthrough):
            loop_task = asyncio.create_task(orch.start_routing_loop())
            await asyncio.sleep(0.2)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        # Only the agent task should be routed
        assert mock_bridge.update_task_status.call_count == 1


# ---------------------------------------------------------------------------
# Task 7.1b: Executor skips manual tasks in assigned subscription
# ---------------------------------------------------------------------------

class TestExecutorSkipsManualTasks:
    """The executor must NOT pick up manual tasks from the assigned queue."""

    @pytest.mark.asyncio
    async def test_manual_task_not_picked_up_by_executor(self):
        """Manual task in assigned queue should be skipped — no _pickup_task call."""
        from mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.create_activity = MagicMock()

        manual_task = {
            "id": "task_manual_assigned",
            "title": "Human task in assigned",
            "assigned_agent": "lead-agent",
            "trust_level": "autonomous",
            "is_manual": True,
        }

        q = asyncio.Queue()
        q.put_nowait([manual_task])
        mock_bridge.async_subscribe = lambda fn, args: q

        executor = TaskExecutor(mock_bridge)

        async def passthrough(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("asyncio.to_thread", side_effect=passthrough):
            loop_task = asyncio.create_task(executor.start_execution_loop())
            await asyncio.sleep(0.2)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        # Should NOT transition status (no pickup)
        mock_bridge.update_task_status.assert_not_called()
        # Should NOT be added to known IDs
        assert "task_manual_assigned" not in executor._known_assigned_ids

    @pytest.mark.asyncio
    async def test_non_manual_task_still_executed(self):
        """Agent tasks in assigned queue should still be picked up normally."""
        from mc.executor import TaskExecutor

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.send_message = MagicMock()
        mock_bridge.create_activity = MagicMock()

        agent_task = {
            "id": "task_agent_assigned",
            "title": "Agent task",
            "assigned_agent": "test-agent",
            "trust_level": "autonomous",
        }

        q = asyncio.Queue()
        q.put_nowait([agent_task])
        mock_bridge.async_subscribe = lambda fn, args: q

        executor = TaskExecutor(mock_bridge)

        with patch.object(executor, "_execute_task", new_callable=AsyncMock):
            async def passthrough(fn, *args, **kwargs):
                return fn(*args, **kwargs)

            with patch("asyncio.to_thread", side_effect=passthrough):
                loop_task = asyncio.create_task(executor.start_execution_loop())
                await asyncio.sleep(0.2)
                loop_task.cancel()
                try:
                    await loop_task
                except asyncio.CancelledError:
                    pass

        # Should have picked up and started executing
        mock_bridge.update_task_status.assert_called()


# ---------------------------------------------------------------------------
# Task 8.3: Python types include MANUAL_TASK_STATUS_CHANGED
# ---------------------------------------------------------------------------

class TestManualTaskEventType:
    """ActivityEventType enum includes the manual task event."""

    def test_manual_task_status_changed_exists(self):
        assert ActivityEventType.MANUAL_TASK_STATUS_CHANGED == "manual_task_status_changed"

    def test_manual_task_status_changed_is_string(self):
        assert isinstance(ActivityEventType.MANUAL_TASK_STATUS_CHANGED, str)
