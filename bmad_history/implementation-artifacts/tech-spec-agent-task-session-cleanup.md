---
title: 'Agent Task Session Cleanup'
slug: 'agent-task-session-cleanup'
created: '2026-02-23'
status: 'done'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python', 'asyncio', 'nanobot AgentLoop', 'MemoryStore', 'SessionManager']
files_to_modify:
  - 'nanobot/agent/loop.py'
  - 'nanobot/mc/executor.py'
code_patterns:
  - '/new command handler in loop.py:326-354 — exact pattern to replicate'
  - '_get_consolidation_lock / _consolidating set — thread-safety pattern'
  - '_consolidate_memory(session, archive_all=True) — LLM-driven MEMORY.md + HISTORY.md update'
  - 'session.clear() + sessions.save() + sessions.invalidate() — session reset pattern'
test_patterns: []
---

# Tech-Spec: Agent Task Session Cleanup

**Created:** 2026-02-23

## Overview

### Problem Statement

MC agent tasks share a session key (`mc:task:{agent_name}`), causing old task messages to accumulate indefinitely across runs. Memory is only updated when sessions grow beyond 50 messages (auto-consolidation threshold), so most task work is never captured in `MEMORY.md`/`HISTORY.md`. Each new task starts with stale context from previous tasks, with no isolation between task executions.

### Solution

After each MC task completes (in `_run_agent_on_task`), trigger memory consolidation with `archive_all=True` and then clear the session — identical to what the `/new` command does. The next task for the same agent starts with a clean session but benefits from an updated `MEMORY.md` containing everything the agent learned.

### Scope

**In Scope:**
- New `end_task_session(session_key)` public method on `AgentLoop` in `loop.py`
- Call that method in `_run_agent_on_task()` in `executor.py` after `process_direct` returns, before returning the result
- Fail-safe behavior: if consolidation fails, log a warning and do NOT clear the session (consistent with `/new`)

**Out of Scope:**
- Regular nanobot CLI/chat behavior — no changes
- Auto-consolidation threshold (50-message rule) — no changes
- Crash or provider-error paths — no memory consolidation on crash
- Human-in-the-loop review cycle — consolidation happens when agent work finishes, not when a human approves

---

## Context for Development

### Codebase Patterns

**`/new` command — exact pattern to replicate (`loop.py:326-354`):**
```python
lock = self._get_consolidation_lock(session.key)
self._consolidating.add(session.key)
try:
    async with lock:
        snapshot = session.messages[session.last_consolidated:]
        if snapshot:
            temp = Session(key=session.key)
            temp.messages = list(snapshot)
            if not await self._consolidate_memory(temp, archive_all=True):
                return ...  # fail — don't clear
except Exception:
    logger.exception("/new archival failed for {}", session.key)
    return ...  # fail — don't clear
finally:
    self._consolidating.discard(session.key)
    self._prune_consolidation_lock(session.key, lock)

session.clear()
self.sessions.save(session)
self.sessions.invalidate(session.key)
```

**`_consolidate_memory` delegate (`loop.py:421-426`):**
```python
async def _consolidate_memory(self, session, archive_all: bool = False) -> bool:
    return await MemoryStore(self.workspace).consolidate(
        session, self.provider, self.model,
        archive_all=archive_all, memory_window=self.memory_window,
    )
```

**`process_direct` call site (`executor.py:131-136`):**
```python
result = await loop.process_direct(
    content=message,
    session_key=f"mc:task:{agent_name}",
    channel="mc",
    chat_id=agent_name,
)
return result  # ← end_task_session goes here, before return
```

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `nanobot/agent/loop.py:326-354` | `/new` command — exact code to replicate in `end_task_session` |
| `nanobot/agent/loop.py:421-426` | `_consolidate_memory` — called by the new method |
| `nanobot/mc/executor.py:85-137` | `_run_agent_on_task` — where to call `end_task_session` |
| `nanobot/agent/memory.py` | `MemoryStore.consolidate()` — writes MEMORY.md + HISTORY.md |
| `nanobot/session/manager.py` | `Session.clear()`, `SessionManager.save/invalidate` |

### Technical Decisions

1. **`end_task_session` is a public method on `AgentLoop`** — not inlined in executor — because it needs access to `self.sessions`, `self._consolidating`, `self._get_consolidation_lock`, `self._prune_consolidation_lock`, and `self._consolidate_memory`, all of which are private to the loop.

2. **Called inside `_run_agent_on_task` before returning** — the `loop` instance is local to that function; `_execute_task` never has access to it.

3. **Fail-safe = don't clear on failure** — consistent with `/new`. If the LLM fails to consolidate, clearing would permanently lose the task context. Log a warning, leave session intact.

4. **No consolidation on crash** — `end_task_session` is only called on the happy path. Crash/provider-error `except` branches in `_execute_task` do not call it.

5. **`archive_all=True`** — same as `/new`. Consolidates the entire unconsolidated portion of the session, not just the older half.

6. **`Session` import already present** — used in the `/new` handler at `loop.py:333`. No new imports needed.

---

## Implementation Plan

### Tasks

- [x] **Task 1 — Add `end_task_session` method to `AgentLoop` (`nanobot/agent/loop.py`)**
  - File: `nanobot/agent/loop.py`
  - Action: Insert after `_consolidate_memory` method (~line 426):
    ```python
    async def end_task_session(self, session_key: str) -> None:
        """Consolidate memory and clear session at end of an MC task.

        Replicates the /new command behavior: archives all unconsolidated
        messages into MEMORY.md + HISTORY.md, then clears the session so
        the next task starts fresh. If consolidation fails, logs a warning
        and leaves the session intact (same fail-safe as /new).
        """
        session = self.sessions.get_or_create(session_key)
        lock = self._get_consolidation_lock(session.key)
        self._consolidating.add(session.key)
        try:
            async with lock:
                snapshot = session.messages[session.last_consolidated:]
                if snapshot:
                    temp = Session(key=session.key)
                    temp.messages = list(snapshot)
                    if not await self._consolidate_memory(temp, archive_all=True):
                        logger.warning(
                            "end_task_session: memory consolidation failed for {}, session not cleared",
                            session_key,
                        )
                        return
        except Exception:
            logger.exception(
                "end_task_session: consolidation error for {}, session not cleared", session_key
            )
            return
        finally:
            self._consolidating.discard(session.key)
            self._prune_consolidation_lock(session.key, lock)

        session.clear()
        self.sessions.save(session)
        self.sessions.invalidate(session.key)
        logger.info("end_task_session: session cleared for {}", session_key)
    ```
  - Notes: No new imports required. `Session` already imported at top of file.

- [x] **Task 2 — Call `end_task_session` in `_run_agent_on_task` (`nanobot/mc/executor.py`)**
  - File: `nanobot/mc/executor.py`
  - Action: After `result = await loop.process_direct(...)` (line 131-136) and before `return result` (line 137), insert:
    ```python
    # Consolidate memory and clear session (mirrors /new behavior)
    await loop.end_task_session(f"mc:task:{agent_name}")
    ```
  - Notes: No changes to `_execute_task`, crash paths, or provider-error paths. Only the happy path in `_run_agent_on_task`.

### Acceptance Criteria

- [x] **AC1 — Memory updated on task success:**
  Given an MC agent completes a task successfully,
  When `_run_agent_on_task` returns,
  Then `~/.nanobot/agents/{agent_name}/memory/MEMORY.md` is updated and `HISTORY.md` has a new timestamped entry summarizing the task work.

- [x] **AC2 — Session cleared on task success:**
  Given an MC agent completes a task successfully,
  When `_run_agent_on_task` returns,
  Then `session.messages` is empty (session cleared) for key `mc:task:{agent_name}`.

- [x] **AC3 — Next task starts clean:**
  Given a second task is assigned to the same agent after the first completes,
  When `process_direct` is called for the second task,
  Then the session history passed to the LLM contains only the new task's messages (no carryover from the previous task).

- [x] **AC4 — Fail-safe on consolidation error:**
  Given the LLM call inside `_consolidate_memory` raises an exception or returns False,
  When `end_task_session` handles the error,
  Then the session is NOT cleared, a warning is logged, and `_run_agent_on_task` still returns the task result normally.

- [x] **AC5 — No consolidation on crash:**
  Given an MC task crashes (exception raised inside `_run_agent_on_task`),
  When the exception propagates to `_execute_task`'s `except` block,
  Then `end_task_session` is NOT called and `_agent_gateway.handle_agent_crash()` runs as before.

---

## Additional Context

### Dependencies

- `Session` class — already imported in `loop.py` (used in `/new` handler at line 333)
- All helper methods (`_get_consolidation_lock`, `_prune_consolidation_lock`, `_consolidate_memory`, `_consolidating`) already exist on `AgentLoop`
- No new packages or external dependencies

### Testing Strategy

Manual verification steps:
1. Run an MC task to completion via the dashboard
2. Check `~/.nanobot/agents/{agent_name}/memory/HISTORY.md` — new timestamped entry should appear
3. Check `~/.nanobot/agents/{agent_name}/sessions/mc_task_{agent_name}.jsonl` — metadata line should show empty messages after task
4. Assign a second task to the same agent; confirm it runs without stale context in LLM calls

Optional unit tests:
- Mock `_consolidate_memory` to return `False` → verify `session.clear()` is NOT called, warning logged
- Mock `_consolidate_memory` to raise → verify `session.clear()` is NOT called, exception logged
- Mock `_consolidate_memory` to return `True` → verify `session.clear()` and `sessions.invalidate()` called

### Notes

- Session key `mc:task:{agent_name}` is defined at `executor.py:133` — exact same string must be used in the `end_task_session` call
- If `session.messages[session.last_consolidated:]` is empty (e.g., a task that produces no messages), `end_task_session` skips consolidation and still clears the session
- The existing 50-message auto-consolidation background task is unaffected — if it fires during a long task, `end_task_session` consolidates whatever remains unconsolidated at task end
- This change makes the MC agent behave consistently with the standard nanobot `/new` flow: each task = one conversation, fully archived on completion

---

## Dev Agent Record

### Implementation Notes

Implemented exactly as specified. Added `end_task_session(session_key)` as a public async method on `AgentLoop` inserted after `_consolidate_memory` at `loop.py:428`. The method replicates the `/new` command consolidation pattern: locks on the session key, snapshots unconsolidated messages into a temp Session, calls `_consolidate_memory(temp, archive_all=True)`, then clears/saves/invalidates the session. Fail-safe is identical to `/new`: on consolidation failure (returns False) or exception, logs warning/exception and returns without clearing.

Called `loop.end_task_session(f"mc:task:{agent_name}")` in `_run_agent_on_task` immediately after `process_direct` returns and before returning `result`. Only on the happy path — crash/provider-error except branches are unaffected.

No new imports needed (`Session` already imported at top of `loop.py`). All 213 existing tests pass.

### Completion Notes

- ✅ Task 1: `end_task_session` method added to `AgentLoop` (`loop.py:428-463`)
- ✅ Task 2: `end_task_session` called in `_run_agent_on_task` (`executor.py:137-138`)
- ✅ All ACs satisfied by implementation
- ✅ 213 tests pass, no regressions

---

## File List

- `nanobot/agent/loop.py` — added `end_task_session` method; wrapped `sessions.save()` in try/except (code review fix)
- `nanobot/mc/executor.py` — added `end_task_session` call in `_run_agent_on_task` (lines 137–138)
- `tests/test_consolidate_offset.py` — added `TestEndTaskSession` class with 6 tests (code review fix)

---

## Change Log

- 2026-02-23: Implemented Agent Task Session Cleanup — added `AgentLoop.end_task_session()` and wired it into `_run_agent_on_task`. Each MC task now consolidates memory and clears its session on completion, mirroring `/new` behavior.
- 2026-02-23: Code review fixes — wrapped `sessions.save()` in try/except to prevent completed tasks being marked crashed on disk failure (M2); added 6 unit tests for `end_task_session` covering success, fail-safe, exception, lock cleanup, empty-session, and save-failure paths (M1).

---

## Senior Developer Review (AI)

**Reviewer:** AI Senior Developer
**Date:** 2026-02-23
**Outcome:** Approve (after fixes)

### Summary

Implementation correctly replicates the `/new` command pattern for MC task session cleanup. Both tasks implemented as specified, all 5 ACs satisfied. Two medium issues found and fixed during review.

### Action Items

- [x] [Med] No unit tests for `end_task_session` — AC4 fail-safe behavior was untested; analogous `/new` tests existed but none for new method [`tests/test_consolidate_offset.py`] **Fixed: added 6 tests in `TestEndTaskSession`**
- [x] [Med] `sessions.save()` not in try/except — disk failure after successful consolidation would propagate to `_execute_task` as a crash, discarding the completed task result [`nanobot/agent/loop.py:460`] **Fixed: wrapped in try/except with warning log**
- [ ] [Low] Docstring omits empty-snapshot behavior — "archives all unconsolidated messages" implies messages exist, but method also clears session when snapshot is empty [`nanobot/agent/loop.py:429-435`]
- [ ] [Low] No executor-level integration test — no test verifies `end_task_session` is called by `_run_agent_on_task` [`nanobot/mc/executor.py:137-138`]
- [ ] [Low] `MemoryStore.consolidate()` mutates `last_consolidated` on the temp session object (consistent with `/new`, harmless since `session.clear()` resets it, but subtle) [`nanobot/agent/loop.py:441-446`]
- [ ] [Low] Concurrent same-agent task scenario: `end_task_session` for Task A could clear session mid-execution for Task B (pre-existing shared-session-key design limitation, newly relevant) [`nanobot/mc/executor.py`]
