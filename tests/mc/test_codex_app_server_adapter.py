from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from mc.contexts.interactive.adapters.codex import CodexInteractiveAdapter
from mc.contexts.interactive.adapters.codex_app_server import (
    CodexAppServerProtocolError,
    CodexAppServerSession,
    CodexSupervisionRelay,
)
from mc.contexts.interactive.errors import InteractiveSessionStartupError
from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.contexts.interactive.supervision_types import InteractiveSupervisionEvent
from mc.types import AgentData


def _identity() -> InteractiveSessionIdentity:
    return InteractiveSessionIdentity(
        provider="codex",
        agent_name="codex-pair",
        scope_kind="chat",
        scope_id="chat-123",
        surface="chat",
    )


def _agent(model: str = "openai-codex/gpt-5.4") -> AgentData:
    return AgentData(
        name="codex-pair",
        display_name="Codex Pair",
        role="Engineer",
        model=model,
        interactive_provider="codex",
    )


def test_codex_supervision_relay_maps_turn_and_item_events() -> None:
    sink = MagicMock()
    relay = CodexSupervisionRelay(
        session_id="interactive_session:codex",
        task_id="task-123",
        step_id="step-456",
        agent_name="codex-pair",
        sink=sink,
    )

    relay.process_message(
        {
            "method": "turn/started",
            "params": {
                "threadId": "thread-1",
                "turn": {"id": "turn-9", "summary": "Starting work"},
            },
        }
    )
    relay.process_message(
        {
            "method": "item/completed",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-9",
                "item": {"id": "item-2", "type": "exec_command"},
            },
        }
    )

    assert sink.handle_event.call_args_list == [
        call(
            InteractiveSupervisionEvent(
                kind="turn_started",
                session_id="interactive_session:codex",
                provider="codex",
                task_id="task-123",
                step_id="step-456",
                turn_id="turn-9",
                summary="Starting work",
                metadata={"thread_id": "thread-1"},
                agent_name="codex-pair",
            )
        ),
        call(
            InteractiveSupervisionEvent(
                kind="item_completed",
                session_id="interactive_session:codex",
                provider="codex",
                task_id="task-123",
                step_id="step-456",
                turn_id="turn-9",
                item_id="item-2",
                metadata={"thread_id": "thread-1", "item_type": "exec_command"},
                agent_name="codex-pair",
            )
        ),
    ]


def test_codex_supervision_relay_maps_approval_and_user_input_requests() -> None:
    sink = MagicMock()
    relay = CodexSupervisionRelay(
        session_id="interactive_session:codex",
        task_id="task-123",
        step_id="step-456",
        agent_name="codex-pair",
        sink=sink,
    )

    relay.process_message(
        {
            "id": 91,
            "method": "item/commandExecution/requestApproval",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-9",
                "itemId": "item-approval",
                "command": "git push",
                "reason": "Needs network access",
            },
        }
    )
    relay.process_message(
        {
            "id": 92,
            "method": "item/tool/requestUserInput",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-9",
                "itemId": "item-user-input",
                "questions": [
                    {
                        "header": "Target",
                        "id": "target_env",
                        "question": "Which environment should I deploy to?",
                        "options": [
                            {"label": "Dev", "description": "Fast iteration"},
                            {"label": "Staging", "description": "Pre-production"},
                            {"label": "Prod", "description": "Live users"},
                        ],
                    }
                ],
            },
        }
    )

    assert sink.handle_event.call_args_list == [
        call(
            InteractiveSupervisionEvent(
                kind="approval_requested",
                session_id="interactive_session:codex",
                provider="codex",
                task_id="task-123",
                step_id="step-456",
                turn_id="turn-9",
                item_id="item-approval",
                summary="Needs network access",
                metadata={
                    "thread_id": "thread-1",
                    "request_id": "91",
                    "method": "item/commandExecution/requestApproval",
                    "command": "git push",
                },
                agent_name="codex-pair",
            )
        ),
        call(
            InteractiveSupervisionEvent(
                kind="user_input_requested",
                session_id="interactive_session:codex",
                provider="codex",
                task_id="task-123",
                step_id="step-456",
                turn_id="turn-9",
                item_id="item-user-input",
                summary="Which environment should I deploy to?",
                metadata={
                    "thread_id": "thread-1",
                    "request_id": "92",
                    "method": "item/tool/requestUserInput",
                    "questions": [
                        {
                            "header": "Target",
                            "id": "target_env",
                            "question": "Which environment should I deploy to?",
                            "options": [
                                {"label": "Dev", "description": "Fast iteration"},
                                {"label": "Staging", "description": "Pre-production"},
                                {"label": "Prod", "description": "Live users"},
                            ],
                        }
                    ],
                },
                agent_name="codex-pair",
            )
        ),
    ]


def test_codex_supervision_relay_captures_final_answer_from_completed_agent_message() -> None:
    sink = MagicMock()
    relay = CodexSupervisionRelay(
        session_id="interactive_session:codex",
        task_id="task-123",
        step_id="step-456",
        agent_name="codex-pair",
        sink=sink,
    )

    relay.process_message(
        {
            "method": "item/completed",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-9",
                "item": {
                    "id": "item-answer",
                    "type": "agentMessage",
                    "phase": "final_answer",
                    "text": "Implemented the fix and verified the focused tests pass.",
                },
            },
        }
    )
    relay.process_message(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "thread-1",
                "turn": {"id": "turn-9", "status": "completed"},
            },
        }
    )

    final_event = sink.handle_event.call_args_list[-1].args[0]
    assert final_event.kind == "turn_completed"
    assert final_event.turn_id == "turn-9"
    assert final_event.final_output == "Implemented the fix and verified the focused tests pass."


def test_codex_supervision_relay_rejects_server_errors() -> None:
    relay = CodexSupervisionRelay(
        session_id="interactive_session:codex",
        task_id="task-123",
        step_id="step-456",
        agent_name="codex-pair",
        sink=MagicMock(),
    )

    with pytest.raises(CodexAppServerProtocolError, match="schema mismatch"):
        relay.process_message(
            {
                "method": "error",
                "params": {"message": "schema mismatch"},
            }
        )


@pytest.mark.asyncio
async def test_prepare_launch_starts_codex_app_server_supervision(tmp_path: Path) -> None:
    async def _start(**_: object) -> CodexAppServerSession:
        ready = asyncio.get_running_loop().create_future()
        ready.set_result(None)
        return CodexAppServerSession(
            session_id="interactive_session:codex",
            stop=MagicMock(),
            ready=ready,
        )

    adapter = CodexInteractiveAdapter(
        cli_path="codex",
        which=MagicMock(return_value="/opt/homebrew/bin/codex"),
        agents_dir=tmp_path,
        supervision_sink=MagicMock(),
        supervision_starter=_start,
    )

    launch = await adapter.prepare_launch(
        identity=_identity(),
        agent=_agent(),
        task_id="task-123",
    )

    assert launch.cwd == tmp_path / "codex-pair"
    assert "interactive-prompts" in launch.capabilities


@pytest.mark.asyncio
async def test_prepare_launch_surfaces_codex_supervision_startup_failure(tmp_path: Path) -> None:
    async def _fail(**_: object) -> CodexAppServerSession:
        raise InteractiveSessionStartupError("Codex app-server supervision failed: boom")

    adapter = CodexInteractiveAdapter(
        cli_path="codex",
        which=MagicMock(return_value="/opt/homebrew/bin/codex"),
        agents_dir=tmp_path,
        supervision_sink=MagicMock(),
        supervision_starter=_fail,
    )

    with pytest.raises(InteractiveSessionStartupError, match="Codex app-server supervision failed"):
        await adapter.prepare_launch(
            identity=_identity(),
            agent=_agent(),
            task_id="task-123",
        )
