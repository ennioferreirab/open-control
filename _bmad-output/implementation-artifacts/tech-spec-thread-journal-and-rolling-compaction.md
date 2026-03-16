# Tech Spec: Thread Journal And Rolling Compaction

Status: ready-for-dev

## Story

As a **Mission Control runtime maintainer**,
I want task threads to have a complete Markdown journal plus mandatory rolling compaction,
so that agents can keep a bounded live context while still having access to the full workflow and task history when needed.

## Acceptance Criteria

### AC1: Task-scoped journal file exists

**Given** a task thread exists
**When** the runtime syncs thread context for that task
**Then** it materializes a complete Markdown journal at `~/.nanobot/tasks/<safe_task_id>/output/THREAD_JOURNAL.md`
**And** that journal contains the current task snapshot, execution plan, and append-only thread events.

### AC2: Convex remains the primary source of truth

**Given** a task has thread messages in Convex
**When** the journal is updated or compaction runs
**Then** Convex messages are not deleted or rewritten
**And** the journal is treated as a derived artifact that can be rebuilt from Convex state.

### AC3: Agents receive journal-aware context

**Given** task, step, mention, or conversation context is built for an agent
**When** the runtime assembles thread context
**Then** the prompt includes:
- a rolling compacted summary,
- a recent raw-message window,
- and the absolute journal path
**And** the prompt explicitly tells the agent the complete thread history is available in the journal.

### AC4: Rolling compaction is recursive and bounded

**Given** the thread crosses the configured message or character threshold
**When** background compaction runs
**Then** it produces a new `compacted_summary` from:
- the previous `compacted_summary`,
- the next eligible batch of older messages,
- and important structured events
**And** the resulting summary remains under the configured upper token limit.

### AC5: Recent live window remains raw

**Given** rolling compaction has already occurred
**When** a new agent context is built
**Then** the most recent 15 messages still appear as raw thread history
**And** only older eligible messages are absorbed into the compacted summary.

### AC6: Important thread semantics survive compaction

**Given** older messages include structured events
**When** those messages are compacted
**Then** the compacted summary still preserves the facts from:
- `lead_agent_plan`,
- `lead_agent_chat` with material decisions,
- `step_completion`,
- `system_error`,
- approvals and denials,
- and messages with relevant files or artifacts.

### AC7: Background compaction is deduplicated per task

**Given** a task crosses the compaction threshold repeatedly before the current compaction finishes
**When** the runtime schedules background work
**Then** only one compaction task is active for that task at a time.

### AC8: Compaction failure crashes the task

**Given** rolling compaction fails
**When** the runtime handles the failure
**Then** it logs the error with the task id and journal path
**And** it transitions the task to `crashed`
**And** it does not use a deterministic fallback or continue with degraded compacted context.

### AC9: Journal sync reconciles direct dashboard writes

**Given** user thread messages may be created directly from the dashboard path
**When** execution or conversation code later reads thread context
**Then** the reconciliation path detects unseen Convex messages and appends them to the local journal before building prompt context.

## Tasks / Subtasks

- [ ] Task 1: Add canonical task journal/state paths and storage primitives (AC: 1, 2)
- [ ] Task 2: Implement journal reconciliation and rolling compaction state (AC: 1, 2, 4, 5, 6, 9)
- [ ] Task 3: Inject journal-aware context into execution and conversation builders (AC: 3, 5)
- [ ] Task 4: Deduplicate background compaction and crash on failure (AC: 7, 8)
- [ ] Task 5: Verify focused tests plus architecture guardrails (AC: 1-9)

## Dev Notes

- Use the task output directory resolved from `task_safe_id(task_id)`.
- Keep the journal and compaction state local to the task workspace; no new Convex schema field is required in the first implementation.
- Reuse existing background-task infrastructure and task-status mutations.
- No fallback summarizer is allowed for this story.

## References

- [Source: /Users/ennio/Documents/nanobot-ennio/.worktrees/thread-journal-design/docs/plans/2026-03-16-thread-journal-and-rolling-compaction-design.md]
- [Source: /Users/ennio/Documents/nanobot-ennio/.worktrees/thread-journal-design/docs/plans/2026-03-16-thread-journal-and-rolling-compaction-implementation-plan.md]
- [Source: /Users/ennio/Documents/nanobot-ennio/mc/application/execution/context_builder.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/mc/application/execution/thread_context.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/mc/application/execution/background_tasks.py]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
