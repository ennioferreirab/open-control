"""Tests for crash-handling and human-step behaviors in mc.contexts.execution.step_dispatcher."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.contexts.execution.step_dispatcher import StepDispatcher
from mc.types import StepStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_step(
    step_id: str = "step-123",
    title: str = "Write tests",
    agent: str = "dev-agent",
    status: str = StepStatus.ASSIGNED,
) -> dict:
    return {
        "id": step_id,
        "title": title,
        "description": "Step description",
        "assigned_agent": agent,
        "status": status,
        "parallel_group": 1,
        "order": 1,
        "blocked_by": [],
    }


def _make_bridge() -> MagicMock:
    """Return a mock ConvexBridge with all needed methods stubbed."""
    bridge = MagicMock()
    bridge.update_step_status = MagicMock(return_value=None)
    bridge.update_task_status = MagicMock(return_value=None)
    bridge.post_system_error = MagicMock(return_value=None)
    bridge.send_message = MagicMock(return_value=None)
    bridge.create_activity = MagicMock(return_value=None)
    bridge.get_task_messages = MagicMock(return_value=[])
    bridge.query = MagicMock(return_value={"title": "Test Task", "status": "in_progress"})
    bridge.get_board_by_id = MagicMock(return_value=None)
    return bridge


def _make_mock_execution_request(step: dict):
    """Build a realistic mock ExecutionRequest for ContextBuilder mocking."""
    from mc.application.execution.request import EntityType, ExecutionRequest

    return ExecutionRequest(
        entity_type=EntityType.STEP,
        entity_id=step.get("id", ""),
        task_id="task-abc",
        title="Test Task",
        step_title=step.get("title", "Untitled"),
        step_description=step.get("description", ""),
        agent_name=step.get("assigned_agent", "nanobot"),
        agent_prompt=None,
        agent_model=None,
        agent_skills=None,
        description=step.get("description", ""),
        is_cc=False,
    )


def _patch_context_builder():
    """Patch ContextBuilder.build_step_context to return a mock ExecutionRequest."""

    async def _mock_build_step_context(self, task_id, step):
        return _make_mock_execution_request(step)

    return patch(
        "mc.application.execution.context_builder.ContextBuilder.build_step_context",
        new=_mock_build_step_context,
    )


async def _sync_to_thread(func, *args, **kwargs):
    """Run to_thread payloads synchronously in tests."""
    return func(*args, **kwargs)


# ---------------------------------------------------------------------------
# Integration tests for _execute_step crash handler
# ---------------------------------------------------------------------------


class TestExecuteStepCrashHandler:
    """Crash in _execute_step marks step as CRASHED and sends a crash message."""

    @pytest.mark.asyncio
    async def test_crash_marks_step_as_crashed(self) -> None:
        """Exception → step status set to CRASHED."""
        bridge = _make_bridge()
        dispatcher = StepDispatcher(bridge)
        exc = RuntimeError("unexpected failure")

        step = _make_step()

        with (
            patch(
                "mc.contexts.execution.step_dispatcher.asyncio.to_thread",
                new=_sync_to_thread,
            ),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(side_effect=exc),
            ),
        ):
            with pytest.raises(RuntimeError):
                await dispatcher._execute_step("task-abc", step)

        # Step must be marked CRASHED
        crashed_calls = [
            c
            for c in bridge.update_step_status.call_args_list
            if len(c[0]) >= 2 and c[0][1] == StepStatus.CRASHED
        ]
        assert crashed_calls, "update_step_status must be called with CRASHED"

    @pytest.mark.asyncio
    async def test_crash_sends_message_with_error_details(self) -> None:
        """RuntimeError → send_message content has error type and agent name."""
        bridge = _make_bridge()
        dispatcher = StepDispatcher(bridge)
        exc = RuntimeError("unexpected failure")

        step = _make_step()

        with (
            patch(
                "mc.contexts.execution.step_dispatcher.asyncio.to_thread",
                new=_sync_to_thread,
            ),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(side_effect=exc),
            ),
        ):
            with pytest.raises(RuntimeError):
                await dispatcher._execute_step("task-abc", step)

        assert bridge.send_message.called
        # send_message args: (task_id, author_name, author_type, content, message_type)
        call_args = bridge.send_message.call_args
        content = call_args[0][3]
        assert "RuntimeError" in content
        assert "dev-agent" in content

    @pytest.mark.asyncio
    async def test_crash_message_contains_step_title(self) -> None:
        """Crash message includes the step title."""
        bridge = _make_bridge()
        dispatcher = StepDispatcher(bridge)
        exc = ValueError("bad value")

        step = _make_step(title="Deploy service", agent="ops-agent")

        with (
            patch(
                "mc.contexts.execution.step_dispatcher.asyncio.to_thread",
                new=_sync_to_thread,
            ),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(side_effect=exc),
            ),
        ):
            with pytest.raises(ValueError):
                await dispatcher._execute_step("task-abc", step)

        call_args = bridge.send_message.call_args
        content = call_args[0][3]
        assert "Deploy service" in content
        assert "ops-agent" in content

    @pytest.mark.asyncio
    async def test_crash_reraises_exception(self) -> None:
        """The original exception is re-raised after crash handling."""
        bridge = _make_bridge()
        dispatcher = StepDispatcher(bridge)

        step = _make_step()

        with (
            patch(
                "mc.contexts.execution.step_dispatcher.asyncio.to_thread",
                new=_sync_to_thread,
            ),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ),
        ):
            with pytest.raises(RuntimeError, match="boom"):
                await dispatcher._execute_step("task-abc", step)


# ---------------------------------------------------------------------------
# Story 7.2: Human step dispatch — human agents never spawn a process
# ---------------------------------------------------------------------------


class TestHumanStepDispatch:
    """Human-assigned steps stay in 'assigned' without any execution."""

    @pytest.mark.asyncio
    async def test_human_step_stays_assigned(self) -> None:
        """assigned_agent='human' → step stays ASSIGNED, no runner called, no status change."""
        bridge = _make_bridge()
        dispatcher = StepDispatcher(bridge)
        step = _make_step(agent="human")

        run_agent_mock = AsyncMock()

        with (
            patch(
                "mc.contexts.execution.step_dispatcher.asyncio.to_thread",
                new=_sync_to_thread,
            ),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=run_agent_mock,
            ),
        ):
            result = await dispatcher._execute_step("task-abc", step)

        # Step status must NOT be changed — no update_step_status call with any
        # terminal/transition status (RUNNING, WAITING_HUMAN, COMPLETED, CRASHED)
        status_calls = [c[0][1] for c in bridge.update_step_status.call_args_list]
        assert StepStatus.WAITING_HUMAN not in status_calls
        assert StepStatus.RUNNING not in status_calls
        assert StepStatus.COMPLETED not in status_calls
        assert StepStatus.CRASHED not in status_calls
        # Runner must NEVER be called
        run_agent_mock.assert_not_called()
        # No unblocked dependents
        assert result == []
