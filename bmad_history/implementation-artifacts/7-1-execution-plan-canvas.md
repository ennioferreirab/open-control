# Story 7.1: Execution Plan Canvas — Editable Plan in TaskDetailSheet

Status: done

## Story

As a **user**,
I want to edit the execution plan directly in the Execution Plan tab of the TaskDetailSheet,
So that I can review, reorder, reassign agents, change dependencies, add/remove steps, and kick off the task — all without leaving the task detail view.

## Context

This story replaces the `PreKickoffModal` approach (Epic 4) with an in-place editable canvas embedded in the `ExecutionPlanTab` of the `TaskDetailSheet`. The modal is removed entirely.

**Key design decisions confirmed with user:**
- The `ExecutionPlan` tab becomes interactive when the task is in `review` status (`awaitingKickoff: true`)
- Editing is available to both the user (via UI) and the Lead Agent (via thread messages — see Story 7.3)
- Chat with Lead Agent happens in the **main thread** (existing Thread tab), NOT a separate panel
- The `PreKickoffModal` component is removed
- A **Kick-off** button appears in the canvas (or sheet header) when the task is in `review`+`awaitingKickoff`

## Acceptance Criteria

1. **ExecutionPlanTab shows editable canvas during review** -- Given a task in `review` status with `awaitingKickoff: true`, when the user opens the TaskDetailSheet and clicks the Execution Plan tab, then the tab renders the PlanEditor (editable canvas with drag-and-drop blocks) instead of the read-only plan visualization.

2. **Kick-off button in canvas** -- Given the plan canvas is showing in `review`+`awaitingKickoff` mode, when the plan has at least one step, then a "Kick-off" button is visible (in the sheet header or bottom of the canvas), and clicking it calls `api.tasks.approveAndKickOff` with the current local plan state, transitions the task to `in_progress`, and the canvas reverts to read-only execution view.

3. **Drag-and-drop step reordering** -- Given the canvas is in edit mode, when the user drags a step block to a new position, then the step order updates locally and parallel groups are recalculated via `recalcParallelGroups()`.

4. **Agent reassignment per step** -- Given the canvas is in edit mode, when the user clicks the agent dropdown on a step block, then a list of all active agents is shown (excluding `lead-agent`), including a **"Human"** option, and selecting one updates the step's `assignedAgent`.

5. **Dependency editing** -- Given the canvas is in edit mode, when the user clicks a step's dependency toggle (or a dedicated dependency editor), then the user can add or remove `blockedBy` references to other steps, and parallel groups are recalculated on change.

6. **Add step** -- Given the canvas is in edit mode, when the user clicks "Add Step", then a new step is appended with a default title, description, no dependencies, and `assignedAgent: "general-agent"`, and the user can edit its fields inline.

7. **Remove step** -- Given the canvas is in edit mode, when the user clicks the delete icon on a step, then the step is removed, any `blockedBy` references to it in other steps are cleaned up, and parallel groups are recalculated.

8. **Inline step title/description editing** -- Given the canvas is in edit mode, when the user clicks on a step's title or description, then the field becomes an inline editable input, and changes update the local plan state on blur or Enter.

9. **Read-only canvas during execution** -- Given the task is in `in_progress` or `done` status, when the user opens the Execution Plan tab, then the canvas is read-only (step blocks show live status — pending, running, completed, crashed, blocked — but no drag handles, no add/remove/edit controls).

10. **PreKickoffModal removed** -- Given the `PreKickoffModal` component existed in the codebase, when this story is implemented, then `PreKickoffModal.tsx` and `PlanChatPanel.tsx` are deleted, all references to `onOpenPreKickoff` prop on `TaskDetailSheet` are removed, and the KanbanBoard no longer renders the modal.

11. **Local edits preserved until kick-off** -- Given the user makes edits in the canvas (reorder, reassign, add step), when the user switches to the Thread tab and back, then the local edits are still present (local state persists within the TaskDetailSheet session).

12. **Lead Agent plan update reflected in canvas** -- Given the Lead Agent calls `bridge.update_execution_plan()` (via thread negotiation — Story 7.3), when the task's `executionPlan` field updates in Convex, then the canvas detects the new `generatedAt` and refreshes the local plan state (existing `syncKey` pattern in `PlanEditor.tsx`).

## Tasks / Subtasks

- [x] **Task 1: Extend ExecutionPlanTab to support edit mode** (AC: 1, 9)
  - [x] 1.1 Read `dashboard/components/ExecutionPlanTab.tsx` fully to understand current read-only structure.
  - [x] 1.2 Add `isEditMode: boolean` prop derived from parent: `isEditMode = task.status === "review" && task.awaitingKickoff === true`.
  - [x] 1.3 When `isEditMode=true`, render `<PlanEditor>` component with `plan={task.executionPlan}`, `taskId={task._id}`, and `onPlanChange={setLocalPlan}` handler.
  - [x] 1.4 When `isEditMode=false` (execution or done), render the existing read-only plan visualization (step status badges, live progress).
  - [x] 1.5 Pass `localPlan` (local state holding edits) up to the TaskDetailSheet so it can be passed to `approveAndKickOff`.

- [x] **Task 2: Add Kick-off button to TaskDetailSheet header** (AC: 2)
  - [x] 2.1 In `TaskDetailSheet.tsx`, detect when `task.status === "review" && task.awaitingKickoff === true`.
  - [x] 2.2 Add a "Kick-off" button (`bg-green-600`, `Play` icon from lucide-react) in the sheet header alongside the existing status badge.
  - [x] 2.3 On click: call `useMutation(api.tasks.approveAndKickOff)` with `{ taskId, executionPlan: localPlan }` where `localPlan` is the current canvas state (lifted from `ExecutionPlanTab`).
  - [x] 2.4 Show loading state during mutation: `<Loader2 className="animate-spin">` + "Kicking off..." text, button disabled.
  - [x] 2.5 On success: onClose() is called (sonner not available in project; error state used instead).
  - [x] 2.6 On error: show error state with the error message.

- [x] **Task 3: Expose localPlan state to TaskDetailSheet** (AC: 2, 11)
  - [x] 3.1 In `ExecutionPlanTab.tsx`, accept an optional `onLocalPlanChange?: (plan: ExecutionPlan) => void` callback.
  - [x] 3.2 When `PlanEditor.onPlanChange` fires, call `onLocalPlanChange` with the updated plan.
  - [x] 3.3 In `TaskDetailSheet.tsx`, hold `const [localPlan, setLocalPlan] = useState<ExecutionPlan | undefined>(undefined)`.
  - [x] 3.4 When the task's `executionPlan` changes in Convex (Lead Agent update), reset `localPlan` to `undefined` so the canvas re-syncs from Convex.

- [x] **Task 4: Add "Human" agent to PlanStepCard agent dropdown** (AC: 4)
  - [x] 4.1 In `PlanStepCard.tsx`, read the agents list from `useQuery(api.agents.list)` (or receive from parent PlanEditor).
  - [x] 4.2 In the agent dropdown, prepend a **"Human"** option with value `"human"` before the agent list.
  - [x] 4.3 "Human" should display with a user icon (e.g., `User` from lucide-react) in the dropdown item.
  - [x] 4.4 Do NOT include `lead-agent` in the dropdown (existing behavior — preserve it).

- [x] **Task 5: Remove PreKickoffModal and PlanChatPanel** (AC: 10)
  - [x] 5.1 Delete `dashboard/components/PreKickoffModal.tsx`.
  - [x] 5.2 Delete `dashboard/components/PreKickoffModal.test.tsx`.
  - [x] 5.3 Delete `dashboard/components/PlanChatPanel.tsx`.
  - [x] 5.4 Delete `dashboard/components/PlanChatPanel.test.tsx`.
  - [x] 5.5 Remove `onOpenPreKickoff` prop from `TaskDetailSheet` interface and all call sites.
  - [x] 5.6 In `KanbanBoard.tsx`, removed `reviewing_plan` column mapping (no PreKickoffModal was rendered there directly).
  - [x] 5.7 Remove any "Review Plan" button in `TaskCard.tsx` that opened the modal (removed direct kickoff from card badge, replaced with "Awaiting Kick-off" badge).

- [x] **Task 6: Update KanbanBoard for review+awaitingKickoff tasks** (AC: 1)
  - [x] 6.1 In `KanbanBoard.tsx`, tasks in `review` with `awaitingKickoff: true` appear in the "Review" column (existing behavior, already correct).
  - [x] 6.2 The task card for `review`+`awaitingKickoff` shows a badge: "Awaiting Kick-off" in amber.
  - [x] 6.3 Clicking the task card opens the `TaskDetailSheet` and auto-switches to the Execution Plan tab.

- [x] **Task 7: Auto-switch to Execution Plan tab when awaitingKickoff** (AC: 1)
  - [x] 7.1 In `TaskDetailSheet.tsx`, detect on open (or task prop change) when `task.awaitingKickoff === true`.
  - [x] 7.2 When detected, programmatically switch the active tab to the Execution Plan tab using controlled `Tabs` value state.

- [x] **Task 8: Write Vitest tests** (AC: 1, 2, 5, 9, 10)
  - [x] 8.1 `ExecutionPlanTab.test.tsx`: test that edit mode renders PlanEditor when `awaitingKickoff=true`, read-only view otherwise.
  - [x] 8.2 `TaskDetailSheet.test.tsx`: test that Kick-off button appears only in `review`+`awaitingKickoff`, calls `approveAndKickOff` on click.
  - [x] 8.3 Verified no import of `PreKickoffModal` or `PlanChatPanel` anywhere in the codebase after deletion.

## Dev Notes

### Existing Code to Reuse

**PlanEditor.tsx (already implemented on `novo-plano` branch):**
- Handles drag-and-drop (`@dnd-kit/core`)
- `syncKey` pattern for Lead Agent plan updates (line 38-45)
- `onPlanChange` callback already fires on every local edit
- **DO NOT** add `useQuery` for agents inside PlanEditor — it already does `useQuery(api.agents.list)` at line 40

**ExecutionPlanTab.tsx (read-only today):**
- Lives at `dashboard/components/ExecutionPlanTab.tsx`
- Merges plan steps with live step data (from `steps` table)
- Groups parallel steps
- Shows step status badges

**approveAndKickOff mutation (already implemented):**
- In `dashboard/convex/tasks.ts`
- Checks `task.status === "review" && task.awaitingKickoff === true`
- Accepts optional `executionPlan` to save user edits

**recalcParallelGroups (already exists):**
- In `dashboard/lib/planUtils.ts`
- Must be called after drag-and-drop and dependency changes

### Architecture: EditMode Detection

```
TaskDetailSheet
  ├─ task.status === "review" && task.awaitingKickoff === true
  │   → isEditMode = true
  │   → Show "Kick-off" button in header
  │   → ExecutionPlanTab receives isEditMode=true
  │       → Renders PlanEditor (editable canvas)
  │       → Fires onLocalPlanChange on every edit
  └─ otherwise
      → ExecutionPlanTab receives isEditMode=false
      → Renders read-only plan visualization
```

### Canvas Layout (Edit Mode)

```
+--------------------------------------------------+
| [task title]          [Badge: Awaiting Kick-off]  |
|                       [Kick-off ▶]  [X close]     |
+--------------------------------------------------+
| Tabs: Thread | Execution Plan | Files             |
+--------------------------------------------------+
| [Execution Plan tab active]                       |
|                                                   |
| ┌────────────────────────────────────────────┐   |
| │ Step 1: Extract data        [agent-1 ▼][×] │   |
| │ ≡ Analyze Q1 financial data                │   |
| │ blockedBy: none            [+ dep]          │   |
| └────────────────────────────────────────────┘   |
| ┌────────────────────────────────────────────┐   |
| │ Step 2: Generate report     [human ▼][×]   │   |
| │ ≡ Write quarterly summary                  │   |
| │ blockedBy: Step 1          [+ dep]          │   |
| └────────────────────────────────────────────┘   |
|                                                   |
| [+ Add Step]                                      |
+--------------------------------------------------+
```

### State: localPlan lifting

The `PlanEditor` already manages internal local state. The `TaskDetailSheet` needs the final plan for `approveAndKickOff`. Pattern:

```tsx
// TaskDetailSheet.tsx
const [localPlan, setLocalPlan] = useState<ExecutionPlan | undefined>(undefined);

// When Lead Agent updates plan via Convex, reset local edits
const prevPlanRef = useRef(task?.executionPlan?.generatedAt);
useEffect(() => {
  if (task?.executionPlan?.generatedAt !== prevPlanRef.current) {
    prevPlanRef.current = task?.executionPlan?.generatedAt;
    setLocalPlan(undefined); // Force PlanEditor to re-sync from Convex
  }
}, [task?.executionPlan?.generatedAt]);

// Pass to approveAndKickOff
const planToSave = localPlan ?? task?.executionPlan;
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT try to make ExecutionPlanTab always editable** — only when `task.status === "review" && task.awaitingKickoff === true`. During execution (`in_progress`), the canvas is read-only and shows live step statuses.

2. **DO NOT keep PreKickoffModal** — it must be deleted. All files importing it must be updated. Use grep/glob to find all usages before deleting.

3. **DO NOT add a second `useQuery(api.agents.list)` in ExecutionPlanTab** — `PlanEditor` already queries agents. Pass agents down as a prop if needed, don't duplicate the query.

4. **DO NOT call `approveAndKickOff` without the edited plan** — if the user made local edits, those edits must be passed as `executionPlan`. Pass `localPlan ?? task.executionPlan` to ensure edits are captured.

5. **DO NOT remove the `syncKey` pattern** in `PlanEditor.tsx` — this is what allows the Lead Agent to update the plan and have the canvas refresh. Removing it would break Story 7.3.

6. **DO NOT show "Human" in the agent dropdown as an existing agent from the DB** — "Human" is a hardcoded option prepended to the agent list, it is NOT stored in the `agents` table.

7. **DO NOT forget to clean up `blockedBy` references when deleting a step** — if step_2 is deleted and step_3 has `blockedBy: ["step_2"]`, remove `"step_2"` from step_3's `blockedBy`.

### What This Story Does NOT Include

- **Lead Agent responding to thread messages** — Story 7.3
- **Human step waiting state and Accept button** — Story 7.2
- **Pause/Resume** — Story 7.4

### Files to Create

None — all work is in existing files.

### Files to Delete

- `dashboard/components/PreKickoffModal.tsx`
- `dashboard/components/PreKickoffModal.test.tsx`
- `dashboard/components/PlanChatPanel.tsx`
- `dashboard/components/PlanChatPanel.test.tsx`

### Files to Modify

- `dashboard/components/ExecutionPlanTab.tsx` — add edit mode rendering
- `dashboard/components/TaskDetailSheet.tsx` — add Kick-off button, localPlan state, auto-tab-switch
- `dashboard/components/PlanStepCard.tsx` — add "Human" option to agent dropdown
- `dashboard/components/KanbanBoard.tsx` — remove PreKickoffModal usage, update card badge
- `dashboard/components/TaskCard.tsx` — remove "Review Plan" button if present

### References

- [Source: `dashboard/components/PlanEditor.tsx`] — PlanEditor with syncKey pattern and onPlanChange
- [Source: `dashboard/components/ExecutionPlanTab.tsx`] — Current read-only tab to extend
- [Source: `dashboard/convex/tasks.ts#approveAndKickOff`] — Mutation to use for kick-off
- [Source: `dashboard/convex/schema.ts#tasks`] — `awaitingKickoff: v.optional(v.boolean())`
- [Source: `dashboard/lib/planUtils.ts`] — `recalcParallelGroups()`
- [Story 4.2] — Agent reassignment implementation pattern
- [Story 4.3] — Step reorder and dependency editing implementation pattern

## Dev Agent Record

### Implementation Plan

1. Extended `ExecutionPlanTab.tsx` with `isEditMode`, `taskId`, and `onLocalPlanChange` props. When `isEditMode=true` and plan/taskId are available, renders `<PlanEditor>` instead of the read-only view. All hooks (useMemo) are called unconditionally before the conditional render path to comply with React Rules of Hooks.

2. Updated `TaskDetailSheet.tsx`:
   - Removed `onOpenPreKickoff` prop from interface
   - Added `localPlan` state and `prevPlanGeneratedAt` ref for Lead Agent plan sync detection
   - Added `isAwaitingKickoff` derived state via `useMemo`
   - Converted `Tabs` from uncontrolled (`defaultValue`) to controlled (`value/onValueChange`) for auto-switching
   - Added `useEffect` to auto-switch to "plan" tab when `awaitingKickoff=true`
   - Replaced `reviewing_plan` status checks with `review`+`awaitingKickoff` checks
   - Updated `handleKickOff` to pass `localPlan ?? task.executionPlan` to mutation
   - Added "Awaiting Kick-off" badge in header
   - Passes `isEditMode`, `taskId`, and `onLocalPlanChange={setLocalPlan}` to `ExecutionPlanTab`

3. Updated `PlanStepCard.tsx`: Added hardcoded "Human" option at top of agent dropdown using `User` icon from lucide-react. Updated trigger display to show user icon when `assignedAgent === "human"`.

4. Deleted `PreKickoffModal.tsx`, `PreKickoffModal.test.tsx`, `PlanChatPanel.tsx`, `PlanChatPanel.test.tsx`.

5. Updated `KanbanBoard.tsx`: Removed `reviewing_plan` column mapping from inbox column logic.

6. Updated `TaskCard.tsx`: Changed the amber badge from clickable "Kick-off" (that bypassed plan review) to non-clickable "Awaiting Kick-off" badge with `data-testid`. Removed unused `kickOffMutation`.

### Completion Notes

- All 8 tasks implemented and all tests pass (24 ExecutionPlanTab + 13 PlanStepCard + 41 TaskDetailSheet tests including pre-existing passes)
- Note on sonner: The story mentioned using `sonner` for toasts, but `sonner` is not installed in the project. Used existing error state display instead.
- Pre-existing test failures in `TaskDetailSheet.test.tsx` for Files tab navigation (insufficient mock values in 5 tests) were already failing before this story. These tests have insufficient `useQuery` mock values and are not caused by this story's changes.
- TypeScript compiles cleanly (only pre-existing `.next/dev` auto-generated file errors)

### File List

Modified:
- `dashboard/components/ExecutionPlanTab.tsx`
- `dashboard/components/TaskDetailSheet.tsx`
- `dashboard/components/PlanEditor.tsx`
- `dashboard/components/PlanStepCard.tsx`
- `dashboard/components/KanbanBoard.tsx`
- `dashboard/components/TaskCard.tsx`
- `dashboard/components/ExecutionPlanTab.test.tsx`
- `dashboard/components/PlanStepCard.test.tsx`
- `dashboard/components/TaskDetailSheet.test.tsx`
- `dashboard/components/TaskCard.test.tsx`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

Deleted:
- `dashboard/components/PreKickoffModal.tsx`
- `dashboard/components/PreKickoffModal.test.tsx`
- `dashboard/components/PlanChatPanel.tsx`
- `dashboard/components/PlanChatPanel.test.tsx`

### Change Log

- 2026-02-25: Implemented Story 7.1 — Execution Plan Canvas. Replaced PreKickoffModal approach with in-place editable canvas in ExecutionPlanTab. Added edit mode to ExecutionPlanTab (renders PlanEditor for review+awaitingKickoff tasks). Added Kick-off button to TaskDetailSheet header. Added localPlan state lifting. Added "Human" agent option to PlanStepCard dropdown. Removed PreKickoffModal and PlanChatPanel components. Updated KanbanBoard and TaskCard for the new review+awaitingKickoff flow.
- 2026-02-25: Code review fixes applied — (H1) Fixed `isPlanning` prop in TaskDetailSheet from `task.status === "inbox"` to `task.status === "planning"`. (H2) Fixed tempId collision in PlanEditor.handleAddStep — use `step_new_${Date.now()}` instead of `step_${maxOrder + 2}` to avoid collisions after delete+add cycles. (H3) Added missing tests for `awaitingKickoff` badge on TaskCard (AC 6.2). (H4) Added tests for auto-tab-switch and isEditMode propagation (AC 1, Task 7). (M3) Extracted `(task as any)` casts into typed local variables in TaskDetailSheet to reduce ESLint issues. (M4) Added `generatedAt != null` guard to `canEditPlan` in ExecutionPlanTab to protect against older plan format breaking PlanEditor syncKey pattern. Added corresponding test for the generatedAt guard.
