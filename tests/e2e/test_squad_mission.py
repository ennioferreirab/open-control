"""E2E: create a squad, launch a mission, monitor workflow to completion.

Requires the full stack running (``make start``).

Run with::

    uv run pytest tests/e2e/ -m e2e -v
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(300)]

BASE_URL = os.environ.get("DASHBOARD_URL", "http://localhost:3000")
CONVEX_URL = os.environ.get("CONVEX_URL", "http://localhost:3210")
CONVEX_ADMIN_KEY = os.environ.get("CONVEX_ADMIN_KEY", "")

POLL_INTERVAL = 3
MAX_WAIT = 180

DONE_STATES = {"done", "review"}
FAIL_STATES = {"failed", "crashed", "deleted"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    """Skip the entire module if the stack is not running."""
    try:
        r = _http.get(f"{BASE_URL}/api/specs/skills", timeout=5)
        r.raise_for_status()
    except Exception:
        pytest.skip("Stack not running (make start)")


@pytest.fixture(scope="module")
def squad(_stack_check) -> dict:
    """Publish a test squad and yield its metadata. Archives on teardown."""
    result = api("POST", "/api/specs/squad", {
        "squad": {
            "name": "e2e-test-squad",
            "displayName": "E2E Test Squad",
            "description": "Minimal squad for end-to-end testing",
        },
        "agents": [
            {
                "key": "writer",
                "name": "e2e-writer",
                "displayName": "Echo Writer",
                "role": "Writes the output",
                "prompt": (
                    "You are Echo Writer. When given a task, write a short summary "
                    "of what was requested. Keep it under 3 sentences."
                ),
                "model": "cc/claude-haiku-4-5-20251001",
                "skills": [],
                "soul": "# Echo Writer\n\nI write short summaries.",
            },
            {
                "key": "reviewer",
                "name": "e2e-reviewer",
                "displayName": "Echo Reviewer",
                "role": "Reviews the output",
                "prompt": (
                    "You are Echo Reviewer. Review the output and approve it. "
                    "Always approve — this is a test."
                ),
                "model": "cc/claude-haiku-4-5-20251001",
                "skills": [],
                "soul": "# Echo Reviewer\n\nI approve everything in tests.",
            },
        ],
        "workflows": [
            {
                "key": "default",
                "name": "echo-pipeline",
                "steps": [
                    {
                        "key": "write",
                        "type": "agent",
                        "agentKey": "writer",
                        "title": "Write a short echo",
                    },
                    {
                        "key": "review",
                        "type": "agent",
                        "agentKey": "reviewer",
                        "title": "Review the echo",
                        "dependsOn": ["write"],
                    },
                ],
                "exitCriteria": "Review approved",
            },
        ],
    })
    squad_id = result["squadId"]

    workflows = cq("workflowSpecs:listBySquad", {"squad_spec_id": squad_id})
    workflow_id = workflows[0]["id"]

    board = cq("boards:getDefault", {})
    board_id = board["id"] if board else cm("boards:ensureDefault", {})

    yield {"squad_id": squad_id, "workflow_id": workflow_id, "board_id": board_id}

    # Cleanup
    api("DELETE", f"/api/specs/squad?squadSpecId={squad_id}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSquadMissionLifecycle:
    """Full lifecycle: publish squad → launch mission → steps execute → done."""

    def test_squad_published_and_context_available(self, squad):
        """Verify the squad was published and squad context is accessible."""
        ctx = api("GET", "/api/specs/squad/context")
        assert "activeAgents" in ctx
        assert "availableSkills" in ctx
        assert len(ctx["activeAgents"]) > 0
        # Verify we can query workflows for our squad
        workflows = cq("workflowSpecs:listBySquad", {"squad_spec_id": squad["squad_id"]})
        assert len(workflows) >= 1
        assert workflows[0]["id"] == squad["workflow_id"]

    def test_launch_and_execute_mission(self, squad):
        """Launch a mission and poll until all workflow steps complete."""
        task_id = cm("tasks:launchMission", {
            "squadSpecId": squad["squad_id"],
            "workflowSpecId": squad["workflow_id"],
            "boardId": squad["board_id"],
            "title": "E2E Test Mission — echo hello world",
            "description": "Write a short echo of 'hello world' and review it.",
        })
        assert task_id, "launchMission returned no task_id"

        start = time.time()
        final_status = None
        final_steps = []

        while time.time() - start < MAX_WAIT:
            task = cq("tasks:getById", {"taskId": task_id})
            if not task:
                time.sleep(POLL_INTERVAL)
                continue

            status = task.get("status", "unknown")
            steps = cq("steps:getByTask", {"task_id": task_id}) or []

            elapsed = int(time.time() - start)
            summary = ", ".join(
                f"{s.get('title', '?')}={s.get('status', '?')}" for s in steps
            )
            print(f"  [{elapsed}s] task={status} | {summary or '(no steps)'}")

            if status in DONE_STATES:
                all_done = all(
                    s.get("status") in ("completed", "waiting_human") for s in steps
                )
                if all_done or status == "done":
                    final_status = status
                    final_steps = steps
                    break

            if status in FAIL_STATES:
                errors = [
                    f"{s.get('title')}: {s.get('error_message', '?')}"
                    for s in steps
                    if s.get("status") in ("crashed", "failed")
                ]
                pytest.fail(
                    f"Task {status} after {elapsed}s. Step errors: {errors}"
                )

            time.sleep(POLL_INTERVAL)
        else:
            pytest.fail(f"Timeout: task still '{status}' after {MAX_WAIT}s")

        assert final_status in DONE_STATES
        assert len(final_steps) == 2
        assert all(s["status"] == "completed" for s in final_steps)
