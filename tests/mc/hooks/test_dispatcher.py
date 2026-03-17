"""Tests for mc.hooks.dispatcher — event routing to handlers."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mc.hooks.config import HookConfig
from mc.hooks.context import HookContext
from mc.hooks.dispatcher import _dispatch, main
from mc.hooks.handler import BaseHandler
from typing import ClassVar


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dispatch_env(tmp_path: Path):
    """Set up environment for dispatcher tests with temp dirs."""
    tracker_dir = tmp_path / ".claude" / "plan-tracker"
    state_dir = tmp_path / ".claude" / "hook-state"
    plans_dir = tmp_path / "docs" / "plans"
    tracker_dir.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    plans_dir.mkdir(parents=True)

    config = HookConfig(
        plan_pattern="docs/plans/*.md",
        tracker_dir=".claude/plan-tracker",
        state_dir=".claude/hook-state",
    )
    with (
        patch("mc.hooks.config.get_project_root", return_value=tmp_path),
        patch("mc.hooks.config.get_config", return_value=config),
        patch("mc.hooks.context.get_project_root", return_value=tmp_path),
        patch("mc.hooks.context.get_config", return_value=config),
        patch("mc.hooks.handlers.plan_tracker.get_project_root", return_value=tmp_path),
        patch("mc.hooks.handlers.plan_tracker.get_config", return_value=config),
        patch("mc.hooks.handlers.plan_capture.get_project_root", return_value=tmp_path),
        patch("mc.hooks.handlers.plan_capture.get_config", return_value=config),
    ):
        yield tmp_path, tracker_dir, state_dir, plans_dir


# ---------------------------------------------------------------------------
# _dispatch tests
# ---------------------------------------------------------------------------


class TestDispatch:
    """Test the _dispatch() function."""

    def test_empty_event_name_returns_none(self, dispatch_env):
        result = _dispatch({"hook_event_name": "", "session_id": "test"})
        assert result is None

    def test_missing_event_name_returns_none(self, dispatch_env):
        result = _dispatch({"session_id": "test"})
        assert result is None

    def test_non_matching_event_returns_none(self, dispatch_env):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "session_id": "test",
            "cwd": "/tmp",
            "tool_input": {"command": "ls"},
        }
        result = _dispatch(payload)
        assert result is None

    def test_skill_event_returns_output(self, dispatch_env):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Skill",
            "session_id": "test",
            "cwd": "/tmp",
            "tool_input": {"skill": "debugging"},
        }
        result = _dispatch(payload)
        assert result is not None
        output = json.loads(result)
        assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert "debugging" in output["hookSpecificOutput"]["additionalContext"]

    def test_agent_start_event(self, dispatch_env):
        payload = {
            "hook_event_name": "SubagentStart",
            "session_id": "test",
            "cwd": "/tmp",
            "agent_id": "a1",
            "agent_type": "Explore",
        }
        result = _dispatch(payload)
        assert result is not None
        output = json.loads(result)
        assert "1 active" in output["hookSpecificOutput"]["additionalContext"]

    def test_agent_lifecycle(self, dispatch_env):
        start = {
            "hook_event_name": "SubagentStart",
            "session_id": "test",
            "cwd": "/tmp",
            "agent_id": "a1",
            "agent_type": "Explore",
        }
        stop = {
            "hook_event_name": "SubagentStop",
            "session_id": "test",
            "cwd": "/tmp",
            "agent_id": "a1",
            "agent_type": "Explore",
        }
        r1 = _dispatch(start)
        assert "1 active" in r1
        r2 = _dispatch(stop)
        assert "0 remaining" in r2

    def test_plan_write_creates_tracker(self, dispatch_env):
        tmp_path, tracker_dir, _, plans_dir = dispatch_env
        plan = plans_dir / "feature.md"
        plan.write_text(
            "# Plan\n\n### Task 1: First step\nDo thing.\n\n### Task 2: Second step\nDo other.\n"
        )

        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "session_id": "test",
            "cwd": str(tmp_path),
            "tool_input": {
                "file_path": "docs/plans/feature.md",
                "content": plan.read_text(),
            },
        }
        result = _dispatch(payload)
        assert result is not None
        assert "Plan tracker created" in result
        assert (tracker_dir / "feature.json").exists()

    def test_output_format(self, dispatch_env):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Skill",
            "session_id": "test",
            "cwd": "/tmp",
            "tool_input": {"skill": "coding"},
        }
        result = _dispatch(payload)
        output = json.loads(result)
        assert "hookSpecificOutput" in output
        assert "hookEventName" in output["hookSpecificOutput"]
        assert "additionalContext" in output["hookSpecificOutput"]

    def test_handler_error_is_isolated(self, dispatch_env):
        """A handler that raises should not crash the dispatcher."""

        class BrokenHandler(BaseHandler):
            events: ClassVar[list[tuple[str, str | None]]] = [("TestBroken", None)]

            def handle(self):
                raise RuntimeError("boom")

        with patch(
            "mc.hooks.discovery.discover_handlers",
            return_value=[BrokenHandler],
        ):
            payload = {
                "hook_event_name": "TestBroken",
                "tool_name": "",
                "session_id": "test",
            }
            # Should not raise, just return None (no successful results)
            result = _dispatch(payload)
            assert result is None

    def test_multiple_handlers_combined(self, dispatch_env):
        """When multiple handlers match, their results are joined with '; '."""

        class HandlerA(BaseHandler):
            events: ClassVar[list[tuple[str, str | None]]] = [("MultiTest", None)]

            def handle(self):
                return "result A"

        class HandlerB(BaseHandler):
            events: ClassVar[list[tuple[str, str | None]]] = [("MultiTest", None)]

            def handle(self):
                return "result B"

        with patch(
            "mc.hooks.discovery.discover_handlers",
            return_value=[HandlerA, HandlerB],
        ):
            payload = {
                "hook_event_name": "MultiTest",
                "tool_name": "",
                "session_id": "test",
            }
            result = _dispatch(payload)
            output = json.loads(result)
            ctx_str = output["hookSpecificOutput"]["additionalContext"]
            assert "result A" in ctx_str
            assert "result B" in ctx_str
            assert "; " in ctx_str

    def test_handler_returning_none_is_skipped(self, dispatch_env):
        """Handlers that return None should not appear in output."""

        class SilentHandler(BaseHandler):
            events: ClassVar[list[tuple[str, str | None]]] = [("SilentTest", None)]

            def handle(self):
                return None

        class LoudHandler(BaseHandler):
            events: ClassVar[list[tuple[str, str | None]]] = [("SilentTest", None)]

            def handle(self):
                return "loud"

        with patch(
            "mc.hooks.discovery.discover_handlers",
            return_value=[SilentHandler, LoudHandler],
        ):
            payload = {
                "hook_event_name": "SilentTest",
                "tool_name": "",
                "session_id": "test",
            }
            result = _dispatch(payload)
            output = json.loads(result)
            assert output["hookSpecificOutput"]["additionalContext"] == "loud"

    def test_context_is_saved_after_dispatch(self, dispatch_env):
        """The dispatcher should call ctx.save() even with no matching handlers."""
        tmp_path, _, state_dir, _ = dispatch_env
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "session_id": "save-check",
            "cwd": "/tmp",
            "tool_input": {"command": "ls"},
        }
        _dispatch(payload)

        # State file should exist for the session
        state_file = state_dir / "save-check.json"
        assert state_file.exists()


# ---------------------------------------------------------------------------
# main() tests (stdin/stdout integration)
# ---------------------------------------------------------------------------


class TestMain:
    def test_main_with_valid_payload(self, dispatch_env):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Skill",
            "session_id": "main-test",
            "cwd": "/tmp",
            "tool_input": {"skill": "testing"},
        }
        stdin = StringIO(json.dumps(payload))
        stdout = StringIO()

        with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
            main()

        output = stdout.getvalue()
        assert output  # should have written something
        parsed = json.loads(output)
        assert "testing" in parsed["hookSpecificOutput"]["additionalContext"]

    def test_main_with_invalid_json_exits_silently(self, dispatch_env):
        stdin = StringIO("not valid json{{{")
        stdout = StringIO()

        with (
            patch("sys.stdin", stdin),
            patch("sys.stdout", stdout),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 0
        assert stdout.getvalue() == ""

    def test_main_with_no_match_writes_nothing(self, dispatch_env):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "session_id": "main-test",
            "cwd": "/tmp",
            "tool_input": {"command": "ls"},
        }
        stdin = StringIO(json.dumps(payload))
        stdout = StringIO()

        with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
            main()

        assert stdout.getvalue() == ""
