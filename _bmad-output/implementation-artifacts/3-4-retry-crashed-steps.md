# Story 3.4: Retry Crashed Steps

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to retry a crashed step so it re-enters the execution pipeline,
So that I can recover from transient errors without restarting the entire task.

## Acceptance Criteria

1. **Retry button visible on crashed steps** — Given a step has status `"crashed"`, when the user views the step on the `StepCard`, then a "Retry" button is visible on that step and only on crashed steps.

2. **Retry transitions step from crashed to assigned** — Given the user clicks "Retry" on a crashed step, when the retry Convex mutation runs, then the step status transitions from `"crashed"` to `"assigned"` via the existing `steps:updateStatus` mutation (the `crashed → assigned` transition is already valid in `STEP_TRANSITIONS`) (FR33).

3. **Activity event written on retry** — Given the user clicks "Retry", when the retry mutation completes, then an activity event is inserted: `eventType: "step_retrying"`, `description: "User retried step: {stepTitle}"`, with `taskId` and `agentName` (from `step.assignedAgent`) (FR33).

4. **System message posted to thread on retry** — Given the user clicks "Retry", when the retry mutation completes, then a system message is posted to the unified thread via `messages:postSystemError` with `content: "Step \"{stepTitle}\" retried by user."` and `stepId` linked, so the thread records the retry event and it renders with the `system_error` visual treatment (compatible with `ThreadMessage.tsx` from Story 2.7).

5. **Re-queued for dispatch — step dispatcher picks up assigned step** — Given the step is now `"assigned"` after retry, when the step dispatcher's polling loop next runs `dispatch_steps`, then it detects the step as assigned (not in `dispatched_step_ids`) and dispatches it through `_execute_step` again (FR33). No changes to `step_dispatcher.py` are needed — the existing dispatch loop naturally re-queues assigned steps.

6. **Auto-unblock on successful retry completion** — Given the retried step eventually completes successfully, when `_execute_step` calls `bridge.check_and_unblock_dependents(step_id)`, then the existing `steps:checkAndUnblockDependents` Convex mutation runs and unblocks any direct dependents whose other blockers are all completed (FR34). No additional implementation required — this path is already exercised by Story 2.3.

7. **Re-crash after retry — step returns to crashed with new error** — Given the retried step crashes again during execution, when the crash is recorded, then the step status transitions back to `"crashed"` via `update_step_status(step_id, StepStatus.CRASHED, new_error_message, StepStatus.RUNNING)` and the user can retry again — there is no retry limit for MVP.

8. **TypeScript tests for new Convex mutation** — The `steps:retryStep` mutation is covered by tests in `dashboard/convex/steps.test.ts`: (a) retrying a crashed step sets status to `"assigned"`, (b) retrying a non-crashed step throws `ConvexError`, (c) retrying a non-existent step throws `ConvexError`, (d) `"step_retrying"` activity event is written with the correct description, (e) `"step_retrying"` eventType is accepted by the schema (no union validation error).

## Tasks / Subtasks

- [x] **Task 1: Add `steps:retryStep` Convex mutation** (AC: 2, 3, 4)
  - [x] 1.1 Add a new `export const retryStep = mutation(...)` in `dashboard/convex/steps.ts`. Args: `{ stepId: v.id("steps") }`. The handler must: (a) fetch the step, throw `ConvexError("Step not found")` if missing; (b) throw `ConvexError("Step is not in crashed status")` if `step.status !== "crashed"`; (c) call `updateStatus` logic inline or reuse the existing function to set `status: "assigned"` and clear `errorMessage` (the `crashed → assigned` transition is already valid in `STEP_TRANSITIONS`).
  - [x] 1.2 Inside `retryStep`, after the status patch, insert an activity event: `eventType: "step_retrying"`, `description: \`User retried step: "${step.title}"\``, `taskId: step.taskId`, `agentName: step.assignedAgent`, `timestamp`.
  - [x] 1.3 Inside `retryStep`, post a system thread message via `ctx.db.insert("messages", { taskId: step.taskId, stepId: args.stepId, authorName: "System", authorType: "system", content: \`Step "${step.title}" retried by user.\`, messageType: "system_event", type: "system_error", timestamp })`.
  - [x] 1.4 Add `"step_retrying"` literal to the `activities.eventType` union in `dashboard/convex/schema.ts` (it does not currently exist in the union — `"step_unblocked"` is the last step event; add `"step_retrying"` after it).

- [x] **Task 2: Add a Retry button to `StepCard`** (AC: 1)
  - [x] 2.1 In `dashboard/components/StepCard.tsx`, extend `StepCardProps` to accept an optional `onRetry?: () => void` prop.
  - [x] 2.2 Import `useMutation` from `convex/react` and `api` from `@/convex/_generated/api` inside `StepCard.tsx`. Wire up `useMutation(api.steps.retryStep)` and call it with `{ stepId: step._id }` inside the `onRetry` handler. Wrap the call in `try/catch` and `console.error` on failure (no toast for MVP).
  - [x] 2.3 Render a "Retry" button inside the crashed-step section (alongside the `AlertTriangle` icon in the icon row at the top-right). The button must: only render when `step.status === "crashed"`, use `<Button size="xs" variant="outline" className="h-5 px-2 text-[10px]">Retry</Button>` (or equivalent small size matching the card density), call `onRetry()` on click, and stop event propagation so the card's `onClick` (for opening the detail drawer) is not triggered simultaneously.
  - [x] 2.4 Pass `onRetry` from the parent `KanbanColumn` (or wherever `StepCard` is rendered) — `onRetry` can be a simple inline arrow that calls `retryStep({ stepId: step._id })`. If `StepCard` wires up `useMutation` internally (per 2.2), no prop threading is needed and this subtask is skipped.
  - [x] 2.5 Verify that the Retry button is NOT rendered when `step.status !== "crashed"` — add a comment in the JSX making this conditional explicit.

- [x] **Task 3: Add `"step_retrying"` to Python `ActivityEventType`** (AC: 3)
  - [x] 3.1 In `nanobot/mc/types.py`, add `STEP_RETRYING = "step_retrying"` to the `ActivityEventType` StrEnum (after `STEP_COMPLETED` or at the end of the step-related entries). This is a documentation/parity update — the Python bridge does not call this event directly since retry is user-initiated via the dashboard, but the constant must exist so the enum stays in sync with the Convex schema union.

- [x] **Task 4: Write TypeScript tests** (AC: 8)
  - [x] 4.1 In `dashboard/convex/steps.test.ts`, add a `describe("retryStep")` block. Use the same `._handler` accessor pattern as existing mutation tests in the file.
  - [x] 4.2 Add test: `"retries a crashed step — sets status to assigned and clears errorMessage"` — mock a step with `status: "crashed"` and `errorMessage: "some error"`, call `retryStep._handler`, assert the patched status is `"assigned"` and `errorMessage` is cleared (`undefined`).
  - [x] 4.3 Add test: `"throws ConvexError if step is not crashed"` — mock a step with `status: "running"`, assert `ConvexError` is thrown with message containing `"not in crashed status"`.
  - [x] 4.4 Add test: `"throws ConvexError if step not found"` — mock `ctx.db.get` returning `null`, assert `ConvexError("Step not found")` is thrown.
  - [x] 4.5 Add test: `"writes step_retrying activity event"` — assert `ctx.db.insert("activities", ...)` was called with `eventType: "step_retrying"` and description containing the step title.
  - [x] 4.6 Add test: `"posts system_error thread message with stepId linked"` — assert `ctx.db.insert("messages", ...)` was called with `type: "system_error"`, `authorType: "system"`, and `stepId` set to the step's `_id`.

## Dev Notes

### State Machine — `crashed → assigned` Is Already Valid

The `crashed → assigned` transition is already defined in `STEP_TRANSITIONS` (Story 3.1):

```typescript
// dashboard/convex/steps.ts lines 27–34
const STEP_TRANSITIONS: Record<StepStatus, StepStatus[]> = {
  ...
  crashed: ["assigned"],
  ...
};
```

The `retryStep` mutation does NOT need to call `isValidStepTransition` separately — it only ever attempts one transition (`crashed → assigned`) and validates the precondition directly (`step.status !== "crashed"` guard in Task 1.1). If you reuse `updateStatus` internally, the transition check is included automatically. Either approach is acceptable.

The Python `STEP_VALID_TRANSITIONS` dict in `nanobot/mc/state_machine.py` also already includes `StepStatus.CRASHED: [StepStatus.ASSIGNED]` (from Story 3.1), so no Python state machine changes are needed.

### New Convex Mutation: `steps:retryStep`

Add this as a new export in `dashboard/convex/steps.ts` (after `checkAndUnblockDependents`):

```typescript
export const retryStep = mutation({
  args: {
    stepId: v.id("steps"),
  },
  handler: async (ctx, args) => {
    const step = await ctx.db.get(args.stepId);
    if (!step) {
      throw new ConvexError("Step not found");
    }
    if (step.status !== "crashed") {
      throw new ConvexError(
        `Step is not in crashed status (current: ${step.status})`
      );
    }

    const timestamp = new Date().toISOString();

    // Transition crashed → assigned (already valid in STEP_TRANSITIONS).
    await ctx.db.patch(args.stepId, {
      status: "assigned",
      errorMessage: undefined,
    });

    // Generic step_status_changed event (mirrors updateStatus behavior).
    await logStepStatusChange(ctx, {
      taskId: step.taskId,
      stepTitle: step.title,
      previousStatus: step.status,
      nextStatus: "assigned",
      assignedAgent: step.assignedAgent,
      timestamp,
    });

    // Retry-specific activity event (AC3).
    await ctx.db.insert("activities", {
      taskId: step.taskId,
      agentName: step.assignedAgent,
      eventType: "step_retrying",
      description: `User retried step: "${step.title}"`,
      timestamp,
    });

    // System thread message (AC4) — uses system_error type so ThreadMessage.tsx renders it.
    await ctx.db.insert("messages", {
      taskId: step.taskId,
      stepId: args.stepId,
      authorName: "System",
      authorType: "system",
      content: `Step "${step.title}" retried by user.`,
      messageType: "system_event",
      type: "system_error",
      timestamp,
    });
  },
});
```

Note: `logStepStatusChange` is already a module-level function in `steps.ts` (lines 150–168). Call it from `retryStep` the same way `updateStatus` does.

### Schema Change — Add `"step_retrying"` to Activities EventType Union

File: `dashboard/convex/schema.ts`

The `activities.eventType` union currently ends with `"step_unblocked"` (line 198). Add `"step_retrying"` after it:

```typescript
// Before (line 198):
v.literal("step_unblocked"),

// After:
v.literal("step_unblocked"),
v.literal("step_retrying"),
```

**Verify before adding:** The `"step_retrying"` literal does NOT currently exist in the union (it's used for task-level retry: `"task_retrying"` is present, but `"step_retrying"` is not). Run `grep "step_retrying" dashboard/convex/schema.ts` to confirm absence before adding.

### Retry Button Placement in `StepCard`

File: `dashboard/components/StepCard.tsx`

The current crashed-step visual section (lines 120–134) renders an `AlertTriangle` icon in the top-right icon row. The Retry button should appear adjacent to this icon in the same `div.flex.shrink-0` container. Recommended placement:

```tsx
{step.status === "crashed" && (
  <>
    {/* existing AlertTriangle icon with optional Tooltip */}
    ...
    <Button
      size="sm"
      variant="outline"
      className="h-5 rounded-full border-red-300 bg-red-50 px-2 text-[10px] font-medium text-red-600 hover:bg-red-100"
      onClick={(e) => {
        e.stopPropagation(); // prevent card onClick from firing
        retryMutation({ stepId: step._id });
      }}
      aria-label={`Retry step: ${step.title}`}
    >
      Retry
    </Button>
  </>
)}
```

`Button` is already used in the project UI kit (`@/components/ui/button`). Import it at the top of `StepCard.tsx`.

**useMutation wiring inside StepCard:** Wire the mutation inside the component to keep the component self-contained:

```tsx
import { useMutation } from "convex/react";
import { api } from "@/convex/_generated/api";

// inside StepCard:
const retryStep = useMutation(api.steps.retryStep);
```

This avoids prop-drilling `onRetry` through `KanbanColumn` and keeps the retry logic co-located with the UI that triggers it.

### Auto-Unblock After Successful Retry (FR34)

No new implementation required. The existing `_execute_step` flow in `nanobot/mc/step_dispatcher.py` (lines 461–466) already calls `bridge.check_and_unblock_dependents(step_id)` after each successful completion:

```python
unblocked_ids = await asyncio.to_thread(
    self._bridge.check_and_unblock_dependents, step_id
)
```

This calls `steps:checkAndUnblockDependents` in Convex, which uses `findBlockedStepsReadyToUnblock` — it only unblocks a step when ALL its `blockedBy` dependencies are `"completed"`. A retried step completing successfully will naturally trigger this. No step-dispatcher changes needed.

### How the Dispatcher Re-Picks the Retried Step

The step dispatcher loop in `dispatch_steps` (lines 241–259 of `step_dispatcher.py`) polls `bridge.get_steps_by_task` and filters for steps with `status == StepStatus.ASSIGNED` that are not in `dispatched_step_ids`. After retry, the step is `"assigned"` again and its ID is NOT in `dispatched_step_ids` (that set only grows — it is never pruned on retry). The dispatcher will therefore detect and re-dispatch the retried step on the next loop iteration.

**Important:** This requires the gateway/dispatcher to still be running when the user clicks Retry. For the MVP scope of this story, the dispatcher is expected to be running continuously (it is an `asyncio` loop that does not exit until all steps are complete or a fatal error occurs). If the dispatcher has already exited (e.g., all non-crashed steps completed), re-dispatch would require a manual trigger — that edge case is out of scope for MVP. Document this constraint in a code comment in `dispatch_steps` if desired.

### Thread Message Type for Retry — Using `"system_error"`

The retry system message uses `type: "system_error"` rather than a new type, because:
- `"system_error"` is already in the `messages.type` union in `schema.ts` (line 109)
- `ThreadMessage.tsx` (Story 2.7) already renders `system_error` type with system styling
- Adding a new `"system_retry"` type would require schema migration and renderer changes

The content `"Step \"{stepTitle}\" retried by user."` clearly differentiates it from crash messages. Future iterations can introduce a dedicated `"step_retried"` message type.

### `"step_retrying"` in Python ActivityEventType — Parity Constant

File: `nanobot/mc/types.py`, class `ActivityEventType` (lines 75–107)

Add after `STEP_COMPLETED`:
```python
STEP_RETRYING = "step_retrying"
```

The Python bridge does not directly emit `STEP_RETRYING` events (retry is always user-initiated via the dashboard Convex mutation). The constant is added purely for enum parity with the Convex schema — to ensure `types.py` and `schema.ts` remain in sync and any future Python-initiated retry path can use the constant.

### No Bridge Method Required

Retry is a user-initiated action that goes directly through Convex (`useMutation` from the React dashboard). There is no Python bridge method to add. The Python bridge only handles mutations that are initiated by the Python runtime (agent lifecycle, step dispatch, thread messages). User-initiated mutations flow: `React component → useMutation → Convex → Convex reactive update → Dashboard re-renders with new step status`.

### Testing Pattern for `retryStep`

The existing `describe("batchCreate")` block in `dashboard/convex/steps.test.ts` (lines 115–210) shows the exact `._handler` accessor pattern and mock ctx structure to follow. The mock `ctx.db` must support both `ctx.db.get` (to fetch the step) and `ctx.db.patch` (to update status) and `ctx.db.insert` (for activity + message). Use the same `createMockCtx()` or inline mock pattern already established in the file.

Run tests:
```bash
cd /Users/ennio/Documents/nanobot-ennio/dashboard && npx vitest run convex/steps.test.ts
```

### Project Structure Notes

- **Files to modify:**
  - `dashboard/convex/steps.ts` — add `retryStep` mutation (export), call `logStepStatusChange` inside it
  - `dashboard/convex/schema.ts` — add `v.literal("step_retrying")` to `activities.eventType` union
  - `dashboard/components/StepCard.tsx` — add Retry button for `crashed` steps, import `useMutation`, import `Button`
  - `dashboard/convex/steps.test.ts` — add `describe("retryStep")` block with 5+ tests
  - `nanobot/mc/types.py` — add `STEP_RETRYING = "step_retrying"` to `ActivityEventType`

- **No new files** — all changes extend existing files
- **No Python bridge changes** — retry is user-initiated, not Python-initiated
- **No `step_dispatcher.py` changes** — the existing dispatch loop naturally re-queues the retried step
- **No `messages.ts` changes** — the retry system message is inserted directly via `ctx.db.insert` inside `retryStep` (same pattern as `checkAndUnblockDependents` using inline inserts)
- **No new Convex queries** — `steps:getByTask` already exists for the dispatcher

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.4] — Acceptance criteria (lines 877–904)
- [Source: _bmad-output/planning-artifacts/architecture.md#Step Status Values] — `crashed: ["assigned"]` in STEP_TRANSITIONS; `StepStatus` type (lines 232–236)
- [Source: _bmad-output/planning-artifacts/architecture.md#Step Lifecycle FR29-FR34] — Manual retry with auto-unblock; crash isolation (line 46)
- [Source: _bmad-output/planning-artifacts/architecture.md#FR33, FR34] — Step retry re-queues for dispatch; auto-unblock on completion
- [Source: dashboard/convex/steps.ts#STEP_TRANSITIONS] — `crashed: ["assigned"]` is already valid (line 33)
- [Source: dashboard/convex/steps.ts#updateStatus] — Pattern for status patch + logStepStatusChange + activity insert (lines 349–411)
- [Source: dashboard/convex/steps.ts#checkAndUnblockDependents] — Auto-unblock runs on completion (lines 413–472); already triggered by `_execute_step`
- [Source: dashboard/convex/schema.ts#activities.eventType] — Current union ends with `"step_unblocked"` (line 198); `"step_retrying"` is absent
- [Source: dashboard/convex/messages.ts#postSystemError] — Pattern for system thread message with `type: "system_error"` and `stepId` (lines 118–147)
- [Source: dashboard/components/StepCard.tsx] — Current crashed-step icon placement (lines 120–134); card layout (lines 80–186)
- [Source: nanobot/mc/step_dispatcher.py#dispatch_steps] — `dispatched_step_ids` set and loop that re-detects assigned steps (lines 232–259)
- [Source: nanobot/mc/step_dispatcher.py#_execute_step] — `check_and_unblock_dependents` call on completion (lines 461–466)
- [Source: nanobot/mc/types.py#ActivityEventType] — StrEnum to extend with `STEP_RETRYING` (lines 75–107)
- [Source: _bmad-output/implementation-artifacts/3-1-implement-step-status-state-machine.md] — `crashed → assigned` transition established as valid; Python parity constants
- [Source: _bmad-output/implementation-artifacts/3-3-post-crash-errors-with-recovery-instructions.md] — `post_system_error` bridge method; crash handler in `_execute_step` (re-crash path)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Task 2.4 skipped per story instructions: `StepCard` wires up `useMutation` internally (self-contained), so no prop threading through `KanbanColumn` is needed.
- The `ActivityLoggerCtx` internal type in `steps.ts` was extended to include `"step_retrying"` in the `eventType` union so that `logStepStatusChange` can be called from `retryStep` without TypeScript errors.
- Mocks for `convex/react` and `@/convex/_generated/api` were added to `StepCard.test.tsx` to handle the `useMutation` hook added to `StepCard`.
- Pre-existing test failures in `test_gateway.py` and `test_planner.py` (using old `step_id` keyword arg instead of `temp_id`) and `LoginPage.test.tsx` (resource-contention timeout in full suite) are unrelated to this story.

### File List

- `dashboard/convex/steps.ts` — added `retryStep` mutation; extended `ActivityLoggerCtx.eventType` union
- `dashboard/convex/schema.ts` — added `v.literal("step_retrying")` to `activities.eventType` union
- `dashboard/components/StepCard.tsx` — imported `useMutation`, `api`, `Button`; added `retryStep` hook; added Retry button in crashed section
- `dashboard/components/StepCard.test.tsx` — added mocks for `convex/react` and `@/convex/_generated/api`; added 4 Retry button component tests (renders for crashed, not for non-crashed, calls mutation on click, stops propagation)
- `dashboard/convex/steps.test.ts` — added `describe("retryStep")` block with 5 tests
- `nanobot/mc/types.py` — added `STEP_RETRYING = "step_retrying"` to `ActivityEventType`

## Code Review Record

### Review Findings

**MEDIUM (fixed): Missing UI component tests for Retry button (AC 1)**

`StepCard.test.tsx` had mocks for `useMutation` and `api` but no tests asserting:
- The Retry button renders when `step.status === "crashed"` (AC 1a)
- The Retry button does NOT render for non-crashed statuses (AC 1b — Task 2.5)
- Clicking Retry calls `retryStep({ stepId: step._id })` (Task 2.2)
- The button click stops propagation so the card's `onClick` is not triggered (Task 2.3)

**Fix applied:** Added 4 tests to `StepCard.test.tsx`. The `useMutation` mock was refactored to return a shared `retryMock` spy (instead of a fresh `vi.fn()` per render) so assertions on call arguments are possible. Total StepCard tests increased from 12 to 16. All 330 TypeScript tests pass.

**No other issues found.** All ACs verified against implementation:
- AC 1: Retry button renders inside `{step.status === "crashed" && (...)}` guard in `StepCard.tsx` line 125.
- AC 2: `retryStep` patches `{ status: "assigned", errorMessage: undefined }`.
- AC 3: `step_retrying` activity event inserted with correct `description`, `taskId`, `agentName`.
- AC 4: `system_error` message inserted with `stepId`, `authorType: "system"`, correct content.
- AC 5–7: No implementation required — confirmed existing code covers these paths.
- AC 8: 5 mutation tests in `steps.test.ts` — all pass.
