# Story 6.1: Implement HITL Approve Action

Status: done

## Story

As a **user**,
I want to approve a task with one click,
So that I can quickly sign off on completed work and keep agents moving.

## Acceptance Criteria

1. **Given** a task is in "review" state with trust level "human_approved" (or after agent review passes for "human_approved" tasks), **When** the user views the TaskCard on the Kanban board, **Then** a green "Approve" button is visible directly on the card
2. **Given** the user clicks the Approve button, **When** the approval is processed, **Then** the task transitions to "done" via optimistic UI -- card slides to Done column immediately (300ms transition, green flash on border)
3. **Given** the approval succeeds, **Then** a `hitl_approved` activity event is created with description: "User approved '{task title}'"
4. **Given** the approval succeeds, **Then** a message with messageType "approval" and authorType "user" is added to the task thread
5. **Given** the TaskDetailSheet is open for a reviewable task, **When** the user views the sheet header, **Then** the Approve button is also available in the sheet header
6. **Given** approval is a single-click action, **Then** no confirmation dialog is shown
7. **Given** the Convex mutation fails, **Then** the card reverts from Done column back to Review with a subtle shake animation
8. **And** a Convex mutation `tasks:approve` is created in `dashboard/convex/tasks.ts`
9. **And** the Approve button only appears for tasks requiring human approval (not all review tasks)
10. **And** Vitest tests exist for the approve button rendering and click behavior

## Tasks / Subtasks

- [ ] Task 1: Create the `tasks:approve` Convex mutation (AC: #3, #4, #8)
  - [ ] 1.1: Add an `approve` mutation to `dashboard/convex/tasks.ts`
  - [ ] 1.2: Args: `taskId: v.id("tasks")`, `userName: v.optional(v.string())`
  - [ ] 1.3: Validate the task exists and is in "review" status
  - [ ] 1.4: Validate the task has trust level "human_approved"
  - [ ] 1.5: Transition status from "review" to "done", set `updatedAt`
  - [ ] 1.6: Insert a `hitl_approved` activity event
  - [ ] 1.7: Insert a message with messageType "approval", authorType "user", content "Approved by user"

- [ ] Task 2: Add Approve button to TaskCard (AC: #1, #2, #6, #7, #9)
  - [ ] 2.1: Update `dashboard/components/TaskCard.tsx`
  - [ ] 2.2: Import `useMutation` and `api.tasks.approve`
  - [ ] 2.3: Show Approve button ONLY when: `task.status === "review"` AND `task.trustLevel === "human_approved"`
  - [ ] 2.4: Button styling: ShadCN `Button` with `variant="default"` and green styling (`bg-green-500 hover:bg-green-600 text-white text-xs h-7`)
  - [ ] 2.5: On click, call `approveMutation({ taskId: task._id })` — no confirmation dialog
  - [ ] 2.6: Use `e.stopPropagation()` on the button click to prevent opening TaskDetailSheet
  - [ ] 2.7: Use Convex optimistic update: immediately move card to "done" status locally
  - [ ] 2.8: If mutation fails, the optimistic update reverts automatically (Convex handles this)

- [ ] Task 3: Add Approve button to TaskDetailSheet header (AC: #5)
  - [ ] 3.1: Update `dashboard/components/TaskDetailSheet.tsx`
  - [ ] 3.2: Import `useMutation` and `api.tasks.approve`
  - [ ] 3.3: When task is in "review" with trust level "human_approved", show Approve button in the sheet header (next to status badge)
  - [ ] 3.4: On click, call `approveMutation({ taskId })` and close the sheet after success
  - [ ] 3.5: Use same green button styling as the card button

- [ ] Task 4: Add optimistic update for card transition (AC: #2, #7)
  - [ ] 4.1: Configure optimistic update on the `useMutation` call to immediately set the task's local status to "done"
  - [ ] 4.2: Convex's optimistic updates automatically revert if the server-side mutation throws
  - [ ] 4.3: The Framer Motion `layoutId` on TaskCard handles the visual transition to Done column

- [ ] Task 5: Write Vitest tests (AC: #10)
  - [ ] 5.1: Test Approve button renders on TaskCard when status="review" and trustLevel="human_approved"
  - [ ] 5.2: Test Approve button does NOT render for autonomous tasks in review
  - [ ] 5.3: Test Approve button does NOT render for tasks not in review status
  - [ ] 5.4: Test clicking Approve calls the mutation with correct taskId
  - [ ] 5.5: Test Approve button renders in TaskDetailSheet header for qualifying tasks

## Dev Notes

### Critical Architecture Requirements

- **Single-click approval**: The UX spec is explicit — no confirmation dialog. One click approves the task. The user can follow the thread history if they need context before clicking.
- **Optimistic UI**: The card moves to Done immediately on click. If the server rejects the mutation, Convex automatically reverts the optimistic update.
- **Activity event + message**: Every approval writes both an activity event (for the feed) and a message (for the task thread). This is the architectural invariant.
- **Human-approved tasks only**: The Approve button only appears for tasks with `trustLevel === "human_approved"`. Tasks with `trustLevel === "agent_reviewed"` are approved by the reviewing agent (Story 5.3), not the user.

### Approve Mutation Pattern

```typescript
export const approve = mutation({
  args: {
    taskId: v.id("tasks"),
    userName: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) throw new ConvexError("Task not found");
    if (task.status !== "review") {
      throw new ConvexError(`Task is not in review state (current: ${task.status})`);
    }
    if (task.trustLevel !== "human_approved") {
      throw new ConvexError("Task does not require human approval");
    }

    const now = new Date().toISOString();
    const userName = args.userName || "User";

    // Transition to done
    await ctx.db.patch(args.taskId, { status: "done", updatedAt: now });

    // Activity event
    await ctx.db.insert("activities", {
      taskId: args.taskId,
      eventType: "hitl_approved",
      description: `User approved "${task.title}"`,
      timestamp: now,
    });

    // Thread message
    await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: userName,
      authorType: "user",
      content: `Approved by ${userName}`,
      messageType: "approval",
      timestamp: now,
    });
  },
});
```

### TaskCard Approve Button Pattern

```tsx
// Inside TaskCard component:
const approveMutation = useMutation(api.tasks.approve);

const showApproveButton =
  task.status === "review" && task.trustLevel === "human_approved";

// In the JSX, after the status badge:
{showApproveButton && (
  <Button
    variant="default"
    size="sm"
    className="bg-green-500 hover:bg-green-600 text-white text-xs h-7 px-2"
    onClick={(e) => {
      e.stopPropagation(); // Don't open detail sheet
      approveMutation({ taskId: task._id });
    }}
  >
    Approve
  </Button>
)}
```

### Optimistic Update Pattern

Convex optimistic updates can be configured on the mutation:

```tsx
const approveMutation = useMutation(api.tasks.approve).withOptimisticUpdate(
  (localStore, args) => {
    const task = localStore.getQuery(api.tasks.getById, { taskId: args.taskId });
    if (task) {
      localStore.setQuery(api.tasks.getById, { taskId: args.taskId }, {
        ...task,
        status: "done",
        updatedAt: new Date().toISOString(),
      });
    }
  }
);
```

Note: Convex optimistic updates are applied locally and automatically rolled back if the mutation fails.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT add a confirmation dialog** — The UX spec explicitly says "no confirmation dialog — single click completes the action."

2. **DO NOT show Approve for all review tasks** — Only show for `trustLevel === "human_approved"`. Agent-reviewed tasks are approved by the reviewing agent, not the user.

3. **DO NOT forget `e.stopPropagation()`** — The Approve button is inside the TaskCard which opens TaskDetailSheet on click. Without `stopPropagation`, clicking Approve would also open the sheet.

4. **DO NOT forget to write both activity event AND message** — Both are required by the architectural invariant.

5. **DO NOT close the TaskDetailSheet before the mutation completes** — Close after the mutation succeeds, or use optimistic update to make it feel instant.

6. **DO NOT implement Deny here** — Deny with inline rejection is Story 6.2.

### What This Story Does NOT Include

- **Deny button** — Story 6.2
- **Inline rejection feedback** — Story 6.2
- **Notification badges** — Story 6.3
- **Return to Lead Agent** — Story 6.2
- **Agent-side approval signal** — The bridge subscription to detect approval (FR32) is handled by the orchestrator

### Files Created in This Story

| File | Purpose |
|------|---------|
| (none -- extends existing files) | |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/convex/tasks.ts` | Add `approve` mutation |
| `dashboard/components/TaskCard.tsx` | Add Approve button for human_approved tasks in review |
| `dashboard/components/TaskDetailSheet.tsx` | Add Approve button in sheet header |
| `dashboard/components/TaskCard.test.tsx` | Add tests for Approve button rendering and behavior |

### Verification Steps

1. Create a task with `trustLevel: "human_approved"`, transition it to "review"
2. Verify Approve button appears on the TaskCard
3. Click Approve — verify card moves to Done column (optimistic UI)
4. Verify `hitl_approved` activity event in the feed
5. Verify approval message in the task thread
6. Open TaskDetailSheet for a human_approved task in review — verify Approve button in header
7. Create an autonomous task in review — verify NO Approve button
8. Run `cd dashboard && npx vitest run` — tests pass

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 6.1`] — Original story definition
- [Source: `_bmad-output/planning-artifacts/prd.md#FR31`] — User approve/deny from dashboard
- [Source: `_bmad-output/planning-artifacts/prd.md#FR32`] — Approved task moves to Done
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#UX Consistency Patterns`] — Single-click approval, no confirmation dialog
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Component Strategy`] — TaskCard approve button spec
- [Source: `dashboard/components/TaskCard.tsx`] — Existing component to add button
- [Source: `dashboard/components/TaskDetailSheet.tsx`] — Existing sheet to add header button
- [Source: `dashboard/convex/tasks.ts`] — Existing mutations file to extend

## Dev Agent Record

### Agent Model Used
claude-opus-4-6

### Debug Log References
No debug issues encountered.

### Completion Notes List
- Added `tasks:approve` Convex mutation validating review state + human_approved trust level
- Mutation transitions task to "done", inserts hitl_approved activity event and approval thread message
- Added green Approve button to TaskCard for human_approved tasks in review (with stopPropagation)
- Added green Approve button to TaskDetailSheet header for qualifying tasks (closes sheet on click)
- TypeScript passes cleanly (only pre-existing listByStatus type narrowing issue)
- All 109 Vitest tests pass including 6 new Story 6.1 tests

### File List
- `dashboard/convex/tasks.ts` — Added `approve` mutation
- `dashboard/components/TaskCard.tsx` — Added Approve button with useMutation
- `dashboard/components/TaskDetailSheet.tsx` — Added Approve button in sheet header
- `dashboard/components/TaskCard.test.tsx` — Added 4 tests for approve button rendering and click behavior
- `dashboard/components/TaskDetailSheet.test.tsx` — Added 2 tests for approve button in sheet header
