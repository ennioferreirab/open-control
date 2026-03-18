# Story MEM.3: Unified Session Consolidation Policy

Status: ready-for-dev

## Story

As a **platform maintainer**,
I want all channels and backends to use the same consolidation policy,
so that memory is persisted predictably regardless of whether the interaction came from Telegram, MC, or CC-backed execution.

## Acceptance Criteria

### AC1: There is one consolidation policy for all channels and backends

**Given** the runtime decides whether to consolidate memory
**When** the decision is evaluated
**Then** the only automatic triggers are `threshold` and `session boundary`
**And** no channel or backend uses a different automatic rule.

### AC2: `/new` and task completion map to the same abstract rule

**Given** an official channel issues `/new`
**When** that command is processed
**Then** the runtime treats it as `session boundary`.

**Given** an MC task ends
**When** post-execution consolidation runs
**Then** the runtime also treats that event as `session boundary`.

### AC3: Threshold behavior is deterministic

**Given** an interaction crosses the configured consolidation threshold
**When** the runtime evaluates the session
**Then** consolidation happens once
**And** the session state is updated so the same threshold crossing does not double-consolidate.

### AC4: The result lands in the same canonical storage

**Given** the same logical agent is used from an official channel, from MC, and from CC-backed execution
**When** consolidation happens
**Then** the resulting `MEMORY.md` and `HISTORY.md` updates are written to the same canonical memory storage for that agent and scope.

### AC5: Consolidation attempts are observable

**Given** the runtime evaluates a consolidation trigger
**When** it consolidates or skips
**Then** logs or runtime metadata record:
- `agent_name`,
- `backend`,
- `channel`,
- `trigger_type`,
- `boundary_reason`,
- `memory_workspace`,
- `artifacts_workspace`,
- `action`,
- `skip_reason`,
- `files_touched`.

### AC6: Tests cover official channel, MC, and CC-backed execution

**Given** the policy is implemented
**When** focused test suites run
**Then** there are automated tests for:
- long channel session without `/new`,
- `/new` as `session boundary`,
- threshold crossing,
- MC task end as `session boundary`,
- parity with a CC-backed execution path.

## Tasks / Subtasks

- [ ] Task 1: Lock the agreed policy in tests (AC: 1, 2, 3, 4, 6)
  - [ ] 1.1 Extend [`tests/mc/test_chat_handler.py`](/Users/ennio/Documents/nanobot-ennio/tests/mc/test_chat_handler.py) for threshold and `/new`.
  - [ ] 1.2 Extend [`tests/mc/memory/test_store.py`](/Users/ennio/Documents/nanobot-ennio/tests/mc/memory/test_store.py) or equivalent memory-store tests for session state updates.
  - [ ] 1.3 Add CC-backed parity coverage in [`tests/mc/test_executor_cc.py`](/Users/ennio/Documents/nanobot-ennio/tests/mc/test_executor_cc.py).

- [ ] Task 2: Implement unified trigger handling (AC: 1, 2, 3, 4)
  - [ ] 2.1 Update [`vendor/nanobot/nanobot/agent/loop.py`](/Users/ennio/Documents/nanobot-ennio/vendor/nanobot/nanobot/agent/loop.py) so official channels use `threshold` and `session boundary`.
  - [ ] 2.2 Update [`mc/contexts/conversation/chat_handler.py`](/Users/ennio/Documents/nanobot-ennio/mc/contexts/conversation/chat_handler.py) and/or post-processing hooks so MC task completion uses the same abstract rule.
  - [ ] 2.3 Ensure CC-backed execution reaches the same consolidation hook path rather than inventing a separate trigger model.

- [ ] Task 3: Add observability (AC: 5)
  - [ ] 3.1 Emit the required consolidation metadata for both executed and skipped attempts.
  - [ ] 3.2 Keep the emitted fields consistent across nanobot backend and CC-backed flows.

- [ ] Task 4: Verify the contract (AC: 6)
  - [ ] 4.1 Run focused tests for channel flow, MC flow, and CC-backed flow.
  - [ ] 4.2 Confirm `telegram_*.jsonl` no longer grows indefinitely without an explicit policy boundary.

## Dev Notes

- This story defines timing only. It does not redefine workspace identity or SQLite path canonicalization.
- Use the same storage contract from MEM.1.
- Use the same invalid-memory and indexing behavior from later memory stories; do not fork a special channel-only path.

### Project Structure Notes

- Trigger orchestration belongs in runtime and conversation code, not in ad hoc UI logic.
- Keep consolidation invocation centralized so logs, skips, and writes are consistent.

### References

- [Source: docs/plans/2026-03-11-memory-consolidation-backlog.md#Story-P0.3]
- [Source: docs/plans/2026-03-11-memory-consolidation-remediation-plan.md#AC2-Channel-Trigger-Parity]
- [Source: /Users/ennio/Documents/nanobot-ennio/vendor/nanobot/nanobot/agent/loop.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/mc/contexts/conversation/chat_handler.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/mc/application/execution/post_processing.py]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
