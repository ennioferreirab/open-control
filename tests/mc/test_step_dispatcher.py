"""Tests for crash-handling and human-step behaviors in mc.step_dispatcher."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.step_dispatcher import StepDispatcher
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
    bridge.post_system_error = MagicMock(return_value=None)
    bridge.send_message = MagicMock(return_value=None)
    bridge.create_activity = MagicMock(return_value=None)
    bridge.get_task_messages = MagicMock(return_value=[])
    bridge.query = MagicMock(return_value={"title": "Test Task"})
    bridge.get_board_by_id = MagicMock(return_value=None)
    # Default: Convex has no data for the agent (prevents pollution of crash tests)
    bridge.get_agent_by_name = MagicMock(return_value=None)
    bridge.post_step_completion = MagicMock(return_value=None)
    bridge.sync_task_output_files = MagicMock(return_value=None)
    bridge.check_and_unblock_dependents = MagicMock(return_value=[])
    return bridge


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
                "mc.step_dispatcher._run_step_agent",
                new=AsyncMock(side_effect=exc),
            ),
            patch("mc.step_dispatcher._load_agent_config", return_value=(None, None, None)),
            patch("mc.step_dispatcher._maybe_inject_orientation", side_effect=lambda n, p: p),
            patch("mc.step_dispatcher._build_step_thread_context", return_value=""),
            patch("mc.executor._snapshot_output_dir", return_value={}),
        ):
            with pytest.raises(RuntimeError):
                await dispatcher._execute_step("task-abc", step)

        # Step must be marked CRASHED
        crashed_calls = [
            c for c in bridge.update_step_status.call_args_list
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
                "mc.step_dispatcher._run_step_agent",
                new=AsyncMock(side_effect=exc),
            ),
            patch("mc.step_dispatcher._load_agent_config", return_value=(None, None, None)),
            patch("mc.step_dispatcher._maybe_inject_orientation", side_effect=lambda n, p: p),
            patch("mc.step_dispatcher._build_step_thread_context", return_value=""),
            patch("mc.executor._snapshot_output_dir", return_value={}),
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
                "mc.step_dispatcher._run_step_agent",
                new=AsyncMock(side_effect=exc),
            ),
            patch("mc.step_dispatcher._load_agent_config", return_value=(None, None, None)),
            patch("mc.step_dispatcher._maybe_inject_orientation", side_effect=lambda n, p: p),
            patch("mc.step_dispatcher._build_step_thread_context", return_value=""),
            patch("mc.executor._snapshot_output_dir", return_value={}),
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
                "mc.step_dispatcher._run_step_agent",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ),
            patch("mc.step_dispatcher._load_agent_config", return_value=(None, None, None)),
            patch("mc.step_dispatcher._maybe_inject_orientation", side_effect=lambda n, p: p),
            patch("mc.step_dispatcher._build_step_thread_context", return_value=""),
            patch("mc.executor._snapshot_output_dir", return_value={}),
        ):
            with pytest.raises(RuntimeError, match="boom"):
                await dispatcher._execute_step("task-abc", step)


# ---------------------------------------------------------------------------
# Convex variable interpolation in step prompt (regression: step_dispatcher
# was bypassing executor._execute_task and never interpolating variables)
# ---------------------------------------------------------------------------


_SUCCESS_PATCHES = (
    "mc.step_dispatcher._maybe_inject_orientation",
    "mc.step_dispatcher._build_step_thread_context",
    "mc.executor._snapshot_output_dir",
    "mc.executor._collect_output_artifacts",
)


class TestConvexVariableInterpolation:
    """Convex variables must be interpolated into the prompt before agent execution."""

    @pytest.mark.asyncio
    async def test_convex_variables_are_interpolated_before_step_execution(self) -> None:
        """{{p_channel_list}} in YAML prompt is replaced with the Convex variable value."""
        yaml_prompt = "Monitor channels: {{p_channel_list}}"
        channel_value = "https://youtube.com/@AIJasonZ,https://youtube.com/@QuantBrasil"

        bridge = _make_bridge()
        bridge.get_agent_by_name = MagicMock(return_value={
            "prompt": yaml_prompt,
            "variables": [{"name": "p_channel_list", "value": channel_value}],
        })
        dispatcher = StepDispatcher(bridge)
        step = _make_step(agent="youtube-summarizer")

        captured: list[str | None] = []

        async def capture(**kwargs):
            captured.append(kwargs.get("agent_prompt"))
            return "done"

        with (
            patch("mc.step_dispatcher._load_agent_config", return_value=(yaml_prompt, None, None)),
            patch("mc.step_dispatcher._run_step_agent", new=capture),
            patch(_SUCCESS_PATCHES[0], side_effect=lambda n, p: p),
            patch(_SUCCESS_PATCHES[1], return_value=""),
            patch(_SUCCESS_PATCHES[2], return_value={}),
            patch(_SUCCESS_PATCHES[3], return_value=[]),
        ):
            await dispatcher._execute_step("task-abc", step)

        assert captured, "Agent must be called"
        prompt = captured[0]
        assert channel_value in prompt, f"Variable not interpolated. Got: {prompt!r}"
        assert "{{p_channel_list}}" not in prompt, f"Placeholder still present. Got: {prompt!r}"

    @pytest.mark.asyncio
    async def test_convex_prompt_overrides_yaml_prompt(self) -> None:
        """Convex prompt takes precedence over the YAML config (Convex as source of truth)."""
        yaml_prompt = "Old YAML prompt"
        convex_prompt = "Updated Convex prompt — source of truth"

        bridge = _make_bridge()
        bridge.get_agent_by_name = MagicMock(return_value={
            "prompt": convex_prompt,
            "variables": [],
        })
        dispatcher = StepDispatcher(bridge)
        step = _make_step(agent="some-agent")

        captured: list[str | None] = []

        async def capture(**kwargs):
            captured.append(kwargs.get("agent_prompt"))
            return "done"

        with (
            patch("mc.step_dispatcher._load_agent_config", return_value=(yaml_prompt, None, None)),
            patch("mc.step_dispatcher._run_step_agent", new=capture),
            patch(_SUCCESS_PATCHES[0], side_effect=lambda n, p: p),
            patch(_SUCCESS_PATCHES[1], return_value=""),
            patch(_SUCCESS_PATCHES[2], return_value={}),
            patch(_SUCCESS_PATCHES[3], return_value=[]),
        ):
            await dispatcher._execute_step("task-abc", step)

        assert captured, "Agent must be called"
        assert captured[0] == convex_prompt, f"Expected Convex prompt, got: {captured[0]!r}"


# ---------------------------------------------------------------------------
# Story 7.2: Human step dispatch (AC: 3, 6)
# NOTE: Human step dispatching (assigned_agent="human" → waiting_human) is
# not yet implemented in step_dispatcher.py. Tests will be added when the
# feature is built.
# ---------------------------------------------------------------------------
