# Story CC-6: Session Management

Status: ready-for-dev

## Story

As an **admin/user**,
I want Claude Code agent sessions to persist and be resumable,
so that agents can continue conversations across task interactions without losing context.

## Acceptance Criteria

### AC1: Session ID Storage in Convex

**Given** a CC agent completes a task
**When** the `CCTaskResult` contains a `session_id`
**Then** the session_id is stored in Convex associated with the agent and task:
  - Via `settings:set` with key `cc_session:{agent_name}:{task_id}` and value `session_id`
**And** the most recent session per agent is also stored: `cc_session:{agent_name}:latest` → `session_id`

### AC2: Session Resume on Follow-up

**Given** a task is assigned to a CC agent that previously worked on it
**When** the executor prepares to run the CC agent
**Then** it looks up `cc_session:{agent_name}:{task_id}` in Convex settings
**And** if found, passes the session_id to `ClaudeCodeProvider.execute_task(session_id=...)`
**And** the CC CLI resumes the session with `--resume <session_id>`
**When** no previous session exists for this agent+task
**Then** a fresh session is started (no `--resume` flag)

### AC3: Session Resume via Thread Reply

**Given** a user sends a follow-up message in a task thread on the dashboard
**When** the message is directed to a CC agent
**Then** MC looks up the agent's session for this task
**And** resumes the CC session with the user's new message as the prompt
**And** the response is posted back to the task thread

### AC4: Session Cleanup

**Given** a task is marked as `done` or `archived`
**When** session cleanup runs
**Then** the `cc_session:{agent_name}:{task_id}` key is deleted from Convex settings
**But** the actual CC session files on disk are NOT deleted (CC manages its own storage)
**When** an agent is deleted from the registry
**Then** all `cc_session:{agent_name}:*` keys are cleaned up

### AC5: Session Listing (CLI)

**Given** an admin runs `nanobot mc sessions` or similar CLI command
**When** sessions are listed
**Then** CC sessions are included with: agent_name, task_id, session_id, timestamp
**And** the output distinguishes between nanobot sessions and CC sessions

## Tasks / Subtasks

- [ ] **Task 1: Store session_id on task completion** (AC: #1)
  - [ ] 1.1 In `mc/executor.py` `_complete_cc_task()`, after posting completion message:
    ```python
    # Store CC session for resume
    if result.session_id:
        self._bridge.mutation("settings:set", {
            "key": f"cc_session:{agent_name}:{task_id}",
            "value": result.session_id,
        })
        self._bridge.mutation("settings:set", {
            "key": f"cc_session:{agent_name}:latest",
            "value": result.session_id,
        })
    ```

- [ ] **Task 2: Look up session on task execution** (AC: #2)
  - [ ] 2.1 In `mc/executor.py` `_execute_cc_task()`, before calling the provider:
    ```python
    # Check for existing CC session
    session_id = None
    try:
        stored = self._bridge.query("settings:get", {
            "key": f"cc_session:{agent_name}:{task_id}"
        })
        if stored and stored.get("value"):
            session_id = stored["value"]
            logger.info("[executor] Resuming CC session %s for %s", session_id, agent_name)
    except Exception:
        pass  # No session found, start fresh
    ```
  - [ ] 2.2 Pass `session_id` to `provider.execute_task(..., session_id=session_id)`

- [ ] **Task 3: Handle thread follow-up messages** (AC: #3)
  - [ ] 3.1 In `mc/chat_handler.py` or the appropriate message handler, detect messages to CC agents:
    ```python
    if agent_data.backend == "claude-code":
        # Look up session for this task
        session_id = bridge.query("settings:get", {
            "key": f"cc_session:{agent_name}:{task_id}"
        })
        if session_id:
            # Resume CC session with new message
            result = await cc_provider.execute_task(
                prompt=user_message,
                agent_config=agent_data,
                task_id=task_id,
                workspace_ctx=ws_ctx,
                session_id=session_id["value"],
            )
            # Post response to thread
            bridge.send_message(task_id, agent_name, "agent", result.output, "text")
    ```

- [ ] **Task 4: Session cleanup on task done/archive** (AC: #4)
  - [ ] 4.1 In `mc/state_machine.py`, when task transitions to `done` or `archived`:
    ```python
    # Clean up CC session references
    try:
        bridge.mutation("settings:delete", {
            "key": f"cc_session:{agent_name}:{task_id}"
        })
    except Exception:
        pass  # Non-critical
    ```
  - [ ] 4.2 If `settings:delete` mutation doesn't exist, use `settings:set` with empty value as a soft delete, or add a `settings:delete` mutation to Convex

- [ ] **Task 5: Agent deletion cleanup** (AC: #4)
  - [ ] 5.1 In `mc/gateway.py`, when an agent is removed from registry:
    - Query all `cc_session:{agent_name}:*` keys
    - Delete each one
  - [ ] 5.2 This may require a new Convex query `settings:listByPrefix` or manual enumeration

- [ ] **Task 6: CLI sessions command** (AC: #5)
  - [ ] 6.1 In `mc/cli.py`, add `mc sessions` command:
    ```python
    @mc_app.command("sessions")
    def sessions_list():
        """List active CC agent sessions."""
        # Query all cc_session:* keys from Convex settings
        # Display in table format: agent, task_id, session_id
    ```

- [ ] **Task 7: Tests** (AC: all)
  - [ ] 7.1 Create `tests/mc/test_cc_sessions.py`:
    - Test session storage on completion
    - Test session lookup for resume
    - Test fresh session when no stored session
    - Test session cleanup on task done
    - Mock ConvexBridge for all tests
  - [ ] 7.2 Run: `uv run pytest tests/mc/test_cc_sessions.py -v`

## Dev Notes

### Architecture & Design Decisions

**Settings table for session storage**: Reuses the existing Convex `settings` key-value table. Session IDs are small strings, and the access pattern (lookup by agent+task) maps well to key-value. No schema changes needed.

**Key format**: `cc_session:{agent_name}:{task_id}` provides unique per-agent-per-task sessions. The `:latest` suffix enables "continue where you left off" for agents without a specific task context.

**Disk session files unmanaged**: Claude Code stores session files locally (~/.claude or workspace). We don't manage these — CC handles its own session persistence. We only store the session_id reference in Convex for the `--resume` flag.

**Thread follow-up is a stretch goal**: AC3 (thread reply → session resume) is the most complex part and may require deeper integration with the existing message routing. It can be deferred if needed.

### Code to Reuse

- `dashboard/convex/settings.ts` — `get`, `set` queries/mutations
- `mc/executor.py` — `_execute_cc_task()` integration point (from CC-5)
- `mc/state_machine.py` — task state transitions
- `mc/cli.py` — existing CLI command patterns

### Common Mistakes to Avoid

- Do NOT delete CC session files from disk — CC manages its own storage
- Do NOT assume session_id is always present — CC may not return one on error
- Settings `get` returns the raw value string (or null) — no JSON parsing needed for session IDs
- Use `uv run python` not `python3`. Use `uv run pytest` for tests.

### Project Structure Notes

- **MODIFIED**: `mc/executor.py` — Add session storage/lookup (~15 lines in _execute_cc_task / _complete_cc_task)
- **MODIFIED**: `mc/state_machine.py` — Add session cleanup on done/archived (~5 lines)
- **MODIFIED**: `mc/cli.py` — Add `mc sessions` command (~20 lines)
- **POSSIBLY MODIFIED**: `mc/chat_handler.py` — Thread follow-up routing for CC agents
- **POSSIBLY MODIFIED**: `dashboard/convex/settings.ts` — Add `delete` mutation if needed
- **NEW**: `tests/mc/test_cc_sessions.py`

### References

- `dashboard/convex/settings.ts` — settings:get, settings:set
- `mc/executor.py` — _execute_cc_task (from CC-5)
- `mc/state_machine.py` — transition_task function
- `mc/cli.py` — mc_app Typer CLI
- Claude Code session resume: `claude -p --resume <session_id>`

## Review Follow-ups (AI)

- [ ] [AI-Review][CRITICAL] Session stored then immediately soft-deleted in _complete_cc_task defeats AC1+AC2 — move cleanup to state_machine.py or a separate lifecycle event [mc/executor.py:1420-1474]
- [ ] [AI-Review][HIGH] AC4 agent deletion cleanup (Task 5) not implemented — cc_session keys are not cleaned up when an agent is removed from registry [mc/gateway.py — missing modification]
- [ ] [AI-Review][HIGH] handle_cc_thread_reply is dead code — never called from any message handler, AC3 thread follow-up not wired [mc/executor.py:1512]
- [ ] [AI-Review][MEDIUM] CLI sessions command shows raw key instead of parsed agent_name, task_id, timestamp columns as specified in AC5 [mc/cli.py:835-843]
- [ ] [AI-Review][MEDIUM] Bare except pass in _execute_cc_task session lookup silently swallows errors — should log warning like handle_cc_thread_reply does [mc/executor.py:1332-1333]
- [ ] [AI-Review][MEDIUM] handle_cc_thread_reply does not post response back to task thread as AC3 requires — only returns text [mc/executor.py:1599]
- [ ] [AI-Review][LOW] handle_cc_thread_reply does not update cc_session:{agent}:latest key, inconsistent with _complete_cc_task [mc/executor.py:1584-1597]
- [ ] [AI-Review][LOW] Unused imports in test file: call from unittest.mock, TaskStatus/ActivityEventType/AuthorType/MessageType from mc.types [tests/mc/test_cc_sessions.py:15,21-29]
- [ ] [AI-Review][LOW] Fragile or-based assertion pattern in test_stored_session_passed_to_provider — use consistent kwargs-only check [tests/mc/test_cc_sessions.py:231-233]

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
