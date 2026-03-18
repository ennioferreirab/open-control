---
title: 'MC Agent Skills-First Orientation'
slug: 'mc-agent-skills-first-orientation'
created: '2026-02-23'
status: 'in-progress'
stepsCompleted: [1]
tech_stack: [python, asyncio, pathlib]
files_to_modify:
  - nanobot/mc/executor.py
  - tests/mc/test_agent_orientation.py
code_patterns: []
test_patterns: []
---

# Tech-Spec: MC Agent Skills-First Orientation

**Created:** 2026-02-23

## Overview

### Problem Statement

MC agents (e.g., youtube-summarizer) bypass their assigned skills and resort to system-level workarounds — crontab, launchd plists, raw shell scripts — when uncertain whether the nanobot system will actually execute their requests. This causes tasks to run outside Mission Control: cron jobs registered outside `~/.nanobot/cron/jobs.json`, no activity events in the dashboard, and a broken cron fire-back loop. The root cause is that agents don't have a clear rule saying "trust your tools; use your skills; don't self-provision at the OS level."

### Solution

Inject a global "skills-first" orientation into all non-lead-agent MC agents by:
1. Creating `~/.nanobot/mc/agent-orientation.md` — a user-editable markdown file with universal behavioral rules (skills-first, no OS-level workarounds, use the nanobot cron tool).
2. Modifying `nanobot/mc/executor.py:_execute_task` to load this file and prepend it before each agent's own `config.yaml` prompt for every agent except `lead-agent`.

### Scope

**In Scope:**
- `~/.nanobot/mc/agent-orientation.md` — new global orientation file (lives outside the repo in the user's home dir; default content provided as part of this spec)
- `nanobot/mc/executor.py` — modify `_execute_task` to load and inject the orientation
- `tests/mc/test_agent_orientation.py` — unit tests for injection logic

**Out of Scope:**
- Modifying individual agent `config.yaml` files (the global injection makes per-agent duplication unnecessary)
- Changing lead-agent behavior
- Dashboard UI changes
- Modifying `ContextBuilder` or the system prompt structure

## Context for Development

### Codebase Patterns

The agent prompt from `config.yaml` is already injected as a message prefix in `_run_agent_on_task` (`executor.py:119`):

```python
if agent_prompt:
    message = f"[System instructions]\n{agent_prompt}\n\n[Task]\n{message}"
```

The global orientation follows the same pattern — it is prepended before this block so the final message structure becomes:

```
[Global orientation]
<orientation content>

[System instructions]
<agent's own config.yaml prompt>

[Task]
<task title + description>
```

The agent name comes from `task_data.get("assigned_agent", "lead-agent")` in `_pickup_task`. Lead-agent is excluded by checking `agent_name != "lead-agent"`.

Bootstrap files (`AGENTS.md`, `SOUL.md`, etc.) are loaded per-agent from `~/.nanobot/agents/<name>/` inside `ContextBuilder._load_bootstrap_files()`. The global orientation purposely bypasses this mechanism to keep it simple and testable.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `nanobot/mc/executor.py` | `_execute_task` and `_run_agent_on_task` — injection point |
| `nanobot/agent/context.py` | `ContextBuilder.build_system_prompt()` — understand existing prompt assembly |
| `~/.nanobot/agents/youtube-summarizer/config.yaml` | Example of an existing per-agent prompt (already has SCHEDULING RULES) |
| `tests/mc/` | Existing test directory — follow its patterns |

### Technical Decisions

- **File over config field**: Stored as a markdown file rather than embedded in `config.json` for readability and easy editing without JSON-quoting issues.
- **Inject before agent prompt**: Global rules take priority and set the ground rules before agent-specific instructions.
- **Graceful degradation**: If `~/.nanobot/mc/agent-orientation.md` doesn't exist, behavior is unchanged — no error, no injection.
- **Exclude lead-agent by name**: Hard-coded string `"lead-agent"` is the exclusion. If future system agents need exclusion, a list can be added.
- **Load at call time**: The file is read on every task execution (not cached) so edits take effect immediately without restarting the MC service.

## Implementation Plan

### Tasks

**Task 1 — Create the global orientation file**

Create `~/.nanobot/mc/agent-orientation.md` (outside the repo, user home dir).
The directory `~/.nanobot/mc/` may not exist yet — create it if needed.

Default content:

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

**Task 2 — Modify `nanobot/mc/executor.py`**

In `_execute_task`, after loading `agent_prompt, agent_model, agent_skills` from `_load_agent_config` (line ~421) and before calling `_run_agent_on_task`, add the orientation injection:

```python
# Inject global orientation for non-lead agents (skills-first rules)
if agent_name != "lead-agent":
    orientation_path = Path.home() / ".nanobot" / "mc" / "agent-orientation.md"
    if orientation_path.exists():
        orientation = orientation_path.read_text(encoding="utf-8").strip()
        if orientation:
            agent_prompt = (
                f"{orientation}\n\n---\n\n{agent_prompt}"
                if agent_prompt
                else orientation
            )
            logger.info(
                "[executor] Global orientation injected for agent '%s'",
                agent_name,
            )
```

No new imports needed — `Path` is already imported.

**Task 3 — Write `tests/mc/test_agent_orientation.py`**

Four unit tests using `pytest`, `tmp_path`, and `unittest.mock`:

1. **`test_orientation_injected_for_non_lead_agent`** — orientation file exists, agent is `youtube-summarizer` → orientation prepended before agent prompt in the call to `_run_agent_on_task`
2. **`test_orientation_not_injected_for_lead_agent`** — orientation file exists, agent is `lead-agent` → `_run_agent_on_task` called with original prompt only (no orientation prepended)
3. **`test_no_error_when_orientation_file_missing`** — orientation file does not exist → task executes normally, no exception
4. **`test_orientation_prepended_before_agent_prompt`** — verify ordering: `orientation_text + "\n\n---\n\n" + agent_prompt`, not reversed

### Acceptance Criteria

```
Given  ~/.nanobot/mc/agent-orientation.md exists with content X
When   a task is assigned to any agent OTHER than lead-agent
Then   X is prepended to that agent's system instructions (before the agent's own prompt)

Given  ~/.nanobot/mc/agent-orientation.md exists
When   a task is assigned to lead-agent
Then   X is NOT included in the message at all

Given  ~/.nanobot/mc/agent-orientation.md does NOT exist
When   any task is assigned
Then   behavior is identical to current (no error, no injection)

Given  an agent has an existing config.yaml prompt P
When   orientation O is injected
Then   message order is: O → (separator) → P → task body
```

## Additional Context

### Dependencies

No new Python dependencies. Uses `pathlib.Path` already imported in `executor.py`.

### Testing Strategy

Unit tests in `tests/mc/test_agent_orientation.py`. Use the `tmp_path` pytest fixture to create a temporary orientation file. Patch `nanobot.mc.executor._run_agent_on_task` with `unittest.mock.AsyncMock` to capture the `agent_prompt` argument without actually calling the LLM. Follow the existing test patterns in `tests/mc/`.

### Notes

- The SCHEDULING RULES already added to `~/.nanobot/agents/youtube-summarizer/config.yaml` overlap with the global orientation. Once the global orientation is in place, those per-agent rules can be removed as a follow-up cleanup — but that's out of scope for this spec.
- Future extension: make the exclusion list configurable via `~/.nanobot/config.json` (e.g., `mc_orientation_excluded_agents: ["lead-agent"]`).
- The orientation file lives at `~/.nanobot/mc/agent-orientation.md`. The `~/.nanobot/mc/` directory is also where `gateway.py` and `bridge.py` write runtime state — it's the right home for this config.
