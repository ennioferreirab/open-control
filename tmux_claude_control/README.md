# tmux_claude_control — Tmux-based Claude Code Controller

This package provides a Python API for controlling Claude Code's terminal UI (TUI)
via tmux keyboard simulation, enabling automated testing and agent-driven interactions.

## Overview

Claude Code runs as a rich TUI in the terminal. An agent can control it
entirely through tmux `send-keys`, without needing any API hooks or MCP
bridges. This approach works because:

1. tmux lets you create sessions, send keystrokes, and capture screen output
2. Claude Code's TUI renders to the terminal — tmux can capture it as text
3. The screen content can be parsed to determine what Claude is showing
4. Keystrokes can navigate options, confirm selections, and send messages

## Package Structure

```
tmux_claude_control/
├── __init__.py           # Public API exports
├── screen_parser.py      # Parses raw tmux capture output into ScreenState objects
├── transcript_reader.py  # Reads Claude Code JSONL transcripts for response extraction
├── claude_controller.py  # High-level ClaudeController API
├── orchestrator.py       # Multi-session Orchestrator for parallel task dispatch
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Shared fixtures, --skip-claude flag, markers
│   ├── test_screen_parser.py   # Pure unit tests for screen_parser
│   ├── test_transcript_reader.py # Pure unit tests for transcript_reader
│   ├── test_claude_controller.py # Tests requiring tmux (no Claude needed)
│   ├── test_orchestrator.py    # Pure unit tests for orchestrator
│   ├── test_integration.py     # Integration tests (requires live Claude)
│   └── test_multi_turn.py      # Multi-turn agent loop tests (requires live Claude)
└── README.md
```

## Running the Tests

```bash
# Run all non-Claude tests (unit + tmux primitive tests)
uv run pytest tmux_claude_control/tests/ --skip-claude -v

# Run only pure unit tests (no tmux, no Claude)
uv run pytest tmux_claude_control/tests/test_screen_parser.py tmux_claude_control/tests/test_transcript_reader.py tmux_claude_control/tests/test_orchestrator.py -v

# Run full test suite including integration tests (requires Claude CLI)
uv run pytest tmux_claude_control/tests/ -v

# Run only multi-turn tests
uv run pytest tmux_claude_control/tests/test_multi_turn.py -v
```

### Requirements

- **tmux** — `brew install tmux` (macOS) or `apt install tmux` (Linux)
- **Python 3.11+** — use `uv run python` as per project conventions
- **Claude CLI** — only for integration/multi-turn tests; install from https://claude.ai/code

## Public API

```python
from tmux_claude_control import (
    ClaudeController,
    Response,
    ClaudeError,
    Orchestrator,
    parse_screen,
    ScreenMode,
    ScreenState,
    ToolCall,
    TranscriptReader,
)
```

### ClaudeController

```python
from tmux_claude_control import ClaudeController, Response

ctrl = ClaudeController(session_name="my-claude", cwd="/tmp/workdir")
ctrl.launch()
resp = ctrl.send_prompt("Write a hello world in Python")
print(resp.text)
ctrl.exit_gracefully()
```

### Orchestrator

```python
from tmux_claude_control import Orchestrator

orch = Orchestrator(prefix="my-orch")
orch.spawn_worker("alpha", cwd="/tmp/alpha")
orch.spawn_worker("beta", cwd="/tmp/beta")

results = orch.dispatch_parallel({
    "alpha": "What is the capital of France?",
    "beta": "What is the capital of Japan?",
})

for name, wr in results.items():
    print(f"{name}: {wr.response.text if wr.response else wr.error}")

orch.shutdown_all()
```

### Screen Parser

```python
from tmux_claude_control import parse_screen, ScreenMode

import subprocess
captured = subprocess.run(
    ["tmux", "capture-pane", "-t", "my-session:0", "-p", "-S", "-50"],
    capture_output=True, text=True
).stdout

state = parse_screen(captured)

if state.mode == ScreenMode.QUESTION:
    print(f"Question: {state.question_text}")
    for opt in state.options:
        print(f"  {opt}")

    # Select option at index N: send N Down arrows then Enter
    target_index = 2
    for _ in range(target_index - state.selected_option_index):
        subprocess.run(["tmux", "send-keys", "-t", "my-session:0", "Down"])
    subprocess.run(["tmux", "send-keys", "-t", "my-session:0", "Enter"])
```

## TUI Interaction Patterns

### AskUserQuestion Widget

Claude Code renders AskUserQuestion as a box with radio-button options:

```
╭─ Question ─────────────────────────────────────╮
│ ? What programming language do you prefer?     │
│                                                 │
│   ● Python          ← currently selected       │
│   ○ TypeScript                                  │
│   ○ Rust                                        │
│   ○ Go                                          │
╰─────────────────────────────────────────────────╯
```

**Unicode glyphs:**
- `●` (U+25CF BLACK CIRCLE) — currently selected/highlighted option
- `○` (U+25CB WHITE CIRCLE) — unselected option
- `◉`, `◎`, `◈` — alternate selected glyphs (version dependent)
- `◯`, `◦`, `•` — alternate unselected glyphs

**Keystroke navigation:**

| Key | Effect |
|-----|--------|
| `Down` | Move highlight to next option (wraps) |
| `Up` | Move highlight to previous option (wraps) |
| `Enter` | Confirm currently highlighted option |
| `Escape` | Cancel / dismiss the widget |
| `Space` | Toggle option in multi-select mode |
| `Tab` | Sometimes cycles focus (version dependent) |

**To select option N (0-indexed):**
```
Send N "Down" keystrokes, then "Enter"
```

Example — select the 3rd option (index 2):
```python
ctrl._tmux_key("Down")   # move to index 1
ctrl._tmux_key("Down")   # move to index 2
ctrl._tmux_key("Enter")  # confirm
```

### Permission Prompts

Claude Code shows permission prompts when a tool needs authorization:

```
Claude wants to run: rm -rf /tmp/test_files

Allow? (Y/n)

❯ Yes, allow
  No, don't allow
  Always allow for this session
```

**Keystroke patterns:**

| Keys | Effect |
|------|--------|
| `y` + `Enter` | Allow (quick shortcut) |
| `n` + `Enter` | Deny |
| `Down` + `Enter` | Move cursor to next option, select |
| `Up` + `Enter` | Move cursor to previous option, select |

**Note:** Using `--dangerously-skip-permissions` when launching Claude
suppresses all permission prompts, which simplifies agent control.

### Sending a Message

When Claude shows the idle input prompt (`>` or `❯`):

```python
ctrl._tmux_send("Your message here")
ctrl._tmux_key("Enter")
```

Or use the high-level API:

```python
resp = ctrl.send_prompt("Your message here")
print(resp.text)
```

### Exiting Claude Code

```python
ctrl.exit_gracefully()
# or for immediate force-kill:
ctrl.kill()
```

## Screen Parser

`screen_parser.py` provides `parse_screen(captured_text: str) -> ScreenState`.

### ScreenMode Values

| Mode | Meaning |
|------|---------|
| `IDLE` | Claude is waiting for user input (shows `>` prompt) |
| `QUESTION` | AskUserQuestion TUI widget is visible |
| `PERMISSION` | Tool/bash permission prompt is visible |
| `PROCESSING` | Claude is generating a response (spinner or "Thinking...") |
| `UNKNOWN` | Could not determine the current state |

### ScreenState Fields

| Field | Type | Description |
|-------|------|-------------|
| `mode` | `ScreenMode` | Current UI state |
| `raw_text` | `str` | ANSI-stripped screen text |
| `question_text` | `str` | The question being asked (if mode=QUESTION) |
| `options` | `list[TUIOption]` | Selectable options (QUESTION or PERMISSION) |
| `selected_option_index` | `int` | Index of highlighted option (0-based) |
| `prompt_text` | `str` | Text in input box (if mode=IDLE) |
| `permission_tool` | `str` | Tool name requesting permission |
| `is_multiselect` | `bool` | True if multi-select mode |

## tmux Command Reference

```bash
# Create new detached session
tmux new-session -d -s my-session

# Send text (no Enter)
tmux send-keys -t my-session:0 "hello world" ""

# Send named key
tmux send-keys -t my-session:0 "Enter"
tmux send-keys -t my-session:0 "Down"
tmux send-keys -t my-session:0 "Up"
tmux send-keys -t my-session:0 "Tab"
tmux send-keys -t my-session:0 "Escape"
tmux send-keys -t my-session:0 "C-c"

# Capture screen content (last 50 lines)
tmux capture-pane -t my-session:0 -p -S -50

# Check if session exists
tmux has-session -t my-session

# Kill session
tmux kill-session -t my-session

# Attach to session (for manual inspection)
tmux attach -t my-session
```

## Architecture

```
Agent
  |
  | subprocess.run(["tmux", "send-keys", ...])
  v
tmux session
  |
  | PTY (pseudo-terminal)
  v
Claude Code TUI (ink-based React)
  |
  | renders to terminal
  v
tmux capture-pane output
  |
  | parse_screen()
  v
ScreenState (mode, options, selected_index, ...)
  |
  | agent logic
  v
next tmux send-keys
```

The loop is:
1. Capture screen → parse state
2. Decide what keystroke to send based on state
3. Send keystroke via `tmux send-keys`
4. Wait for re-render (50-300ms)
5. Repeat from 1

## Timing Notes

- Claude's TUI re-renders in ~50-150ms after a keystroke
- Claude's AI response can take 5-90 seconds
- `RENDER_WAIT = 0.3` seconds is a safe delay after navigation keystrokes
- `RESPONSE_TIMEOUT = 90.0` seconds is the maximum wait for a response
- Use `ctrl.wait_for_idle()` rather than fixed sleeps for response detection

## Limitations

- **Fragile to UI changes**: The parser uses text pattern matching. If Anthropic
  changes Claude Code's TUI layout or glyph choices, the parser may need updates.
- **Race conditions**: If Claude renders very slowly, a `0.3s` delay may not be
  enough. Adjust `RENDER_WAIT` if navigation seems unreliable.
- **No scroll back**: `tmux capture-pane -S -100` captures 100 lines of scrollback
  (in ClaudeController). For very long responses, increase the `-S` value.
- **ANSI codes**: Some terminals/configurations emit complex ANSI sequences.
  The regex stripper handles common cases but may miss unusual codes.
