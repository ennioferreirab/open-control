"""Tests for InboxWorker ai_workflow bypass.

When a task has work_mode='ai_workflow' and a workflow-generated execution plan,
InboxWorker must materialize steps and dispatch them for execution.
"""

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
    bridge.update_task_status.return_value = None
    bridge.transition_task_from_snapshot.return_value = {"kind": "applied"}
    bridge.mutation.return_value = None
    bridge.create_activity.return_value = None
    bridge.patch_routing_decision.return_value = None
    return bridge


def _make_ctx(bridge: MagicMock | None = None) -> RuntimeContext:
    if bridge is None:
        bridge = _make_bridge()
    return RuntimeContext(bridge=bridge, agents_dir=Path("/tmp/test-agents"))


def _make_materializer_and_dispatcher():
    materializer = MagicMock()
    materializer.materialize.return_value = ["step-real-1"]
    dispatcher = MagicMock()
    dispatcher.dispatch_steps = AsyncMock()
    return materializer, dispatcher


def _make_workflow_worker(bridge=None):
    if bridge is None:
        bridge = _make_bridge()
    materializer, dispatcher = _make_materializer_and_dispatcher()
    worker = InboxWorker(
        _make_ctx(bridge),
        plan_materializer=materializer,
        step_dispatcher=dispatcher,
    )
    return worker, materializer, dispatcher


def _make_workflow_task(task_id: str = "task-workflow-1") -> dict:
    return {
        "id": task_id,
        "title": "Squad Mission: Review Release",
        "description": "Run the review workflow",
        "assigned_agent": None,
        "is_manual": False,
        "work_mode": "ai_workflow",
        "execution_plan": {
            "generated_by": "workflow",
            "generated_at": "2026-03-14T10:00:00.000Z",
            "steps": [
                {
                    "temp_id": "step-1",
                    "title": "Research",
                    "description": "Research the topic",
                    "assigned_agent": "researcher",
                    "blocked_by": [],
                    "parallel_group": 1,
                    "order": 1,
                }
            ],
        },
    }


def _mock_llm_router(target_agent: str = "nanobot"):
    decision = RoutingDecision(
        target_agent=target_agent,
        reason=f"LLM picked {target_agent}",
        reason_code="llm_delegation",
        registry_snapshot=[],
        routed_at="2026-01-01T00:00:00+00:00",
    )
    mock_router = MagicMock()
    mock_router.route = AsyncMock(return_value=decision)
    return mock_router


class TestInboxWorkerAiWorkflowBypass:
    """Workflow tasks get materialized and dispatched."""

    @pytest.mark.asyncio
    async def test_workflow_task_materializes_and_dispatches(self) -> None:
        worker, materializer, dispatcher = _make_workflow_worker()
        task = _make_workflow_task()

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        materializer.materialize.assert_called_once()
        dispatcher.dispatch_steps.assert_awaited_once_with("task-workflow-1", ["step-real-1"])

    @pytest.mark.asyncio
    async def test_workflow_task_never_reaches_planning(self) -> None:
        worker, _, _ = _make_workflow_worker()
        task = _make_workflow_task()

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        bridge = worker._bridge
        for call in bridge.transition_task_from_snapshot.call_args_list:
            assert call[0][1] in ("assigned", "in_progress")

    @pytest.mark.asyncio
    async def test_normal_task_routes_via_llm_delegation(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-normal",
            "title": "Normal task",
            "description": "Do something",
            "assigned_agent": None,
            "is_manual": False,
        }

        mock_router = _mock_llm_router("nanobot")
        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.runtime.workers.inbox.LLMDelegationRouter", return_value=mock_router),
        ):
            await worker.process_task(task)

        mock_router.route.assert_awaited_once()
        bridge.update_task_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_ai_workflow_without_plan_routes_via_llm(self) -> None:
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-no-plan",
            "title": "Workflow task without plan",
            "description": "Missing plan",
            "assigned_agent": None,
            "is_manual": False,
            "work_mode": "ai_workflow",
        }

        mock_router = _mock_llm_router("nanobot")
        with (
            patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.runtime.workers.inbox.LLMDelegationRouter", return_value=mock_router),
        ):
            await worker.process_task(task)

        mock_router.route.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_claim_prevents_duplicate_routing(self) -> None:
        bridge = _make_bridge()
        claims: set[tuple[str, str, str]] = set()

        def _mutation(name: str, args: dict) -> dict | None:
            if name != "runtimeClaims:acquire":
                return None
            claim = (args["claim_kind"], args["entity_type"], args["entity_id"])
            if claim in claims:
                return {"granted": False, "ownerId": "other-runtime"}
            claims.add(claim)
            return {"granted": True, "claimId": "claim-1"}

        bridge.mutation.side_effect = _mutation
        materializer, dispatcher = _make_materializer_and_dispatcher()
        worker = InboxWorker(
            _make_ctx(bridge),
            plan_materializer=materializer,
            step_dispatcher=dispatcher,
        )
        task = _make_workflow_task()

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_batch([task])
            worker._known_inbox_ids.clear()
            await worker.process_batch([task])

        materializer.materialize.assert_called_once()
