"""Tests for InboxWorker ai_workflow bypass (defense-in-depth Layer 2).

When a task has work_mode='ai_workflow' and execution_plan.generatedBy='workflow',
InboxWorker must NOT route the task to 'planning' — it should go directly to 'review'
with awaitingKickoff=True so the workflow plan is preserved.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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
    return bridge


def _make_ctx(bridge: MagicMock | None = None) -> RuntimeContext:
    if bridge is None:
        bridge = _make_bridge()
    return RuntimeContext(bridge=bridge, agents_dir=Path("/tmp/test-agents"))


def _make_workflow_task(task_id: str = "task-workflow-1") -> dict:
    """Build a task dict that represents a launched squad mission with a compiled workflow plan."""
    return {
        "id": task_id,
        "title": "Squad Mission: Review Release",
        "description": "Run the review workflow",
        "assigned_agent": None,
        "is_manual": False,
        "work_mode": "ai_workflow",
        "execution_plan": {
            "generatedBy": "workflow",
            "generatedAt": "2026-03-14T10:00:00.000Z",
            "steps": [
                {
                    "tempId": "step-1",
                    "title": "Research",
                    "description": "Research the topic",
                    "assignedAgent": "researcher",
                    "blockedBy": [],
                    "parallelGroup": 1,
                    "order": 1,
                }
            ],
        },
    }


class TestInboxWorkerAiWorkflowBypass:
    """Layer 2 guardrail: InboxWorker must bypass planning for workflow tasks."""

    @pytest.mark.asyncio
    async def test_workflow_task_goes_to_review_not_planning(self) -> None:
        """ai_workflow tasks with a workflow plan must NOT be routed to 'planning'."""
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))
        task = _make_workflow_task()

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        # Must NOT call planning
        call_args_list = bridge.transition_task_from_snapshot.call_args_list
        statuses = [call[0][1] for call in call_args_list]
        assert "planning" not in statuses, (
            "ai_workflow tasks with a workflow plan must not be routed to planning"
        )

    @pytest.mark.asyncio
    async def test_workflow_task_is_transitioned_to_review(self) -> None:
        """ai_workflow tasks must be transitioned to 'review' status."""
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))
        task = _make_workflow_task()

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        bridge.transition_task_from_snapshot.assert_called_once()
        call_args = bridge.transition_task_from_snapshot.call_args
        assert call_args.args[0]["id"] == "task-workflow-1"
        assert call_args.args[1] == "review"

    @pytest.mark.asyncio
    async def test_workflow_task_sets_awaiting_kickoff(self) -> None:
        """Transition to review must set awaitingKickoff=True so dashboard shows kick-off UI."""
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))
        task = _make_workflow_task()

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        kwargs = bridge.transition_task_from_snapshot.call_args.kwargs
        assert kwargs["awaiting_kickoff"] is True
        assert kwargs["review_phase"] == "plan_review"

    @pytest.mark.asyncio
    async def test_normal_task_still_routes_to_planning(self) -> None:
        """Non-workflow tasks must still be routed to 'planning' as before."""
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-normal",
            "title": "Normal task",
            "description": "Do something",
            "assigned_agent": None,
            "is_manual": False,
            # no work_mode, no execution_plan
        }

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        bridge.transition_task_from_snapshot.assert_called_once()
        call_args = bridge.transition_task_from_snapshot.call_args
        assert call_args.args[0]["id"] == "task-normal"
        assert call_args.args[1] == "planning"
        assert call_args.kwargs["reason"] == "Inbox task routed to planning"

    @pytest.mark.asyncio
    async def test_ai_workflow_without_workflow_plan_still_routes_to_planning(self) -> None:
        """ai_workflow tasks without a pre-compiled workflow plan go to planning normally."""
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-no-plan",
            "title": "Workflow task without plan",
            "description": "Missing plan",
            "assigned_agent": None,
            "is_manual": False,
            "work_mode": "ai_workflow",
            # execution_plan is absent — plan not yet compiled
        }

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        bridge.transition_task_from_snapshot.assert_called_once()
        assert bridge.transition_task_from_snapshot.call_args.args[1] == "planning"

    @pytest.mark.asyncio
    async def test_ai_workflow_with_lead_agent_plan_still_routes_to_planning(self) -> None:
        """ai_workflow tasks whose plan was generated by lead-agent go to planning normally."""
        bridge = _make_bridge()
        worker = InboxWorker(_make_ctx(bridge))

        task = {
            "id": "task-lead-plan",
            "title": "Lead agent plan task",
            "description": "Has lead-agent plan",
            "assigned_agent": None,
            "is_manual": False,
            "work_mode": "ai_workflow",
            "execution_plan": {
                "generatedBy": "lead-agent",  # NOT a workflow plan
                "generatedAt": "2026-03-14T10:00:00.000Z",
                "steps": [],
            },
        }

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_task(task)

        bridge.transition_task_from_snapshot.assert_called_once()
        assert bridge.transition_task_from_snapshot.call_args.args[1] == "planning"

    @pytest.mark.asyncio
    async def test_claim_prevents_duplicate_routing_when_known_ids_are_cleared(self) -> None:
        """Persistent claims, not _known_inbox_ids, must gate duplicate inbox routing."""
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
        worker = InboxWorker(_make_ctx(bridge))
        task = _make_workflow_task()

        with patch("mc.runtime.workers.inbox.asyncio.to_thread", new=_sync_to_thread):
            await worker.process_batch([task])
            worker._known_inbox_ids.clear()
            await worker.process_batch([task])

        bridge.transition_task_from_snapshot.assert_called_once()
