"""Tests for task routing through InboxWorker — LLM delegation and human routing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.contexts.routing.router import RoutingDecision
from mc.infrastructure.runtime_context import RuntimeContext
from mc.runtime.workers.inbox import InboxWorker


async def _sync_to_thread(func, *args, **kwargs):
    """Run asyncio.to_thread payloads synchronously in tests."""
    return func(*args, **kwargs)


def _make_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.mutation.return_value = {"granted": True}
    bridge.update_task_status.return_value = None
    bridge.create_activity.return_value = None
    bridge.patch_routing_decision.return_value = None
    bridge.list_active_registry_view.return_value = []
    bridge.get_board_by_id.return_value = None
    bridge.transition_task_from_snapshot.return_value = {"kind": "applied"}
    return bridge


def _make_ctx(bridge: MagicMock | None = None) -> RuntimeContext:
    if bridge is None:
        bridge = _make_bridge()
    return RuntimeContext(bridge=bridge, agents_dir=Path("/tmp/test-agents"))


def _mock_router(target_agent: str = "agent-alpha", reason_code: str = "llm_delegation"):
    """Create a mock LLMDelegationRouter that returns a decision."""
    decision = RoutingDecision(
        target_agent=target_agent,
        reason=f"LLM picked {target_agent}",
        reason_code=reason_code,
        registry_snapshot=[{"name": target_agent, "role": "dev"}],
        routed_at="2026-01-01T00:00:00+00:00",
    )
    mock = MagicMock()
    mock.route = AsyncMock(return_value=decision)
    return mock


class TestInboxWorkerLLMDelegation:
    """Tests that InboxWorker routes tasks via LLMDelegationRouter."""

    @pytest.mark.asyncio
    async def test_task_transitions_to_assigned(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-dd-1",
            "title": "Some task",
            "description": "A task for delegation",
            "is_manual": False,
        }

        mock_router = _mock_router("agent-alpha")
        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.runtime.workers.inbox.LLMDelegationRouter", return_value=mock_router),
        ):
            await worker.process_task(task)

        bridge.update_task_status.assert_called_once()
        call_args = bridge.update_task_status.call_args[0]
        assert call_args[1] == "assigned"
        assert call_args[2] == "agent-alpha"

    @pytest.mark.asyncio
    async def test_stores_routing_metadata(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-dd-2",
            "title": "Delegated task",
            "is_manual": False,
        }

        mock_router = _mock_router("agent-beta", reason_code="explicit_assignment")
        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.runtime.workers.inbox.LLMDelegationRouter", return_value=mock_router),
        ):
            await worker.process_task(task)

        bridge.patch_routing_decision.assert_called_once()

    @pytest.mark.asyncio
    async def test_delegation_failure_fails_task_explicitly(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-dd-3",
            "title": "No agent available",
            "is_manual": False,
        }

        mock_router = MagicMock()
        mock_router.route = AsyncMock(side_effect=RuntimeError("No active agents"))
        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.runtime.workers.inbox.LLMDelegationRouter", return_value=mock_router),
        ):
            await worker.process_task(task)

        bridge.transition_task_from_snapshot.assert_called_once()
        call_args = bridge.transition_task_from_snapshot.call_args
        assert call_args[0][1] == "failed"

    @pytest.mark.asyncio
    async def test_workflow_task_bypasses_delegation(self) -> None:
        """Workflow tasks get materialized and dispatched, bypassing LLM delegation."""
        bridge = _make_bridge()
        mock_materializer = MagicMock()
        mock_materializer.materialize.return_value = ["step-1"]
        mock_dispatcher = MagicMock()
        mock_dispatcher.dispatch_steps = AsyncMock()
        worker = InboxWorker(
            _make_ctx(bridge),
            plan_materializer=mock_materializer,
            step_dispatcher=mock_dispatcher,
        )

        task = {
            "id": "task-wf-1",
            "title": "Workflow task",
            "work_mode": "ai_workflow",
            "execution_plan": {
                "generated_by": "workflow",
                "generated_at": "2026-01-01",
                "steps": [
                    {
                        "temp_id": "s1",
                        "title": "Step",
                        "description": "Do",
                        "assigned_agent": "nanobot",
                        "blocked_by": [],
                        "parallel_group": 1,
                        "order": 1,
                    }
                ],
            },
            "is_manual": False,
        }

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        mock_materializer.materialize.assert_called_once()
        mock_dispatcher.dispatch_steps.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_routing_metadata_failure_does_not_block_assignment(self) -> None:
        bridge = _make_bridge()
        bridge.patch_routing_decision.side_effect = Exception("Convex error")
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-dd-4",
            "title": "Resilient delegation",
            "is_manual": False,
        }

        mock_router = _mock_router("agent-gamma")
        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.runtime.workers.inbox.LLMDelegationRouter", return_value=mock_router),
        ):
            await worker.process_task(task)

        bridge.update_task_status.assert_called_once()


class TestInboxWorkerHumanRouting:
    """Tests that human-routed tasks bypass the LLMDelegationRouter."""

    @pytest.mark.asyncio
    async def test_human_routed_task_bypasses_router(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-human-1",
            "title": "Operator-assigned task",
            "routing_mode": "human",
            "assigned_agent": "coder-agent",
            "is_manual": False,
        }

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        bridge.transition_task_from_snapshot.assert_called_once()
        call_args = bridge.transition_task_from_snapshot.call_args
        assert call_args[0][1] == "assigned"
        bridge.patch_routing_decision.assert_not_called()

    @pytest.mark.asyncio
    async def test_human_routed_task_without_agent_falls_through(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-human-2",
            "title": "Human-routed but no agent",
            "routing_mode": "human",
            "is_manual": False,
        }

        mock_router = MagicMock()
        mock_router.route = AsyncMock(side_effect=RuntimeError("No agents"))
        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.runtime.workers.inbox.LLMDelegationRouter", return_value=mock_router),
        ):
            await worker.process_task(task)

        # Without assigned_agent, human routing doesn't activate — falls to LLM which fails
        bridge.transition_task_from_snapshot.assert_called_once()
        call_args = bridge.transition_task_from_snapshot.call_args
        assert call_args[0][1] == "failed"
