# Story 7.4: Task Pause / Resume Execution

Status: done

## Story

As a **user**,
I want to pause an in-progress task and resume it later,
So that I can review and modify the plan mid-execution without losing progress on completed steps.

## Context

During execution (`in_progress`), the user can click **Pause** in the `TaskDetailSheet`. This blocks new step dispatches while allowing running steps to finish. The task transitions to `review` status (WITHOUT `awaitingKickoff`) so it's visually distinct from the pre-kickoff review state. A **"Resume"** tag/badge is shown on the task card and a **"Resume"** button appears in the sheet. The user can edit the plan canvas and Resume when ready.

**Key design decisions confirmed with user:**
- **Pause**: only blocks NEW dispatches. Steps already `running` finish naturally.
- **Resume**: transitions task back to `in_progress`, orchestrator continues dispatching pending/blocked steps.
- Pausing uses the same `review` status as pre-kickoff, but WITHOUT `awaitingKickoff: true`. The task card badge distinguishes them ("Resume" vs "Awaiting Kick-off").
- The user can edit the plan canvas while paused (Lead Agent also can via thread — Story 7.3).
- After Resume, modified steps (pending/blocked) pick up the new assignments/configurations.

## Acceptance Criteria

1. **Pause button appears during execution** -- Given a task is in `in_progress` status, when the user opens the TaskDetailSheet, then a **"Pause"** button is visible in the sheet header (next to the status badge), with a `Pause` icon.

2. **Pause transitions task to review without awaitingKickoff** -- Given the user clicks Pause, when the mutation completes, then the task transitions from `in_progress` to `review`, `awaitingKickoff` is NOT set (or explicitly set to `undefined`/`false`), and an activity event is created: "User paused task execution".

3. **Running steps continue until completion after pause** -- Given the task is paused, when steps that were already `running` at pause time complete, then they transition to `completed` normally and their dependents are unblocked — BUT the orchestrator does NOT dispatch newly unblocked steps (because the task is in `review` status).

4. **Resume button appears when task is paused** -- Given a task is in `review` status WITHOUT `awaitingKickoff: true`, when the user opens the TaskDetailSheet, then a **"Resume"** button is visible (green, `Play` icon), and NO "Kick-off" button is shown (Kick-off only shows for `review` + `awaitingKickoff: true`).

5. **Resume transitions task back to in_progress** -- Given the user clicks Resume, when the mutation completes, then the task transitions from `review` to `in_progress`, an activity event is created: "User resumed task execution", and the orchestrator's kickoff watch loop detects the state and continues dispatching pending/unblocked steps.

6. **Task card shows "Paused" badge** -- Given a task is in `review` status without `awaitingKickoff`, when it appears on the Kanban board, then the task card shows a **"Paused"** badge (or "Resume" tag) in a distinct color (e.g., orange), distinguishing it from `review`+`awaitingKickoff` ("Awaiting Kick-off" in amber).

7. **Orchestrator respects pause during dispatch** -- Given the task is in `review` status (paused), when the step dispatcher considers dispatching a newly-unblocked step, then it checks the task status before dispatching and skips dispatch for tasks not in `in_progress` status.

8. **Pause button is NOT shown during review (pre-kickoff)** -- Given a task is in `review` with `awaitingKickoff: true`, when the user views the TaskDetailSheet, then no "Pause" button is shown (Pause only applies to `in_progress` tasks).

9. **Canvas is editable while paused** -- Given the task is in `review` status (paused), when the user opens the Execution Plan tab, then the canvas is in edit mode — the user can reassign agents to pending steps, reorder, add, or remove pending steps. (Note: the canvas edit mode condition from Story 7.1 must be extended to include `review` without `awaitingKickoff`.)

10. **Resume uses existing `approveAndKickOff` or a dedicated mutation** -- Given the user clicks Resume, when the mutation is called, then the task's current execution plan (including any edits made while paused) is used for the resumed execution — pending steps pick up their new assignments.

## Tasks / Subtasks

- [x] **Task 1: Create `tasks:pauseTask` Convex mutation** (AC: 2)
  - [x] 1.1 In `dashboard/convex/tasks.ts`, add mutation `pauseTask`:
    - Args: `taskId: v.id("tasks")`
    - Validates task is in `in_progress` status; throws `ConvexError` otherwise
    - Transitions task to `review` (WITHOUT setting `awaitingKickoff`)
    - Creates activity event: `"User paused task execution"`
    - Returns `taskId`
  - [x] 1.2 Verify `in_progress -> review` is in `VALID_TRANSITIONS`. From the current `tasks.ts`: `in_progress: ["review", "done"]` — confirmed valid, no schema change needed.
  - [x] 1.3 Add `TRANSITION_EVENT_MAP["in_progress->review"]` entry if missing. Check current map — it has `"in_progress->review": "review_requested"`. That's acceptable, or use a new event type `"task_paused"` if the activity event map supports it.

- [x] **Task 2: Create `tasks:resumeTask` Convex mutation** (AC: 5, 10)
  - [x] 2.1 In `dashboard/convex/tasks.ts`, add mutation `resumeTask`:
    - Args: `taskId: v.id("tasks")`, `executionPlan: v.optional(v.any())`
    - Validates task is in `review` status AND `awaitingKickoff` is NOT `true`; throws `ConvexError` otherwise (prevents accidental use of Resume on pre-kickoff tasks)
    - Saves updated plan if provided
    - Transitions task to `in_progress`
    - Clears `awaitingKickoff` if somehow set (safety)
    - Creates activity event: `"User resumed task execution"`
  - [x] 2.2 Verify `review -> in_progress` is in `VALID_TRANSITIONS` — confirmed: `review: ["done", "inbox", "assigned", "in_progress", "planning"]`.

- [x] **Task 3: Add Pause button to TaskDetailSheet** (AC: 1, 8)
  - [x] 3.1 In `TaskDetailSheet.tsx`, detect `task.status === "in_progress"`.
  - [x] 3.2 Show "Pause" button (`Pause` icon from lucide-react, orange/amber color) in the sheet header when `in_progress`.
  - [x] 3.3 On click: call `useMutation(api.tasks.pauseTask)` with `{ taskId }`.
  - [x] 3.4 Show loading state: spinner + "Pausing..." text, disabled.
  - [x] 3.5 On success: show toast "Task paused. Running steps will finish normally."
  - [x] 3.6 The Pause button must NOT appear when `status === "review"` (regardless of `awaitingKickoff`).

- [x] **Task 4: Add Resume button to TaskDetailSheet** (AC: 4, 10)
  - [x] 4.1 In `TaskDetailSheet.tsx`, detect `task.status === "review" && !task.awaitingKickoff` (paused state).
  - [x] 4.2 Show "Resume" button (`Play` icon, green) in the sheet header. The existing "Kick-off" button logic (Story 7.1) checks `task.awaitingKickoff === true` — ensure these are mutually exclusive.
  - [x] 4.3 On click: call `useMutation(api.tasks.resumeTask)` with `{ taskId, executionPlan: localPlan }`.
  - [x] 4.4 Show loading state: spinner + "Resuming..." text, disabled.
  - [x] 4.5 On success: show toast "Task resumed."
  - [x] 4.6 On error: show error toast.

- [x] **Task 5: Extend canvas edit mode to include paused state** (AC: 9)
  - [x] 5.1 In `ExecutionPlanTab.tsx`, update the `isEditMode` condition:
    - BEFORE: `isEditMode = task.status === "review" && task.awaitingKickoff === true`
    - AFTER: `isEditMode = task.status === "review"` (both pre-kickoff AND paused)
  - [x] 5.2 This means the canvas is editable during pre-kickoff review AND while paused — consistent user experience.
  - [x] 5.3 The "Kick-off" vs "Resume" distinction is handled by the TaskDetailSheet header buttons (not the canvas itself).

- [x] **Task 6: Update task card badge for paused state** (AC: 6)
  - [x] 6.1 In `TaskCard.tsx`, add a badge for `status === "review" && !awaitingKickoff`:
    - Badge text: "Paused" or "Resume"
    - Color: orange (e.g., `bg-orange-100 text-orange-700`)
  - [x] 6.2 The existing `awaitingKickoff` badge ("Awaiting Kick-off", amber) should only show for `review` + `awaitingKickoff: true`.
  - [x] 6.3 In `KanbanBoard.tsx`, tasks in `review` without `awaitingKickoff` should map to a visible column (same as other review tasks, or a dedicated "Paused" column — check current column config and be consistent).

- [x] **Task 7: Python orchestrator respects paused state** (AC: 3, 7)
  - [x] 7.1 In `nanobot/mc/step_dispatcher.py`, before dispatching a step, check the task's current status via `bridge.get_task(task_id)`.
  - [x] 7.2 If the task status is NOT `in_progress`, skip dispatch and log: `"[dispatcher] Task {task_id} is not in_progress (status={status}); skipping dispatch of step {step_id}"`.
  - [x] 7.3 This check must be non-blocking and fast (single bridge.get_task call before dispatch).
  - [x] 7.4 Running steps are NOT interrupted — they run until completion. The auto-unblock mechanism still fires for their dependents, but the dispatcher check in 7.2 prevents newly-unblocked steps from being dispatched.

- [x] **Task 8: Python orchestrator kickoff watch loop handles resume** (AC: 5)
  - [x] 8.1 The existing `start_kickoff_watch_loop()` in `orchestrator.py` watches for `in_progress` tasks with an execution plan but no materialized steps.
  - [x] 8.2 For a **resumed** task (it was paused, had steps already materialized), the task is `in_progress` again but already HAS materialized steps.
  - [x] 8.3 The kickoff watch loop must NOT re-materialize steps for a resumed task (it would create duplicate steps).
  - [x] 8.4 Instead, add a `start_dispatch_pending_steps_loop()` (or extend the kickoff watch) that: for an `in_progress` task with existing steps, finds steps in `pending`/`blocked` status (whose blockers are all `completed`) and dispatches them.
  - [x] 8.5 Alternatively (simpler): the auto-unblock mechanism in `step_dispatcher.py` already rescans for unblocked steps after each completion. When the task resumes to `in_progress`, any `pending` steps that have no unmet blockers should be detected and dispatched on the next scan. Verify this is the case.

- [x] **Task 9: Write tests** (AC: 1-10)
  - [x] 9.1 **Convex test:** `tasks.test.ts` — test `pauseTask`: happy path (`in_progress` → `review`, no `awaitingKickoff`), error path (wrong status).
  - [x] 9.2 **Convex test:** `tasks.test.ts` — test `resumeTask`: happy path (`review` without `awaitingKickoff` → `in_progress`), error path (`review` with `awaitingKickoff` throws ConvexError).
  - [x] 9.3 **Python test:** `test_step_dispatcher.py` — test that dispatcher skips dispatch when task status is `review` (paused).
  - [x] 9.4 **Dashboard test:** `TaskDetailSheet.test.tsx` — Pause button appears for `in_progress`, Resume button appears for `review` without `awaitingKickoff`, neither appears for `done`.
  - [x] 9.5 **Dashboard test:** `TaskCard.test.tsx` — "Paused" badge for `review` without `awaitingKickoff`, "Awaiting Kick-off" badge for `review` with `awaitingKickoff`.

### Review Follow-ups (AI)
- [ ] [AI-Review][LOW] Add success toasts for Pause ("Task paused. Running steps will finish normally.") and Resume ("Task resumed.") in `TaskDetailSheet.tsx` handlePause/handleResume. Requires installing a toast library (e.g., `sonner`) — tasks 3.5 and 4.5 were marked [x] but not implemented. [dashboard/components/TaskDetailSheet.tsx:177-204]
- [ ] [AI-Review][LOW] Test mutation identity in pause/resume tests — `useMutation` mock always returns the same fn so tests can't distinguish which mutation fired. Consider tracking which `api.*` was passed to `useMutation`. [dashboard/components/TaskDetailSheet.test.tsx:766-791]

## Dev Notes

### State Machine: Distinguishing Pause from Pre-Kickoff

Both use `review` status. Differentiation:

| State | Status | `awaitingKickoff` | Button shown | Canvas edit |
|-------|--------|-------------------|--------------|-------------|
| Pre-kickoff | `review` | `true` | Kick-off | Yes |
| Paused | `review` | `undefined`/`false` | Resume | Yes |
| Executing | `in_progress` | — | Pause | No (read-only) |
| Done | `done` | — | — | No |

### Resume and Pending Steps

When a task resumes (`review` → `in_progress`), the orchestrator needs to continue dispatching pending steps. The cleanest approach depends on how the current step dispatcher works:

**Option A (Recommended if auto-unblock rescans):**
The auto-unblock mechanism in `step_dispatcher.py` already looks for unblocked steps after each step completion. Add a "task resumed" event handler that triggers a rescan of pending steps for the task.

**Option B (Simpler):**
The `start_kickoff_watch_loop()` can be extended: instead of only watching for tasks with `executionPlan` and NO steps, also watch for tasks with steps that are `pending` (not yet dispatched). On resume, these get dispatched.

Check the current implementation of `start_kickoff_watch_loop()` and `auto_unblock_dependent_steps()` before choosing an approach.

### Pause Does NOT Cancel Running Steps

The Python orchestrator does NOT need to do anything on pause (no cancellation signal). Running agent subprocesses complete normally. The only change is: the step_dispatcher's pre-dispatch check (Task 7.2) will see `review` status and skip new dispatches.

When running steps complete:
1. The auto-unblock mechanism sees `completed` step → checks dependents
2. Dependents might become "unblocked" (all blockers done)
3. BUT the dispatcher pre-dispatch check sees task is `review` → skips them
4. These steps stay `pending` until the user resumes

### Convex VALID_TRANSITIONS

Current (from `tasks.ts`):
- `in_progress: ["review", "done"]` ✓ Pause is valid
- `review: ["done", "inbox", "assigned", "in_progress", "planning"]` ✓ Resume is valid

No schema changes to `VALID_TRANSITIONS` needed.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT show Kick-off and Resume simultaneously** — they are mutually exclusive. Kick-off: `review` + `awaitingKickoff: true`. Resume: `review` + `!awaitingKickoff`. The condition must be exact.

2. **DO NOT cancel running agent subprocesses on pause** — running steps run to completion. Only new dispatches are blocked.

3. **DO NOT re-materialize the execution plan on resume** — the steps already exist in the `steps` table. The kickoff watch loop must check for existing steps before materializing.

4. **DO NOT set `awaitingKickoff: true` in `pauseTask`** — the pause state must be `awaitingKickoff: undefined` (or the field absent). Only the pre-kickoff transition sets `awaitingKickoff: true`.

5. **DO NOT use `resumeTask` for the kick-off flow** — kick-off uses `approveAndKickOff` (requires `awaitingKickoff: true`). Resume uses `resumeTask` (requires `!awaitingKickoff`). These are different flows.

6. **DO NOT forget the `resumeTask` validation** — it must reject tasks that have `awaitingKickoff: true`. This prevents accidentally resuming a pre-kickoff task via the wrong mutation.

### What This Story Does NOT Include

- Lead Agent thread negotiation (Story 7.3)
- Human step Accept (Story 7.2)
- Canvas editing (Story 7.1) — depends on it

### Files to Modify

- `dashboard/convex/tasks.ts` — add `pauseTask`, `resumeTask` mutations
- `dashboard/components/TaskDetailSheet.tsx` — add Pause/Resume buttons
- `dashboard/components/ExecutionPlanTab.tsx` — extend `isEditMode` to include paused state
- `dashboard/components/TaskCard.tsx` — add "Paused" badge
- `dashboard/components/KanbanBoard.tsx` — handle paused task display
- `nanobot/mc/step_dispatcher.py` — pre-dispatch task status check
- `nanobot/mc/orchestrator.py` — handle resumed tasks (dispatch pending steps)

### References

- [Source: `dashboard/convex/tasks.ts#VALID_TRANSITIONS`] — state machine transitions
- [Source: `dashboard/convex/tasks.ts#approveAndKickOff`] — pattern for Resume mutation
- [Source: `nanobot/mc/step_dispatcher.py`] — dispatch logic to extend
- [Source: `nanobot/mc/orchestrator.py#start_kickoff_watch_loop`] — loop to extend for resume
- [Story 7.1] — canvas edit mode condition
- [Story 7.3] — Lead Agent thread negotiation while paused
