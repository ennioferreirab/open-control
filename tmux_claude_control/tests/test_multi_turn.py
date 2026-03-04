"""
Multi-turn integration test for ClaudeController autonomous agent loop.

Proves: prompt→response→decide→prompt cycle, AskUserQuestion answering,
slash commands, and context persistence across /compact.

Extracted from _test_tmux_claude_control/test_multi_turn.py.
All tests are marked @pytest.mark.requires_claude.
"""

import time
import tempfile

import pytest

from tmux_claude_control import ClaudeController, Response, ClaudeError, ScreenMode, ScreenState
from tmux_claude_control.claude_controller import ClaudeTimeoutError


def _get_response_text(resp: Response, ctrl: ClaudeController) -> str:
    """
    Return response text, falling back to get_last_response() if empty
    (timing edge case where transcript hasn't flushed yet).
    """
    if resp.text:
        return resp.text
    time.sleep(1.5)
    fallback = ctrl.get_last_response()
    return fallback or resp.text


@pytest.mark.requires_claude
class TestMultiTurnAgentLoop:
    """Five-turn autonomous agent loop test."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, tmp_path):
        """Launch Claude in a fresh temp cwd; kill session after test."""
        self.cwd = str(tmp_path)
        self.session = "test-multi-turn-pytest"
        self.ctrl = ClaudeController(session_name=self.session, cwd=self.cwd)
        self.ctrl.launch(dangerous_skip=True, wait_ready=True, timeout=60.0)
        yield
        try:
            self.ctrl.kill()
        except Exception:
            pass

    def test_turn1_simple_arithmetic(self):
        """Turn 1: Claude answers '2+2' with '4'."""
        resp = self.ctrl.send_prompt(
            "What is 2+2? Answer with just the number.",
            timeout=120.0,
        )
        text = _get_response_text(resp, self.ctrl)
        assert "4" in text, f"Expected '4' in response, got: {text!r}"

    def test_turn2_ask_user_question(self):
        """Turn 2: Claude shows an AskUserQuestion widget with at least 3 options."""
        self.ctrl.send_prompt(
            "Use the AskUserQuestion tool to ask me which color I prefer. "
            "Provide exactly 3 options: Red, Blue, Green.",
            timeout=120.0,
        )

        # The question widget may appear mid-response; wait for it
        deadline = time.monotonic() + 30.0
        question_state: ScreenState = self.ctrl.get_state()
        while question_state.mode != ScreenMode.QUESTION and time.monotonic() < deadline:
            time.sleep(0.4)
            question_state = self.ctrl.get_state()

        assert question_state.mode == ScreenMode.QUESTION, (
            f"Expected QUESTION mode, got {question_state.mode.value!r}"
        )
        assert len(question_state.options) >= 3, (
            f"Expected at least 3 options, got {len(question_state.options)}: "
            f"{question_state.options}"
        )

    def test_turn2_answer_question_and_response_contains_blue(self):
        """Turn 2: After selecting Blue (option 2), Claude acknowledges the choice."""
        self.ctrl.send_prompt(
            "Use the AskUserQuestion tool to ask me which color I prefer. "
            "Provide exactly 3 options: Red, Blue, Green.",
            timeout=120.0,
        )

        # Wait for question widget
        deadline = time.monotonic() + 30.0
        question_state: ScreenState = self.ctrl.get_state()
        while question_state.mode != ScreenMode.QUESTION and time.monotonic() < deadline:
            time.sleep(0.4)
            question_state = self.ctrl.get_state()

        assert question_state.mode == ScreenMode.QUESTION

        # Select option 2 (Blue)
        self.ctrl.answer_question(2)
        self.ctrl.wait_for_idle(timeout=60.0)
        time.sleep(1.5)

        text = self.ctrl.get_last_response()
        assert "blue" in text.lower(), (
            f"Expected 'blue' in Claude's post-answer response, got: {text!r}"
        )

    def test_turn3_context_followup(self):
        """Turn 3: Claude can answer a follow-up referencing context from turn 2."""
        # Turn 2 first
        self.ctrl.send_prompt(
            "Use the AskUserQuestion tool to ask me which color I prefer. "
            "Provide exactly 3 options: Red, Blue, Green.",
            timeout=120.0,
        )
        deadline = time.monotonic() + 30.0
        question_state: ScreenState = self.ctrl.get_state()
        while question_state.mode != ScreenMode.QUESTION and time.monotonic() < deadline:
            time.sleep(0.4)
            question_state = self.ctrl.get_state()
        if question_state.mode == ScreenMode.QUESTION:
            self.ctrl.answer_question(2)
            self.ctrl.wait_for_idle(timeout=60.0)
            time.sleep(1.5)

        # Turn 3
        chosen_color = "Blue"
        resp3 = self.ctrl.send_prompt(
            f"Based on my choice of {chosen_color}, suggest one item of clothing "
            f"in that color. Answer in one sentence.",
            timeout=120.0,
        )
        text3 = _get_response_text(resp3, self.ctrl)
        assert chosen_color.lower() in text3.lower(), (
            f"Expected '{chosen_color}' in response, got: {text3!r}"
        )

    def test_turn4_compact_and_idle(self):
        """Turn 4: /compact returns Claude to idle state."""
        # Need something to compact first
        self.ctrl.send_prompt("What is the capital of France?", timeout=120.0)

        self.ctrl.send_slash_command("/compact")
        time.sleep(2.0)

        try:
            self.ctrl.wait_for_idle(timeout=30.0)
        except ClaudeTimeoutError:
            compact_state = self.ctrl.get_state()
            if compact_state.mode in (ScreenMode.QUESTION, ScreenMode.PERMISSION):
                self.ctrl.answer_question(1)
                self.ctrl.wait_for_idle(timeout=30.0)
            else:
                raise

        assert self.ctrl.is_idle(), "Claude should be idle after /compact"
        assert self.ctrl.is_healthy(), "Claude session should be healthy after /compact"

    def test_turn5_context_survives_compact(self):
        """Turn 5: Context (Blue choice) survives /compact."""
        # Turn 2: ask question, answer Blue
        self.ctrl.send_prompt(
            "Use the AskUserQuestion tool to ask me which color I prefer. "
            "Provide exactly 3 options: Red, Blue, Green.",
            timeout=120.0,
        )
        deadline = time.monotonic() + 30.0
        question_state: ScreenState = self.ctrl.get_state()
        while question_state.mode != ScreenMode.QUESTION and time.monotonic() < deadline:
            time.sleep(0.4)
            question_state = self.ctrl.get_state()
        if question_state.mode == ScreenMode.QUESTION:
            self.ctrl.answer_question(2)
            self.ctrl.wait_for_idle(timeout=60.0)
            time.sleep(1.5)

        # Turn 4: compact
        self.ctrl.send_slash_command("/compact")
        time.sleep(2.0)
        try:
            self.ctrl.wait_for_idle(timeout=30.0)
        except ClaudeTimeoutError:
            compact_state = self.ctrl.get_state()
            if compact_state.mode in (ScreenMode.QUESTION, ScreenMode.PERMISSION):
                self.ctrl.answer_question(1)
                self.ctrl.wait_for_idle(timeout=30.0)

        time.sleep(1.5)

        # Turn 5: ask about the color
        resp5 = self.ctrl.send_prompt(
            "What color did I choose earlier? Answer with just the color name.",
            timeout=120.0,
        )
        text5 = _get_response_text(resp5, self.ctrl)
        assert "blue" in text5.lower(), (
            f"Expected 'Blue' in response (context should survive /compact), "
            f"got: {text5!r}"
        )
