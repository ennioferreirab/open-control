"""Tests for unified thread_context_builder module."""

from __future__ import annotations

from typing import Any

from mc.application.execution.thread_context_builder import build_thread_context


def _user_msg(content: str) -> dict[str, Any]:
    return {
        "author_name": "User",
        "author_type": "user",
        "message_type": "user_message",
        "timestamp": "2026-01-01T10:00:00Z",
        "content": content,
    }


def _agent_msg(content: str) -> dict[str, Any]:
    return {
        "author_name": "nanobot",
        "author_type": "agent",
        "message_type": "work",
        "timestamp": "2026-01-01T10:01:00Z",
        "content": content,
    }


def _step_completion(
    step_id: str, content: str, agent: str = "agent-1"
) -> dict[str, Any]:
    return {
        "author_name": agent,
        "author_type": "agent",
        "step_id": step_id,
        "type": "step_completion",
        "timestamp": "2026-01-01T10:02:00Z",
        "content": content,
    }


class TestBuildThreadContextLegacy:
    """Tests for legacy (task) thread context building."""

    def test_empty_messages(self) -> None:
        assert build_thread_context([]) == ""

    def test_no_user_messages_returns_empty(self) -> None:
        msgs = [_agent_msg("hello")]
        assert build_thread_context(msgs) == ""

    def test_user_message_produces_context(self) -> None:
        msgs = [_user_msg("hello")]
        result = build_thread_context(msgs)
        assert "hello" in result
        assert "[Latest Follow-up]" in result

    def test_multiple_messages_with_thread_history(self) -> None:
        msgs = [
            _user_msg("first message"),
            _agent_msg("agent reply"),
            _user_msg("second message"),
        ]
        result = build_thread_context(msgs)
        assert "[Thread History]" in result
        assert "[Latest Follow-up]" in result
        assert "second message" in result


class TestBuildThreadContextStepAware:
    """Tests for step-aware thread context building (with predecessors)."""

    def test_predecessor_context_included(self) -> None:
        msgs = [
            _step_completion("step_0", "Step 0 done"),
            _user_msg("Go ahead"),
        ]
        result = build_thread_context(
            msgs, predecessor_step_ids=["step_0"]
        )
        assert "Step 0 done" in result

    def test_predecessor_without_user_messages(self) -> None:
        """Step context should work even without user messages."""
        msgs = [_step_completion("step_0", "Step 0 done")]
        result = build_thread_context(
            msgs, predecessor_step_ids=["step_0"]
        )
        assert "Step 0 done" in result

    def test_empty_predecessors_falls_back_to_legacy(self) -> None:
        msgs = [_agent_msg("no user messages")]
        result = build_thread_context(msgs, predecessor_step_ids=[])
        assert result == ""


class TestBuildThreadContextSharedInterface:
    """Tests that the function serves as a single shared interface."""

    def test_same_function_for_tasks_and_steps(self) -> None:
        """Both task and step paths use the same build_thread_context."""
        msgs = [_user_msg("test")]

        # Task mode (no predecessors)
        task_result = build_thread_context(msgs)
        assert "test" in task_result

        # Step mode (with predecessors)
        step_result = build_thread_context(msgs, predecessor_step_ids=[])
        # Empty predecessors = legacy behavior
        assert "test" in step_result

    def test_max_messages_parameter(self) -> None:
        msgs = [_user_msg(f"msg {i}") for i in range(30)]
        result = build_thread_context(msgs, max_messages=5)
        assert "earlier messages omitted" in result
