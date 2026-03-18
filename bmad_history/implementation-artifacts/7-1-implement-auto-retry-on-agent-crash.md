# Story 7.1: Implement Auto-Retry on Agent Crash

Status: done

## Story

As a **user**,
I want the system to automatically retry a task once when an agent crashes,
So that transient failures are recovered without my intervention.

## Acceptance Criteria

1. **Given** an agent crashes while processing a task in "in_progress" state, **When** the crash is detected by the Agent Gateway, **Then** the task status transitions to "retrying" (FR37)
2. **Given** the task transitions to "retrying", **Then** a `task_retrying` activity event is created: "Agent {name} crashed. Auto-retrying (attempt 1/1)"
3. **Given** the task is retrying, **Then** the TaskCard shows a "Retrying" badge with amber styling
4. **Given** the system re-dispatches the task, **Then** it is sent to the same agent (or Lead Agent if the original agent is unavailable)
5. **Given** the auto-retry succeeds, **When** the agent completes the retried task, **Then** normal task flow resumes (transitions to review or done based on trust level)
6. **Given** the auto-retry also fails (second crash), **When** the second crash is detected, **Then** the task status transitions to "crashed" (FR38)
7. **Given** the task transitions to "crashed", **Then** a `task_crashed` activity event is created with full error log
8. **Given** the task is crashed, **Then** the TaskCard shows: red left-border accent, red "Crashed" badge, and the error details are available in the task thread
9. **Given** crash recovery logic is active, **Then** recovery completes within 30 seconds of initial crash detection (NFR10)
10. **And** crash detection and retry logic is implemented in `nanobot/mc/gateway.py`
11. **And** the `state_machine.py` allows: `in_progress -> retrying`, `retrying -> in_progress` (on retry), `retrying -> crashed`
12. **And** unit tests exist for crash detection, retry logic, and exhaustion handling

## Tasks / Subtasks

- [ ] Task 1: Extend the state machine for retry transitions (AC: #11)
  - [ ] 1.1: Update `nanobot/mc/state_machine.py` to add transitions:
    - `retrying -> in_progress` (for dispatching the retry)
    - `retrying -> crashed` (when retry fails)
  - [ ] 1.2: The existing `in_progress -> retrying` and `any -> retrying` / `any -> crashed` universal transitions already handle the initial crash
  - [ ] 1.3: Update `dashboard/convex/tasks.ts` `VALID_TRANSITIONS` to match:
    - Add `retrying: ["in_progress", "crashed"]`

- [ ] Task 2: Implement crash detection in the gateway (AC: #1, #9, #10)
  - [ ] 2.1: Update `nanobot/mc/gateway.py` to monitor agent processes/tasks
  - [ ] 2.2: Implement `_detect_agent_crash(agent_name: str, task_id: str)` method
  - [ ] 2.3: When an agent process dies or stops responding while a task is in "in_progress", detect the crash
  - [ ] 2.4: Crash detection must complete within 30 seconds (NFR10)
  - [ ] 2.5: On crash detection: transition task to "retrying" via bridge, log error to stdout

- [ ] Task 3: Implement auto-retry logic (AC: #1, #2, #4, #5)
  - [ ] 3.1: Add `_auto_retry_task(task_id: str, agent_name: str, error: str)` method to the gateway
  - [ ] 3.2: Track retry count per task (use a dict: `_retry_counts: dict[str, int]`)
  - [ ] 3.3: If retry count for this task is 0 (first crash):
    - Transition task to "retrying"
    - Create activity event: "Agent {name} crashed. Auto-retrying (attempt 1/1)"
    - Write error details as a system message to the task thread
    - Increment retry count
    - Re-dispatch the task to the same agent (or Lead Agent if unavailable)
  - [ ] 3.4: If retry count is already 1 (second crash):
    - Transition task to "crashed"
    - Create activity event with full error log
    - Write error details as a system message to the task thread
    - Do NOT retry again

- [ ] Task 4: Implement error logging to task thread (AC: #7, #8)
  - [ ] 4.1: When a crash occurs, send a message to the task thread with:
    - messageType: "system_event"
    - authorType: "system"
    - content: formatted error message including agent name, error type, and stack trace (if available)
  - [ ] 4.2: Error messages render in the ThreadMessage with system_event variant (gray-50 bg, italic) and monospace font for error details

- [ ] Task 5: Verify TaskCard crashed/retrying display (AC: #3, #8)
  - [ ] 5.1: Verify `STATUS_COLORS` in `dashboard/lib/constants.ts` already handles "retrying" and "crashed" states
  - [ ] 5.2: "retrying" should have amber styling (already defined: `border-l-amber-600`)
  - [ ] 5.3: "crashed" should have red styling (already defined: `border-l-red-500`)
  - [ ] 5.4: Optionally add an `AlertTriangle` icon to crashed TaskCards if not already present

- [ ] Task 6: Write unit tests (AC: #12)
  - [ ] 6.1: Create or extend `nanobot/mc/test_gateway.py`
  - [ ] 6.2: Test crash detection transitions task from "in_progress" to "retrying"
  - [ ] 6.3: Test auto-retry dispatches the task again
  - [ ] 6.4: Test second crash transitions from "retrying" to "crashed"
  - [ ] 6.5: Test retry count is tracked per task
  - [ ] 6.6: Test error message is written to task thread
  - [ ] 6.7: Test activity events are created for both retrying and crashed transitions
  - [ ] 6.8: Test state machine transitions: retrying -> in_progress, retrying -> crashed

## Dev Notes

### Critical Architecture Requirements

- **Single retry only**: FR37 specifies auto-retry happens once. After one retry failure, the task goes to "crashed" and requires manual intervention (Story 6.4).
- **Gateway is the crash detector**: The Agent Gateway (`gateway.py`) manages agent processes. It detects crashes by monitoring agent health — process exit, heartbeat timeout, or exception propagation.
- **Error context is preserved**: Error details (stack trace, error message) are written to the task thread so the user can see what went wrong when they click the crashed task.
- **State machine is the gatekeeper**: All transitions go through the state machine (both Python-side pre-validation and Convex-side enforcement). The state machine must allow the new retrying transitions.

### Retry Flow Diagram

```
Agent crashes while task is "in_progress"
    |
    v
Gateway detects crash
    |
    v
Check retry count for this task
    |
    +-- retry_count == 0 (first crash)
    |       |
    |       v
    |   Transition: in_progress -> retrying
    |   Activity: "Agent X crashed. Auto-retrying (attempt 1/1)"
    |   Thread: error details as system message
    |   Increment retry count
    |   Re-dispatch task to agent
    |       |
    |       +-- Agent completes successfully
    |       |       -> Normal flow continues
    |       |
    |       +-- Agent crashes again
    |               |
    |               v
    |           retry_count == 1 (second crash)
    |               |
    |               v
    |           Transition: retrying -> crashed (or in_progress -> crashed)
    |           Activity: "Agent X crashed. Retry failed. Task marked as crashed."
    |           Thread: error details as system message
    |           Task stays in "crashed" — manual retry only (Story 6.4)
    |
    +-- retry_count >= 1 (already retried)
            |
            v
        Transition: -> crashed
        (same as second crash above)
```

### Gateway Crash Detection Pattern

```python
class AgentGateway:
    def __init__(self, bridge: ConvexBridge):
        self._bridge = bridge
        self._retry_counts: dict[str, int] = {}  # task_id -> retry count

    async def _on_agent_crash(
        self, agent_name: str, task_id: str, error: Exception
    ) -> None:
        """Handle an agent crash during task execution."""
        error_msg = f"{type(error).__name__}: {error}"
        current_retries = self._retry_counts.get(task_id, 0)

        if current_retries == 0:
            # First crash — auto-retry
            self._retry_counts[task_id] = 1
            self._bridge.update_task_status(
                task_id, "retrying", agent_name=agent_name,
                description=f"Agent {agent_name} crashed. Auto-retrying (attempt 1/1)",
            )
            self._bridge.send_message(
                task_id=task_id,
                author_name="System",
                author_type="system",
                content=f"Agent crash detected:\n```\n{error_msg}\n```\nAuto-retrying...",
                message_type="system_event",
            )
            # Re-dispatch
            await self._dispatch_task(task_id, agent_name)
        else:
            # Retry exhausted — mark as crashed
            self._retry_counts.pop(task_id, None)
            self._bridge.update_task_status(
                task_id, "crashed", agent_name=agent_name,
                description=f"Agent {agent_name} crashed. Retry failed. Task marked as crashed.",
            )
            self._bridge.send_message(
                task_id=task_id,
                author_name="System",
                author_type="system",
                content=f"Retry failed. Agent crash:\n```\n{error_msg}\n```\nTask marked as crashed. Use 'Retry from Beginning' to try again.",
                message_type="system_event",
            )
```

### State Machine Extensions

```python
# In state_machine.py, add to VALID_TRANSITIONS:
TaskStatus.RETRYING: [TaskStatus.IN_PROGRESS, TaskStatus.CRASHED],
```

```typescript
// In tasks.ts, add to VALID_TRANSITIONS:
retrying: ["in_progress", "crashed"],
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT retry more than once** — FR37 specifies a single auto-retry. After one retry failure, the task goes to "crashed".

2. **DO NOT retry to "inbox"** — Auto-retry re-dispatches to the same agent (or Lead Agent if unavailable). Only manual retry (Story 6.4) goes to "inbox".

3. **DO NOT lose error context** — Every crash must write error details to the task thread. The user needs to see what went wrong.

4. **DO NOT block the gateway on retry** — Crash handling and retry dispatch should be non-blocking. Use asyncio patterns.

5. **DO NOT clear retry count on success** — Clean up `_retry_counts` when the task completes (transitions to "done") or is manually retried (transitions to "inbox").

6. **DO NOT forget the 30-second NFR** — Crash detection + retry dispatch must complete within 30 seconds (NFR10).

### What This Story Does NOT Include

- **Manual retry button** — Already implemented in Story 6.4
- **Timeout detection** — Story 7.2
- **Agent process management** — The gateway's process management is a prerequisite but the details of how agents are spawned/monitored may vary

### Files Created in This Story

| File | Purpose |
|------|---------|
| `nanobot/mc/test_gateway.py` | Tests for crash detection and retry logic |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `nanobot/mc/gateway.py` | Add crash detection and auto-retry logic |
| `nanobot/mc/state_machine.py` | Add retrying -> in_progress, retrying -> crashed transitions |
| `dashboard/convex/tasks.ts` | Add retrying transitions to VALID_TRANSITIONS and TRANSITION_EVENT_MAP |

### Verification Steps

1. Simulate agent crash while task is "in_progress" — verify task transitions to "retrying"
2. Verify activity event: "Agent X crashed. Auto-retrying (attempt 1/1)"
3. Verify error details appear in task thread
4. Simulate successful retry — verify task continues normal flow
5. Simulate crash during retry — verify task transitions to "crashed"
6. Verify activity event with full error log for crashed task
7. Verify TaskCard shows "Retrying" badge (amber) and "Crashed" badge (red) respectively
8. Run `pytest nanobot/mc/test_gateway.py` — all tests pass

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 7.1`] — Original story definition
- [Source: `_bmad-output/planning-artifacts/prd.md#FR37`] — Auto-retry once on crash
- [Source: `_bmad-output/planning-artifacts/prd.md#FR38`] — Crashed status with error log
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR10`] — Crash recovery < 30 seconds
- [Source: `nanobot/mc/state_machine.py`] — State machine to extend
- [Source: `nanobot/mc/gateway.py`] — Gateway to implement crash handling
- [Source: `nanobot/mc/bridge.py`] — Bridge methods for status updates and messages
- [Source: `dashboard/lib/constants.ts`] — STATUS_COLORS for retrying and crashed states

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References
- All 30 gateway tests pass (18 new auto-retry + 12 existing registry sync)
- All state machine tests pass (1 pre-existing failure in test_review_to_inbox unrelated to this story)

### Completion Notes List
- Task 1: Extended state machine with `retrying -> [in_progress, crashed]` in both Python and Convex
- Task 2-3: Implemented `AgentGateway` class with `handle_agent_crash()` method for crash detection and auto-retry
- Task 4: Error logging writes system_event messages to task thread with formatted error details
- Task 5: Verified STATUS_COLORS in constants.ts already has retrying (amber) and crashed (red) styling
- Task 6: Added 18 unit tests across 5 test classes covering all acceptance criteria
- Pre-existing test bug: `test_state_machine.py::TestInvalidTransitions::test_review_to_inbox` expects review->inbox to be invalid, but the state machine correctly defines it as valid

### File List
- `nanobot/mc/gateway.py` -- Added `AgentGateway` class with crash detection, auto-retry, and retry count tracking
- `nanobot/mc/state_machine.py` -- Added `retrying -> [in_progress, crashed]` transitions and event mappings
- `dashboard/convex/tasks.ts` -- Added `retrying: ["in_progress", "crashed"]` to VALID_TRANSITIONS and TRANSITION_EVENT_MAP
- `nanobot/mc/test_gateway.py` -- Added 18 tests for auto-retry logic across 5 test classes
