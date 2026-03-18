# Story 7.2: Implement Timeout Detection and Escalation

Status: done

## Story

As a **user**,
I want stalled tasks and slow reviews to be flagged automatically,
So that nothing gets stuck without me noticing.

## Acceptance Criteria

1. **Given** a task has been in "in_progress" state longer than the configured task timeout, **When** the timeout threshold is exceeded, **Then** the system flags the task as stalled (FR39) with a `system_error` activity event: "Task '{title}' stalled -- in progress for {duration}"
2. **Given** a stalled task is detected, **Then** the TaskCard shows an amber "Stalled" badge indicator
3. **Given** an inter-agent review request has been pending longer than the configured inter-agent timeout, **When** the timeout threshold is exceeded, **Then** the system escalates the review (FR40) with a `system_error` activity event: "Review for '{title}' timed out -- escalating"
4. **Given** a review is escalated, **Then** a system message is added to the task thread about the escalation
5. **Given** no custom timeout is configured on a task, **When** timeout checking runs, **Then** the global default timeout values are used (from settings)
6. **Given** a task has a custom timeout configured (FR42), **When** timeout checking runs, **Then** the per-task timeout overrides the global default
7. **And** timeout checking is implemented as a periodic check in `nanobot/mc/gateway.py`
8. **And** timeout values are read from Convex `settings` table with per-task override from task document
9. **And** unit tests cover timeout detection, escalation, and per-task override logic

## Tasks / Subtasks

- [ ] Task 1: Create Convex settings queries and mutations (AC: #5, #8)
  - [ ] 1.1: Create `dashboard/convex/settings.ts` with queries and mutations
  - [ ] 1.2: Add `get` query: takes a `key` string, returns the value from the settings table (using `by_key` index)
  - [ ] 1.3: Add `set` mutation: takes `key` and `value` strings, upserts the setting
  - [ ] 1.4: Add `list` query: returns all settings as key-value pairs
  - [ ] 1.5: Define default values: `task_timeout_minutes: "30"`, `inter_agent_timeout_minutes: "10"`

- [ ] Task 2: Implement timeout detection loop in the gateway (AC: #1, #3, #7)
  - [ ] 2.1: Add `_start_timeout_checker()` async method to the gateway
  - [ ] 2.2: Run a periodic check every 60 seconds (using `asyncio.sleep(60)`)
  - [ ] 2.3: For each task in "in_progress" state, check if `updatedAt` exceeds the timeout threshold
  - [ ] 2.4: For each task in "review" state with reviewers, check if `updatedAt` exceeds the inter-agent timeout threshold
  - [ ] 2.5: Read timeout values from settings via `bridge.query("settings:get", {"key": "task_timeout_minutes"})`
  - [ ] 2.6: Override with per-task values if `task.task_timeout` or `task.inter_agent_timeout` is set

- [ ] Task 3: Implement stall detection (AC: #1, #2)
  - [ ] 3.1: When a task exceeds its timeout in "in_progress" state:
    - Create a `system_error` activity event with the stall message
    - Send a system message to the task thread: "Task stalled. In progress for {duration}. Consider checking on the assigned agent."
    - Track already-flagged tasks to avoid duplicate alerts (use a set of task IDs)
  - [ ] 3.2: The "Stalled" indicator on the dashboard is driven by the activity event — the TaskCard can check for recent `system_error` events or add a `stalled` flag to the task document

- [ ] Task 4: Implement review escalation (AC: #3, #4)
  - [ ] 4.1: When a review request exceeds the inter-agent timeout:
    - Create a `system_error` activity event: "Review for '{title}' timed out -- escalating"
    - Send a system message to the task thread
    - Optionally notify the Lead Agent to re-route the review
  - [ ] 4.2: Track already-escalated reviews to avoid duplicates

- [ ] Task 5: Add stalled indicator to TaskCard (AC: #2)
  - [ ] 5.1: Option A: Add a `stalled` boolean field to the task document (set by the gateway)
  - [ ] 5.2: Option B: Check if a recent `system_error` activity event exists for the task
  - [ ] 5.3: When stalled, show an amber "Stalled" badge on the TaskCard (using `Badge` with amber styling)
  - [ ] 5.4: Use `Clock` or `AlertTriangle` Lucide icon alongside the badge

- [ ] Task 6: Write unit tests (AC: #9)
  - [ ] 6.1: Test timeout detection flags a task that exceeds the default timeout
  - [ ] 6.2: Test per-task timeout override is respected
  - [ ] 6.3: Test review escalation for reviews exceeding inter-agent timeout
  - [ ] 6.4: Test no duplicate alerts for already-flagged tasks
  - [ ] 6.5: Test default values are used when no settings are configured

## Dev Notes

### Critical Architecture Requirements

- **Timeout detection is periodic, not event-driven**: The gateway checks for stalled tasks on an interval (every 60 seconds). This is simpler and sufficient for MVP.
- **Settings are stored in Convex**: The `settings` table stores global defaults as key-value pairs. The gateway reads them via the bridge.
- **Per-task overrides are on the task document**: The `taskTimeout` and `interAgentTimeout` fields on the task (already in schema) override global defaults.
- **Stall detection does NOT change task status**: A stalled task stays in "in_progress". The system creates an alert (activity event + badge) but does not force a status change. The user or Lead Agent can decide what to do.

### Timeout Configuration Hierarchy

```
Per-task timeout (task.taskTimeout)  >  Global default (settings table)  >  Hardcoded fallback (30 min / 10 min)
```

### Settings Table Patterns

```typescript
// dashboard/convex/settings.ts
import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const get = query({
  args: { key: v.string() },
  handler: async (ctx, args) => {
    const setting = await ctx.db
      .query("settings")
      .withIndex("by_key", (q) => q.eq("key", args.key))
      .first();
    return setting?.value ?? null;
  },
});

export const set = mutation({
  args: { key: v.string(), value: v.string() },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("settings")
      .withIndex("by_key", (q) => q.eq("key", args.key))
      .first();
    if (existing) {
      await ctx.db.patch(existing._id, { value: args.value });
    } else {
      await ctx.db.insert("settings", { key: args.key, value: args.value });
    }
  },
});

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("settings").collect();
  },
});
```

### Timeout Detection Pattern

```python
import asyncio
from datetime import datetime, timezone, timedelta

DEFAULT_TASK_TIMEOUT_MINUTES = 30
DEFAULT_INTER_AGENT_TIMEOUT_MINUTES = 10

class TimeoutChecker:
    def __init__(self, bridge: ConvexBridge):
        self._bridge = bridge
        self._flagged_tasks: set[str] = set()  # Avoid duplicate alerts

    async def start(self) -> None:
        """Periodically check for stalled tasks."""
        while True:
            try:
                await self._check_timeouts()
            except Exception as e:
                logger.error("Timeout check failed: %s", e)
            await asyncio.sleep(60)

    async def _check_timeouts(self) -> None:
        now = datetime.now(timezone.utc)

        # Read global timeout settings
        task_timeout_str = self._bridge.query("settings:get", {"key": "task_timeout_minutes"})
        task_timeout = int(task_timeout_str) if task_timeout_str else DEFAULT_TASK_TIMEOUT_MINUTES

        review_timeout_str = self._bridge.query("settings:get", {"key": "inter_agent_timeout_minutes"})
        review_timeout = int(review_timeout_str) if review_timeout_str else DEFAULT_INTER_AGENT_TIMEOUT_MINUTES

        # Check in_progress tasks
        in_progress = self._bridge.query("tasks:listByStatus", {"status": "in_progress"})
        for task in (in_progress or []):
            task_id = task.get("id")
            if task_id in self._flagged_tasks:
                continue
            timeout_minutes = task.get("task_timeout") or task_timeout
            updated_at = datetime.fromisoformat(task.get("updated_at", now.isoformat()))
            if now - updated_at > timedelta(minutes=timeout_minutes):
                self._flag_stalled_task(task_id, task, now - updated_at)

        # Check review tasks for inter-agent timeout
        review_tasks = self._bridge.query("tasks:listByStatus", {"status": "review"})
        for task in (review_tasks or []):
            task_id = task.get("id")
            if task_id in self._flagged_tasks:
                continue
            if not task.get("reviewers"):
                continue  # Only check tasks with configured reviewers
            timeout_minutes = task.get("inter_agent_timeout") or review_timeout
            updated_at = datetime.fromisoformat(task.get("updated_at", now.isoformat()))
            if now - updated_at > timedelta(minutes=timeout_minutes):
                self._escalate_review(task_id, task, now - updated_at)
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT change task status on timeout** — Stalled detection is an alert, not a state transition. The task stays in "in_progress" or "review".

2. **DO NOT check every second** — A 60-second interval is sufficient for timeout detection. More frequent checks waste resources.

3. **DO NOT send duplicate alerts** — Track flagged task IDs to avoid spamming the activity feed with repeated stall notifications.

4. **DO NOT hardcode timeout values** — Read from the settings table first, fall back to defaults only if no settings exist.

5. **DO NOT forget per-task overrides** — If `task.taskTimeout` is set, use it instead of the global default.

6. **DO NOT use `time.sleep()` in async code** — Use `asyncio.sleep()` in the async gateway context.

### What This Story Does NOT Include

- **Dashboard settings panel** — Story 7.3 builds the UI for configuring timeouts
- **Per-task timeout input at creation** — Story 7.3 adds timeout fields to TaskInput
- **Auto-resolution of stalled tasks** — Stall detection only alerts; resolution is manual

### Files Created in This Story

| File | Purpose |
|------|---------|
| `dashboard/convex/settings.ts` | Settings queries (get, set, list) and mutations |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `nanobot/mc/gateway.py` | Add timeout detection loop with stall and review escalation |
| `dashboard/components/TaskCard.tsx` | Optionally add "Stalled" badge for stalled tasks |
| `nanobot/mc/test_gateway.py` | Add tests for timeout detection |

### Verification Steps

1. Set global task timeout to 1 minute (for testing)
2. Create a task and transition to "in_progress" — wait 2 minutes
3. Verify "Task stalled" activity event appears in feed
4. Verify system message in task thread
5. Set a per-task timeout of 5 minutes — verify it overrides the 1-minute global
6. Create a review task with reviewers — set inter-agent timeout to 1 minute — wait 2 minutes
7. Verify "Review timed out" escalation event
8. Run `pytest nanobot/mc/test_gateway.py` — all tests pass

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 7.2`] — Original story definition
- [Source: `_bmad-output/planning-artifacts/prd.md#FR39`] — Stalled task detection
- [Source: `_bmad-output/planning-artifacts/prd.md#FR40`] — Inter-agent timeout escalation
- [Source: `_bmad-output/planning-artifacts/prd.md#FR42`] — Per-task timeout override
- [Source: `dashboard/convex/schema.ts`] — Settings table schema, task timeout fields
- [Source: `nanobot/mc/gateway.py`] — Gateway to add timeout checking
- [Source: `nanobot/mc/bridge.py`] — Bridge for querying settings and tasks

## Dev Agent Record

### Agent Model Used
claude-opus-4-6

### Debug Log References
All 17 tests pass: `python3 -m pytest nanobot/mc/test_timeout_checker.py -v`

### Completion Notes List
- Created TimeoutChecker class in dedicated module (timeout_checker.py)
- Periodic check every 60 seconds via asyncio loop
- Stalled task detection: flags in_progress tasks exceeding timeout
- Review escalation: escalates review tasks with reviewers exceeding inter-agent timeout
- Settings read from Convex settings table (task_timeout_minutes, inter_agent_timeout_minutes)
- Per-task override via task.task_timeout / task.inter_agent_timeout
- Hardcoded fallback: 30 min task timeout, 10 min inter-agent timeout
- Duplicate alert prevention via flagged task ID sets
- Stall detection does NOT change task status (alert only)
- Added stalledAt field to schema + markStalled mutation
- Added Stalled badge (amber, Clock icon) to TaskCard
- Integrated TimeoutChecker into run_gateway alongside orchestrator
- Convex settings.ts already existed (created by another story)
- Pre-existing test failure in test_state_machine.py (review_to_inbox) unrelated to this story

### File List
- `nanobot/mc/timeout_checker.py` (NEW) -- TimeoutChecker class
- `nanobot/mc/test_timeout_checker.py` (NEW) -- 17 unit tests
- `nanobot/mc/gateway.py` (MODIFIED) -- Integrated TimeoutChecker into run_gateway
- `dashboard/convex/schema.ts` (MODIFIED) -- Added stalledAt optional field to tasks
- `dashboard/convex/tasks.ts` (MODIFIED) -- Added markStalled mutation
- `dashboard/components/TaskCard.tsx` (MODIFIED) -- Added Stalled badge indicator
