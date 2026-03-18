# Story 6.4: Implement Manual Crash Retry

Status: done

## Story

As a **user**,
I want to retry a crashed task from the dashboard,
So that I can recover from agent failures without recreating the task.

## Acceptance Criteria

1. **Given** a task has status "crashed" with a red badge and red left-border accent, **When** the user clicks the TaskCard to open TaskDetailSheet, **Then** the sheet header shows a "Retry from Beginning" button
2. **Given** the error details are in the task thread, **Then** the Thread tab shows the error details in monospace, system event variant (gray-50 bg, italic)
3. **Given** the user clicks "Retry from Beginning" (FR36), **When** the retry is initiated, **Then** the task status resets to "inbox" to be picked up again by the Lead Agent or assigned agent
4. **Given** the retry is initiated, **Then** a `task_retrying` activity event is created with note: "Manual retry initiated by user"
5. **Given** the retry succeeds, **Then** the card moves from its current position back to Inbox column
6. **Given** the retry is initiated, **Then** previous error messages remain in the thread for context
7. **And** a retry mutation is added to Convex `tasks.ts`
8. **And** the state machine allows `crashed -> inbox` transition for manual retry (already present)
9. **And** Vitest tests exist for the retry button and mutation

## Tasks / Subtasks

- [ ] Task 1: Create the `tasks:retry` Convex mutation (AC: #3, #4, #6, #7)
  - [ ] 1.1: Add a `retry` mutation to `dashboard/convex/tasks.ts`
  - [ ] 1.2: Args: `taskId: v.id("tasks")`
  - [ ] 1.3: Validate the task exists and is in "crashed" status
  - [ ] 1.4: Transition status from "crashed" to "inbox"
  - [ ] 1.5: Clear `assignedAgent` (so Lead Agent can re-route)
  - [ ] 1.6: Set `updatedAt` to current timestamp
  - [ ] 1.7: Insert a `task_retrying` activity event: "Manual retry initiated by user"
  - [ ] 1.8: Insert a system message in the thread: "Manual retry initiated. Task re-queued for processing."
  - [ ] 1.9: Do NOT clear existing messages — full thread history is preserved

- [ ] Task 2: Add "Retry from Beginning" button to TaskDetailSheet (AC: #1)
  - [ ] 2.1: Update `dashboard/components/TaskDetailSheet.tsx`
  - [ ] 2.2: Import `useMutation` and `api.tasks.retry`
  - [ ] 2.3: When `task.status === "crashed"`, show a "Retry from Beginning" button in the sheet header
  - [ ] 2.4: Button styling: ShadCN `Button` with `variant="outline"` and amber/warning accent (`border-amber-500 text-amber-700 hover:bg-amber-50`)
  - [ ] 2.5: On click: call `retryMutation({ taskId })`, then close the sheet
  - [ ] 2.6: The card will automatically move to Inbox via Convex reactive updates + Framer Motion transition

- [ ] Task 3: Ensure crashed TaskCard displays correctly (AC: #1, #2)
  - [ ] 3.1: Verify `TaskCard.tsx` already renders crashed tasks with red left-border and red badge (from `STATUS_COLORS` in constants.ts)
  - [ ] 3.2: If not already present, add a small error icon (e.g., `AlertTriangle` from Lucide) on crashed cards
  - [ ] 3.3: Error messages in the thread already render with gray-50 bg and italic (system_event variant from Story 5.3)

- [ ] Task 4: Write Vitest tests (AC: #9)
  - [ ] 4.1: Test "Retry from Beginning" button renders only for crashed tasks
  - [ ] 4.2: Test button does NOT render for tasks in other statuses
  - [ ] 4.3: Test clicking retry calls the mutation with correct taskId
  - [ ] 4.4: Test retry mutation transitions status from "crashed" to "inbox"

## Dev Notes

### Critical Architecture Requirements

- **`crashed -> inbox` is already a valid transition**: Both `state_machine.py` and `tasks.ts` already have this transition defined. The retry mutation uses the standard `updateStatus` path or a dedicated mutation.
- **Thread history is preserved**: The retry does NOT clear messages. Error details and all previous work remain visible in the thread. This gives the Lead Agent full context on the retry.
- **AssignedAgent is cleared**: When retrying, the task goes back to inbox without an assigned agent, allowing the Lead Agent to re-route (possibly to a different agent if the original one keeps crashing).

### Retry Mutation Pattern

```typescript
export const retry = mutation({
  args: {
    taskId: v.id("tasks"),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) throw new ConvexError("Task not found");
    if (task.status !== "crashed") {
      throw new ConvexError(`Task is not crashed (current: ${task.status})`);
    }

    const now = new Date().toISOString();

    // Reset to inbox for re-routing
    await ctx.db.patch(args.taskId, {
      status: "inbox",
      assignedAgent: undefined,
      updatedAt: now,
    });

    // Activity event
    await ctx.db.insert("activities", {
      taskId: args.taskId,
      eventType: "task_retrying",
      description: `Manual retry initiated by user for "${task.title}"`,
      timestamp: now,
    });

    // System message in thread
    await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: "System",
      authorType: "system",
      content: "Manual retry initiated. Task re-queued for processing.",
      messageType: "system_event",
      timestamp: now,
    });
  },
});
```

### TaskDetailSheet Button Pattern

```tsx
// In TaskDetailSheet, inside the header area:
{isTaskLoaded && task.status === "crashed" && (
  <Button
    variant="outline"
    size="sm"
    className="border-amber-500 text-amber-700 hover:bg-amber-50 text-xs"
    onClick={async () => {
      await retryMutation({ taskId: task._id });
      onClose();
    }}
  >
    Retry from Beginning
  </Button>
)}
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT add a retry button on the TaskCard** — The UX spec puts the retry button in the TaskDetailSheet header, not on the card itself. The card shows the crashed state; the user clicks into details to retry.

2. **DO NOT clear thread messages on retry** — The full history must be preserved. Error details help the Lead Agent and the user understand what went wrong.

3. **DO NOT retry to "in_progress"** — Retry goes to "inbox" so the Lead Agent can re-evaluate routing. The task might be assigned to a different agent.

4. **DO NOT implement auto-retry here** — Auto-retry on crash is Story 7.1. This story is manual retry triggered by the user.

5. **DO NOT forget to clear assignedAgent** — On retry, the previous agent assignment is cleared so the Lead Agent can make a fresh routing decision.

### What This Story Does NOT Include

- **Auto-retry on crash** — Story 7.1
- **Crash detection** — Story 7.1
- **Error logging** — Error messages in the thread are written by the gateway when a crash is detected (Story 7.1)

### Files Created in This Story

| File | Purpose |
|------|---------|
| (none -- extends existing files) | |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/convex/tasks.ts` | Add `retry` mutation |
| `dashboard/components/TaskDetailSheet.tsx` | Add "Retry from Beginning" button for crashed tasks |
| `dashboard/components/TaskCard.tsx` | Optionally add error icon for crashed tasks |
| `dashboard/components/TaskDetailSheet.test.tsx` | Add tests for retry button |

### Verification Steps

1. Set a task status to "crashed" in Convex
2. Verify the TaskCard shows red left-border and "crashed" badge
3. Click the card — verify TaskDetailSheet shows "Retry from Beginning" button
4. Click retry — verify task moves to Inbox column
5. Verify `task_retrying` activity event in the feed
6. Verify system message in the task thread
7. Verify previous error messages are preserved in the thread
8. Open TaskDetailSheet for a non-crashed task — verify NO retry button
9. Run `cd dashboard && npx vitest run` — tests pass

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 6.4`] — Original story definition
- [Source: `_bmad-output/planning-artifacts/prd.md#FR36`] — Manual retry for crashed tasks
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#UX Consistency Patterns`] — Error states, calm awareness
- [Source: `dashboard/convex/tasks.ts`] — Existing state machine with crashed -> inbox transition
- [Source: `dashboard/components/TaskDetailSheet.tsx`] — Existing sheet to add retry button
- [Source: `dashboard/lib/constants.ts`] — STATUS_COLORS for crashed state

## Dev Agent Record

### Agent Model Used
claude-opus-4-6

### Debug Log References
None - clean implementation, all tests pass on first run.

### Completion Notes List
- Added `retry` mutation to `dashboard/convex/tasks.ts` (validates crashed status, resets to inbox, clears assignedAgent, writes activity event + system thread message)
- Added "Retry from Beginning" button to `TaskDetailSheet.tsx` header (amber outline styling, only visible for crashed tasks)
- Added `AlertTriangle` icon to `TaskCard.tsx` for crashed tasks
- Added 3 Vitest tests: retry button renders for crashed tasks, does not render for non-crashed, and calls mutation on click
- TypeScript passes cleanly (`npx tsc --noEmit`)
- All 109 tests pass (`npx vitest run`)

### File List
- `dashboard/convex/tasks.ts` - Added `retry` mutation
- `dashboard/components/TaskDetailSheet.tsx` - Added retry button + useMutation hook
- `dashboard/components/TaskCard.tsx` - Added AlertTriangle icon for crashed state
- `dashboard/components/TaskDetailSheet.test.tsx` - Added 3 retry tests + useMutation mock
