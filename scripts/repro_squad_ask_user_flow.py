"""Run a real squad mission and validate the ask_user thread flow end-to-end.

This script uses the live local Convex + gateway stack. It does not use mocks.

Flow:
1. Resolve the published "POV Proposal Squad" and its default workflow.
2. Launch a fresh mission on the default board.
3. Approve + kick off the mission.
4. Poll until the first agent opens an execution question.
5. Assert that the task is paused in review with awaiting_kickoff=False.
6. Assert that no lead-agent plan/chat message was injected after the ask_user pause.
7. Reply as the user through messages:postUserReply.
8. Poll until the question is answered and the task resumes.

Example:
    uv run python scripts/repro_squad_ask_user_flow.py
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from mc.bridge import ConvexBridge

DEFAULT_CONVEX_URL = "http://127.0.0.1:3210"
SQUAD_DISPLAY_NAME = "POV Proposal Squad"
MISSION_TITLE_PREFIX = "E2E ask_user flow"
REPLY_TEXT = "isso e apenas um teste. pode preencher qualquer coisa"
ASK_USER_TIMEOUT_SECONDS = 120
RESUME_TIMEOUT_SECONDS = 120
POLL_INTERVAL_SECONDS = 2


@dataclass
class MissionContext:
    task_id: str
    squad_spec_id: str
    workflow_spec_id: str
    board_id: str
    approval_timestamp: str


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _bridge() -> ConvexBridge:
    convex_url = (
        os.environ.get("CONVEX_URL")
        or os.environ.get("NEXT_PUBLIC_CONVEX_URL")
        or DEFAULT_CONVEX_URL
    )
    admin_key = os.environ.get("CONVEX_ADMIN_KEY")
    return ConvexBridge(deployment_url=convex_url, admin_key=admin_key)


def _resolve_squad(bridge: ConvexBridge) -> tuple[str, str]:
    squads = bridge.query("squadSpecs:list", {}) or []
    for squad in squads:
        if squad.get("display_name") == SQUAD_DISPLAY_NAME and squad.get("status") == "published":
            workflow_spec_id = squad.get("default_workflow_spec_id")
            if not workflow_spec_id:
                raise RuntimeError(f"{SQUAD_DISPLAY_NAME!r} has no default workflow")
            squad_id = squad.get("id") or squad.get("_id")
            if not squad_id:
                raise RuntimeError(f"{SQUAD_DISPLAY_NAME!r} returned without an id")
            return str(squad_id), str(workflow_spec_id)
    raise RuntimeError(f"Published squad not found: {SQUAD_DISPLAY_NAME}")


def _resolve_default_board(bridge: ConvexBridge) -> str:
    board = bridge.query("boards:getDefault", {})
    if not board:
        raise RuntimeError("Default board not found")
    board_id = board.get("id") or board.get("_id")
    if not board_id:
        raise RuntimeError("Default board returned without an id")
    return str(board_id)


def _launch_mission(bridge: ConvexBridge) -> MissionContext:
    squad_spec_id, workflow_spec_id = _resolve_squad(bridge)
    board_id = _resolve_default_board(bridge)
    title = f"{MISSION_TITLE_PREFIX} {datetime.now().strftime('%H:%M:%S')}"
    task_id = bridge.mutation(
        "tasks:launchMission",
        {
            "squad_spec_id": squad_spec_id,
            "workflow_spec_id": workflow_spec_id,
            "board_id": board_id,
            "title": title,
            "description": "Scripted end-to-end validation of ask_user thread routing.",
        },
    )
    task = bridge.query("tasks:getById", {"task_id": task_id})
    execution_plan = task.get("execution_plan")
    if not execution_plan:
        raise RuntimeError(f"Task {task_id} launched without execution_plan")
    approval_timestamp = _utcnow()
    bridge.mutation(
        "tasks:approveAndKickOff",
        {
            "task_id": task_id,
            "execution_plan": execution_plan,
        },
    )
    return MissionContext(
        task_id=str(task_id),
        squad_spec_id=squad_spec_id,
        workflow_spec_id=workflow_spec_id,
        board_id=board_id,
        approval_timestamp=approval_timestamp,
    )


def _messages_for_task(bridge: ConvexBridge, task_id: str) -> list[dict[str, Any]]:
    messages = bridge.query("messages:listByTask", {"task_id": task_id}) or []
    return sorted(
        messages,
        key=lambda item: (
            item.get("timestamp") or "",
            float(item.get("_creation_time") or 0),
        ),
    )


def _steps_for_task(bridge: ConvexBridge, task_id: str) -> list[dict[str, Any]]:
    return bridge.query("steps:getByTask", {"task_id": task_id}) or []


def _find_ask_user_message(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    for message in reversed(messages):
        if message.get("author_name") != "offer-strategist":
            continue
        content = str(message.get("content") or "")
        if "is asking:" in content and "Questionnaire" in content:
            return message
    return None


def _lead_agent_messages_since(
    messages: list[dict[str, Any]],
    *,
    since_timestamp: str,
) -> list[dict[str, Any]]:
    leaked: list[dict[str, Any]] = []
    for message in messages:
        timestamp = str(message.get("timestamp") or "")
        if timestamp < since_timestamp:
            continue
        if message.get("author_name") != "lead-agent":
            continue
        if message.get("type") == "lead_agent_chat":
            leaked.append(message)
    return leaked


def _wait_for_pending_question(
    bridge: ConvexBridge,
    task_id: str,
    *,
    timeout_seconds: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        task = bridge.query("tasks:getById", {"task_id": task_id}) or {}
        messages = _messages_for_task(bridge, task_id)
        ask_message = _find_ask_user_message(messages)
        question = bridge.query("executionQuestions:getPendingForTask", {"task_id": task_id})
        if question and ask_message:
            return task, question, ask_message
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Timed out waiting for ask_user on task {task_id}")


def _wait_for_resume(bridge: ConvexBridge, task_id: str, *, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        task = bridge.query("tasks:getById", {"task_id": task_id}) or {}
        pending_question = bridge.query(
            "executionQuestions:getPendingForTask", {"task_id": task_id}
        )
        if not pending_question and task.get("status") in {"in_progress", "review", "done"}:
            return task
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Timed out waiting for task {task_id} to resume")


def _print_json(label: str, payload: Any) -> None:
    print(f"{label}={json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)}")


def main() -> int:
    bridge = _bridge()
    mission = _launch_mission(bridge)
    print(f"task_id={mission.task_id}")
    print(f"squad_spec_id={mission.squad_spec_id}")
    print(f"workflow_spec_id={mission.workflow_spec_id}")

    task, question, ask_message = _wait_for_pending_question(
        bridge,
        mission.task_id,
        timeout_seconds=ASK_USER_TIMEOUT_SECONDS,
    )
    messages = _messages_for_task(bridge, mission.task_id)
    steps = _steps_for_task(bridge, mission.task_id)
    leaked_before_reply = _lead_agent_messages_since(
        messages,
        since_timestamp=mission.approval_timestamp,
    )

    _print_json("task_when_asked", task)
    _print_json("pending_question", question)
    _print_json("ask_message", ask_message)
    _print_json("steps_when_asked", steps)
    _print_json(
        "messages_after_approval",
        [
            {
                "timestamp": message.get("timestamp"),
                "author_name": message.get("author_name"),
                "type": message.get("type"),
                "content_preview": str(message.get("content") or "")[:140],
            }
            for message in messages
            if str(message.get("timestamp") or "") >= mission.approval_timestamp
        ],
    )

    failures: list[str] = []
    if task.get("awaiting_kickoff") is True:
        failures.append("task.awaiting_kickoff stayed true after ask_user pause")
    if task.get("status") != "review":
        failures.append(
            f"task.status expected 'review' during ask_user, got {task.get('status')!r}"
        )
    if leaked_before_reply:
        failures.append("lead-agent posted review/plan messages during ask_user pause")

    bridge.mutation(
        "messages:postUserReply",
        {
            "task_id": mission.task_id,
            "content": REPLY_TEXT,
        },
    )
    reply_timestamp = _utcnow()

    resumed_task = _wait_for_resume(
        bridge,
        mission.task_id,
        timeout_seconds=RESUME_TIMEOUT_SECONDS,
    )
    messages_after_reply = _messages_for_task(bridge, mission.task_id)
    leaked_after_reply = _lead_agent_messages_since(
        messages_after_reply,
        since_timestamp=reply_timestamp,
    )

    _print_json("task_after_reply", resumed_task)
    _print_json(
        "messages_after_reply",
        [
            {
                "timestamp": message.get("timestamp"),
                "author_name": message.get("author_name"),
                "type": message.get("type"),
                "content_preview": str(message.get("content") or "")[:140],
            }
            for message in messages_after_reply
            if str(message.get("timestamp") or "") >= reply_timestamp
        ],
    )

    if leaked_after_reply:
        failures.append("lead-agent posted review/plan messages after plain user reply")

    if failures:
        print("result=FAIL")
        for failure in failures:
            print(f"failure={failure}")
        return 1

    print("result=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
