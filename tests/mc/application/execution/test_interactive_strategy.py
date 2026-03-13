from __future__ import annotations

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
    assert result.output == "Implemented the requested step."
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
async def test_execute_fails_cleanly_when_interactive_runtime_is_unavailable() -> None:
    strategy = InteractiveTuiRunnerStrategy(
        bridge=MagicMock(),
        session_coordinator=None,
        poll_interval_seconds=0,
    )

    result = await strategy.execute(_request(provider="codex"))

    assert result.success is False
    assert "Interactive session coordinator is not available" in (result.error_message or "")
