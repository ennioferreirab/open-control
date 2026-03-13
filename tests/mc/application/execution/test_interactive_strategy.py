from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from mc.application.execution.request import (
    EntityType,
    ExecutionRequest,
    RunnerType,
)
from mc.application.execution.strategies.interactive import InteractiveTuiRunnerStrategy
from mc.types import AgentData


def _request(*, provider: str = "claude-code") -> ExecutionRequest:
    return ExecutionRequest(
        entity_type=EntityType.STEP,
        entity_id="step-456",
        task_id="task-123",
        step_id="step-456",
        title="Implement step",
        description="Do the work",
        agent_name="interactive-agent",
        agent=AgentData(
            name="interactive-agent",
            display_name="Interactive Agent",
            role="Engineer",
            model="claude-sonnet-4-6" if provider == "claude-code" else "openai-codex/gpt-5.4",
            backend="claude-code" if provider == "claude-code" else "nanobot",
            interactive_provider=provider,
        ),
        runner_type=RunnerType.INTERACTIVE_TUI,
    )


@pytest.mark.asyncio
async def test_execute_creates_backend_owned_interactive_session_and_waits_for_completion() -> None:
    coordinator = MagicMock()
    coordinator.create_or_attach = AsyncMock(
        return_value={"session_id": "interactive_session:claude", "attach_token": "attach-1"}
    )
    bridge = MagicMock()
    bridge.query.side_effect = [
        {
            "session_id": "interactive_session:claude",
            "last_event_kind": "turn_started",
            "supervision_state": "running",
            "summary": "Working",
        },
        {
            "session_id": "interactive_session:claude",
            "last_event_kind": "turn_completed",
            "supervision_state": "idle",
            "summary": "Implemented the requested step.",
            "final_result": "Implemented the requested step with passing tests.",
        },
    ]
    strategy = InteractiveTuiRunnerStrategy(
        bridge=bridge,
        session_coordinator=coordinator,
        poll_interval_seconds=0,
    )

    result = await strategy.execute(_request())

    assert result.success is True
    assert result.session_id == "interactive_session:claude"
    assert result.output == "Implemented the requested step with passing tests."
    coordinator.create_or_attach.assert_awaited_once()
    kwargs = coordinator.create_or_attach.await_args.kwargs
    assert kwargs["task_id"] == "task-123"
    assert kwargs["step_id"] == "step-456"


@pytest.mark.asyncio
async def test_execute_returns_error_when_supervision_reports_failure() -> None:
    coordinator = MagicMock()
    coordinator.create_or_attach = AsyncMock(
        return_value={"session_id": "interactive_session:claude", "attach_token": "attach-1"}
    )
    bridge = MagicMock()
    bridge.query.return_value = {
        "session_id": "interactive_session:claude",
        "last_event_kind": "session_failed",
        "supervision_state": "failed",
        "last_error": "Claude crashed while applying edits.",
    }
    strategy = InteractiveTuiRunnerStrategy(
        bridge=bridge,
        session_coordinator=coordinator,
        poll_interval_seconds=0,
    )

    result = await strategy.execute(_request())

    assert result.success is False
    assert result.error_message == "Claude crashed while applying edits."


@pytest.mark.asyncio
async def test_execute_fails_when_interactive_session_completes_without_canonical_result() -> None:
    coordinator = MagicMock()
    coordinator.create_or_attach = AsyncMock(
        return_value={"session_id": "interactive_session:codex", "attach_token": "attach-1"}
    )
    bridge = MagicMock()
    bridge.query.return_value = {
        "session_id": "interactive_session:codex",
        "last_event_kind": "turn_completed",
        "supervision_state": "idle",
        "summary": "Turn completed.",
    }
    strategy = InteractiveTuiRunnerStrategy(
        bridge=bridge,
        session_coordinator=coordinator,
        poll_interval_seconds=0,
    )

    result = await strategy.execute(_request(provider="codex"))

    assert result.success is False
    assert result.session_id == "interactive_session:codex"
    assert "missing a canonical final result" in (result.error_message or "")


@pytest.mark.asyncio
async def test_execute_fails_cleanly_when_interactive_runtime_is_unavailable() -> None:
    strategy = InteractiveTuiRunnerStrategy(
        bridge=MagicMock(),
        session_coordinator=None,
        poll_interval_seconds=0,
    )

    result = await strategy.execute(_request(provider="codex"))

    assert result.success is False
    assert "Interactive session coordinator is not available" in (result.error_message or "")


@pytest.mark.asyncio
async def test_execute_waits_for_manual_done_when_human_has_taken_over() -> None:
    coordinator = MagicMock()
    coordinator.create_or_attach = AsyncMock(
        return_value={"session_id": "interactive_session:claude", "attach_token": "attach-1"}
    )
    bridge = MagicMock()
    bridge.query.side_effect = [
        {
            "session_id": "interactive_session:claude",
            "last_event_kind": "turn_completed",
            "supervision_state": "idle",
            "summary": "Agent turn completed while human was intervening.",
            "final_result": "Agent claimed a final result that should not complete the step yet.",
            "control_mode": "human",
        },
        {
            "session_id": "interactive_session:claude",
            "last_event_kind": "turn_completed",
            "supervision_state": "idle",
            "summary": "Human marked the step done from Live.",
            "final_result": "Human operator completed the step manually from Live.",
            "control_mode": "human",
            "manual_completion_requested_at": "2026-03-13T12:10:00.000Z",
        },
    ]
    strategy = InteractiveTuiRunnerStrategy(
        bridge=bridge,
        session_coordinator=coordinator,
        poll_interval_seconds=0,
    )

    result = await strategy.execute(_request())

    assert result.success is True
    assert result.session_id == "interactive_session:claude"
    assert result.output == "Human operator completed the step manually from Live."


@pytest.mark.asyncio
async def test_execute_passes_memory_workspace_and_bootstrap_prompt_to_interactive_startup() -> (
    None
):
    coordinator = MagicMock()
    coordinator.create_or_attach = AsyncMock(
        return_value={"session_id": "interactive_session:claude", "attach_token": "attach-1"}
    )
    bridge = MagicMock()
    bridge.query.return_value = {
        "session_id": "interactive_session:claude",
        "last_event_kind": "turn_completed",
        "supervision_state": "idle",
        "final_result": "Interactive run completed with the provided startup context.",
    }
    strategy = InteractiveTuiRunnerStrategy(
        bridge=bridge,
        session_coordinator=coordinator,
        poll_interval_seconds=0,
    )
    request = _request()
    request.step_title = "Add human takeover"
    request.description = "Update the live runtime and validate the new controls."
    request.agent_prompt = "Global orientation for interactive execution."
    request.board_name = "default"
    request.memory_mode = "with_history"
    request.memory_workspace = Path("/tmp/board-memory")

    result = await strategy.execute(request)

    assert result.success is True
    kwargs = coordinator.create_or_attach.await_args.kwargs
    assert kwargs["orientation"] == "Global orientation for interactive execution."
    assert kwargs["memory_mode"] == "with_history"
    assert kwargs["memory_workspace"] == Path("/tmp/board-memory")
    assert kwargs["task_prompt"] == (
        "Step: Add human takeover\n\nUpdate the live runtime and validate the new controls."
    )
