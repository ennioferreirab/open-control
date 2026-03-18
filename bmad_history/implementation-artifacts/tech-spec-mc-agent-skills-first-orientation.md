---
title: 'MC Agent Skills-First Orientation'
slug: 'mc-agent-skills-first-orientation'
created: '2026-02-23'
status: 'done'
stepsCompleted: [1, 2, 3, 4]
tech_stack: [python, pathlib, pytest, pytest-asyncio]
files_to_modify:
  - nanobot/mc/executor.py
  - tests/mc/test_agent_orientation.py
code_patterns:
  - sync-helper-method-on-TaskExecutor
  - patch-pathlib-home-for-tmp_path
  - class-based-pytest-tests
test_patterns:
  - unittest.mock.MagicMock for bridge
  - patch("pathlib.Path.home", return_value=tmp_path)
  - direct sync method call (no asyncio needed)
---

# Tech-Spec: MC Agent Skills-First Orientation

**Created:** 2026-02-23

## Overview

### Problem Statement

MC agents (e.g., youtube-summarizer) bypass their assigned skills and resort to system-level workarounds — crontab, launchd plists, raw shell scripts — when uncertain whether the nanobot system will actually execute their requests. This causes tasks to run outside Mission Control: cron jobs registered outside `~/.nanobot/cron/jobs.json`, no activity events in the dashboard, and a broken cron fire-back loop. The root cause is that agents don't have a clear rule saying "trust your tools; use your skills; don't self-provision at the OS level."

### Solution

Inject a global "skills-first" orientation into all non-lead-agent MC agents by:
1. Creating `~/.nanobot/mc/agent-orientation.md` — a user-editable markdown file with universal behavioral rules.
2. Adding `TaskExecutor._maybe_inject_orientation(agent_name, agent_prompt)` — a sync helper that loads the file and prepends it.
3. Calling that helper in `_execute_task` after `_load_agent_config`, for every agent except `lead-agent`.

### Scope

**In Scope:**
- `~/.nanobot/mc/agent-orientation.md` — new global orientation file (user home dir, outside repo)
- `nanobot/mc/executor.py` — new `_maybe_inject_orientation()` method + one-line call in `_execute_task`
- `tests/mc/test_agent_orientation.py` — 5 unit tests

**Out of Scope:**
- Modifying individual agent `config.yaml` files
- Changing lead-agent behavior
- Dashboard UI changes
- Modifying `ContextBuilder` or system prompt structure

## Context for Development

### Codebase Patterns

The agent prompt from `config.yaml` is already injected as a message prefix in `_run_agent_on_task` (`executor.py:119`):

```python
if agent_prompt:
    message = f"[System instructions]\n{agent_prompt}\n\n[Task]\n{message}"
```

The global orientation is prepended *before* the agent's own prompt via `_maybe_inject_orientation`. Final message structure after injection:

```
[Global orientation]
<orientation content>

---

[System instructions]
<agent's own config.yaml prompt>

[Task]
<task title + description>
```

Agent name comes from `task_data.get("assigned_agent", "lead-agent")` in `_pickup_task`. Lead-agent is excluded by checking `agent_name != "lead-agent"`.

**Test patterns** from `tests/mc/test_boards.py` and `test_manual_tasks.py`:
- Class-based grouping (one class per behavior/story)
- `patch("pathlib.Path.home", return_value=tmp_path)` for filesystem isolation
- `MagicMock()` for bridge, `_make_executor()` factory helper
- `_maybe_inject_orientation` is **sync** — plain `def` tests, no `@pytest.mark.asyncio`

`~/.nanobot/mc/` directory does **not** currently exist on this system — must be created.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `nanobot/mc/executor.py` | `_execute_task` (line 368), `_load_agent_config` (line 277), `_run_agent_on_task` (line 85) — injection point |
| `nanobot/agent/context.py` | `build_system_prompt()` — shows existing prompt assembly order |
| `tests/mc/test_boards.py` | Class-based test patterns, `_make_executor()` helper pattern |
| `tests/mc/test_manual_tasks.py` | Executor mock setup, `passthrough` pattern for `asyncio.to_thread` |

### Technical Decisions

- **Extracted helper `_maybe_inject_orientation`** — keeps the logic isolated and directly testable without mocking the full `_execute_task` async call chain.
- **Sync method** — local file read is fast, no `asyncio.to_thread` needed.
- **Markdown file over config field** — readable and editable without JSON-quoting concerns.
- **Inject before agent prompt** — global rules take priority over per-agent instructions.
- **Graceful degradation** — missing file = returns `agent_prompt` unchanged, no error.
- **Separator `\n\n---\n\n`** — standard markdown horizontal rule; visually separates orientation from agent's own prompt when viewing raw text.
- **Exclude `lead-agent` by name** — hard-coded string; can be made into a configurable list later.
- **Load at call time, not cached** — file is re-read on every task so edits take effect without MC restart.

## Implementation Plan

### Tasks

- [x] **Task 1: Create global orientation file**
  - File: `~/.nanobot/mc/agent-orientation.md` (user home dir, outside the repo)
  - Action: Create directory and file with default orientation content shown below
  - Notes: `~/.nanobot/mc/` does not exist yet — run `mkdir -p ~/.nanobot/mc` first. This file is the single place to update rules for all MC agents at once.

  Default file content:

  ```markdown
  # Global Agent Orientation

  You are a nanobot agent running inside Mission Control. The following rules apply to ALL tasks,
  regardless of your specific role:

  ## Skills First

  You have been assigned specific skills. **Always use them.** Before doing anything else:
  1. Check your available skills (listed in your context under `# Skills`).
  2. Use the skill that fits the task.
  3. Only if a skill is unavailable or broken, report the problem — do NOT bypass it with a workaround.

  ## No OS-Level Workarounds

  **Never** use system-level schedulers or scripts as a substitute for your tools:
  - Do NOT use `crontab`, `launchd`, `.plist` files, or shell scripts to schedule work.
  - Do NOT write Python scripts to disk and schedule them via the OS.
  - The OS-level scheduler runs OUTSIDE Mission Control and will NOT be visible in the dashboard.

  ## Scheduling Rules

  When asked to schedule a recurring task:
  - Use the `cron` tool (action="add") — this is the ONLY supported scheduler.
  - After adding a cron job, do NOT delete it. Leave it running.
  - When the cron fires, a new task will be created in Mission Control and routed back to you.
  - The cron message should be a plain task description, not a command to run a script.

  ## If Something Doesn't Work

  If a skill or tool fails or seems unavailable:
  1. Report what you tried and what failed.
  2. Ask the user how to proceed.
  3. Do NOT silently fall back to an OS-level workaround.
  ```

- [x] **Task 2: Add `_maybe_inject_orientation` method to `TaskExecutor`**
  - File: `nanobot/mc/executor.py`
  - Action: Insert this new sync method into the `TaskExecutor` class, immediately before `_execute_task` (around line 305). No new imports needed — `Path` and `logger` are already at the top of the file.

  ```python
  def _maybe_inject_orientation(
      self, agent_name: str, agent_prompt: str | None
  ) -> str | None:
      """Prepend global orientation for non-lead-agent MC agents.

      Reads ~/.nanobot/mc/agent-orientation.md and prepends its content
      before the agent's own prompt. Returns prompt unchanged if:
      - agent is 'lead-agent'
      - orientation file does not exist
      - orientation file is empty
      """
      if agent_name == "lead-agent":
          return agent_prompt

      orientation_path = Path.home() / ".nanobot" / "mc" / "agent-orientation.md"
      if not orientation_path.exists():
          return agent_prompt

      orientation = orientation_path.read_text(encoding="utf-8").strip()
      if not orientation:
          return agent_prompt

      logger.info(
          "[executor] Global orientation injected for agent '%s'", agent_name
      )
      if agent_prompt:
          return f"{orientation}\n\n---\n\n{agent_prompt}"
      return orientation
  ```

- [x] **Task 3: Call `_maybe_inject_orientation` in `_execute_task`**
  - File: `nanobot/mc/executor.py`
  - Action: In `_execute_task`, find the existing `_load_agent_config` call (line ~421) and add one line immediately after it:

  ```python
  # Load agent prompt, model, and skills from YAML config
  agent_prompt, agent_model, agent_skills = self._load_agent_config(agent_name)
  # Inject global orientation for non-lead agents
  agent_prompt = self._maybe_inject_orientation(agent_name, agent_prompt)
  ```

  - Notes: This is the only change to `_execute_task`. The injected `agent_prompt` then flows naturally into `_run_agent_on_task` which prepends it as `[System instructions]` before the task body.

- [x] **Task 4: Write unit tests**
  - File: `tests/mc/test_agent_orientation.py` (new file)
  - Action: Create the file with the following content exactly:

  ```python
  """Tests for MC Agent Skills-First Orientation.

  Covers TaskExecutor._maybe_inject_orientation():
  1. orientation injected for non-lead agents when file exists
  2. orientation NOT injected for lead-agent
  3. graceful no-op when orientation file is missing
  4. orientation comes before agent's own prompt
  5. orientation alone becomes prompt when agent has no config prompt
  """

  from unittest.mock import MagicMock, patch

  import pytest


  def _make_executor(bridge=None):
      from nanobot.mc.executor import TaskExecutor
      return TaskExecutor(bridge or MagicMock())


  class TestMaybeInjectOrientation:

      def test_orientation_injected_for_non_lead_agent(self, tmp_path):
          """Orientation content is prepended for non-lead agents."""
          mc_dir = tmp_path / ".nanobot" / "mc"
          mc_dir.mkdir(parents=True)
          (mc_dir / "agent-orientation.md").write_text(
              "use your skills", encoding="utf-8"
          )
          executor = _make_executor()
          with patch("pathlib.Path.home", return_value=tmp_path):
              result = executor._maybe_inject_orientation(
                  "youtube-summarizer", "agent prompt"
              )
          assert result is not None
          assert "use your skills" in result
          assert "agent prompt" in result

      def test_orientation_not_injected_for_lead_agent(self, tmp_path):
          """lead-agent is exempt from the global orientation."""
          mc_dir = tmp_path / ".nanobot" / "mc"
          mc_dir.mkdir(parents=True)
          (mc_dir / "agent-orientation.md").write_text(
              "use your skills", encoding="utf-8"
          )
          executor = _make_executor()
          with patch("pathlib.Path.home", return_value=tmp_path):
              result = executor._maybe_inject_orientation(
                  "lead-agent", "lead-agent prompt"
              )
          assert result == "lead-agent prompt"
          assert "use your skills" not in (result or "")

      def test_no_error_when_orientation_file_missing(self, tmp_path):
          """No orientation file -> returns original prompt unchanged, no exception."""
          executor = _make_executor()
          with patch("pathlib.Path.home", return_value=tmp_path):
              result = executor._maybe_inject_orientation("some-agent", "my prompt")
          assert result == "my prompt"

      def test_orientation_prepended_before_agent_prompt(self, tmp_path):
          """Orientation must come BEFORE the agent's own prompt."""
          mc_dir = tmp_path / ".nanobot" / "mc"
          mc_dir.mkdir(parents=True)
          (mc_dir / "agent-orientation.md").write_text("ORIENTATION", encoding="utf-8")
          executor = _make_executor()
          with patch("pathlib.Path.home", return_value=tmp_path):
              result = executor._maybe_inject_orientation("agent", "AGENT_PROMPT")
          assert result is not None
          assert result.index("ORIENTATION") < result.index("AGENT_PROMPT")

      def test_orientation_becomes_prompt_when_no_agent_prompt(self, tmp_path):
          """If agent has no config.yaml prompt, orientation alone becomes the prompt."""
          mc_dir = tmp_path / ".nanobot" / "mc"
          mc_dir.mkdir(parents=True)
          (mc_dir / "agent-orientation.md").write_text("rules", encoding="utf-8")
          executor = _make_executor()
          with patch("pathlib.Path.home", return_value=tmp_path):
              result = executor._maybe_inject_orientation("agent", None)
          assert result == "rules"
  ```

  - Notes: All 5 tests are sync (no `@pytest.mark.asyncio`). Run with `uv run pytest tests/mc/test_agent_orientation.py -v`.

### Acceptance Criteria

- [x] **AC 1:** Given `~/.nanobot/mc/agent-orientation.md` exists with content X, when a task is assigned to any agent other than `lead-agent`, then X appears in the agent's system instructions before the agent's own config.yaml prompt.

- [x] **AC 2:** Given `~/.nanobot/mc/agent-orientation.md` exists with content X, when a task is assigned to `lead-agent`, then X does NOT appear in the message at all — `lead-agent prompt` is returned unchanged.

- [x] **AC 3:** Given `~/.nanobot/mc/agent-orientation.md` does NOT exist, when any task is assigned, then behavior is identical to the current baseline — no exception, no injection, agent prompt unchanged.

- [x] **AC 4:** Given an agent has config.yaml prompt P and orientation O is injected, when `_maybe_inject_orientation` runs, then the result is `"O\n\n---\n\nP"` (orientation first, markdown separator, then agent prompt).

- [x] **AC 5:** Given an agent has no config.yaml prompt (`None`), when orientation O is injected, then the result is `"O"` (orientation alone becomes the prompt, no separator, no `None` artifacts).

- [ ] **AC 6:** Given the orientation file exists and a non-lead-agent task executes, when the agent encounters a scheduling task, then the agent uses the `cron` tool instead of crontab/launchd/shell scripts (behavioral validation — manual test with youtube-summarizer).

## Additional Context

### Dependencies

No new Python packages. `pathlib.Path` and `logging.logger` are already imported in `executor.py`.

### Testing Strategy

**Unit tests (automated):**
- `uv run pytest tests/mc/test_agent_orientation.py -v` — 5 sync tests, fast
- Run the full MC suite to check for regressions: `uv run pytest tests/mc/ -v`

**Manual / behavioral test (AC 6):**
1. Ensure `~/.nanobot/mc/agent-orientation.md` exists (Task 1 completed)
2. Ensure `nanobot mc start` is running
3. Create a task: "Schedule a daily summary for channel X at 9am"
4. Assign it to `youtube-summarizer`
5. **Expected:** Agent uses `cron(action="add", ...)` — new entry appears in `~/.nanobot/cron/jobs.json` and in the CronJobsModal
6. **Failure condition:** Agent uses crontab, launchd, or writes a .plist/.sh file

**Regression guard:**
- The 185 existing tests should continue to pass after adding the method and call-site

### Notes

- **Pre-mortem risk**: `patch("pathlib.Path.home", ...)` patches the global `pathlib.Path.home` classmethod. If the executor imports `Path` via `from pathlib import Path`, the patch target must be `pathlib.Path.home` (not `nanobot.mc.executor.Path.home`) — this is how `tests/mc/test_boards.py` does it and it works.
- **Cleanup opportunity**: The SCHEDULING RULES already added to `~/.nanobot/agents/youtube-summarizer/config.yaml` overlap with the global orientation content. Once this spec is implemented, those per-agent rules can be removed as a follow-up to avoid redundancy — out of scope here.
- **Future extension**: The exclusion of `lead-agent` is hard-coded. If more system agents need exemption, the check can be changed to `if agent_name in {"lead-agent", "mc-planner"}:` or made configurable via `~/.nanobot/config.json`.
- **Live reloading**: Since the file is read at call time (not startup), you can edit `~/.nanobot/mc/agent-orientation.md` while MC is running and the next task will pick up the changes immediately.

## Dev Agent Record

### Implementation Notes

Implemented `TaskExecutor._maybe_inject_orientation(agent_name, agent_prompt)` as a sync helper that reads `~/.nanobot/mc/agent-orientation.md` and prepends it before the agent's own prompt for all non-lead-agent executions. Called immediately after `_load_agent_config` in `_execute_task`. Graceful degradation: missing file, empty file, or lead-agent all return the original prompt unchanged.

Also fixed a pre-existing test breakage in `tests/mc/test_boards.py::TestBoardSessionKey::test_run_agent_uses_board_session_key` — the `fake_process_direct` mock needed `task_id=None` to match the new signature added to `loop.process_direct()` by a concurrent change.

### Completion Notes

- All 4 tasks completed, all 5 unit ACs verified by automated tests
- 139/139 MC tests pass (no regressions) — 9 orientation tests + 130 existing
- AC 6 (behavioral/manual) requires live testing with `youtube-summarizer`

### Code Review Fixes (2026-02-23)

- Added 4 new tests: empty file, whitespace-only file, empty-string agent_prompt, exact separator format
- Removed unused `import pytest`
- Total orientation tests: 9 (up from 5)

## File List

- `~/.nanobot/mc/agent-orientation.md` — created (outside repo, user home dir)
- `nanobot/mc/executor.py` — added `_maybe_inject_orientation` method + one-line call in `_execute_task`
- `tests/mc/test_agent_orientation.py` — new test file (5 unit tests)
- `tests/mc/test_boards.py` — fixed `fake_process_direct` mock signature (pre-existing breakage)

## Change Log

- 2026-02-23: Implemented MC agent skills-first orientation. Added `_maybe_inject_orientation` to `TaskExecutor`, created `~/.nanobot/mc/agent-orientation.md`, wrote 5 unit tests. Fixed pre-existing test_boards mock signature.
- 2026-02-23: Code review fixes — added 4 edge-case tests (empty file, whitespace-only, empty-string prompt, exact separator), removed unused import. Total: 9 tests.
