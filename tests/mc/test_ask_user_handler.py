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

    assert bridge.update_task_status.call_count == 2
    assert bridge.update_task_status.call_args_list[0][0][1] == "review"
    assert bridge.update_task_status.call_args_list[1][0][1] == "in_progress"


@pytest.mark.asyncio
async def test_ask_without_options() -> None:
    handler = AskUserHandler()
    bridge = MagicMock()
    bridge.send_message = MagicMock(return_value=None)
    bridge.update_task_status = MagicMock(return_value=None)

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
