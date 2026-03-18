"""Tests for PlanningWorker ai_workflow bypass (defense-in-depth Layer 3).

When a task has work_mode='ai_workflow' and execution_plan.generatedBy='workflow',
PlanningWorker must NOT call the lead-agent planner — the existing workflow plan
must be preserved.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.infrastructure.runtime_context import RuntimeContext
from mc.runtime.workers.planning import PlanningWorker
from mc.types import ExecutionPlan, ExecutionPlanStep


async def _sync_to_thread(func, *args, **kwargs):
    """Run to_thread payloads synchronously in tests."""
    return func(*args, **kwargs)


def _make_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.create_task_directory.return_value = None
    bridge.list_agents.return_value = []
    bridge.update_execution_plan.return_value = None
    bridge.batch_create_steps.return_value = ["step-1"]
    bridge.kick_off_task.return_value = None
    bridge.update_task_status.return_value = None
    bridge.transition_task_from_snapshot.return_value = {"kind": "applied"}
    bridge.create_activity.return_value = None
    bridge.send_message.return_value = None
    return bridge


def _make_ctx(bridge: MagicMock | None = None) -> RuntimeContext:
    if bridge is None:
        bridge = _make_bridge()
    return RuntimeContext(bridge=bridge, agents_dir=Path("/tmp/test-agents"))


def _make_materializer() -> MagicMock:
    mat = MagicMock()
    mat.materialize.return_value = ["step-1"]
    return mat


def _make_dispatcher() -> MagicMock:
    disp = MagicMock()
    disp.dispatch_steps = AsyncMock()
    return disp


def _make_workflow_task(task_id: str = "task-workflow-1") -> dict:
    """Build a task dict that represents a squad mission with a compiled workflow plan."""
    return {
        "id": task_id,
        "title": "Squad Mission: Review Release",
        "description": "Run the review workflow",
        "assigned_agent": None,
        "is_manual": False,
        "supervision_mode": "autonomous",
        "status": "planning",
        "trust_level": "autonomous",
        "files": [],
        "work_mode": "ai_workflow",
        "execution_plan": {
            "generated_by": "workflow",
            "generated_at": "2026-03-14T10:00:00.000Z",
            "steps": [
                {
                    "temp_id": "step-research",
                    "title": "Research",
                    "description": "Research the topic",
                    "assigned_agent": "researcher",
                    "blocked_by": [],
                    "parallel_group": 1,
                    "order": 1,
                },
                {
                    "temp_id": "step-write",
                    "title": "Write",
                    "description": "Write the post",
                    "assigned_agent": "writer",
                    "blocked_by": ["step-research"],
                    "parallel_group": 2,
                    "order": 2,
                },
            ],
        },
    }


def _make_legacy_workflow_task(task_id: str = "task-legacy-workflow-1") -> dict:
    task = _make_workflow_task(task_id)
    task.pop("work_mode", None)
    return task


def _make_bridge_workflow_task(task_id: str = "task-bridge-workflow-1") -> dict:
    """Build a workflow task as it actually arrives from the Python bridge."""
    task = _make_workflow_task(task_id)
    task["execution_plan"] = {
        "generated_by": "workflow",
        "generated_at": "2026-03-14T10:00:00.000Z",
        "steps": task["execution_plan"]["steps"],
    }
    return task


def _make_normal_task(task_id: str = "task-normal-1") -> dict:
    """Build a normal (non-workflow) task dict."""
    return {
        "id": task_id,
        "title": "Normal task",
        "description": "Do something useful",
        "assigned_agent": None,
        "is_manual": False,
        "supervision_mode": "autonomous",
        "status": "planning",
        "trust_level": "autonomous",
        "files": [],
    }


def _make_lead_agent_plan() -> ExecutionPlan:
    return ExecutionPlan(
        steps=[
            ExecutionPlanStep(
                temp_id="step_1",
                title="Do something",
                description="Lead agent step",
                assigned_agent="nanobot",
                blocked_by=[],
                parallel_group=1,
                order=1,
            )
        ]
    )


class TestPlanningWorkerAiWorkflowBypass:
    """Layer 3 guardrail: PlanningWorker must not generate a new plan for workflow tasks."""

    @pytest.mark.asyncio
    async def test_workflow_task_does_not_call_planner(self) -> None:
        """PlanningWorker must NOT invoke the LLM planner for workflow tasks."""
        bridge = _make_bridge()
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)
        task = _make_workflow_task()

        def _capture_create_task(coro):
            coro.close()
            return MagicMock()

        with (
            patch("mc.runtime.workers.planning.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.planning.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
            patch("mc.runtime.workers.planning.TaskPlanner") as planner_cls,
        ):
            await worker.process_task(task)
            # The LLM planner must NOT be called
            planner_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_workflow_task_does_not_overwrite_execution_plan(self) -> None:
        """PlanningWorker must NOT overwrite the existing workflow execution plan."""
        bridge = _make_bridge()
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)
        task = _make_workflow_task()

        def _capture_create_task(coro):
            coro.close()
            return MagicMock()

        with (
            patch("mc.runtime.workers.planning.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.planning.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
            patch("mc.runtime.workers.planning.TaskPlanner"),
        ):
            await worker.process_task(task)

        # update_execution_plan must NOT be called (would overwrite the workflow plan)
        bridge.update_execution_plan.assert_not_called()

    @pytest.mark.asyncio
    async def test_workflow_task_materializes_and_dispatches_existing_plan(self) -> None:
        """PlanningWorker should materialize and dispatch the existing workflow plan."""
        bridge = _make_bridge()
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)
        task = _make_workflow_task()

        scheduled_coroutines: list[object] = []

        def _capture_create_task(coro):
            scheduled_coroutines.append(coro)
            coro.close()
            return MagicMock()

        with (
            patch("mc.runtime.workers.planning.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.planning.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
            patch("mc.runtime.workers.planning.TaskPlanner"),
        ):
            await worker.process_task(task)

        # Materializer must be called with the workflow plan
        materializer.materialize.assert_called_once()
        materialize_call = materializer.materialize.call_args
        assert materialize_call[0][0] == "task-workflow-1"
        # The plan passed should have 2 steps from the workflow
        passed_plan: ExecutionPlan = materialize_call[0][1]
        assert len(passed_plan.steps) == 2
        assert passed_plan.generated_by == "workflow"

        # Dispatch must be called
        assert len(scheduled_coroutines) == 1

    @pytest.mark.asyncio
    async def test_legacy_workflow_task_without_work_mode_still_bypasses_planner(self) -> None:
        """Legacy workflow tasks should still use the precompiled workflow plan."""
        bridge = _make_bridge()
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)
        task = _make_legacy_workflow_task()

        scheduled_coroutines: list[object] = []

        def _capture_create_task(coro):
            scheduled_coroutines.append(coro)
            coro.close()
            return MagicMock()

        with (
            patch("mc.runtime.workers.planning.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.planning.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
            patch("mc.runtime.workers.planning.TaskPlanner"),
        ):
            await worker.process_task(task)

        materializer.materialize.assert_called_once()
        assert len(scheduled_coroutines) == 1

    @pytest.mark.asyncio
    async def test_bridge_workflow_task_with_snake_case_plan_bypasses_planner(self) -> None:
        """Bridge-normalized workflow payloads must not invoke the lead-agent planner."""
        bridge = _make_bridge()
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)
        task = _make_bridge_workflow_task()

        scheduled_coroutines: list[object] = []

        def _capture_create_task(coro):
            scheduled_coroutines.append(coro)
            coro.close()
            return MagicMock()

        with (
            patch("mc.runtime.workers.planning.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.planning.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
            patch("mc.runtime.workers.planning.TaskPlanner") as planner_cls,
        ):
            await worker.process_task(task)
            planner_cls.assert_not_called()

        materializer.materialize.assert_called_once()
        assert len(scheduled_coroutines) == 1

    @pytest.mark.asyncio
    async def test_workflow_task_preserves_step_assignments(self) -> None:
        """The workflow plan's step-to-agent assignments must be preserved."""
        bridge = _make_bridge()
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)
        task = _make_workflow_task()

        def _capture_create_task(coro):
            coro.close()
            return MagicMock()

        with (
            patch("mc.runtime.workers.planning.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.planning.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
            patch("mc.runtime.workers.planning.TaskPlanner"),
        ):
            await worker.process_task(task)

        materialize_call = materializer.materialize.call_args
        passed_plan: ExecutionPlan = materialize_call[0][1]

        step_agents = {s.temp_id: s.assigned_agent for s in passed_plan.steps}
        assert step_agents["step-research"] == "researcher"
        assert step_agents["step-write"] == "writer"

    @pytest.mark.asyncio
    async def test_normal_task_still_calls_planner(self) -> None:
        """Non-workflow tasks must still be planned by the LLM planner."""
        bridge = _make_bridge()
        bridge.list_agents.return_value = [
            {
                "name": "nanobot",
                "display_name": "Owl",
                "role": "Generalist",
                "skills": ["general"],
                "enabled": True,
            }
        ]
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)
        task = _make_normal_task()
        plan = _make_lead_agent_plan()

        def _capture_create_task(coro):
            coro.close()
            return MagicMock()

        with (
            patch("mc.runtime.workers.planning.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.planning.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
            patch("mc.runtime.workers.planning.TaskPlanner") as planner_cls,
        ):
            planner = planner_cls.return_value
            planner.plan_task = AsyncMock(return_value=plan)
            await worker.process_task(task)

        # The planner must be called for normal tasks
        planner_cls.assert_called_once()
        planner.plan_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_ai_workflow_without_workflow_plan_still_calls_planner(self) -> None:
        """ai_workflow tasks without a pre-compiled workflow plan use the LLM planner."""
        bridge = _make_bridge()
        bridge.list_agents.return_value = []
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)
        plan = _make_lead_agent_plan()

        task = {
            "id": "task-no-plan",
            "title": "No plan yet",
            "description": "Missing plan",
            "assigned_agent": None,
            "is_manual": False,
            "supervision_mode": "autonomous",
            "status": "planning",
            "trust_level": "autonomous",
            "files": [],
            "work_mode": "ai_workflow",
            # No execution_plan — plan not yet compiled
        }

        def _capture_create_task(coro):
            coro.close()
            return MagicMock()

        with (
            patch("mc.runtime.workers.planning.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.planning.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
            patch("mc.runtime.workers.planning.TaskPlanner") as planner_cls,
        ):
            planner = planner_cls.return_value
            planner.plan_task = AsyncMock(return_value=plan)
            await worker.process_task(task)

        planner_cls.assert_called_once()
        planner.plan_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_supervised_plan_transitions_via_canonical_review_transition(self) -> None:
        bridge = _make_bridge()
        bridge.list_agents.return_value = []
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)
        task = {
            **_make_normal_task("task-supervised"),
            "supervision_mode": "supervised",
        }
        plan = _make_lead_agent_plan()

        with (
            patch("mc.runtime.workers.planning.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.runtime.workers.planning.TaskPlanner") as planner_cls,
        ):
            planner = planner_cls.return_value
            planner.plan_task = AsyncMock(return_value=plan)
            await worker.process_task(task)

        bridge.transition_task_from_snapshot.assert_called_once()
        call_args = bridge.transition_task_from_snapshot.call_args
        assert call_args.args[0]["id"] == "task-supervised"
        assert call_args.args[1] == "review"
        assert call_args.kwargs["awaiting_kickoff"] is True
        assert call_args.kwargs["review_phase"] == "plan_review"

    @pytest.mark.asyncio
    async def test_claim_prevents_duplicate_workflow_dispatch_when_known_ids_are_cleared(
        self,
    ) -> None:
        """Persistent claims, not _known_planning_ids, must gate duplicate planning work."""
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
        materializer = _make_materializer()
        dispatcher = _make_dispatcher()
        worker = PlanningWorker(_make_ctx(bridge), materializer, dispatcher)
        task = _make_workflow_task()

        def _capture_create_task(coro):
            coro.close()
            return MagicMock()

        with (
            patch("mc.runtime.workers.planning.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.runtime.workers.planning.asyncio.create_task",
                side_effect=_capture_create_task,
            ),
            patch("mc.runtime.workers.planning.TaskPlanner"),
        ):
            await worker.process_batch([task])
            worker._known_planning_ids.clear()
            await worker.process_batch([task])

        materializer.materialize.assert_called_once()
