"""
Integration tests that require a live Claude Code session.

Extracted from:
- test_tmux_control.py Part 3 (integration test)
- claude_controller.py's _run_full_tests()

All tests are marked @pytest.mark.requires_claude.
Run these with: uv run pytest tmux_claude_control/tests/test_integration.py -v
Skip with:      uv run pytest tmux_claude_control/tests/ --skip-claude -v
"""

import time
import tempfile
import subprocess

import pytest

from tmux_claude_control import ClaudeController, ScreenMode
from tmux_claude_control.claude_controller import ClaudeTimeoutError


@pytest.mark.requires_claude
class TestClaudeControllerIntegration:
    """Full integration tests that launch a real Claude Code session."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, tmp_path):
        """Create controller for a fresh temp cwd; kill session after each test."""
        self.cwd = str(tmp_path)
        self.session = "claude-ctrl-itest"
        self.ctrl = ClaudeController(session_name=self.session, cwd=self.cwd)
        yield
        # Always clean up the tmux session
        try:
            self.ctrl.kill()
        except Exception:
            pass

    def test_launch_and_idle(self):
        """After launch(), Claude is alive and in IDLE state."""
        self.ctrl.launch(dangerous_skip=True, wait_ready=True, timeout=60.0)
        assert self.ctrl._tmux_session_exists(), "Tmux session should exist after launch"
        assert self.ctrl.is_idle(), (
            f"Claude should be idle after launch, got: {self.ctrl.get_state().mode.value}"
        )

    def test_send_simple_prompt(self):
        """send_prompt() returns a non-empty response."""
        self.ctrl.launch(dangerous_skip=True, wait_ready=True, timeout=60.0)
        resp = self.ctrl.send_prompt("Say hello in exactly 3 words", timeout=120.0)
        assert resp.text, "Expected non-empty response text"
        assert resp.duration > 0

    def test_compact_slash_command(self):
        """After /compact, Claude returns to IDLE state."""
        self.ctrl.launch(dangerous_skip=True, wait_ready=True, timeout=60.0)
        # Send something first so there is content to compact
        self.ctrl.send_prompt("What is 2+2?", timeout=120.0)

        self.ctrl.send_slash_command("/compact")
        time.sleep(2.0)

        try:
            self.ctrl.wait_for_idle(timeout=30.0)
        except ClaudeTimeoutError:
            # /compact may ask a confirmation question — answer the first option
            state = self.ctrl.get_state()
            if state.mode == ScreenMode.QUESTION:
                self.ctrl.answer_question(1)
                self.ctrl.wait_for_idle(timeout=30.0)
            else:
                raise

        assert self.ctrl.is_idle(), "Claude should be idle after /compact"

    def test_exit_gracefully(self):
        """exit_gracefully() terminates the tmux session."""
        self.ctrl.launch(dangerous_skip=True, wait_ready=True, timeout=60.0)
        self.ctrl.exit_gracefully()
        time.sleep(1.0)
        assert not self.ctrl._tmux_session_exists(), (
            "Expected tmux session to be gone after exit_gracefully()"
        )


@pytest.mark.requires_claude
class TestTmuxIntegrationLegacy:
    """Integration test mirroring test_tmux_control.py Part 3."""

    def test_ask_user_question_widget(self):
        """Claude can show an AskUserQuestion TUI widget and receive a selection."""
        session = "test-claude-control-itest"
        cwd = tempfile.mkdtemp(prefix="itest_")
        ctrl = ClaudeController(session_name=session, cwd=cwd)

        try:
            ctrl.launch(dangerous_skip=True, wait_ready=True, timeout=60.0)

            prompt = (
                "Use the AskUserQuestion tool to ask me which programming language I prefer. "
                "Provide exactly these 4 options: Python, TypeScript, Rust, Go. "
                "Start with option 1 (Python) as the first option."
            )

            # The question widget appears mid-response (before send_prompt returns),
            # so we detect it first then answer it.
            # send_prompt may block waiting for idle after the answer — that's fine.
            ctrl._tmux_send(prompt)
            time.sleep(0.5)
            ctrl._tmux_key("Enter")

            # Wait for the question widget to appear
            deadline = time.monotonic() + 60.0
            question_state = ctrl.get_state()
            while question_state.mode != ScreenMode.QUESTION and time.monotonic() < deadline:
                time.sleep(0.4)
                question_state = ctrl.get_state()

            assert question_state.mode == ScreenMode.QUESTION, (
                f"Expected QUESTION mode, got {question_state.mode.value!r}"
            )
            assert len(question_state.options) >= 4, (
                f"Expected at least 4 options, got {len(question_state.options)}"
            )

            # Select option 2 (TypeScript) by pressing Down once, then Enter
            ctrl._tmux_key("Down")
            time.sleep(0.3)
            ctrl._tmux_key("Enter")

            # Wait for Claude to return to idle
            ctrl.wait_for_idle(timeout=60.0)

        finally:
            try:
                ctrl.kill()
            except Exception:
                pass
            import shutil
            shutil.rmtree(cwd, ignore_errors=True)
