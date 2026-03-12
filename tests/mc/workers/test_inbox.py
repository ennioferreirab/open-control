"""Tests for InboxWorker — new task processing, auto-title, initial routing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.infrastructure.runtime_context import RuntimeContext
from mc.runtime.workers.inbox import InboxWorker


async def _sync_to_thread(func, *args, **kwargs):
    """Run to_thread payloads synchronously in tests."""
    return func(*args, **kwargs)


def _make_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.update_task_status.return_value = None
    bridge.mutation.return_value = None
    bridge.create_activity.return_value = None
    return bridge


def _make_ctx(bridge: MagicMock | None = None) -> RuntimeContext:
    if bridge is None:
        bridge = _make_bridge()
    return RuntimeContext(bridge=bridge, agents_dir=Path("/tmp/test-agents"))


class TestInboxWorkerProcessTask:
    """Happy path and error path tests for InboxWorker.process_task."""

    @pytest.mark.asyncio
    async def test_routes_to_planning_when_no_assigned_agent(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-1",
            "title": "Do something",
            "description": "Details",
            "assigned_agent": None,
            "is_manual": False,
        }

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        bridge.update_task_status.assert_called_once_with("task-1", "planning")

    @pytest.mark.asyncio
    async def test_routes_to_assigned_when_agent_set(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-2",
            "title": "Assigned task",
            "description": "Details",
            "assigned_agent": "nanobot",
            "is_manual": False,
        }

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        bridge.update_task_status.assert_called_once_with("task-2", "assigned")

    @pytest.mark.asyncio
    async def test_skips_manual_tasks(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-manual",
            "title": "Manual task",
            "is_manual": True,
        }

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        bridge.update_task_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_title_called_when_requested(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-3",
            "title": "",
            "description": "Build a widget",
            "assigned_agent": None,
            "auto_title": True,
            "is_manual": False,
        }

        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.inbox.generate_title_via_low_agent",
                new=AsyncMock(return_value="Widget Builder"),
            ),
        ):
            await worker.process_task(task)

        bridge.mutation.assert_called_once_with(
            "tasks:updateTitle",
            {"task_id": "task-3", "title": "Widget Builder"},
        )
        bridge.update_task_status.assert_called_once_with("task-3", "planning")

    @pytest.mark.asyncio
    async def test_auto_title_failure_still_transitions(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-4",
            "title": "",
            "description": "Something",
            "assigned_agent": None,
            "auto_title": True,
            "is_manual": False,
        }

        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.inbox.generate_title_via_low_agent",
                new=AsyncMock(return_value=None),
            ),
        ):
            await worker.process_task(task)

        # Should still transition even if auto-title fails
        bridge.update_task_status.assert_called_once_with("task-4", "planning")


class TestInboxWorkerProcessBatch:
    """Tests for batch deduplication and pruning logic."""

    @pytest.mark.asyncio
    async def test_deduplicates_tasks_in_same_batch(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        tasks = [
            {
                "id": "task-1",
                "title": "A",
                "description": "D",
                "assigned_agent": None,
                "is_manual": False,
            },
            {
                "id": "task-1",
                "title": "A",
                "description": "D",
                "assigned_agent": None,
                "is_manual": False,
            },
        ]

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_batch(tasks)

        # Only one call (deduplication)
        assert bridge.update_task_status.call_count == 1

    @pytest.mark.asyncio
    async def test_prunes_stale_ids_so_reentry_works(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-1",
            "title": "A",
            "description": "D",
            "assigned_agent": None,
            "is_manual": False,
        }

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            # First batch
            await worker.process_batch([task])
            assert bridge.update_task_status.call_count == 1

            # Task leaves inbox (empty batch prunes)
            await worker.process_batch([])

            # Task re-enters inbox -- should be processed again
            await worker.process_batch([task])
            assert bridge.update_task_status.call_count == 2

    @pytest.mark.asyncio
    async def test_error_in_one_task_does_not_block_others(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        # First task will error, second should still process
        call_count = 0

        original_process = worker.process_task

        async def _failing_process(task_data):
            nonlocal call_count
            call_count += 1
            if task_data["id"] == "task-fail":
                raise RuntimeError("boom")
            await original_process(task_data)

        worker.process_task = _failing_process

        tasks = [
            {"id": "task-fail", "title": "A", "is_manual": False},
            {
                "id": "task-ok",
                "title": "B",
                "description": "D",
                "assigned_agent": None,
                "is_manual": False,
            },
        ]

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_batch(tasks)

        assert call_count == 2
        bridge.update_task_status.assert_called_once_with("task-ok", "planning")
