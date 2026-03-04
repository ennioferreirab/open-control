"""
claude_controller.py — High-level Python API to control a Claude Code session via tmux.

Combines screen parsing (screen_parser.py) with transcript reading
(transcript_reader.py) to drive Claude Code programmatically.

Usage:
    from tmux_claude_control import ClaudeController, Response

    ctrl = ClaudeController(session_name="my-claude", cwd="/tmp/workdir")
    ctrl.launch()
    resp = ctrl.send_prompt("Write a hello world in Python")
    print(resp.text)
    ctrl.exit_gracefully()
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .screen_parser import (
    ScreenMode,
    ScreenState,
    parse_screen,
)
from .transcript_reader import ToolCall, TranscriptReader


# ── Constants ─────────────────────────────────────────────────────────────────

POLL_INTERVAL: float = 0.4          # seconds between wait_for_idle polls
CLAUDE_STARTUP_WAIT: float = 6.0    # seconds to wait after launching Claude
KEYSTROKE_SLEEP: float = 0.05       # sleep between individual keystrokes
PRE_ENTER_SLEEP: float = 0.5        # sleep after typing text but before Enter (Claude TUI needs time to render)

# Patterns that indicate an error state in the screen output
ERROR_PATTERNS: list[str] = [
    "rate limit",
    "Rate limit",
    "Error:",
    "error:",
    "Connection refused",
    "ECONNREFUSED",
    "context window",
    "token limit",
    "API error",
    "timed out",
    "Session expired",
]


# ── Custom exceptions ─────────────────────────────────────────────────────────

class ClaudeError(Exception):
    """Base exception for Claude controller errors."""


class ClaudeTimeoutError(ClaudeError):
    """Timed out waiting for Claude."""


class ClaudeNotReadyError(ClaudeError):
    """Claude is not in the expected state."""


class ClaudeSessionError(ClaudeError):
    """Tmux session does not exist or Claude crashed."""


# ── Response dataclass ────────────────────────────────────────────────────────

@dataclass
class Response:
    """Result of sending a prompt to Claude."""
    text: str                          # The assistant's response text (from JSONL)
    screen_text: str                   # Raw screen capture at completion
    duration: float                    # Seconds from prompt send to idle
    state: ScreenState                 # Final screen state
    tool_calls: list[ToolCall] = field(default_factory=list)  # Tools used during this response


# ── ClaudeController ──────────────────────────────────────────────────────────

class ClaudeController:
    """
    High-level controller for a Claude Code session running inside a tmux pane.

    The controller combines:
      - tmux send-keys / capture-pane for driving the TUI
      - screen_parser.parse_screen() for state detection
      - TranscriptReader for reliable response extraction from JSONL

    All I/O is synchronous (subprocess + time.sleep). No async required.
    """

    def __init__(self, session_name: str = "claude-ctrl", cwd: str = ".") -> None:
        """Initialize controller. Does NOT launch Claude yet; call launch() for that."""
        self.session_name = session_name
        self.cwd = str(Path(cwd).expanduser().resolve())
        self._transcript: Optional[TranscriptReader] = None
        self._pane: str = f"{session_name}:0"

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def launch(
        self,
        dangerous_skip: bool = True,
        wait_ready: bool = True,
        timeout: float = 30.0,
    ) -> None:
        """
        Create a detached tmux session, launch Claude Code inside it, and wait
        until Claude is at the idle input prompt.

        Steps:
          1. Kill any existing session with the same name (cleanup).
          2. Create a new detached tmux session.
          3. cd into self.cwd.
          4. Run 'claude [--dangerously-skip-permissions]'.
          5. Wait CLAUDE_STARTUP_WAIT seconds, then press Enter to dismiss any
             welcome/update banners.
          6. Optionally wait for idle screen state.
          7. Detect the transcript file (most recently modified ses_*.jsonl).
        """
        # 1. Kill any existing session with the same name
        if self._tmux_session_exists():
            subprocess.run(
                ["tmux", "kill-session", "-t", self.session_name],
                check=False,
                capture_output=True,
            )
            time.sleep(0.2)

        # 2. Create a new detached tmux session
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", self.session_name],
            check=True,
            capture_output=True,
        )
        time.sleep(0.1)

        # 3. cd into the working directory
        self._tmux_send(f"cd {self.cwd}")
        self._tmux_key("Enter")
        time.sleep(0.2)

        # 4. Launch Claude Code
        claude_cmd = "claude"
        if dangerous_skip:
            claude_cmd += " --dangerously-skip-permissions"
        self._tmux_send(claude_cmd)
        self._tmux_key("Enter")

        # 5. Wait for Claude to start up, then handle any trust / welcome prompts
        time.sleep(CLAUDE_STARTUP_WAIT)

        # Claude Code shows a "trust this folder?" question for new directories.
        # Detect it and press Enter to accept the default ("Yes, I trust this folder").
        trust_deadline = time.monotonic() + 15.0
        entered_once = False
        while time.monotonic() < trust_deadline:
            raw = self._tmux_capture()
            state = parse_screen(raw)
            if state.mode == ScreenMode.QUESTION:
                # Trust question or other startup prompt — accept default
                self._tmux_key("Enter")
                time.sleep(1.5)
                entered_once = False  # reset — need to re-check
            elif state.mode == ScreenMode.IDLE:
                break
            elif not entered_once:
                # First time seeing non-idle/non-question — press Enter once
                # to dismiss welcome banner, then wait for state to settle
                self._tmux_key("Enter")
                entered_once = True
                time.sleep(1.0)
            else:
                # Already pressed Enter once, just wait
                time.sleep(0.5)

        # 6. Wait for idle state
        if wait_ready:
            self.wait_for_idle(timeout=timeout)

        # 7. Detect the transcript file (most recently modified *.jsonl,
        #    checking both ~/.claude/projects/<cwd>/ and ~/.claude/transcripts/)
        transcript_path = TranscriptReader.detect_transcript_for_session(
            self.session_name, cwd=self.cwd
        )
        if transcript_path is not None:
            self._transcript = TranscriptReader(transcript_path)

    def kill(self) -> None:
        """Kill the tmux session forcefully."""
        if self._tmux_session_exists():
            subprocess.run(
                ["tmux", "kill-session", "-t", self.session_name],
                check=False,
                capture_output=True,
            )

    def exit_gracefully(self) -> None:
        """Send /exit to Claude, wait for process to end, then kill the tmux session."""
        if not self._tmux_session_exists():
            return

        try:
            # Send /exit and press Enter
            self._tmux_send("/exit")
            self._tmux_key("Enter")

            # Wait up to 10 seconds for the session to disappear or Claude to quit
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                if not self._tmux_session_exists():
                    return
                # Check if the shell prompt is back (Claude exited but shell running)
                raw = self._tmux_capture()
                clean = raw.strip().splitlines()
                last_lines = [l.strip() for l in clean[-5:] if l.strip()]
                if any(
                    l.startswith("$") or l.startswith("%") or l.endswith("$") or l.endswith("%")
                    for l in last_lines
                ):
                    break
                time.sleep(0.5)
        except Exception:
            pass

        # Forcefully kill whatever remains
        self.kill()

    # ── Core interaction ───────────────────────────────────────────────────────

    def send_prompt(self, text: str, timeout: float = 120.0) -> Response:
        """
        Send a prompt to Claude and wait for the complete response.

        Steps:
          1. Verify Claude is in IDLE state (wait for it if not).
          2. Record the current transcript file position / timestamp.
          3. Type the prompt and press Enter.
          4. Wait for Claude to start processing (leave IDLE).
          5. Wait for Claude to finish (screen returns to IDLE).
          6. Extract response from JSONL transcript.
          7. Return Response object.
        """
        # 1. Ensure Claude is idle before sending
        state = self.get_state()
        if state.mode != ScreenMode.IDLE:
            self.wait_for_idle(timeout=min(30.0, timeout))

        # 2. Record baseline timestamp for filtering new tool calls later.
        #    Also refresh the transcript reference in case it was created after launch().
        self._refresh_transcript()
        tool_call_baseline_time: Optional[str] = None
        if self._transcript is not None:
            try:
                existing_calls = self._transcript.get_tool_calls()
                if existing_calls:
                    tool_call_baseline_time = existing_calls[-1].timestamp
            except Exception:
                pass

        start_time = time.monotonic()

        # 3. Type the prompt and press Enter
        self._tmux_send(text)
        time.sleep(PRE_ENTER_SLEEP)
        self._tmux_key("Enter")

        # 4. Wait for Claude to start processing (leave IDLE state).
        #    This avoids the race where we poll for IDLE before Claude has even
        #    begun thinking.
        self._wait_for_processing(timeout=15.0)

        # 5. Now wait for Claude to return to IDLE (response complete).
        remaining = timeout - (time.monotonic() - start_time)
        final_state = self.wait_for_idle(timeout=max(remaining, 5.0))
        duration = time.monotonic() - start_time

        # 6. Capture screen at completion
        screen_text = self._tmux_capture()

        # Refresh transcript reference — it may have been created DURING the
        # response (first prompt of a brand-new session).  Poll briefly to give
        # Claude time to flush the JSONL writer before we read.
        response_text = self._wait_for_transcript_response(
            baseline_response=self._transcript.get_last_response()
            if self._transcript is not None else "",
            send_time=start_time,
            timeout=10.0,
        )

        # 7. Extract tool calls from the JSONL transcript
        tool_calls: list[ToolCall] = []
        if self._transcript is not None:
            try:
                all_calls = self._transcript.get_tool_calls()
                if tool_call_baseline_time is not None:
                    tool_calls = [
                        tc for tc in all_calls
                        if tc.timestamp > tool_call_baseline_time
                    ]
                else:
                    tool_calls = all_calls
            except Exception:
                tool_calls = []

        return Response(
            text=response_text,
            screen_text=screen_text,
            duration=duration,
            state=final_state,
            tool_calls=tool_calls,
        )

    def wait_for_idle(self, timeout: float = 120.0) -> ScreenState:
        """
        Poll the screen until Claude is in IDLE state.

        Raises ClaudeTimeoutError if the timeout is exceeded.
        Raises ClaudeError if an error pattern is detected on screen.
        Raises ClaudeSessionError if the tmux session disappears.
        """
        deadline = time.monotonic() + timeout

        # Only raise on patterns that definitively indicate a terminal/fatal error
        # and are unlikely to appear in normal tool output.
        FATAL_PATTERNS = [
            "rate limit",
            "Rate limit",
            "Connection refused",
            "ECONNREFUSED",
            "context window",
            "token limit",
            "API error",
            "Session expired",
        ]

        while time.monotonic() < deadline:
            if not self._tmux_session_exists():
                raise ClaudeSessionError(
                    f"Tmux session '{self.session_name}' no longer exists"
                )

            raw = self._tmux_capture()

            # Check for fatal error patterns before doing normal state detection
            for pattern in FATAL_PATTERNS:
                if pattern in raw:
                    raise ClaudeError(
                        f"Fatal error pattern detected on screen: {pattern!r}\n"
                        f"Screen snippet: {raw[-500:]!r}"
                    )

            state = parse_screen(raw)
            if state.mode == ScreenMode.IDLE:
                return state

            time.sleep(POLL_INTERVAL)

        raise ClaudeTimeoutError(
            f"Timed out after {timeout}s waiting for Claude to become idle"
        )

    def answer_question(self, option: int | str) -> None:
        """
        Answer an AskUserQuestion widget.

        Parameters
        ----------
        option:
            If int   — press that number key directly (1-indexed instant select).
            If str   — navigate to the "Type something" option, type the text,
                       then press Enter.

        Waits for QUESTION state first if not already showing.
        """
        # Ensure we are in QUESTION state
        state = self.get_state()
        if state.mode != ScreenMode.QUESTION:
            # Wait briefly for question to appear
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                state = self.get_state()
                if state.mode == ScreenMode.QUESTION:
                    break
                time.sleep(POLL_INTERVAL)
            else:
                raise ClaudeNotReadyError(
                    f"Expected QUESTION mode, got {state.mode.value!r}"
                )

        if isinstance(option, int):
            # Press the digit key directly (Claude Code supports 1-indexed instant select)
            self._tmux_key(str(option))
            time.sleep(PRE_ENTER_SLEEP)
            self._tmux_key("Enter")
        else:
            # Navigate to "Type something" option
            # Find it in options list
            type_something_idx: Optional[int] = None
            for opt in state.options:
                if "type something" in opt.label.lower():
                    type_something_idx = opt.index
                    break

            if type_something_idx is None:
                raise ClaudeNotReadyError(
                    "Could not find 'Type something' option in question widget"
                )

            # Navigate using Up/Down arrows to reach the "Type something" option
            current_idx = state.selected_option_index
            steps = type_something_idx - current_idx
            key = "Down" if steps > 0 else "Up"
            for _ in range(abs(steps)):
                self._tmux_key(key)
                time.sleep(KEYSTROKE_SLEEP)

            # Press Enter to select the "Type something" option
            self._tmux_key("Enter")
            time.sleep(0.2)

            # Type the text and submit
            self._tmux_send(option)
            time.sleep(PRE_ENTER_SLEEP)
            self._tmux_key("Enter")

    def send_slash_command(self, cmd: str) -> None:
        """
        Send a slash command such as /compact, /clear, /model, /exit.

        Does not wait for a response (some commands are instant, others
        may trigger a transition — caller should wait_for_idle() if needed).
        """
        # Ensure cmd starts with a slash
        if not cmd.startswith("/"):
            cmd = "/" + cmd
        self._tmux_send(cmd)
        time.sleep(PRE_ENTER_SLEEP)
        self._tmux_key("Enter")

    def cancel(self) -> None:
        """Cancel the current operation by sending Escape then Ctrl+C."""
        self._tmux_key("Escape")
        time.sleep(KEYSTROKE_SLEEP)
        self._tmux_key("C-c")
        time.sleep(0.2)

    # ── State queries ──────────────────────────────────────────────────────────

    def get_state(self) -> ScreenState:
        """Capture the current screen and parse it into a ScreenState."""
        raw = self._tmux_capture()
        return parse_screen(raw)

    def get_last_response(self) -> str:
        """Return the last assistant response from the JSONL transcript."""
        if self._transcript is None:
            # Try to auto-detect the transcript lazily
            transcript_path = TranscriptReader.detect_transcript_for_session(
                self.session_name, cwd=self.cwd
            )
            if transcript_path is None:
                return ""
            self._transcript = TranscriptReader(transcript_path)
        try:
            return self._transcript.get_last_response()
        except Exception:
            return ""

    def is_healthy(self) -> bool:
        """
        Check if the Claude session is alive and responsive.

        Returns False if:
          - The tmux session does not exist.
          - The screen contains a fatal error indicator.
        """
        if not self._tmux_session_exists():
            return False
        try:
            raw = self._tmux_capture()
        except Exception:
            return False
        # Check for hard error patterns
        for pattern in ("Session expired", "ECONNREFUSED", "Connection refused"):
            if pattern in raw:
                return False
        return True

    def is_idle(self) -> bool:
        """Return True if Claude is currently at the idle input prompt."""
        state = self.get_state()
        return state.mode == ScreenMode.IDLE

    # ── Low-level tmux operations ──────────────────────────────────────────────

    def _tmux_send(self, text: str) -> None:
        """
        Send literal text to the tmux pane.

        Uses the empty string "" as the terminator so that special characters
        in `text` are not interpreted as key names by tmux.
        """
        subprocess.run(
            ["tmux", "send-keys", "-t", self._pane, text, ""],
            check=True,
            capture_output=True,
        )

    def _tmux_key(self, key: str) -> None:
        """
        Send a named key to the tmux pane.

        Named keys include: Enter, Up, Down, Left, Right, Escape, C-c, Tab, etc.
        """
        subprocess.run(
            ["tmux", "send-keys", "-t", self._pane, key],
            check=True,
            capture_output=True,
        )

    def _tmux_capture(self) -> str:
        """
        Capture the current tmux pane content.

        Uses -S -100 to include up to 100 lines of scrollback so we don't miss
        content that has scrolled off the visible area.
        """
        result = subprocess.run(
            [
                "tmux", "capture-pane",
                "-t", self._pane,
                "-p",          # print to stdout
                "-S", "-100",  # include 100 lines of scrollback
            ],
            capture_output=True,
            text=True,
        )
        return result.stdout

    def _tmux_session_exists(self) -> bool:
        """Return True if the tmux session currently exists."""
        result = subprocess.run(
            ["tmux", "has-session", "-t", self.session_name],
            capture_output=True,
        )
        return result.returncode == 0

    def _wait_for_processing(self, timeout: float = 15.0) -> None:
        """
        Poll until Claude leaves IDLE (i.e., starts processing the prompt).

        This is used after pressing Enter on a prompt to avoid the race condition
        where wait_for_idle() returns immediately because the screen is still in
        IDLE mode before Claude has started thinking.

        Does NOT raise on timeout — if Claude never leaves IDLE it could mean the
        prompt was rejected or the session stalled; wait_for_idle() will handle
        the wait for the actual response.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self._tmux_session_exists():
                return
            state = parse_screen(self._tmux_capture())
            if state.mode != ScreenMode.IDLE:
                return  # Claude started doing something
            time.sleep(POLL_INTERVAL)

    def _refresh_transcript(self) -> None:
        """
        Re-detect the most recently modified transcript file.

        Called both before and after sending a prompt to handle the case where
        the transcript file is created during the first response (after launch()).
        If a newer file exists than what we currently have, update self._transcript.
        """
        try:
            latest_path = TranscriptReader.detect_transcript_for_session(
                self.session_name, cwd=self.cwd
            )
        except Exception:
            return

        if latest_path is None:
            return

        if self._transcript is None or latest_path != self._transcript.path:
            self._transcript = TranscriptReader(latest_path)

    def _wait_for_transcript_response(
        self,
        baseline_response: str,
        send_time: float,
        timeout: float = 10.0,
    ) -> str:
        """
        Poll the transcript until a NEW assistant response appears (different
        from `baseline_response`) and return it.

        This is needed because the JSONL writer may flush slightly after the
        screen returns to IDLE.  We also re-detect the transcript file here in
        case Claude created a new one during the response (first prompt of a
        brand-new session).

        Parameters
        ----------
        baseline_response:
            The last known response BEFORE this prompt was sent.  We poll
            until a DIFFERENT (newer) response appears.
        send_time:
            monotonic timestamp of when the prompt was sent.  Used to avoid
            mistaking a previous response for the new one.
        timeout:
            Maximum seconds to wait for the response to appear in the transcript.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # Re-detect the transcript file (handles the case where Claude
            # created a new file for this session)
            self._refresh_transcript()

            if self._transcript is not None:
                try:
                    latest = self._transcript.get_last_response()
                    if latest and latest != baseline_response:
                        return latest
                except Exception:
                    pass

            time.sleep(0.3)

        # Timed out waiting for transcript — return whatever we have
        if self._transcript is not None:
            try:
                return self._transcript.get_last_response()
            except Exception:
                pass
        return ""

