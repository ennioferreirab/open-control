from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.contexts.execution.executor import TaskExecutor
from mc.types import TaskStatus


async def _to_thread_passthrough(func, *args, **kwargs):
    return func(*args, **kwargs)


@pytest.mark.asyncio
async def test_pickup_task_uses_canonical_transition_contract() -> None:
    bridge = MagicMock()
    bridge.transition_task_from_snapshot.return_value = {"kind": "applied"}
    bridge.send_message = MagicMock()

    task_data = {
        "id": "task-pickup",
        "title": "Pickup task",
        "description": "Do the work",
        "status": "assigned",
        "state_version": 4,
        "assigned_agent": "agent-x",
        "trust_level": "autonomous",
    }

    executor = TaskExecutor(bridge)

    with (
        patch.object(executor, "_execute_task", new_callable=AsyncMock) as mock_execute,
        patch("asyncio.to_thread", side_effect=_to_thread_passthrough),
    ):
        await executor._pickup_task(task_data)

    bridge.transition_task_from_snapshot.assert_called_once()
    transition_call = bridge.transition_task_from_snapshot.call_args
    assert transition_call.args[0]["id"] == "task-pickup"
    assert transition_call.args[0]["status"] == "assigned"
    assert transition_call.args[0]["state_version"] == 4
    assert transition_call.args[1] == TaskStatus.IN_PROGRESS
    assert transition_call.kwargs["agent_name"] == "agent-x"
    assert "started work" in transition_call.kwargs["reason"]
    mock_execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_task_completes_with_fresh_task_snapshot_transition() -> None:
    bridge = MagicMock()
    bridge.get_task.return_value = {
        "id": "task-complete",
        "status": "in_progress",
        "state_version": 7,
        "trust_level": "autonomous",
    }
    bridge.transition_task_from_snapshot.return_value = {"kind": "applied"}
    bridge.send_message = MagicMock()
    bridge.create_activity = MagicMock()
    bridge.get_agent_by_name = MagicMock(return_value=None)
    bridge.sync_task_output_files = MagicMock()

    executor = TaskExecutor(bridge, on_task_completed=None)

    with (
        patch(
            "mc.contexts.execution.executor._run_agent_on_task",
            new_callable=AsyncMock,
            return_value=("Done", "mock_session_key", MagicMock()),
        ),
        patch.object(executor, "_load_agent_config", return_value=(None, None, None)),
        patch("asyncio.to_thread", side_effect=_to_thread_passthrough),
    ):
        await executor._execute_task(
            "task-complete",
            "Complete task",
            "Ship it",
            "agent-x",
            "autonomous",
            {
                "id": "task-complete",
                "status": "in_progress",
                "state_version": 1,
                "trust_level": "autonomous",
            },
        )

    bridge.get_task.assert_called_once_with("task-complete")
    bridge.transition_task_from_snapshot.assert_called_once()
    transition_call = bridge.transition_task_from_snapshot.call_args
    assert transition_call.args[0]["state_version"] == 7
    assert transition_call.args[1] == TaskStatus.REVIEW
    assert transition_call.kwargs["agent_name"] == "agent-x"
    assert "completed task" in transition_call.kwargs["reason"]
