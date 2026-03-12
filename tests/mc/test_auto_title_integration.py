"""Integration tests for auto-title wiring inside _process_inbox_task."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.runtime.orchestrator import TaskOrchestrator


def _make_bridge():
    """Return a minimal mock bridge that satisfies the orchestrator's dependencies."""
    bridge = MagicMock()
    bridge.create_task_directory = MagicMock()
    bridge.list_agents = MagicMock(return_value=[])
    bridge.create_activity = MagicMock()
    bridge.update_task_status = MagicMock()
    bridge.send_message = MagicMock()
    bridge.update_execution_plan = MagicMock()
    bridge.mutation = MagicMock(return_value=None)
    bridge.get_board_by_id = MagicMock(return_value=None)
    return bridge


def _make_task(auto_title: bool = True, description: str = "Some task description") -> dict:
    return {
        "id": "task123",
        "title": "placeholder title...",
        "description": description,
        "auto_title": auto_title,
        "assigned_agent": None,
        "is_manual": False,
        "board_id": None,
        "supervision_mode": "autonomous",
        "trust_level": "autonomous",
        "files": [],
    }


@pytest.mark.asyncio
async def test_auto_title_updates_title_and_continues():
    """When auto_title=True and LLM returns a title, updateTitle mutation is called before planning."""
    bridge = _make_bridge()

    async def passthrough(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    with (
        patch(
            "mc.runtime.workers.inbox.generate_title_via_low_agent",
            new=AsyncMock(return_value="A Forca dos Poemas Curtos"),
        ),
        patch("asyncio.to_thread", side_effect=passthrough),
    ):
        orchestrator = TaskOrchestrator(bridge)
        task = _make_task(auto_title=True, description="Poemas curtos revelam a forca...")
        await orchestrator._inbox_worker.process_task(task)

    # updateTitle mutation must have been called with the generated title
    bridge.mutation.assert_called_once_with(
        "tasks:updateTitle",
        {"task_id": "task123", "title": "A Forca dos Poemas Curtos"},
    )


@pytest.mark.asyncio
async def test_auto_title_skipped_when_llm_returns_none():
    """When generate_title_via_low_agent returns None, updateTitle is NOT called."""
    bridge = _make_bridge()

    async def passthrough(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    with (
        patch(
            "mc.runtime.workers.inbox.generate_title_via_low_agent",
            new=AsyncMock(return_value=None),
        ),
        patch("asyncio.to_thread", side_effect=passthrough),
    ):
        orchestrator = TaskOrchestrator(bridge)
        task = _make_task(auto_title=True, description="Poemas curtos revelam a forca...")
        await orchestrator._inbox_worker.process_task(task)

    # updateTitle must NOT have been called
    bridge.mutation.assert_not_called()


@pytest.mark.asyncio
async def test_auto_title_not_called_when_flag_false():
    """When auto_title is False, generate_title_via_low_agent is never invoked."""
    bridge = _make_bridge()

    async def passthrough(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    with (
        patch(
            "mc.runtime.workers.inbox.generate_title_via_low_agent",
            new=AsyncMock(return_value="Should Not Be Called"),
        ) as mock_gen,
        patch("asyncio.to_thread", side_effect=passthrough),
    ):
        orchestrator = TaskOrchestrator(bridge)
        task = _make_task(auto_title=False, description="Poemas curtos revelam a forca...")
        await orchestrator._inbox_worker.process_task(task)

    mock_gen.assert_not_called()
    bridge.mutation.assert_not_called()


@pytest.mark.asyncio
async def test_auto_title_not_called_when_no_description():
    """When auto_title=True but description is None, generate_title_via_low_agent is skipped."""
    bridge = _make_bridge()

    async def passthrough(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    with (
        patch(
            "mc.runtime.workers.inbox.generate_title_via_low_agent",
            new=AsyncMock(return_value="Should Not Be Called"),
        ) as mock_gen,
        patch("asyncio.to_thread", side_effect=passthrough),
    ):
        orchestrator = TaskOrchestrator(bridge)
        task = _make_task(auto_title=True, description=None)
        task["description"] = None
        await orchestrator._inbox_worker.process_task(task)

    mock_gen.assert_not_called()
    bridge.mutation.assert_not_called()
