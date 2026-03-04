"""
Tests for ClaudeController that do NOT require a live Claude Code session.

Extracted from claude_controller.py's original _run_skip_claude_tests() function.
Marked with @pytest.mark.requires_tmux since they need tmux for the
_tmux_session_exists() calls (which just run `tmux has-session`).
"""

import pytest
from pathlib import Path

from tmux_claude_control import ClaudeController, Response, ClaudeError
from tmux_claude_control import ScreenMode, ScreenState
from tmux_claude_control.claude_controller import (
    ClaudeTimeoutError,
    ClaudeNotReadyError,
    ClaudeSessionError,
)


@pytest.mark.requires_tmux
class TestClaudeControllerNoSession:
    """Tests that verify controller behaviour without a live Claude session."""

    def test_instantiation(self):
        """ClaudeController initialises with correct attributes."""
        ctrl = ClaudeController(session_name="test-skip", cwd="/tmp")
        assert ctrl.session_name == "test-skip"
        assert ctrl.cwd == str(Path("/tmp").resolve())
        assert ctrl._pane == "test-skip:0"
        assert ctrl._transcript is None

    def test_tmux_session_exists_false_for_unknown(self):
        """_tmux_session_exists() returns False for a session name that doesn't exist."""
        ctrl = ClaudeController(session_name="test-skip", cwd="/tmp")
        assert ctrl._tmux_session_exists() is False

    def test_is_healthy_false_when_no_session(self):
        """is_healthy() returns False when the tmux session does not exist."""
        ctrl = ClaudeController(session_name="test-skip", cwd="/tmp")
        assert ctrl.is_healthy() is False

    def test_get_last_response_empty_when_no_transcript(self):
        """get_last_response() returns '' when no transcript file exists."""
        ctrl = ClaudeController(
            session_name="test-no-transcript-xyz",
            cwd="/nonexistent/path/xyz123",
        )
        resp = ctrl.get_last_response()
        assert resp == "", f"Expected '' but got {resp!r}"

    def test_kill_noop_on_nonexistent_session(self):
        """kill() on a non-existent session does not raise."""
        ctrl = ClaudeController(session_name="test-skip", cwd="/tmp")
        ctrl.kill()  # should not raise

    def test_exit_gracefully_noop_on_nonexistent_session(self):
        """exit_gracefully() on a non-existent session does not raise."""
        ctrl = ClaudeController(session_name="test-skip", cwd="/tmp")
        ctrl.exit_gracefully()  # should not raise

    def test_response_dataclass_construction(self):
        """Response dataclass can be constructed with the expected fields."""
        state = ScreenState(mode=ScreenMode.IDLE, raw_text="test")
        r = Response(
            text="Hello world",
            screen_text="raw capture",
            duration=1.23,
            state=state,
            tool_calls=[],
        )
        assert r.text == "Hello world"
        assert r.duration == 1.23

    def test_exception_hierarchy(self):
        """ClaudeTimeoutError, ClaudeNotReadyError, ClaudeSessionError all subclass ClaudeError."""
        assert issubclass(ClaudeTimeoutError, ClaudeError)
        assert issubclass(ClaudeNotReadyError, ClaudeError)
        assert issubclass(ClaudeSessionError, ClaudeError)
