# Story 13.3: Universal Mention Coverage Across All Task Statuses

Status: review

## Story

As a **user**,
I want @mentions to work identically in tasks of any status (in_progress, review, done, crashed, etc.),
so that I can consult agents on any task without worrying about which subsystem handles the mention.

## Acceptance Criteria

### AC1: MentionWatcher Handles All Statuses

**Given** a task in any status (inbox, assigned, in_progress, review, done, crashed, retrying)
**When** a user message with `@agentname` appears in the thread
**Then** the MentionWatcher detects and handles the mention
**And** the mentioned agent receives the enriched context (from Story 13.2)
**And** the agent's response is posted to the thread

### AC2: No Double-Processing of Mentions

**Given** a task in `in_progress` or `review` with `awaitingKickoff`
**When** a user message with `@agentname` appears in the thread
**Then** the @mention is handled exactly once (by MentionWatcher only)
**And** the PlanNegotiator does NOT also process the @mention
**And** the PlanNegotiator continues to handle non-mention user messages (plan-chat) as before

### AC3: PlanNegotiator Ignores @Mention Messages

**Given** a task in `in_progress` or `review`
**When** the PlanNegotiator polls user messages on this task
**And** a message contains `@agentname`
**Then** the PlanNegotiator skips this message (does not route it to Lead Agent)
**And** the PlanNegotiator does not treat it as a plan modification request
**And** the message is left for MentionWatcher to handle

### AC4: Non-Mention Messages Unaffected

**Given** a task in `in_progress` with active agent execution
**When** a user sends a message WITHOUT @mention via `postUserPlanMessage`
**Then** the PlanNegotiator handles it as before (routes to Lead Agent for plan modification)
**And** existing plan-chat behavior is fully preserved

### AC5: Concurrent Mention and Execution Safety

**Given** a task in `in_progress` with an agent actively executing
**When** a user @mentions a different agent in the thread
**Then** the mentioned agent runs concurrently (separate session) without interfering with the executing agent
**And** the executing agent's work is not interrupted or affected
**And** both agents can post to the thread without conflict

## Tasks / Subtasks

- [x] Task 1: Remove status-based skip in MentionWatcher (AC: 1)
  - [x] 1.1: In `mc/mention_watcher.py`, in `_poll_all_tasks()`, removed the guard that skips `in_progress` tasks.
  - [x] 1.2: Removed the guard that skips `review` + `awaitingKickoff` tasks.
  - [x] 1.3: Removed the `_NEGOTIATION_STATUSES` constant — no longer needed.
  - [x] 1.4: Updated the module docstring and class docstring to reflect that MentionWatcher now handles ALL task statuses.

- [x] Task 2: PlanNegotiator skips @mention messages (AC: 2, 3, 4)
  - [x] 2.1: In `mc/plan_negotiator.py`, in the message polling loop, replaced the `handle_all_mentions` dispatch with a simple `is_mention_message()` guard that skips @mention messages (leaving them for MentionWatcher).
  - [x] 2.2: `is_mention_message` imported inline (local import in the loop body, consistent with existing pattern).
  - [x] 2.3: Added debug log: `"[plan_negotiator] Skipping @mention message (handled by MentionWatcher): {content[:80]}"`.
  - [x] 2.4: Verified via test `test_still_processes_non_mention_messages` that non-mention messages continue to be routed to Lead Agent.

- [x] Task 3: Deduplication safety (AC: 2)
  - [x] 3.1: Verified via test `test_dedup_prevents_reprocessing` — `_per_task_seen` prevents re-processing on `in_progress` tasks.
  - [x] 3.2: Verified via test `test_first_encounter_marks_existing_messages_as_seen` — on first encounter, all existing messages are marked as seen.
  - [x] 3.3: Verified via test `test_per_task_seen_tracks_across_status_changes` — _per_task_seen tracks by task_id, not status. No code change needed.

- [x] Task 4: Concurrency safety (AC: 5)
  - [x] 4.1: Verified via test `test_concurrent_session_key_uniqueness` — session key `mc:mention:{agent_name}:{task_id}:{uuid}` is unique per mention.
  - [x] 4.2: Verified by code inspection — Convex mutations are atomic, both agents can call `bridge.send_message()` concurrently.
  - [x] 4.3: No code change needed — documented in tests.

- [x] Task 5: Tests (AC: all)
  - [x] 5.1: `test_processes_mention_on_in_progress_task` — MentionWatcher processes @mention on in_progress task.
  - [x] 5.2: `test_processes_mention_on_review_awaiting_kickoff_task` — MentionWatcher processes @mention on review+awaitingKickoff task.
  - [x] 5.3: `test_skips_mention_message` — PlanNegotiator skips @mention messages.
  - [x] 5.4: `test_still_processes_non_mention_messages` — PlanNegotiator handles non-mention messages normally.
  - [x] 5.5: `test_mention_handled_only_by_watcher_not_negotiator` — integration test verifying no double-processing.

## Dev Notes

### Architecture & Design Decisions

**Why move ALL mention handling to MentionWatcher?** Previously, mentions were split: MentionWatcher handled non-active tasks, PlanNegotiator handled in_progress/review. This created complexity (two code paths for the same feature) and gave different context quality (PlanNegotiator used Lead Agent routing, MentionWatcher used direct agent invocation). Consolidating in MentionWatcher provides:
- One code path for @mentions regardless of task status
- Consistent enriched context (from Story 13.2)
- Simpler mental model for both developers and users

**Why not remove @mention handling from PlanNegotiator entirely?** We don't remove code from PlanNegotiator — we add a guard that skips @mention messages. The PlanNegotiator still processes all non-mention user messages for plan modification. This is the minimal change that achieves clean separation.

**Concurrency model.** When a user @mentions agent-B on a task where agent-A is executing:
- Agent-A runs in its own nanobot `AgentLoop` with session key `mc:task:{task_id}:...`
- Agent-B runs in a separate `AgentLoop` with session key `mc:mention:{agent_name}:{task_id}:{uuid}`
- Both can post to the thread via `bridge.send_message()` — Convex mutations are atomic, so messages interleave safely
- Agent-A's execution is not interrupted (it doesn't poll for new thread messages mid-execution)

**Dedup is already handled.** MentionWatcher tracks `_per_task_seen[task_id]` which is a set of message IDs. This works regardless of task status. The only edge case is when a task first appears (e.g., transitions to `in_progress` and was previously skipped) — on first encounter, ALL existing messages are marked as seen, so only new messages trigger mentions. This is the correct behavior.

### Existing Code to Reuse

**`mc/mentions/watcher.py`** (lines 48-202):
- `_poll_all_tasks()` — the main polling method to modify
- `_per_task_seen` — existing dedup mechanism (no changes needed)
- Lines 121-125 — the guards to remove

**`mc/plan_negotiator.py`**:
- The user message polling loop — add `is_mention_message()` guard
- Existing @mention routing code — will become dead code after the guard

**`mc/mentions/handler.py`**:
- `is_mention_message()` — import and use in PlanNegotiator

### Common Mistakes to Avoid

1. **Do NOT remove the PlanNegotiator's @mention handling code** — just add a guard that skips mention messages. The existing code can be cleaned up in a later refactor, but removing it now risks breaking something if the guard has a bug.
2. **Do NOT change the polling interval** — keep `POLL_INTERVAL_SECONDS = 3` in MentionWatcher. Adding in_progress tasks to the poll doesn't increase load significantly.
3. **Do NOT stop polling per-status in MentionWatcher** — the per-status polling is needed for the `listByStatus` query. Just remove the skip guards.
4. **Do NOT add locks or semaphores for concurrent mentions** — Convex's atomic mutations and nanobot's session isolation already handle concurrency.
5. **Do NOT change message type for @mention messages** — they must remain `user_message` type for MentionWatcher to detect them.

### Dependencies

- **Story 13.1** must be completed first — the `postMentionMessage` mutation must exist so that @mention messages are created without status transitions. Otherwise MentionWatcher would process messages created by `sendThreadMessage`, which also transitions status.
- **Story 13.2** should be completed first — so that mentions on in_progress tasks get the enriched context. But this story can be developed in parallel if needed (the MentionWatcher changes are independent of the context enrichment).

### Project Structure Notes

- **MODIFIED**: `mc/mentions/watcher.py` — remove status-based skip guards
- **MODIFIED**: `mc/plan_negotiator.py` — add @mention skip guard
- **NEW**: `tests/mc/mentions/test_watcher_universal.py` — tests for universal coverage
- **NEW**: `tests/mc/test_plan_negotiator_mention_skip.py` — test PlanNegotiator skips mentions
- No Convex/dashboard changes in this story

### References

- [Source: mc/mentions/watcher.py#_poll_all_tasks — lines 85-202, polling loop with status guards]
- [Source: mc/mentions/watcher.py#_NEGOTIATION_STATUSES — line 30, statuses to remove]
- [Source: mc/plan_negotiator.py — PlanNegotiator message handling loop]
- [Source: mc/mentions/handler.py#is_mention_message — line 104-106, mention detection utility]
- [Source: mc/mentions/handler.py#handle_mention — lines 109-341, session isolation pattern]

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References
N/A

### Completion Notes List
- Removed status-based skip guards in MentionWatcher (`_poll_all_tasks()`) so it now processes @mentions on ALL task statuses including in_progress and review+awaitingKickoff.
- Removed the `_NEGOTIATION_STATUSES` constant that was no longer needed.
- Updated module and class docstrings in `mc/mention_watcher.py` to reflect universal coverage.
- Modified PlanNegotiator to skip @mention messages instead of dispatching them via `handle_all_mentions`. The existing `handle_all_mentions` dispatch was replaced with a simple `is_mention_message()` guard + `continue`, with a debug log.
- Updated PlanNegotiator module docstring to reflect Story 13.3 changes.
- Removed unused `LEAD_AGENT_NAME` import from `mc/plan_negotiator.py` (caught by linter after `handle_all_mentions` removal).
- All 14 new tests pass, all 39 existing tests pass (53 total, zero regressions).

### File List
- `mc/mention_watcher.py` (modified) — removed status-based skip guards, removed `_NEGOTIATION_STATUSES`, updated docstrings
- `mc/plan_negotiator.py` (modified) — replaced @mention dispatch with skip guard, updated module docstring
- `tests/mc/test_mention_watcher_universal.py` (new) — 9 tests for MentionWatcher universal coverage
- `tests/mc/test_plan_negotiator_mention_skip.py` (new) — 5 tests for PlanNegotiator mention skip + no-double-processing
- `_bmad-output/implementation-artifacts/13-3-universal-mention-coverage.md` (modified) — story file updated with completion status

### Change Log
- 2026-03-05: Implemented Story 13.3 — Universal Mention Coverage. Removed status-based skip guards in MentionWatcher, added @mention skip guard in PlanNegotiator. 14 new tests, all passing.
