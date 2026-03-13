from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mc.runtime.nanobot_interactive_session import (
    NanobotInteractiveSessionConfig,
    NanobotInteractiveSessionRunner,
)


@dataclass
class _FakeLoop:
    replies: list[str]

    async def process_direct(
        self,
        content: str,
        session_key: str,
        *,
        channel: str,
        chat_id: str,
        task_id: str,
        on_progress=None,
    ) -> str:
        if on_progress is not None:
            await on_progress(f"Handling {content}", tool_hint=False)
        return self.replies.pop(0)


class _SequencedInput:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def readline(self) -> str:
        if not self._responses:
            return ""
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_runner_records_initial_result_and_keeps_repl_open() -> None:
    bridge = MagicMock()
    bridge.query.side_effect = [{"session_id": "interactive_session:mc"}]
    supervisor = MagicMock()
    output = StringIO()
    fake_loop = _FakeLoop(["Follow-up answer"])

    async def fake_run_turn(**kwargs):
        assert kwargs["agent_name"] == "nanobot-pair"
        assert kwargs["task_title"] == "Validate Live parity"
        assert kwargs["task_description"] == "Confirm Nanobot uses the interactive runtime."
        assert kwargs["memory_workspace"] == Path("/tmp/memory")
        return (
            "Initial answer",
            "mc:session-1",
            fake_loop,
        )

    runner = NanobotInteractiveSessionRunner(
        config=NanobotInteractiveSessionConfig(
            session_id="interactive_session:mc",
            task_id="task-123",
            agent_name="nanobot-pair",
            agent_prompt="Stay concise.",
            task_prompt=(
                "Step: Validate Live parity\n\nConfirm Nanobot uses the interactive runtime."
            ),
            board_name="default",
            memory_workspace=Path("/tmp/memory"),
        ),
        bridge=bridge,
        supervisor=supervisor,
        run_initial_turn=fake_run_turn,
        stdin=StringIO("/exit\n"),
        stdout=output,
        registration_poll_interval=0,
    )

    code = await runner.run()

    assert code == 0
    assert "Initial answer" in output.getvalue()
    kinds = [call.args[0].kind for call in supervisor.handle_event.call_args_list]
    assert "session_ready" in kinds
    assert "turn_completed" in kinds
    supervisor.record_final_result.assert_called_with(
        session_id="interactive_session:mc",
        content="Initial answer",
        source="mc-runtime",
    )


@pytest.mark.asyncio
async def test_runner_emits_failure_event_when_initial_turn_crashes() -> None:
    bridge = MagicMock()
    bridge.query.side_effect = [{"session_id": "interactive_session:mc"}]
    supervisor = MagicMock()
    output = StringIO()

    async def fake_run_turn(**kwargs):
        raise RuntimeError("provider exploded")

    runner = NanobotInteractiveSessionRunner(
        config=NanobotInteractiveSessionConfig(
            session_id="interactive_session:mc",
            task_id="task-123",
            agent_name="nanobot-pair",
        ),
        bridge=bridge,
        supervisor=supervisor,
        run_initial_turn=fake_run_turn,
        stdin=StringIO(""),
        stdout=output,
        registration_poll_interval=0,
    )

    code = await runner.run()

    assert code == 1
    assert "provider exploded" in output.getvalue()
    kinds = [call.args[0].kind for call in supervisor.handle_event.call_args_list]
    assert "session_failed" in kinds


@pytest.mark.asyncio
async def test_runner_keeps_session_alive_across_initial_eof_until_user_attaches() -> None:
    bridge = MagicMock()
    bridge.query.side_effect = [{"session_id": "interactive_session:mc"}]
    supervisor = MagicMock()
    output = StringIO()

    async def fake_run_turn(**kwargs):
        return (
            "Initial answer",
            "mc:session-1",
            _FakeLoop(["Follow-up answer"]),
        )

    runner = NanobotInteractiveSessionRunner(
        config=NanobotInteractiveSessionConfig(
            session_id="interactive_session:mc",
            task_id="task-123",
            agent_name="nanobot-pair",
        ),
        bridge=bridge,
        supervisor=supervisor,
        run_initial_turn=fake_run_turn,
        stdin=_SequencedInput(["", "/exit\n"]),
        stdout=output,
        registration_poll_interval=0,
        repl_idle_poll_seconds=0,
    )

    code = await runner.run()

    assert code == 0
    assert "Session ready. Type /exit to close Live." in output.getvalue()
