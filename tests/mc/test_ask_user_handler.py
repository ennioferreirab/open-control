"""Tests for the unified AskUserHandler."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from mc.contexts.conversation.ask_user.handler import AskUserHandler


async def _wait_for_pending_request(handler: AskUserHandler, *, timeout: float = 1.0) -> str:
    """Wait until handler has a pending request and return its request_id."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if handler._pending_ask:
            return next(iter(handler._pending_ask.keys()))
        await asyncio.sleep(0.01)
    raise AssertionError("Timed out waiting for pending ask request")


@pytest.mark.asyncio
async def test_deliver_user_reply_resolves_future() -> None:
    handler = AskUserHandler()
    request_id = "req-123"
    task_id = "task-abc"
    future = asyncio.get_running_loop().create_future()
    handler._pending_ask[request_id] = future
    handler._task_to_request[task_id] = request_id

    handler.deliver_user_reply(task_id, "Yes")

    assert future.done()
    assert future.result() == "Yes"


@pytest.mark.asyncio
async def test_ask_posts_question_and_waits() -> None:
    handler = AskUserHandler()
    bridge = MagicMock()
    bridge.send_message = MagicMock(return_value=None)
    bridge.update_task_status = MagicMock(return_value=None)
    bridge.transition_task_from_snapshot = MagicMock(return_value={"kind": "applied"})
    bridge.update_step_status = MagicMock(return_value=None)
    bridge.get_task = MagicMock(
        side_effect=[
            {"id": "task-1", "status": "in_progress", "state_version": 3},
            {"id": "task-1", "status": "review", "state_version": 4},
        ]
    )
    bridge.get_steps_by_task = MagicMock(return_value=[{"id": "step-1", "status": "running"}])

    ask_task = asyncio.create_task(
        handler.ask(
            question="What color?",
            options=["Blue", "Green"],
            agent_name="agent-x",
            task_id="task-1",
            bridge=bridge,
        )
    )

    await _wait_for_pending_request(handler)
    handler.deliver_user_reply("task-1", "Blue")

    answer = await asyncio.wait_for(ask_task, timeout=2)
    assert answer == "Blue"

    bridge.send_message.assert_called_once()
    send_call = bridge.send_message.call_args
    assert send_call[0][0] == "task-1"
    assert send_call[0][1] == "agent-x"
    assert send_call[0][2] == "agent"
    assert send_call[0][4] == "work"
    assert "**agent-x is asking:**" in send_call[0][3]
    assert "What color?" in send_call[0][3]
    assert "1. Blue" in send_call[0][3]
    assert "2. Green" in send_call[0][3]

    assert bridge.transition_task_from_snapshot.call_count == 2
    assert bridge.transition_task_from_snapshot.call_args_list[0].args[1] == "review"
    assert bridge.transition_task_from_snapshot.call_args_list[1].args[1] == "in_progress"
    assert bridge.transition_task_from_snapshot.call_args_list[0].kwargs["review_phase"] == (
        "execution_pause"
    )
    assert (
        bridge.transition_task_from_snapshot.call_args_list[0].kwargs["awaiting_kickoff"] is False
    )
    assert bridge.update_step_status.call_args_list[0][0] == ("step-1", "waiting_human")
    assert bridge.update_step_status.call_args_list[1][0] == ("step-1", "running")
    assert bridge.create_activity.call_args_list[0][0] == (
        "review_requested",
        "Interactive session paused for review for @agent-x.",
        "task-1",
        "agent-x",
    )
    assert bridge.create_activity.call_args_list[1][0] == (
        "step_started",
        "Interactive session resumed after user reply for @agent-x.",
        "task-1",
        "agent-x",
    )


@pytest.mark.asyncio
async def test_ask_without_options() -> None:
    handler = AskUserHandler()
    bridge = MagicMock()
    bridge.send_message = MagicMock(return_value=None)
    bridge.update_task_status = MagicMock(return_value=None)
    bridge.transition_task_from_snapshot = MagicMock(return_value={"kind": "applied"})
    bridge.update_step_status = MagicMock(return_value=None)
    bridge.get_task = MagicMock(
        side_effect=[
            {"id": "task-2", "status": "in_progress", "state_version": 1},
            {"id": "task-2", "status": "review", "state_version": 2},
        ]
    )
    bridge.get_steps_by_task = MagicMock(return_value=[])

    ask_task = asyncio.create_task(
        handler.ask(
            question="Proceed?",
            options=None,
            agent_name="agent-y",
            task_id="task-2",
            bridge=bridge,
        )
    )

    await _wait_for_pending_request(handler)
    handler.deliver_user_reply("task-2", "Yes")

    answer = await asyncio.wait_for(ask_task, timeout=2)
    assert answer == "Yes"

    sent_content = bridge.send_message.call_args[0][3]
    assert "Proceed?" in sent_content
    assert "Options:" not in sent_content


@pytest.mark.asyncio
async def test_ask_cleanup_on_exception() -> None:
    handler = AskUserHandler()
    bridge = MagicMock()
    bridge.send_message = MagicMock(return_value=None)
    bridge.update_task_status = MagicMock(return_value=None)
    bridge.transition_task_from_snapshot = MagicMock(return_value={"kind": "applied"})
    bridge.update_step_status = MagicMock(return_value=None)
    bridge.get_task = MagicMock(
        return_value={"id": "task-3", "status": "in_progress", "state_version": 1}
    )
    bridge.get_steps_by_task = MagicMock(return_value=[])

    ask_task = asyncio.create_task(
        handler.ask(
            question="Will fail?",
            options=None,
            agent_name="agent-z",
            task_id="task-3",
            bridge=bridge,
        )
    )

    request_id = await _wait_for_pending_request(handler)
    handler._pending_ask[request_id].set_exception(RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        await asyncio.wait_for(ask_task, timeout=2)

    assert request_id not in handler._pending_ask
    assert "task-3" not in handler._task_to_request


@pytest.mark.asyncio
async def test_ask_posts_structured_questionnaire() -> None:
    handler = AskUserHandler()
    bridge = MagicMock()
    bridge.send_message = MagicMock(return_value=None)
    bridge.update_task_status = MagicMock(return_value=None)
    bridge.transition_task_from_snapshot = MagicMock(return_value={"kind": "applied"})
    bridge.update_step_status = MagicMock(return_value=None)
    bridge.get_task = MagicMock(
        side_effect=[
            {"id": "task-q", "status": "in_progress", "state_version": 5},
            {"id": "task-q", "status": "review", "state_version": 6},
        ]
    )
    bridge.get_steps_by_task = MagicMock(return_value=[{"id": "step-q", "status": "running"}])

    questions = [
        {
            "header": "Goal",
            "id": "goal",
            "question": "What is the main goal?",
            "options": [
                {"label": "Ship", "description": "Ship as fast as possible."},
                {"label": "Polish", "description": "Improve quality first."},
                {"label": "Learn", "description": "Explore before committing."},
            ],
        },
        {
            "header": "Audience",
            "id": "audience",
            "question": "Who is this for?",
            "options": [
                {"label": "Internal", "description": "Internal team only."},
                {"label": "Beta", "description": "Small external beta."},
                {"label": "Public", "description": "General availability."},
            ],
        },
    ]

    ask_task = asyncio.create_task(
        handler.ask(
            question=None,
            options=None,
            questions=questions,
            agent_name="agent-q",
            task_id="task-q",
            bridge=bridge,
        )
    )

    await _wait_for_pending_request(handler)
    handler.deliver_user_reply("task-q", '{"goal":"Ship","audience":"Public"}')

    answer = await asyncio.wait_for(ask_task, timeout=2)
    assert answer == '{"goal":"Ship","audience":"Public"}'

    sent_content = bridge.send_message.call_args[0][3]
    assert "Questionnaire" in sent_content
    assert "Goal" in sent_content
    assert "1. Ship" in sent_content
    assert "4. Other" in sent_content
    assert "Audience" in sent_content
    assert bridge.update_step_status.call_args_list[0][0] == ("step-q", "waiting_human")
    assert bridge.update_step_status.call_args_list[1][0] == ("step-q", "running")
