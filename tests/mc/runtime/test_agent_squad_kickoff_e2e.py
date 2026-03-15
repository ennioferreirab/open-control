"""Backend end-to-end coverage for canonical agent workflow kickoff."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from mc.contexts.planning.materializer import PlanMaterializer
from mc.infrastructure.runtime_context import RuntimeContext
from mc.runtime.workers.kickoff import KickoffResumeWorker
from mc.types import ActivityEventType, StepStatus, TaskStatus


class InMemoryBridge:
    """Minimal bridge implementation for backend workflow kickoff tests."""

    def __init__(self, task: dict[str, Any]) -> None:
        self.tasks: dict[str, dict[str, Any]] = {str(task["id"]): deepcopy(task)}
        self.steps_by_task: dict[str, list[dict[str, Any]]] = {str(task["id"]): []}
        self.workflow_runs: list[dict[str, Any]] = []
        self.activities: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []
        self._next_step_id = 1

    def get_steps_by_task(self, task_id: str) -> list[dict[str, Any]]:
        steps = self.steps_by_task.get(task_id, [])
        return [deepcopy(step) for step in steps]

    def batch_create_steps(self, task_id: str, steps: list[dict[str, Any]]) -> list[str]:
        created_ids: list[str] = []
        stored_steps = self.steps_by_task.setdefault(task_id, [])

        for step in steps:
            step_id = f"step-{self._next_step_id}"
            self._next_step_id += 1
            stored_steps.append(
                {
                    "id": step_id,
                    "task_id": task_id,
                    "title": step["title"],
                    "description": step["description"],
                    "assigned_agent": step["assigned_agent"],
                    "blocked_by": [],
                    "parallel_group": step["parallel_group"],
                    "order": step["order"],
                    "status": StepStatus.ASSIGNED,
                    "temp_id": step["temp_id"],
                    "workflow_step_id": step.get("workflow_step_id"),
                    "workflow_step_type": step.get("workflow_step_type"),
                    "agent_id": step.get("agent_id"),
                    "review_spec_id": step.get("review_spec_id"),
                    "on_reject_step_id": step.get("on_reject_step_id"),
                }
            )
            created_ids.append(step_id)

        return created_ids

    def mutation(self, name: str, args: dict[str, Any]) -> str:
        if name == "workflowRuns:create":
            workflow_run_id = f"workflow-run-{len(self.workflow_runs) + 1}"
            self.workflow_runs.append({"id": workflow_run_id, **deepcopy(args)})
            return workflow_run_id
        msg = f"Unsupported mutation: {name}"
        raise AssertionError(msg)

    def query(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "tasks:getById":
            task = self.tasks.get(str(args["task_id"]))
            if task is None:
                msg = f"Unknown task: {args['task_id']}"
                raise AssertionError(msg)
            return deepcopy(task)
        msg = f"Unsupported query: {name}"
        raise AssertionError(msg)

    def create_activity(
        self,
        event_type: str,
        description: str,
        task_id: str | None = None,
        agent_name: str | None = None,
    ) -> None:
        self.activities.append(
            {
                "event_type": event_type,
                "description": description,
                "task_id": task_id,
                "agent_name": agent_name,
            }
        )

    def update_task_status(
        self,
        task_id: str,
        status: str,
        assigned_agent: str | None = None,
        description: str | None = None,
    ) -> None:
        task = self.tasks[task_id]
        task["status"] = status
        task["assigned_agent"] = assigned_agent
        task["status_description"] = description

    def send_message(
        self,
        task_id: str,
        sender_name: str,
        author_type: str,
        content: str,
        message_type: str,
    ) -> None:
        self.messages.append(
            {
                "task_id": task_id,
                "sender_name": sender_name,
                "author_type": author_type,
                "content": content,
                "message_type": message_type,
            }
        )


class RecordingStepDispatcher:
    """Real async dispatcher replacement that records the handoff boundary."""

    def __init__(self, bridge: InMemoryBridge) -> None:
        self._bridge = bridge
        self.calls: list[dict[str, Any]] = []

    async def dispatch_steps(self, task_id: str, step_ids: list[str]) -> None:
        self.calls.append(
            {
                "task_id": task_id,
                "step_ids": list(step_ids),
                "steps": self._bridge.get_steps_by_task(task_id),
            }
        )


@pytest.mark.asyncio
async def test_kickoff_materializes_registered_agent_steps_end_to_end() -> None:
    """Kickoff preserves canonical agent ids through workflow materialization."""
    task = {
        "id": "task-agent-squad-1",
        "title": "Create launch plan",
        "status": TaskStatus.IN_PROGRESS,
        "work_mode": "ai_workflow",
        "squad_spec_id": "squad-spec-1",
        "workflow_spec_id": "workflow-spec-1",
        "board_id": "board-1",
        "execution_plan": {
            "steps": [
                {
                    "tempId": "draft-plan",
                    "title": "Draft execution plan",
                    "description": "Build the squad execution plan",
                    "assignedAgent": "nanobot",
                    "workflowStepId": "draft-plan",
                    "workflowStepType": "agent",
                    "agentId": "agent-registered-1",
                    "blockedBy": [],
                    "parallelGroup": 1,
                    "order": 1,
                }
            ],
            "generatedAt": "2026-03-15T12:00:00Z",
            "generatedBy": "lead-agent",
        },
        "updated_at": "2026-03-15T12:00:00Z",
    }
    bridge = InMemoryBridge(task)
    dispatcher = RecordingStepDispatcher(bridge)
    worker = KickoffResumeWorker(
        ctx=RuntimeContext(bridge=bridge, agents_dir=Path("/tmp/test-agents")),
        plan_materializer=PlanMaterializer(bridge),
        step_dispatcher=dispatcher,
    )

    await worker.process_batch([deepcopy(task)])

    for _ in range(20):
        if dispatcher.calls:
            break
        await asyncio.sleep(0.01)

    assert dispatcher.calls == [
        {
            "task_id": "task-agent-squad-1",
            "step_ids": ["step-1"],
            "steps": [
                {
                    "id": "step-1",
                    "task_id": "task-agent-squad-1",
                    "title": "Draft execution plan",
                    "description": "Build the squad execution plan",
                    "assigned_agent": "nanobot",
                    "blocked_by": [],
                    "parallel_group": 1,
                    "order": 1,
                    "status": StepStatus.ASSIGNED,
                    "temp_id": "draft-plan",
                    "workflow_step_id": "draft-plan",
                    "workflow_step_type": "agent",
                    "agent_id": "agent-registered-1",
                    "review_spec_id": None,
                    "on_reject_step_id": None,
                }
            ],
        }
    ]
    assert bridge.workflow_runs == [
        {
            "id": "workflow-run-1",
            "task_id": "task-agent-squad-1",
            "squad_spec_id": "squad-spec-1",
            "workflow_spec_id": "workflow-spec-1",
            "board_id": "board-1",
            "launched_at": bridge.workflow_runs[0]["launched_at"],
            "step_mapping": {"draft-plan": "step-1"},
        }
    ]
    assert bridge.tasks["task-agent-squad-1"]["status"] == TaskStatus.IN_PROGRESS
    assert bridge.messages == []
    assert not any(
        activity["event_type"] == ActivityEventType.SYSTEM_ERROR for activity in bridge.activities
    )
