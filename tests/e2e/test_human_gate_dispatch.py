"""E2E: verify that accepting a human gate step unblocks and dispatches dependents.

This test creates a workflow with:
  - Step A (agent) — parallel group 1
  - Step B (human gate) — parallel group 1
  - Step C (agent) — parallel group 2, depends on A and B

Flow:
  1. Launch mission → A dispatches (runs agent), B dispatches (waiting_human)
  2. A completes, B still waiting for human
  3. User accepts B → B completes → C unblocks → C dispatches → C completes → task done

Requires the full stack running (``make start``).

Run with::

    uv run pytest tests/e2e/test_human_gate_dispatch.py -m e2e -v
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(300)]

BASE_URL = os.environ.get("DASHBOARD_URL", "http://localhost:3000")
# Inside the container, CONVEX_URL points to the cloud-style self-hosted URL
# (e.g. https://careful-bobcat-15.convex.cloud). The Python ConvexClient
# uses WebSocket which doesn't work on localhost:3210 from within the container.
CONVEX_URL = os.environ.get("CONVEX_URL", "http://localhost:3210")
CONVEX_ADMIN_KEY = os.environ.get("CONVEX_ADMIN_KEY", "")

POLL_INTERVAL = 3
MAX_WAIT = 180

_http = httpx.Client(timeout=30)


def _bridge():
    from mc.bridge.client import BridgeClient

    return BridgeClient(CONVEX_URL, CONVEX_ADMIN_KEY or None)


def api(method: str, path: str, json: dict | None = None) -> dict:
    r = _http.request(method, f"{BASE_URL}{path}", json=json)
    return r.json()


def cq(fn: str, args: dict | None = None) -> Any:
    return _bridge().query(fn, args or {})


def cm(fn: str, args: dict | None = None) -> Any:
    return _bridge().mutation(fn, args or {})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _stack_check():
    """Skip if the stack is not running."""
    try:
        r = _http.get(f"{BASE_URL}/api/specs/skills", timeout=5)
        r.raise_for_status()
    except Exception:
        pytest.skip("Stack not running (make start)")


@pytest.fixture(scope="module")
def squad(_stack_check) -> dict:
    """Publish a test squad with a human-gate workflow."""
    result = api("POST", "/api/specs/squad", {
        "squad": {
            "name": "e2e-human-gate-test",
            "displayName": "E2E Human Gate Test",
            "description": "Tests human gate step unblocking and dispatch continuation",
        },
        "agents": [
            {
                "key": "worker",
                "name": "e2e-gate-worker",
                "displayName": "Gate Worker",
                "role": "Executes agent steps",
                "prompt": (
                    "You are a test worker agent. Write a single sentence "
                    "acknowledging the task. Keep it under 20 words."
                ),
                "model": "cc/claude-haiku-4-5-20251001",
                "skills": [],
                "soul": "# Worker\n\nI acknowledge tasks briefly.",
            },
        ],
        "workflows": [
            {
                "key": "default",
                "name": "human-gate-pipeline",
                "steps": [
                    {
                        "key": "work",
                        "type": "agent",
                        "agentKey": "worker",
                        "title": "Do initial work",
                    },
                    {
                        "key": "approve",
                        "type": "human",
                        "title": "Human approval gate",
                    },
                    {
                        "key": "finalize",
                        "type": "agent",
                        "agentKey": "worker",
                        "title": "Finalize after approval",
                        "dependsOn": ["work", "approve"],
                    },
                ],
                "exitCriteria": "All steps completed after human approval",
            },
        ],
    })
    squad_id = result["squadId"]

    workflows = cq("workflowSpecs:listBySquad", {"squad_spec_id": squad_id})
    workflow_id = workflows[0]["id"]

    board = cq("boards:getDefault", {})
    board_id = board["id"] if board else cm("boards:ensureDefault", {})

    yield {"squad_id": squad_id, "workflow_id": workflow_id, "board_id": board_id}

    api("DELETE", f"/api/specs/squad?squadSpecId={squad_id}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _poll_steps(task_id: str) -> list[dict]:
    return cq("steps:getByTask", {"task_id": task_id}) or []


def _print_status(elapsed: int, task_status: str, steps: list[dict]) -> None:
    summary = ", ".join(
        f"{s.get('title', '?')}={s.get('status', '?')}" for s in steps
    )
    print(f"  [{elapsed}s] task={task_status} | {summary or '(no steps)'}")


def _find_step(steps: list[dict], *, key: str | None = None, status: str | None = None) -> dict | None:
    for s in steps:
        if key and s.get("workflow_step_id") != key:
            continue
        if status and s.get("status") != status:
            continue
        return s
    return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHumanGateDispatch:
    """Accept human gate → dependents unblock → dispatch continues → task done."""

    def test_human_gate_accept_continues_workflow(self, squad):
        """Launch mission, wait for human step, accept, verify completion."""
        task_id = cm("tasks:launchMission", {
            "squadSpecId": squad["squad_id"],
            "workflowSpecId": squad["workflow_id"],
            "boardId": squad["board_id"],
            "title": "E2E Human Gate Test — approve and continue",
            "description": "Test that accepting a human gate unblocks the final step.",
        })
        assert task_id, "launchMission returned no task_id"

        # Phase 1: Wait for human step to reach waiting_human
        human_step_id = None
        start = time.time()

        while time.time() - start < MAX_WAIT:
            task = cq("tasks:getById", {"taskId": task_id})
            if not task:
                time.sleep(POLL_INTERVAL)
                continue

            steps = _poll_steps(task_id)
            elapsed = int(time.time() - start)
            _print_status(elapsed, task.get("status", "?"), steps)

            if task.get("status") in ("crashed", "failed", "deleted"):
                errors = [
                    f"{s.get('title')}: {s.get('error_message', '?')}"
                    for s in steps if s.get("status") in ("crashed", "failed")
                ]
                pytest.fail(f"Task {task['status']} in phase 1. Errors: {errors}")

            human_step = _find_step(steps, key="approve", status="waiting_human")
            if human_step:
                human_step_id = human_step["id"]
                print(f"  [{elapsed}s] Human step reached waiting_human — accepting now")
                break

            time.sleep(POLL_INTERVAL)
        else:
            pytest.fail(f"Timeout: human step never reached waiting_human after {MAX_WAIT}s")

        # Phase 2: Accept the human step
        cm("steps:acceptHumanStep", {"step_id": human_step_id})
        print(f"  Human step accepted (id={human_step_id})")

        # Phase 3: Wait for task to complete (finalize step should dispatch and finish)
        start2 = time.time()
        final_status = None
        final_steps = []

        while time.time() - start2 < MAX_WAIT:
            task = cq("tasks:getById", {"taskId": task_id})
            if not task:
                time.sleep(POLL_INTERVAL)
                continue

            status = task.get("status", "unknown")
            steps = _poll_steps(task_id)
            elapsed = int(time.time() - start2)
            _print_status(elapsed, status, steps)

            if status == "done":
                final_status = status
                final_steps = steps
                break

            if status in ("crashed", "failed", "deleted"):
                errors = [
                    f"{s.get('title')}: {s.get('error_message', '?')}"
                    for s in steps if s.get("status") in ("crashed", "failed")
                ]
                pytest.fail(f"Task {status} in phase 3. Errors: {errors}")

            time.sleep(POLL_INTERVAL)
        else:
            steps = _poll_steps(task_id)
            step_info = ", ".join(
                f"{s.get('title')}={s.get('status')}" for s in steps
            )
            pytest.fail(
                f"Timeout: task not done after {MAX_WAIT}s post-accept. "
                f"Steps: {step_info}"
            )

        assert final_status == "done"
        assert len(final_steps) == 3

        # Verify all steps completed
        for step in final_steps:
            assert step["status"] == "completed", (
                f"Step '{step.get('title')}' is {step['status']}, expected completed"
            )

        # Verify the finalize step actually ran after the human gate
        finalize_step = _find_step(final_steps, key="finalize")
        assert finalize_step is not None
        assert finalize_step["status"] == "completed"

        approve_step = _find_step(final_steps, key="approve")
        assert approve_step is not None
        assert approve_step["status"] == "completed"

        print(f"\n  SUCCESS: All 3 steps completed, task is done.")
