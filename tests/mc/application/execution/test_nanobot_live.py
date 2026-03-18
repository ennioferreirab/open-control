"""Tests for nanobot live session reporting (Live tab wiring).

Proves that NanobotRunnerStrategy correctly creates interactive sessions
and streams progress events to sessionActivityLog via the bridge.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mc.application.execution.request import (
    EntityType,
    ExecutionRequest,
    RunnerType,
)
from mc.application.execution.strategies.nanobot import (
    NanobotRunnerStrategy,
    _parse_tool_name,
)


def _make_request(
    title: str = "Test Task",
    agent_model: str = "gpt-4o",
    task_id: str = "task_live_1",
    entity_id: str = "step_1",
) -> ExecutionRequest:
    return ExecutionRequest(
        entity_type=EntityType.TASK,
        entity_id=entity_id,
        task_id=task_id,
        title=title,
        agent_name="test-agent",
        runner_type=RunnerType.NANOBOT,
        agent_model=agent_model,
        description="Test description",
    )


def _make_fake_loop_result(content: str, is_error: bool = False):
    from mc.contexts.execution.agent_runner import AgentRunResult

    return AgentRunResult(
        content=content,
        is_error=is_error,
        error_message="Agent error" if is_error else None,
    )


# ---------------------------------------------------------------------------
# Finding 9: tool_name parsing
# ---------------------------------------------------------------------------


class TestParseToolName:
    """Verifies _parse_tool_name handles edge cases."""

    def test_normal_tool_call(self) -> None:
        assert _parse_tool_name('web_search("query")') == "web_search"

    def test_no_parens(self) -> None:
        assert _parse_tool_name("some_tool") == "some_tool"

    def test_empty_before_paren(self) -> None:
        """Leading paren should fall back to 'tool_use'."""
        assert _parse_tool_name("(something)") == "tool_use"

    def test_long_name_truncated(self) -> None:
        long_name = "x" * 300
        assert len(_parse_tool_name(long_name)) == 200

    def test_whitespace_stripped(self) -> None:
        assert _parse_tool_name("  web_search  (q)") == "web_search"


# ---------------------------------------------------------------------------
# on_progress callback
# ---------------------------------------------------------------------------


class TestOnProgressCallback:
    """Tests for the _build_on_progress callback behavior."""

    @pytest.mark.asyncio()
    async def test_on_progress_text_writes_activity_log(self) -> None:
        """tool_hint=False → kind='text', source_type='assistant'."""
        bridge = MagicMock()
        strategy = NanobotRunnerStrategy(bridge=bridge)

        callback = strategy._build_on_progress(
            "session-1",
            agent_name="test-agent",
        )
        assert callback is not None

        with patch(
            "mc.contexts.interactive.activity_service.safe_string_for_convex",
            side_effect=lambda v, **_kw: v,
        ):
            await callback("Agent thinking about the task")

        bridge.mutation.assert_called_once()
        args = bridge.mutation.call_args
        assert args[0][0] == "sessionActivityLog:append"
        payload = args[0][1]
        assert payload["kind"] == "text"
        assert payload["source_type"] == "assistant"
        assert payload["summary"] == "Agent thinking about the task"
        assert payload["raw_text"] == "Agent thinking about the task"
        assert payload["session_id"] == "session-1"
        assert payload["agent_name"] == "test-agent"
        assert payload["provider"] == "nanobot"

    @pytest.mark.asyncio()
    async def test_on_progress_tool_hint_writes_activity_log(self) -> None:
        """tool_hint=True → kind='tool_use', source_type='tool_use', parsed tool_name."""
        bridge = MagicMock()
        strategy = NanobotRunnerStrategy(bridge=bridge)

        callback = strategy._build_on_progress(
            "session-1",
            agent_name="test-agent",
        )

        await callback('web_search("query string")', tool_hint=True)

        bridge.mutation.assert_called_once()
        payload = bridge.mutation.call_args[0][1]
        assert payload["kind"] == "tool_use"
        assert payload["source_type"] == "tool_use"
        assert payload["tool_name"] == "web_search"
        assert payload["summary"] == 'web_search("query string")'

    @pytest.mark.asyncio()
    async def test_on_progress_text_truncates_summary(self) -> None:
        """Summary is truncated to 1000 chars for both text and tool_hint."""
        bridge = MagicMock()
        strategy = NanobotRunnerStrategy(bridge=bridge)

        callback = strategy._build_on_progress("session-1", agent_name="test-agent")
        long_text = "x" * 2000

        with patch(
            "mc.contexts.interactive.activity_service.safe_string_for_convex",
            side_effect=lambda v, **_kw: v,
        ):
            await callback(long_text)

        payload = bridge.mutation.call_args[0][1]
        assert len(payload["summary"]) == 1000
        assert payload["raw_text"] == long_text

    @pytest.mark.asyncio()
    async def test_on_progress_tool_hint_truncates_summary(self) -> None:
        """tool_hint=True also truncates summary to 1000 chars."""
        bridge = MagicMock()
        strategy = NanobotRunnerStrategy(bridge=bridge)

        callback = strategy._build_on_progress("session-1", agent_name="test-agent")
        long_text = "t" * 2000

        await callback(long_text, tool_hint=True)

        payload = bridge.mutation.call_args[0][1]
        assert len(payload["summary"]) == 1000

    @pytest.mark.asyncio()
    async def test_on_progress_text_uses_overflow_protection(self) -> None:
        """raw_text goes through safe_string_for_convex."""
        bridge = MagicMock()
        strategy = NanobotRunnerStrategy(bridge=bridge)

        callback = strategy._build_on_progress("session-1", agent_name="test-agent")

        with patch(
            "mc.contexts.interactive.activity_service.safe_string_for_convex",
            return_value="[safe]",
        ) as mock_safe:
            await callback("big content")

        mock_safe.assert_called_once()
        payload = bridge.mutation.call_args[0][1]
        assert payload["raw_text"] == "[safe]"


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


class TestSessionLifecycle:
    """Tests for session creation and status transitions."""

    @pytest.mark.asyncio()
    async def test_session_created_on_execute(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """interactiveSessions:upsert called with status='ready' before execution."""
        from mc.application.execution.strategies import nanobot as nanobot_mod

        bridge = MagicMock()
        strategy = NanobotRunnerStrategy(bridge=bridge)

        class FakeLoop:
            memory_workspace = Path("/tmp/fake")

        success_result = _make_fake_loop_result("Done", is_error=False)

        async def fake_run_nanobot_task(**kwargs):
            return (success_result, "session_key", FakeLoop())

        monkeypatch.setattr(nanobot_mod, "run_nanobot_task", fake_run_nanobot_task)
        monkeypatch.setattr(nanobot_mod, "_PROVIDER_ERRORS", ())

        await strategy.execute(_make_request())

        session_calls = [
            c for c in bridge.mutation.call_args_list if c[0][0] == "interactiveSessions:upsert"
        ]
        assert len(session_calls) >= 1

        # First call should be status="ready"
        first_payload = session_calls[0][0][1]
        assert first_payload["status"] == "ready"
        assert first_payload["agent_name"] == "test-agent"
        assert first_payload["provider"] == "nanobot"
        assert first_payload["surface"] == "nanobot"
        assert first_payload["task_id"] == "task_live_1"
        assert first_payload["scope_id"] == "task_live_1"

    @pytest.mark.asyncio()
    async def test_session_ended_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """status='ended' and finalResult populated after successful execution."""
        from mc.application.execution.strategies import nanobot as nanobot_mod

        bridge = MagicMock()
        strategy = NanobotRunnerStrategy(bridge=bridge)

        class FakeLoop:
            memory_workspace = Path("/tmp/fake")

        success_result = _make_fake_loop_result("Task completed.", is_error=False)

        async def fake_run_nanobot_task(**kwargs):
            return (success_result, "session_key", FakeLoop())

        monkeypatch.setattr(nanobot_mod, "run_nanobot_task", fake_run_nanobot_task)
        monkeypatch.setattr(nanobot_mod, "_PROVIDER_ERRORS", ())

        await strategy.execute(_make_request())

        session_calls = [
            c for c in bridge.mutation.call_args_list if c[0][0] == "interactiveSessions:upsert"
        ]
        last_payload = session_calls[-1][0][1]
        assert last_payload["status"] == "ended"
        assert last_payload["final_result"] == "Task completed."
        assert last_payload["task_id"] == "task_live_1"
        assert last_payload["scope_id"] == "task_live_1"

    @pytest.mark.asyncio()
    async def test_session_error_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """status='error' and lastError populated on execution failure."""
        from mc.application.execution.strategies import nanobot as nanobot_mod

        bridge = MagicMock()
        strategy = NanobotRunnerStrategy(bridge=bridge)

        error_result = _make_fake_loop_result("Error occurred", is_error=True)

        async def fake_run_nanobot_task(**kwargs):
            return (error_result, "session_key", object())

        monkeypatch.setattr(nanobot_mod, "run_nanobot_task", fake_run_nanobot_task)
        monkeypatch.setattr(nanobot_mod, "_PROVIDER_ERRORS", ())

        await strategy.execute(_make_request())

        session_calls = [
            c for c in bridge.mutation.call_args_list if c[0][0] == "interactiveSessions:upsert"
        ]
        last_payload = session_calls[-1][0][1]
        assert last_payload["status"] == "error"
        assert last_payload.get("last_error") is not None
        assert last_payload["task_id"] == "task_live_1"

    @pytest.mark.asyncio()
    async def test_session_error_on_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """status='error' when _run_agent_loop raises an exception."""
        from mc.application.execution.strategies import nanobot as nanobot_mod

        bridge = MagicMock()
        strategy = NanobotRunnerStrategy(bridge=bridge)

        async def fake_run_nanobot_task(**kwargs):
            raise RuntimeError("Connection lost")

        monkeypatch.setattr(nanobot_mod, "run_nanobot_task", fake_run_nanobot_task)
        monkeypatch.setattr(nanobot_mod, "_PROVIDER_ERRORS", ())

        result = await strategy.execute(_make_request())

        assert result.success is False
        session_calls = [
            c for c in bridge.mutation.call_args_list if c[0][0] == "interactiveSessions:upsert"
        ]
        last_payload = session_calls[-1][0][1]
        assert last_payload["status"] == "error"
        assert "Connection lost" in last_payload["last_error"]

    @pytest.mark.asyncio()
    async def test_ready_and_ended_use_same_session_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both ready and ended calls target the same mc_session_id."""
        from mc.application.execution.strategies import nanobot as nanobot_mod

        bridge = MagicMock()
        strategy = NanobotRunnerStrategy(bridge=bridge)

        class FakeLoop:
            memory_workspace = Path("/tmp/fake")

        success_result = _make_fake_loop_result("Done", is_error=False)

        async def fake_run_nanobot_task(**kwargs):
            return (success_result, "session_key", FakeLoop())

        monkeypatch.setattr(nanobot_mod, "run_nanobot_task", fake_run_nanobot_task)
        monkeypatch.setattr(nanobot_mod, "_PROVIDER_ERRORS", ())

        await strategy.execute(_make_request())

        session_calls = [
            c for c in bridge.mutation.call_args_list if c[0][0] == "interactiveSessions:upsert"
        ]
        session_ids = {c[0][1]["session_id"] for c in session_calls}
        assert len(session_ids) == 1, f"Expected single session ID, got {session_ids}"


# ---------------------------------------------------------------------------
# Result event in activity log
# ---------------------------------------------------------------------------


class TestResultEvent:
    """Tests that a result event is appended to sessionActivityLog."""

    @pytest.mark.asyncio()
    async def test_success_result_event_appended(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On success, a result event with source_type='result' is written."""
        from mc.application.execution.strategies import nanobot as nanobot_mod

        bridge = MagicMock()
        strategy = NanobotRunnerStrategy(bridge=bridge)

        class FakeLoop:
            memory_workspace = Path("/tmp/fake")

        success_result = _make_fake_loop_result("Final answer here.", is_error=False)

        async def fake_run_nanobot_task(**kwargs):
            return (success_result, "session_key", FakeLoop())

        monkeypatch.setattr(nanobot_mod, "run_nanobot_task", fake_run_nanobot_task)
        monkeypatch.setattr(nanobot_mod, "_PROVIDER_ERRORS", ())

        await strategy.execute(_make_request())

        result_calls = [
            c
            for c in bridge.mutation.call_args_list
            if c[0][0] == "sessionActivityLog:append" and c[0][1].get("kind") == "result"
        ]
        assert len(result_calls) == 1
        payload = result_calls[0][0][1]
        assert payload["source_type"] == "result"
        assert payload["source_subtype"] == "success"
        assert "Final answer here." in payload["summary"]

    @pytest.mark.asyncio()
    async def test_error_result_event_appended(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On is_error, a result event with source_subtype='error' is written."""
        from mc.application.execution.strategies import nanobot as nanobot_mod

        bridge = MagicMock()
        strategy = NanobotRunnerStrategy(bridge=bridge)

        error_result = _make_fake_loop_result("Something broke", is_error=True)

        async def fake_run_nanobot_task(**kwargs):
            return (error_result, "session_key", object())

        monkeypatch.setattr(nanobot_mod, "run_nanobot_task", fake_run_nanobot_task)
        monkeypatch.setattr(nanobot_mod, "_PROVIDER_ERRORS", ())

        await strategy.execute(_make_request())

        result_calls = [
            c
            for c in bridge.mutation.call_args_list
            if c[0][0] == "sessionActivityLog:append" and c[0][1].get("kind") == "result"
        ]
        assert len(result_calls) == 1
        payload = result_calls[0][0][1]
        assert payload["source_type"] == "result"
        assert payload["source_subtype"] == "error"


# ---------------------------------------------------------------------------
# No bridge
# ---------------------------------------------------------------------------


class TestNoBridge:
    """Tests that bridge=None doesn't crash."""

    @pytest.mark.asyncio()
    async def test_no_bridge_no_crash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """bridge=None → no writes, no errors, execution completes normally."""
        from mc.application.execution.strategies import nanobot as nanobot_mod

        class FakeLoop:
            memory_workspace = Path("/tmp/fake")

        success_result = _make_fake_loop_result("Done", is_error=False)

        async def fake_run_nanobot_task(**kwargs):
            assert kwargs.get("on_progress") is None
            return (success_result, "session_key", FakeLoop())

        monkeypatch.setattr(nanobot_mod, "run_nanobot_task", fake_run_nanobot_task)
        monkeypatch.setattr(nanobot_mod, "_PROVIDER_ERRORS", ())

        strategy = NanobotRunnerStrategy()
        result = await strategy.execute(_make_request())

        assert result.success is True

    def test_build_on_progress_returns_none_without_bridge(self) -> None:
        """_build_on_progress returns None when bridge is None."""
        strategy = NanobotRunnerStrategy()
        callback = strategy._build_on_progress("session-1", agent_name="test-agent")
        assert callback is None


# ---------------------------------------------------------------------------
# Bridge failure resilience
# ---------------------------------------------------------------------------


class TestBridgeFailureResilience:
    """Tests that bridge failures don't break execution."""

    @pytest.mark.asyncio()
    async def test_bridge_write_failure_swallowed(self) -> None:
        """bridge.mutation raises → on_progress continues without error."""
        bridge = MagicMock()
        bridge.mutation.side_effect = Exception("Bridge unavailable")

        strategy = NanobotRunnerStrategy(bridge=bridge)
        callback = strategy._build_on_progress("session-1", agent_name="test-agent")

        # Should not raise
        with patch(
            "mc.contexts.interactive.activity_service.safe_string_for_convex",
            side_effect=lambda v, **_kw: v,
        ):
            await callback("Some progress text")
        await callback("More progress", tool_hint=True)

    @pytest.mark.asyncio()
    async def test_session_persist_failure_swallowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """bridge.mutation failure in _persist_session doesn't crash execute()."""
        from mc.application.execution.strategies import nanobot as nanobot_mod

        call_count = 0

        def flaky_mutation(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Bridge down")

        bridge = MagicMock()
        bridge.mutation.side_effect = flaky_mutation

        class FakeLoop:
            memory_workspace = Path("/tmp/fake")

        success_result = _make_fake_loop_result("Done", is_error=False)

        async def fake_run_nanobot_task(**kwargs):
            return (success_result, "session_key", FakeLoop())

        monkeypatch.setattr(nanobot_mod, "run_nanobot_task", fake_run_nanobot_task)
        monkeypatch.setattr(nanobot_mod, "_PROVIDER_ERRORS", ())

        strategy = NanobotRunnerStrategy(bridge=bridge)
        result = await strategy.execute(_make_request())

        assert result.success is True
