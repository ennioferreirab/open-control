"""Force a real ask_user pause on a live workflow step and validate thread routing.

Unlike provider-level repro scripts, this drives the interaction layer directly
against the live Convex + gateway stack. No mocks, no Playwright.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from typing import Any

from mc.bridge import ConvexBridge
from mc.contexts.interaction.service import InteractionService
from mc.contexts.interaction.types import InteractionContext

DEFAULT_CONVEX_URL = "http://127.0.0.1:3210"
SQUAD_DISPLAY_NAME = "POV Proposal Squad"
MISSION_TITLE_PREFIX = "Forced ask_user flow"
REPLY_TEXT = "isso e apenas um teste. pode preencher qualquer coisa"
RUNNING_STEP_TIMEOUT_SECONDS = 120
QUESTION_TIMEOUT_SECONDS = 30
RESUME_TIMEOUT_SECONDS = 30
POLL_INTERVAL_SECONDS = 1.5


def _bridge() -> ConvexBridge:
    convex_url = (
        os.environ.get("CONVEX_URL")
        or os.environ.get("NEXT_PUBLIC_CONVEX_URL")
        or DEFAULT_CONVEX_URL
    )
    return ConvexBridge(
        deployment_url=convex_url,
        admin_key=os.environ.get("CONVEX_ADMIN_KEY"),
    )


def _print(label: str, payload: Any) -> None:
    print(f"{label}={json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)}", flush=True)


def _resolve_squad(bridge: ConvexBridge) -> tuple[str, str]:
    squads = bridge.query("squadSpecs:list", {}) or []
    for squad in squads:
        if squad.get("display_name") == SQUAD_DISPLAY_NAME and squad.get("status") == "published":
            squad_id = squad.get("id") or squad.get("_id")
            workflow_spec_id = squad.get("default_workflow_spec_id")
            if squad_id and workflow_spec_id:
                return str(squad_id), str(workflow_spec_id)
    raise RuntimeError(f"Published squad not found: {SQUAD_DISPLAY_NAME}")


def _resolve_default_board(bridge: ConvexBridge) -> str:
    board = bridge.query("boards:getDefault", {})
    board_id = (board or {}).get("id") or (board or {}).get("_id")
    if not board_id:
        raise RuntimeError("Default board not found")
    return str(board_id)


def _launch_and_kickoff(bridge: ConvexBridge) -> str:
    squad_spec_id, workflow_spec_id = _resolve_squad(bridge)
    board_id = _resolve_default_board(bridge)
    task_id = bridge.mutation(
        "tasks:launchMission",
        {
            "squad_spec_id": squad_spec_id,
            "workflow_spec_id": workflow_spec_id,
            "board_id": board_id,
            "title": f"{MISSION_TITLE_PREFIX} {datetime.now().strftime('%H:%M:%S')}",
            "description": "Live runtime validation of ask_user data flow.",
        },
    )
    task = bridge.query("tasks:getById", {"task_id": task_id}) or {}
    bridge.mutation(
        "tasks:approveAndKickOff",
        {
            "task_id": task_id,
            "execution_plan": task.get("execution_plan"),
        },
    )
    return str(task_id)


def _messages(bridge: ConvexBridge, task_id: str) -> list[dict[str, Any]]:
    messages = bridge.query("messages:listByTask", {"task_id": task_id}) or []
    return sorted(
        messages,
        key=lambda item: (str(item.get("timestamp") or ""), float(item.get("creation_time") or 0)),
    )


def _wait_for_running_step(bridge: ConvexBridge, task_id: str) -> dict[str, Any]:
    deadline = time.time() + RUNNING_STEP_TIMEOUT_SECONDS
    while time.time() < deadline:
        steps = bridge.query("steps:getByTask", {"task_id": task_id}) or []
        for step in steps:
            if step.get("status") == "running":
                return step
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Timed out waiting for a running step on task {task_id}")


def _wait_for_question(bridge: ConvexBridge, task_id: str) -> dict[str, Any]:
    deadline = time.time() + QUESTION_TIMEOUT_SECONDS
    while time.time() < deadline:
        question = bridge.query("executionQuestions:getPendingForTask", {"task_id": task_id})
        if question:
            return question
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Timed out waiting for execution question on task {task_id}")


def _lead_agent_messages(messages: list[dict[str, Any]], since: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for message in messages:
        if str(message.get("timestamp") or "") < since:
            continue
        if message.get("author_name") != "lead-agent":
            continue
        if message.get("type") in {"lead_agent_plan", "lead_agent_chat"}:
            result.append(message)
    return result


def main() -> int:
    bridge = _bridge()
    task_id = _launch_and_kickoff(bridge)
    print(f"task_id={task_id}", flush=True)

    running_step = _wait_for_running_step(bridge, task_id)
    _print("running_step", running_step)

    context = InteractionContext(
        session_id=f"forced-{task_id}-{running_step['id']}",
        task_id=task_id,
        step_id=str(running_step["id"]),
        agent_name=str(running_step.get("assigned_agent") or "offer-strategist"),
        provider="claude-code",
    )
    interaction_service = InteractionService(bridge)
    failures: list[str] = []
    answer_holder: dict[str, str] = {}

    def _ask() -> None:
        answer_holder["answer"] = interaction_service.ask_user(
            context=context,
            questions=[
                {
                    "header": "Sobre a Easy",
                    "id": "industry",
                    "question": "Qual e o setor da Easy?",
                    "options": [
                        {"label": "E-commerce", "description": "Venda online"},
                        {"label": "Fintech", "description": "Pagamentos e servicos financeiros"},
                        {"label": "Outro", "description": "Descreva o setor"},
                    ],
                }
            ],
        )

    ask_started_at = datetime.utcnow().isoformat()
    ask_thread = threading.Thread(target=_ask, daemon=True)
    ask_thread.start()

    pending_question = _wait_for_question(bridge, task_id)
    task_when_paused = bridge.query("tasks:getById", {"task_id": task_id}) or {}
    messages_when_paused = _messages(bridge, task_id)
    leaked_before_reply = _lead_agent_messages(messages_when_paused, ask_started_at)

    _print("task_when_paused", task_when_paused)
    _print("pending_question", pending_question)
    _print(
        "messages_when_paused",
        [
            {
                "timestamp": message.get("timestamp"),
                "author_name": message.get("author_name"),
                "type": message.get("type"),
                "message_type": message.get("message_type"),
                "content_preview": str(message.get("content") or "")[:160],
            }
            for message in messages_when_paused
        ],
    )

    if task_when_paused.get("awaiting_kickoff") is True:
        failures.append("task.awaiting_kickoff remained true during ask_user pause")
    if leaked_before_reply:
        failures.append("lead-agent emitted plan/chat messages during ask_user pause")

    reply_sent_at = datetime.utcnow().isoformat()
    bridge.mutation(
        "messages:postUserReply",
        {
            "task_id": task_id,
            "content": REPLY_TEXT,
        },
    )

    deadline = time.time() + RESUME_TIMEOUT_SECONDS
    while time.time() < deadline:
        if not ask_thread.is_alive():
            break
        time.sleep(POLL_INTERVAL_SECONDS)
    ask_thread.join(timeout=1)

    task_after_reply = bridge.query("tasks:getById", {"task_id": task_id}) or {}
    messages_after_reply = _messages(bridge, task_id)
    leaked_after_reply = _lead_agent_messages(messages_after_reply, reply_sent_at)

    _print("task_after_reply", task_after_reply)
    _print("answer_holder", answer_holder)
    _print(
        "messages_after_reply",
        [
            {
                "timestamp": message.get("timestamp"),
                "author_name": message.get("author_name"),
                "type": message.get("type"),
                "message_type": message.get("message_type"),
                "content_preview": str(message.get("content") or "")[:160],
            }
            for message in messages_after_reply
            if str(message.get("timestamp") or "") >= reply_sent_at
        ],
    )

    if ask_thread.is_alive():
        failures.append("ask_user did not resume after postUserReply")
    if answer_holder.get("answer") != REPLY_TEXT:
        failures.append("ask_user did not receive the plain user reply")
    if leaked_after_reply:
        failures.append("lead-agent emitted plan/chat messages after plain user reply")

    if failures:
        print("result=FAIL", flush=True)
        for failure in failures:
            print(f"failure={failure}", flush=True)
        return 1

    print("result=PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
