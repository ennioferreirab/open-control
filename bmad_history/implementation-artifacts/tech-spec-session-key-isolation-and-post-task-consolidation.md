---
title: 'Session Key Isolation & Post-Task Memory Consolidation'
slug: 'session-key-isolation-post-task-consolidation'
created: '2026-02-28'
status: 'in-progress'
tech_stack: ['Python', 'asyncio', 'nanobot AgentLoop', 'MemoryStore', 'SessionManager']
files_to_modify:
  - 'nanobot/mc/executor.py'
code_patterns:
  - 'session_key construction at executor.py:188-192'
  - 'end_task_session already implemented at loop.py:476-517'
  - '_execute_task completion path at executor.py:1060-1183'
---

# Tech-Spec: Session Key Isolation & Post-Task Memory Consolidation

**Created:** 2026-02-28

## Architectural Decision Record

### Context

When multiple tasks are assigned to the same agent on the same board, they share a
single session key (`mc:board:{board_name}:task:{agent_name}`). This causes:

1. **Thread contamination** — the LLM receives `messages[]` containing conversation
   history from OTHER tasks via `session.get_history()`, polluting the current task's
   context with unrelated exchanges.
2. **Race conditions** — concurrent tasks read/write the same JSONL session file.
3. **Premature cleanup** — `end_task_session` from Task A clears the session while
   Task B is still running.

### Decision

**Isolate session keys by task_id; consolidate memory after each task completes.**

- Session key includes `task_id` → each task gets its own conversation thread
- `MEMORY.md` remains board-scoped (shared) → agents accumulate long-term knowledge
  across all tasks on the board
- `end_task_session` runs AFTER the task is marked done in Convex → the user
  never notices the consolidation latency
- Consolidation is fire-and-forget (best-effort) → failures don't affect task outcome

### Consequences

- **Thread isolation**: LLM only sees messages from the current task
- **Memory sharing**: agents still learn across tasks via board-scoped MEMORY.md
- **No buffer accumulation**: since each task has its own short session (~3-6 msgs),
  auto-consolidation (50-msg threshold) never triggers; `end_task_session` replaces it
- **1 extra LLM call per task**: consolidation call after completion (small, fast,
  uses `max_tokens=4096`)

---

## Problem Statement

The session key `mc:board:{board_name}:task:{agent_name}` does NOT include the
`task_id`, so all tasks for the same agent on the same board share one session.
The `messages[]` sent to the LLM include conversation history from unrelated tasks.

## Solution

Two changes in `nanobot/mc/executor.py`:

1. **Add `task_id` to session key** — isolates the LLM thread per task
2. **Call `end_task_session` after task is marked done** — consolidates the short
   session into MEMORY.md, then clears the session file

## Scope

**In Scope:**
- Modify session key construction in `_run_agent_on_task` (line 188-192)
- Add fire-and-forget `end_task_session` call in `_execute_task` after task status
  is updated to done/review (after line 1143)
- Pass `session_key` back from `_run_agent_on_task` so `_execute_task` can use it

**Out of Scope:**
- `end_task_session` method itself — already implemented and tested (loop.py:476-517)
- Memory consolidation logic — no changes to MemoryStore
- Chat handler, mention handler — already have isolated session keys
- Auto-consolidation threshold — remains for non-MC paths (CLI, Telegram)

---

## Implementation Plan

### Task 1 — Add task_id to session_key in `_run_agent_on_task`

**File:** `nanobot/mc/executor.py` lines 188-192

**Before:**
```python
if board_name:
    session_key = f"mc:board:{board_name}:task:{agent_name}"
else:
    session_key = f"mc:task:{agent_name}"
```

**After:**
```python
if board_name:
    session_key = f"mc:board:{board_name}:task:{agent_name}:{task_id}" if task_id else f"mc:board:{board_name}:task:{agent_name}"
else:
    session_key = f"mc:task:{agent_name}:{task_id}" if task_id else f"mc:task:{agent_name}"
```

### Task 2 — Return session_key from `_run_agent_on_task`

Change return type from `str` to `tuple[str, str]` (result, session_key).

**Before:**
```python
async def _run_agent_on_task(...) -> str:
    ...
    return result
```

**After:**
```python
async def _run_agent_on_task(...) -> tuple[str, str]:
    ...
    return result, session_key
```

Update the call site in `_execute_task`:
```python
# Before:
result = await _run_agent_on_task(...)
# After:
result, session_key = await _run_agent_on_task(...)
```

### Task 3 — Fire-and-forget consolidation after task marked done

In `_execute_task`, after the task status is updated (line 1143) and retry count
is cleared (line 1146), add fire-and-forget consolidation:

```python
# Post-task memory consolidation (fire-and-forget, after task is done)
# Runs after status is updated so user sees completion immediately.
asyncio.create_task(
    _consolidate_after_task(session_key, agent_name, memory_workspace, agent_model)
)
```

Create a helper function `_consolidate_after_task` that:
1. Creates a minimal AgentLoop (just for session/memory access)
2. Calls `loop.end_task_session(session_key)`
3. Logs success/failure
4. Swallows all exceptions (best-effort)

**IMPORTANT:** The AgentLoop created inside `_run_agent_on_task` is local and goes
out of scope. We need to either:
- (a) Keep a reference to it and pass it back, OR
- (b) Create a new minimal AgentLoop just for consolidation

Option (a) is cleaner — return the loop instance alongside result and session_key.

**Revised approach for Task 2:**

Return a dataclass or named tuple with (result, session_key, loop):

```python
async def _run_agent_on_task(...) -> tuple[str, str, "AgentLoop"]:
    ...
    return result, session_key, loop
```

Then in `_execute_task`:
```python
result, session_key, loop = await _run_agent_on_task(...)

# ... (post step completion, sync files, update status — all existing code) ...

# Fire-and-forget memory consolidation after task is marked done
async def _consolidate():
    try:
        await loop.end_task_session(session_key)
    except Exception:
        logger.warning("[executor] Post-task consolidation failed for '%s'", title, exc_info=True)

asyncio.create_task(_consolidate())
```

### Task 4 — Remove stale TODO comment

Remove the commented-out code at executor.py:249-251:
```python
# TODO: revisit task-based consolidation — may be better than message-count
# Consolidate memory and clear session (mirrors /new behavior)
# await loop.end_task_session(session_key)
```

---

## Acceptance Criteria

- **AC1 — Session isolation:** Two concurrent tasks for the same agent on the same
  board produce separate JSONL session files with independent message histories.

- **AC2 — LLM receives only current task messages:** The `messages[]` sent to the LLM
  contain only the conversation history for the current task, not from other tasks.

- **AC3 — Memory consolidation after done:** After a task is marked done/review in
  Convex, `end_task_session` is called and MEMORY.md + HISTORY.md are updated.

- **AC4 — Consolidation is non-blocking:** The user sees task completion immediately;
  consolidation runs asynchronously after status update.

- **AC5 — Consolidation failure doesn't affect task:** If `end_task_session` fails,
  a warning is logged but the task result and status are unaffected.

- **AC6 — No consolidation on crash:** If the task crashes or hits a provider error,
  `end_task_session` is NOT called (only on happy path).

- **AC7 — Backward compatible:** Tasks without `task_id` (edge case) fall back to
  the old session key format without task_id suffix.

---

## Testing Strategy

### Existing tests
- `tests/test_consolidate_offset.py::TestEndTaskSession` — 6 tests covering
  `end_task_session` success, fail-safe, exception, lock cleanup, empty-session,
  and save-failure paths. These remain valid, no changes needed.

### Manual verification
1. Create two tasks on same board assigned to same agent
2. Run them (sequentially or concurrently)
3. Verify separate JSONL files in `sessions/` directory
4. Verify MEMORY.md is updated after each task completes
5. Verify second task's LLM call does NOT contain first task's messages

---

## File List

- `nanobot/mc/executor.py` — session key fix + fire-and-forget consolidation
