"""Tests for InboxWorker — new task processing, auto-title, initial routing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.contexts.routing.router import RoutingDecision
from mc.infrastructure.runtime_context import RuntimeContext
from mc.runtime.workers.inbox import InboxWorker


async def _sync_to_thread(func, *args, **kwargs):
    """Run to_thread payloads synchronously in tests."""
    return func(*args, **kwargs)


def _make_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.mutation.return_value = {"granted": True}
    bridge.transition_task_from_snapshot.return_value = {"kind": "applied"}
    bridge.update_task_status.return_value = None
    bridge.create_activity.return_value = None
    bridge.patch_routing_decision.return_value = None
    return bridge


def _make_ctx(bridge: MagicMock | None = None) -> RuntimeContext:
    if bridge is None:
        bridge = _make_bridge()
    return RuntimeContext(bridge=bridge, agents_dir=Path("/tmp/test-agents"))


def _mock_llm_router(target_agent: str = "nanobot", reason_code: str = "llm_delegation"):
    """Create a mock LLMDelegationRouter that returns a successful decision."""
    decision = RoutingDecision(
        target_agent=target_agent,
        reason=f"LLM picked {target_agent}",
        reason_code=reason_code,
        registry_snapshot=[{"name": target_agent, "role": "agent"}],
        routed_at="2025-01-01T00:00:00+00:00",
    )
    mock_router = MagicMock()
    mock_router.route = AsyncMock(return_value=decision)
    return mock_router


class TestInboxWorkerProcessTask:
    """Happy path and error path tests for InboxWorker.process_task."""

    @pytest.mark.asyncio
    async def test_routes_via_llm_delegation_when_no_assigned_agent(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-1",
            "title": "Do something",
            "description": "Details",
            "assigned_agent": None,
            "is_manual": False,
        }

        mock_router = _mock_llm_router("nanobot")
        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.runtime.workers.inbox.LLMDelegationRouter", return_value=mock_router),
        ):
            await worker.process_task(task)

        mock_router.route.assert_awaited_once_with(task)
        bridge.update_task_status.assert_called_once_with(
            "task-1",
            "assigned",
            "nanobot",
            "Delegated to nanobot (llm_delegation)",
        )

    @pytest.mark.asyncio
    async def test_routes_via_explicit_assignment_when_agent_set(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-2",
            "title": "Assigned task",
            "description": "Details",
            "assigned_agent": "nanobot",
            "is_manual": False,
        }

        mock_router = _mock_llm_router("nanobot", reason_code="explicit_assignment")
        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.runtime.workers.inbox.LLMDelegationRouter", return_value=mock_router),
        ):
            await worker.process_task(task)

        mock_router.route.assert_awaited_once()
        bridge.update_task_status.assert_called_once()

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

        bridge.transition_task_from_snapshot.assert_not_called()

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

        mock_router = _mock_llm_router("nanobot")
        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.inbox.generate_title_via_low_agent",
                new=AsyncMock(return_value="Widget Builder"),
            ),
            patch("mc.runtime.workers.inbox.LLMDelegationRouter", return_value=mock_router),
        ):
            await worker.process_task(task)

        bridge.mutation.assert_any_call(
            "tasks:updateTitle",
            {"task_id": "task-3", "title": "Widget Builder"},
        )
        # Task goes through LLM delegation after title generation
        mock_router.route.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_auto_title_failure_still_routes(self) -> None:
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

        mock_router = _mock_llm_router("nanobot")
        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.inbox.generate_title_via_low_agent",
                new=AsyncMock(return_value=None),
            ),
            patch("mc.runtime.workers.inbox.LLMDelegationRouter", return_value=mock_router),
        ):
            await worker.process_task(task)

        # Should still route even if auto-title fails
        mock_router.route.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_llm_delegation_failure_fails_task_explicitly(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-5",
            "title": "Test",
            "description": "Details",
            "assigned_agent": None,
            "is_manual": False,
        }

        mock_router = MagicMock()
        mock_router.route = AsyncMock(side_effect=RuntimeError("LLM timeout"))
        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.runtime.workers.inbox.LLMDelegationRouter", return_value=mock_router),
        ):
            await worker.process_task(task)

        # Task should transition to failed
        bridge.transition_task_from_snapshot.assert_called_once()
        call_args = bridge.transition_task_from_snapshot.call_args
        assert call_args[0][1] == "failed"
        assert "LLM" in call_args[1]["reason"]

    @pytest.mark.asyncio
    async def test_workflow_task_materializes_and_dispatches(self) -> None:
        bridge = _make_bridge()
        bridge.batch_create_steps.return_value = ["step-real-1"]
        bridge.kick_off_task.return_value = None
        mock_materializer = MagicMock()
        mock_materializer.materialize.return_value = ["step-real-1"]
        mock_dispatcher = MagicMock()
        mock_dispatcher.dispatch_steps = AsyncMock()
        worker = InboxWorker(
            _make_ctx(bridge),
            plan_materializer=mock_materializer,
            step_dispatcher=mock_dispatcher,
        )

        task = {
            "id": "task-wf",
            "title": "Workflow task",
            "is_manual": False,
            "work_mode": "ai_workflow",
            "squad_spec_id": "squad-1",
            "execution_plan": {
                "steps": [
                    {
                        "temp_id": "step_1",
                        "title": "Do thing",
                        "description": "Do the thing",
                        "assigned_agent": "nanobot",
                        "blocked_by": [],
                        "parallel_group": 1,
                        "order": 1,
                    }
                ],
                "generated_at": "2025-01-01",
                "generated_by": "workflow",
            },
        }

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        mock_materializer.materialize.assert_called_once()
        mock_dispatcher.dispatch_steps.assert_awaited_once_with("task-wf", ["step-real-1"])


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

        mock_router = _mock_llm_router("nanobot")
        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.runtime.workers.inbox.LLMDelegationRouter", return_value=mock_router),
        ):
            await worker.process_batch(tasks)

        # Only one route call (deduplication)
        assert mock_router.route.await_count == 1

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

        mock_router = _mock_llm_router("nanobot")
        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.runtime.workers.inbox.LLMDelegationRouter", return_value=mock_router),
        ):
            # First batch
            await worker.process_batch([task])
            assert mock_router.route.await_count == 1

            # Task leaves inbox (empty batch prunes)
            await worker.process_batch([])

            # Task re-enters inbox — should be processed again
            await worker.process_batch([task])
            assert mock_router.route.await_count == 2

    @pytest.mark.asyncio
    async def test_error_in_one_task_does_not_block_others(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

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

        mock_router = _mock_llm_router("nanobot")
        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.runtime.workers.inbox.LLMDelegationRouter", return_value=mock_router),
        ):
            await worker.process_batch(tasks)

        assert call_count == 2
        # Second task should have been routed successfully
        mock_router.route.assert_awaited_once()
