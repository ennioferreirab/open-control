"""
Tests for the screen_parser module.

Covers:
- Self-test samples from screen_parser.py's original __main__ block (7 samples)
- Unit tests from test_tmux_control.py Part 4 (~23 tests)
"""

import pytest

from tmux_claude_control import (
    ScreenMode,
    ScreenState,
    parse_screen,
)
from tmux_claude_control.screen_parser import (
    is_waiting_for_input,
    is_showing_question,
    is_showing_permission,
    is_processing,
)


# ── Sample screen captures used across tests ──────────────────────────────────

SCREEN_QUESTION_OLD = """
╭─ Claude ─────────────────────────────────────────────────╮
│ What programming language do you prefer?                  │
│                                                           │
│  ● Python                                                 │
│  ○ TypeScript                                             │
│  ○ Rust                                                   │
│  ○ Go                                                     │
╰───────────────────────────────────────────────────────────╯
"""

SCREEN_QUESTION_V21 = """
 ☐ Language

Which programming language do you prefer?

❯ 1. Python
     General-purpose language popular for scripting, data science, and backend
     development
  2. TypeScript
     Typed superset of JavaScript for frontend and backend development
  3. Rust
     Systems programming language focused on safety and performance
  4. Go
     Statically typed language designed for simplicity and concurrency
  5. Type something.
────────────────────────────────────────────────────────────────────────────────
  6. Chat about this

Enter to select · ↑/↓ to navigate · Esc to cancel
"""

SCREEN_QUESTION_V21_SEL2 = """
 ☐ Language

Which programming language do you prefer?

  1. Python
     General-purpose language
❯ 2. TypeScript
     Typed superset of JavaScript
  3. Rust
  4. Go
  5. Type something.
────────────────────────────────────────────────────────────────────────────────
  6. Chat about this

Enter to select · ↑/↓ to navigate · Esc to cancel
"""

SCREEN_PERMISSION = """
Claude wants to run: rm -rf /tmp/test_files

Allow? (Y/n)

❯ Yes, allow
  No, don't allow
  Always allow for this session
"""

SCREEN_IDLE = """
Claude Code v2.1.63

? for shortcuts
>
"""

SCREEN_PROCESSING_SPINNER = "⠙ Thinking...\n\nI'll help you with that."
SCREEN_PROCESSING_KEYWORD = "Working...\n\nGenerating response..."
SCREEN_TRANSFIGURING = "✽ Transfiguring…\n"
SCREEN_SCHLEPPING = "✢ Schlepping…\n"

SCREEN_QUESTION_OLD_SEL2 = """
│  What programming language do you prefer?                         │
│   ○ Python                                                         │
│   ● TypeScript                                                     │
│   ○ Rust                                                           │
│   ○ Go                                                             │
"""

SCREEN_ANSI = "\x1b[32m● Python\x1b[0m\n\x1b[0m○ TypeScript\n"


# ── Self-test sample tests (7 samples from original __main__ block) ────────────

class TestSelfTestSamples:
    """Tests mirroring the original screen_parser __main__ self-test."""

    def test_question_old_mode(self):
        """Old-style radio-button question is detected as QUESTION mode."""
        state = parse_screen(SCREEN_QUESTION_OLD)
        assert state.mode == ScreenMode.QUESTION

    def test_question_old_has_options(self):
        """Old-style question has options detected."""
        state = parse_screen(SCREEN_QUESTION_OLD)
        assert len(state.options) > 0

    def test_question_v21_mode(self):
        """v2.1.x numbered-option question is detected as QUESTION mode."""
        state = parse_screen(SCREEN_QUESTION_V21)
        assert state.mode == ScreenMode.QUESTION

    def test_question_v21_has_options(self):
        """v2.1.x question has options detected."""
        state = parse_screen(SCREEN_QUESTION_V21)
        assert len(state.options) > 0

    def test_permission_mode(self):
        """Permission prompt with Allow?(Y/n) is detected as PERMISSION mode."""
        state = parse_screen(SCREEN_PERMISSION)
        assert state.mode == ScreenMode.PERMISSION

    def test_permission_has_options(self):
        """Permission prompt options are parsed."""
        state = parse_screen(SCREEN_PERMISSION)
        assert len(state.options) > 0

    def test_idle_mode(self):
        """The '? for shortcuts' + '>' prompt is detected as IDLE mode."""
        state = parse_screen(SCREEN_IDLE)
        assert state.mode == ScreenMode.IDLE

    def test_processing_spinner_mode(self):
        """A braille spinner followed by 'Thinking...' is detected as PROCESSING."""
        state = parse_screen(SCREEN_PROCESSING_SPINNER)
        assert state.mode == ScreenMode.PROCESSING

    def test_transfiguring_mode(self):
        """'✽ Transfiguring…' is detected as PROCESSING."""
        state = parse_screen(SCREEN_TRANSFIGURING)
        assert state.mode == ScreenMode.PROCESSING

    def test_schlepping_mode(self):
        """'✢ Schlepping…' is detected as PROCESSING."""
        state = parse_screen(SCREEN_SCHLEPPING)
        assert state.mode == ScreenMode.PROCESSING


# ── Part 4 screen parser unit tests (from test_tmux_control.py Part 4) ─────────

class TestQuestionWidgetOldFormat:
    """Tests for the old radio-button glyph (● / ○) question format."""

    def test_question_detected(self):
        """Question widget is detected as QUESTION mode."""
        state = parse_screen(SCREEN_QUESTION_OLD)
        assert state.mode == ScreenMode.QUESTION

    def test_option_count(self):
        """Four options are detected: Python, TypeScript, Rust, Go."""
        state = parse_screen(SCREEN_QUESTION_OLD)
        assert len(state.options) == 4, f"options={[o.label for o in state.options]}"

    def test_first_option_preselected(self):
        """The first option (Python, marked ●) is pre-selected at index 0."""
        state = parse_screen(SCREEN_QUESTION_OLD)
        assert state.selected_option_index == 0

    def test_option_label_extracted(self):
        """The first option label is 'Python' (stripped of the ● glyph)."""
        state = parse_screen(SCREEN_QUESTION_OLD)
        assert state.options, "No options found"
        assert state.options[0].label in ("Python", "● Python")

    def test_second_option_selected(self):
        """When ● is on TypeScript (index 1), selected_option_index is 1."""
        state = parse_screen(SCREEN_QUESTION_OLD_SEL2)
        assert state.selected_option_index == 1, (
            f"selected_index={state.selected_option_index}"
        )


class TestPermissionPrompt:
    """Tests for permission prompt detection and option parsing."""

    def test_permission_detected(self):
        """Allow?(Y/n) is detected as PERMISSION mode."""
        state = parse_screen(SCREEN_PERMISSION)
        assert state.mode == ScreenMode.PERMISSION

    def test_permission_has_options(self):
        """At least one option is parsed from the permission prompt."""
        state = parse_screen(SCREEN_PERMISSION)
        assert len(state.options) > 0, f"options={[o.label for o in state.options]}"


class TestProcessingState:
    """Tests for processing / spinner states."""

    def test_spinner_detected(self):
        """A braille spinner character triggers PROCESSING mode."""
        state = parse_screen(SCREEN_PROCESSING_SPINNER)
        assert state.mode == ScreenMode.PROCESSING

    def test_keyword_processing_detected(self):
        """'Working...' keyword triggers PROCESSING mode."""
        state = parse_screen(SCREEN_PROCESSING_KEYWORD)
        assert state.mode == ScreenMode.PROCESSING

    def test_transfiguring_detected(self):
        """'✽ Transfiguring…' is detected as PROCESSING."""
        state = parse_screen(SCREEN_TRANSFIGURING)
        assert state.mode == ScreenMode.PROCESSING


class TestIdleState:
    """Tests for idle input prompt detection."""

    def test_idle_detected(self):
        """'? for shortcuts' + '>' is detected as IDLE mode."""
        state = parse_screen(SCREEN_IDLE)
        assert state.mode == ScreenMode.IDLE


class TestConveniencePredicates:
    """Tests for the is_* predicate functions."""

    def test_is_showing_question_true(self):
        """is_showing_question returns True for a question screen."""
        state = parse_screen(SCREEN_QUESTION_OLD)
        assert is_showing_question(state)

    def test_is_showing_permission_true(self):
        """is_showing_permission returns True for a permission screen."""
        state = parse_screen(SCREEN_PERMISSION)
        assert is_showing_permission(state)

    def test_is_processing_true(self):
        """is_processing returns True for a spinner screen."""
        state = parse_screen(SCREEN_PROCESSING_SPINNER)
        assert is_processing(state)

    def test_is_waiting_for_input_true(self):
        """is_waiting_for_input returns True for an idle screen."""
        state = parse_screen(SCREEN_IDLE)
        assert is_waiting_for_input(state)


class TestV21NumberedFormat:
    """Tests for the v2.1.x numbered-option format with ❯ cursor."""

    def test_question_detected(self):
        """v2.1 numbered format is detected as QUESTION mode."""
        state = parse_screen(SCREEN_QUESTION_V21)
        assert state.mode == ScreenMode.QUESTION

    def test_five_options(self):
        """Five options are detected including 'Type something.'."""
        state = parse_screen(SCREEN_QUESTION_V21)
        assert len(state.options) == 5, f"options={[o.label for o in state.options]}"

    def test_first_option_selected(self):
        """The ❯ cursor on option 1 means selected_option_index is 0."""
        state = parse_screen(SCREEN_QUESTION_V21)
        assert state.selected_option_index == 0

    def test_first_label_is_python(self):
        """The first option label is 'Python'."""
        state = parse_screen(SCREEN_QUESTION_V21)
        assert state.options, "No options found"
        assert state.options[0].label == "Python", f"label={state.options[0].label!r}"

    def test_question_text_extracted(self):
        """The question text contains 'programming language'."""
        state = parse_screen(SCREEN_QUESTION_V21)
        assert "programming language" in state.question_text.lower(), (
            f"question={state.question_text!r}"
        )

    def test_second_option_selected_after_down(self):
        """When ❯ is on option 2 (TypeScript), selected_option_index is 1."""
        state = parse_screen(SCREEN_QUESTION_V21_SEL2)
        assert state.selected_option_index == 1, (
            f"selected_index={state.selected_option_index}"
        )


class TestAnsiStripping:
    """Tests for ANSI escape code removal before parsing."""

    def test_ansi_stripped_question_detected(self):
        """ANSI codes are stripped and the question is still detected."""
        state = parse_screen(SCREEN_ANSI)
        assert state.mode == ScreenMode.QUESTION
        assert len(state.options) == 2


class TestSelectedOptionMethod:
    """Tests for the selected_option() convenience method on ScreenState."""

    def test_selected_option_returns_correct_option(self):
        """selected_option() returns the TUIOption at selected_option_index."""
        state = parse_screen(SCREEN_QUESTION_OLD)
        assert state.options, "No options found"
        sel = state.selected_option()
        assert sel is not None
        assert sel.index == state.selected_option_index
