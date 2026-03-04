"""
screen_parser.py — Parse Claude Code TUI screen captures into structured state.

Claude Code renders a terminal UI using ink/react-blessed-like components.
This module pattern-matches raw tmux capture output to identify what Claude is
currently showing and what interaction is expected from the user.

Usage:
    from tmux_claude_control import parse_screen, ScreenState, ScreenMode

    captured = subprocess.run(
        ["tmux", "capture-pane", "-t", "session:0", "-p", "-S", "-50"],
        capture_output=True, text=True
    ).stdout
    state = parse_screen(captured)
    print(state.mode, state.options, state.selected_option_index)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Unicode glyphs used by Claude Code's TUI ──────────────────────────────────
#
# AskUserQuestion (v2.1.x) renders numbered options with a cursor prefix:
#
#   ❯ 1. Python               ← selected/highlighted (cursor ❯ + number)
#        Description here      ← description on next line (indented)
#     2. TypeScript            ← unselected (spaces + number)
#     3. Rust
#     4. Go
#     5. Type something.       ← free-text "Other" option
#   ──────────────────────
#     6. Chat about this       ← below separator, meta-option
#
#   Enter to select · ↑/↓ to navigate · Esc to cancel   ← footer hint
#
# Older versions may use radio-button glyphs:
#   ○  U+25CB WHITE CIRCLE          — unselected option
#   ●  U+25CF BLACK CIRCLE          — selected / highlighted option
#
# Permission prompts use the same cursor:
#   ❯  U+276F HEAVY RIGHT-POINTING ANGLE QUOTATION MARK ORNAMENT
#
# Processing / spinner frames (braille pattern spinners):
#   ⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏  — braille spinner characters
#
# Other processing indicators (decorative Unicode + space + text + "…"):
#   ✽  U+273D — "✽ Transfiguring…"
#   ✢  U+2722 — "✢ Schlepping…"
#   ★  U+2605 — "★ Conjuring…"
#   ✧  U+2727 — various
#   ✦  U+2726 — various
#   ✻  U+273B — various
#   ❋  U+274B — various
#   ⏺  U+23FA — tool execution / completed action marker

UNSELECTED_GLYPHS = {"○", "◯", "◦", "•"}
SELECTED_GLYPHS = {"●", "◉", "◎", "◈"}
SPINNER_GLYPHS = set("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
# Decorative Unicode symbols Claude Code uses as processing indicators,
# e.g. "✽ Transfiguring…", "✢ Schlepping…", "★ Conjuring…"
PROCESSING_INDICATOR_GLYPHS = set("✽✢★✧✦✻❋✾✿❀❁❂❃")
CURSOR_GLYPH = "❯"

# Regex for Claude Code's numbered option format: "❯ 1. Label" or "  2. Label"
# The ❯ prefix marks the currently highlighted option
NUMBERED_OPTION_RE = re.compile(r"^(\s*)(❯\s*)?\d+\.\s+(.+)$")
# Footer hint that confirms we're in an AskUserQuestion widget
ASK_FOOTER_RE = re.compile(r"Enter to select.*↑/↓ to navigate|↑/↓ to navigate.*Esc to cancel")

# ANSI escape sequence remover
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Patterns for detecting Claude Code states
PERMISSION_PATTERNS = [
    re.compile(r"Allow\?", re.IGNORECASE),
    re.compile(r"Do you want to allow", re.IGNORECASE),
    re.compile(r"\(Y/n\)", re.IGNORECASE),
    re.compile(r"\(y/N\)", re.IGNORECASE),
    re.compile(r"Always allow", re.IGNORECASE),
    re.compile(r"Yes, allow", re.IGNORECASE),
    re.compile(r"No, don't allow", re.IGNORECASE),
    # Bash/tool permission prompts
    re.compile(r"would like to run", re.IGNORECASE),
    re.compile(r"wants to use the", re.IGNORECASE),
]

PROCESSING_PATTERNS = [
    re.compile(r"Thinking\.\.\."),
    re.compile(r"Working\.\.\."),
    re.compile(r"Generating\.\.\."),
    re.compile(r"Processing\.\.\."),
    # Any decorative Unicode indicator followed by a space, some text, and "…"
    # Covers: ✽ Transfiguring…, ✢ Schlepping…, ★ Conjuring…, ✧/✦/✻/❋ <verb>…, etc.
    re.compile(r"[✽✢★✧✦✻❋✾✿❀❁❂❃]\s+\S.*…"),
    # Spinner followed by text
    re.compile(r"[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]\s+\w"),
]

# Claude Code's main input prompt indicator
INPUT_PROMPT_PATTERNS = [
    re.compile(r"^\s*>\s*$", re.MULTILINE),         # bare ">" prompt
    re.compile(r"^\s*❯\s*$", re.MULTILINE),          # unicode cursor
    re.compile(r"\? for shortcuts"),                  # Claude Code footer hint
    re.compile(r"Human:\s*$", re.MULTILINE),          # conversation marker
    re.compile(r"What would you like", re.IGNORECASE),
]

# AskUserQuestion widget detection patterns
ASK_USER_QUESTION_PATTERNS = [
    # The options list with radio circles (older format)
    re.compile(r"[○●◯◉◦◎◈]"),
    # "? <question text>" header pattern
    re.compile(r"^\s*\?\s+.{5,}", re.MULTILINE),
    # Numbered options with cursor (v2.1.x format): "❯ 1. Label" or "  2. Label"
    re.compile(r"^\s*❯?\s*\d+\.\s+\S", re.MULTILINE),
    # Footer hint confirming AskUserQuestion widget
    re.compile(r"Enter to select.*↑/↓ to navigate"),
    # Checkbox header: "☐ Header" or "☑ Header"
    re.compile(r"^\s*[☐☑]\s+\S", re.MULTILINE),
]


class ScreenMode(str, Enum):
    """What Claude Code is currently displaying/expecting."""
    IDLE = "idle"              # Showing the input prompt, waiting for a message
    QUESTION = "question"      # AskUserQuestion TUI widget with selectable options
    PERMISSION = "permission"  # Tool/bash permission prompt ("Allow?")
    PROCESSING = "processing"  # Spinner, "Thinking...", or mid-generation
    UNKNOWN = "unknown"        # Could not determine state


@dataclass
class TUIOption:
    """A single selectable option in an AskUserQuestion widget."""
    label: str
    description: str = ""
    is_selected: bool = False
    index: int = 0

    def __repr__(self) -> str:
        marker = "●" if self.is_selected else "○"
        return f"{marker} [{self.index}] {self.label!r}"


@dataclass
class ScreenState:
    """
    Structured representation of what Claude Code is currently showing.

    Fields:
        mode: The current UI state (idle / question / permission / processing / unknown)
        raw_text: The raw captured screen text (ANSI stripped)
        question_text: The question being asked (if mode == 'question')
        options: List of TUIOption objects (if mode == 'question' or 'permission')
        selected_option_index: Index of the currently highlighted option (0-based)
        prompt_text: The current text in the input box (if mode == 'idle')
        permission_tool: Name of the tool/command requesting permission
        is_multiselect: True if the question allows multiple selections
    """
    mode: ScreenMode = ScreenMode.UNKNOWN
    raw_text: str = ""
    question_text: str = ""
    options: list[TUIOption] = field(default_factory=list)
    selected_option_index: int = 0
    prompt_text: str = ""
    permission_tool: str = ""
    is_multiselect: bool = False

    def has_options(self) -> bool:
        return len(self.options) > 0

    def selected_option(self) -> Optional[TUIOption]:
        if self.options and 0 <= self.selected_option_index < len(self.options):
            return self.options[self.selected_option_index]
        return None

    def __repr__(self) -> str:
        parts = [f"ScreenState(mode={self.mode.value!r}"]
        if self.question_text:
            parts.append(f"  question={self.question_text!r}")
        if self.options:
            parts.append(f"  options={self.options}")
            parts.append(f"  selected_index={self.selected_option_index}")
        if self.prompt_text:
            parts.append(f"  prompt={self.prompt_text!r}")
        if self.permission_tool:
            parts.append(f"  permission_tool={self.permission_tool!r}")
        parts.append(")")
        return "\n".join(parts)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return ANSI_ESCAPE_RE.sub("", text)


def _extract_options_from_lines(lines: list[str]) -> tuple[list[TUIOption], int]:
    """
    Scan lines for option entries — supports both formats:

    1. Radio-button glyphs (older): ● Python / ○ TypeScript
    2. Numbered with cursor (v2.1.x): ❯ 1. Python / 2. TypeScript

    Returns (options_list, selected_index) where selected_index is the index
    of the highlighted option, defaulting to 0.
    """
    options: list[TUIOption] = []
    selected_idx = 0
    # Track if we hit a separator line (────) to stop collecting main options
    past_separator = False

    for line_idx, line in enumerate(lines):
        # Strip box-drawing borders before checking for glyphs
        stripped = _strip_box_border(line)
        if not stripped:
            continue

        # Detect horizontal separator (──────) — options after this are meta-options
        if re.match(r"^[─━═]{3,}$", stripped):
            past_separator = True
            continue

        # Stop if we hit the footer hint
        if ASK_FOOTER_RE.search(stripped):
            break

        # ── Format 1: Radio-button glyphs ──
        first_char = stripped[0] if stripped else ""
        is_unselected_glyph = first_char in UNSELECTED_GLYPHS
        is_selected_glyph = first_char in SELECTED_GLYPHS

        if is_unselected_glyph or is_selected_glyph:
            label = stripped[1:].strip()
            description = ""
            for sep in [" — ", " – "]:
                if sep in label:
                    parts = label.split(sep, 1)
                    label = parts[0].strip()
                    description = parts[1].strip() if len(parts) > 1 else ""
                    break

            if label:
                idx = len(options)
                opt = TUIOption(
                    label=label,
                    description=description,
                    is_selected=is_selected_glyph,
                    index=idx,
                )
                if is_selected_glyph:
                    selected_idx = idx
                options.append(opt)
            continue

        # ── Format 2: Numbered options with ❯ cursor (v2.1.x) ──
        m = NUMBERED_OPTION_RE.match(stripped)
        if m:
            has_cursor = m.group(2) is not None  # ❯ prefix present
            label = m.group(3).strip()

            # Skip meta-options past separator (like "Chat about this")
            # but keep "Type something." as it's the free-text option
            if past_separator and "type something" not in label.lower():
                continue

            if label:
                idx = len(options)
                opt = TUIOption(
                    label=label,
                    description="",
                    is_selected=has_cursor,
                    index=idx,
                )
                if has_cursor:
                    selected_idx = idx
                options.append(opt)
            continue

    return options, selected_idx


def _find_question_text(lines: list[str], option_start_line: int) -> str:
    """
    Look backwards from the first option line to find the question text.
    Claude Code typically renders:
        ┌─ Question header ─────────┐
        │ ? The actual question?    │
        │   ○ Option 1              │
        │   ● Option 2 (selected)   │
        └───────────────────────────┘
    """
    for i in range(option_start_line - 1, max(option_start_line - 15, -1), -1):
        line = lines[i].strip()
        if not line:
            continue
        # Skip pure box-drawing border lines (─────, ╭─────╮, etc.)
        if all(c in "─│┌┐└┘├┤┬┴┼╔╗╚╝╠╣╦╩╬═╭╮╰╯┃" for c in line if c.strip()):
            continue
        # Strip leading box border character and "?" or ">" markers
        candidate = _strip_box_border(line)
        candidate = re.sub(r"^[?>\|]\s*", "", candidate).strip()
        # Must be at least 5 chars and contain at least one letter
        if len(candidate) >= 5 and re.search(r"[a-zA-Z]", candidate):
            return candidate
    return ""


def _strip_box_border(line: str) -> str:
    """
    Strip leading/trailing box-drawing border characters (│, ┃, |) from a line.

    Claude Code renders option lists inside bordered boxes. The raw captured line
    looks like:
        │   ● Python
        │   ○ TypeScript

    After stripping the border and whitespace we get:
        ● Python
        ○ TypeScript
    """
    stripped = line.strip()
    # Remove leading │, ┃, |, ║ border characters and the spaces after them
    stripped = re.sub(r"^[│┃|║]\s*", "", stripped)
    # Remove trailing border characters
    stripped = re.sub(r"\s*[│┃|║]$", "", stripped)
    return stripped


def _find_option_block_start(lines: list[str]) -> int:
    """
    Return the index of the first line containing an option indicator, or -1.

    Detects both formats:
        ● Python          ← radio-button glyph (older)
        │   ● Python      ← inside a box border
        ❯ 1. Python       ← numbered with cursor (v2.1.x)
          2. TypeScript    ← numbered without cursor
    """
    all_glyphs = UNSELECTED_GLYPHS | SELECTED_GLYPHS
    for i, line in enumerate(lines):
        candidate = _strip_box_border(line)
        if not candidate:
            continue
        # Radio-button glyph
        if candidate[0] in all_glyphs:
            return i
        # Numbered option with or without cursor
        if NUMBERED_OPTION_RE.match(candidate):
            return i
    return -1


def _detect_permission_tool(text: str) -> str:
    """Try to extract the tool/command name from a permission prompt."""
    # Pattern: "wants to use the <tool_name> tool" or "run <command>"
    patterns = [
        re.compile(r"use the\s+(\w+)\s+tool", re.IGNORECASE),
        re.compile(r"run:\s*`?(.+?)`?(?:\n|$)"),
        re.compile(r"execute:\s*`?(.+?)`?(?:\n|$)"),
        re.compile(r"Tool:\s*(\w+)", re.IGNORECASE),
    ]
    for pat in patterns:
        m = pat.search(text)
        if m:
            return m.group(1).strip()
    return ""


def _extract_permission_options(lines: list[str]) -> list[TUIOption]:
    """
    Extract permission prompt choices from screen lines.

    Claude Code permission prompts typically look like:
        ❯ Yes, allow
          No, don't allow
          Always allow for this session
    or:
        [1] Yes
        [2] No (don't allow)
        [3] Always allow
    """
    options = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Cursor-prefixed option (currently highlighted)
        if stripped.startswith(CURSOR_GLYPH):
            label = stripped[len(CURSOR_GLYPH):].strip()
            if label:
                options.append(TUIOption(label=label, is_selected=True, index=len(options)))
            continue

        # Numbered options [1], [2], etc.
        m = re.match(r"^\[(\d+)\]\s+(.+)$", stripped)
        if m:
            options.append(TUIOption(label=m.group(2).strip(), index=len(options)))
            continue

        # Match known permission option keywords
        for keyword in ("Yes, allow", "Yes (allow)", "Always allow",
                        "No, don't allow", "No (deny)", "Deny"):
            if stripped.lower().startswith(keyword.lower()):
                options.append(TUIOption(label=stripped, index=len(options)))
                break

    # Deduplicate by label
    seen = set()
    unique = []
    for opt in options:
        if opt.label not in seen:
            seen.add(opt.label)
            unique.append(opt)
    return unique


def parse_screen(captured_text: str) -> ScreenState:
    """
    Parse a raw tmux capture-pane output into a ScreenState.

    Parameters:
        captured_text: Raw output from `tmux capture-pane -p -S -50`

    Returns:
        ScreenState describing Claude Code's current UI state.
    """
    # Strip ANSI codes and split into lines
    clean = strip_ansi(captured_text)
    lines = clean.splitlines()
    state = ScreenState(raw_text=clean)

    # ── 1. Check for AskUserQuestion widget ──────────────────────────────────
    # Detect via: radio-button glyphs (older) OR numbered options with footer hint
    has_footer_hint = ASK_FOOTER_RE.search(clean) is not None
    option_start = _find_option_block_start(lines)

    if option_start >= 0:
        options, selected_idx = _extract_options_from_lines(lines[option_start:])
        if options:
            question_text = _find_question_text(lines, option_start)
            state.mode = ScreenMode.QUESTION
            state.question_text = question_text
            state.options = options
            state.selected_option_index = selected_idx
            return state

    # ── 2. Check for permission prompts ───────────────────────────────────────
    for pat in PERMISSION_PATTERNS:
        if pat.search(clean):
            state.mode = ScreenMode.PERMISSION
            state.permission_tool = _detect_permission_tool(clean)
            perm_options = _extract_permission_options(lines)
            if perm_options:
                state.options = perm_options
                # Find the currently highlighted (selected) one
                for i, opt in enumerate(perm_options):
                    if opt.is_selected:
                        state.selected_option_index = i
                        break
            # Fallback options if we couldn't parse them
            if not state.options:
                state.options = [
                    TUIOption(label="Yes", index=0, is_selected=True),
                    TUIOption(label="No", index=1),
                ]
            return state

    # ── 3. Check for processing/spinner states ────────────────────────────────
    for pat in PROCESSING_PATTERNS:
        if pat.search(clean):
            state.mode = ScreenMode.PROCESSING
            return state

    # Also check for spinner glyphs anywhere in the text
    if any(c in clean for c in SPINNER_GLYPHS):
        state.mode = ScreenMode.PROCESSING
        return state

    # ── 4. Check for idle input prompt ────────────────────────────────────────
    for pat in INPUT_PROMPT_PATTERNS:
        if pat.search(clean):
            state.mode = ScreenMode.IDLE
            # Try to extract what the user has typed in the prompt box
            m = re.search(r"^\s*[>❯]\s*(.*)$", clean, re.MULTILINE)
            if m:
                state.prompt_text = m.group(1).strip()
            return state

    # ── 5. Fallback: unknown ──────────────────────────────────────────────────
    state.mode = ScreenMode.UNKNOWN
    return state


# ── Convenience predicates ────────────────────────────────────────────────────

def is_waiting_for_input(state: ScreenState) -> bool:
    """True if Claude is showing the idle input prompt."""
    return state.mode == ScreenMode.IDLE


def is_showing_question(state: ScreenState) -> bool:
    """True if Claude is showing an AskUserQuestion TUI widget."""
    return state.mode == ScreenMode.QUESTION


def is_showing_permission(state: ScreenState) -> bool:
    """True if Claude is showing a tool/bash permission prompt."""
    return state.mode == ScreenMode.PERMISSION


def is_processing(state: ScreenState) -> bool:
    """True if Claude is currently generating a response."""
    return state.mode == ScreenMode.PROCESSING


