# Story 4.1: Build Pre-Kickoff Modal Shell

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want a full-screen modal to open when my supervised task's plan is ready,
so that I have a dedicated workspace to review and edit the plan before anything executes.

## Acceptance Criteria

1. **PreKickoffModal opens automatically when task status is "reviewing_plan"** -- Given a task was created with `supervisionMode: "supervised"`, when the Lead Agent completes plan generation and the task status becomes `"reviewing_plan"`, then the `PreKickoffModal` opens automatically as a full-screen modal overlay (not a Sheet) (FR11). The modal uses Radix UI Dialog primitives (already installed as `@radix-ui/react-dialog` via the existing ShadCN `dialog.tsx` component).

2. **Two-panel layout: plan editor (left) and Lead Agent chat (right)** -- Given the `PreKickoffModal` is open, when the execution plan data is loaded from the task's `executionPlan` field, then the modal displays a two-panel layout: the plan editor panel on the left (~60% width) showing all steps with agent assignments, dependencies, and parallel groups; and the Lead Agent chat panel on the right (~40% width) showing thread messages filtered to `type: "lead_agent_chat"` or `type: "lead_agent_plan"`. The plan renders within 2 seconds (NFR2).

3. **Modal header with task title and disabled Kick-off button** -- Given the `PreKickoffModal` is open, when the header is displayed, then it shows: the task title, a "Kick-off" button (disabled in this story -- it will be enabled in Story 4.6), and a close button (X icon). The header also shows a `"reviewing_plan"` status badge using the appropriate color from `STATUS_COLORS`.

4. **Modal closes without losing the plan** -- Given the user clicks outside the modal or presses Escape, when the close action is triggered, then the modal closes but the task remains in `"reviewing_plan"` status -- the `executionPlan` field is preserved. The user can reopen the modal from the task detail sheet or a "Review Plan" button on the task card.

5. **"reviewing_plan" status is fully supported in schema and constants** -- Given the task status `"reviewing_plan"` is already referenced in `VALID_TRANSITIONS` in `tasks.ts`, when it is used in the UI, then it is also present in: (a) the `status` union in `schema.ts` tasks table, (b) the `TASK_STATUS` constant in `lib/constants.ts`, (c) the `STATUS_COLORS` map in `lib/constants.ts`, and (d) the `TaskStatus` derived type.

6. **"Review Plan" button on TaskCard for reviewing_plan tasks** -- Given a task has `status: "reviewing_plan"` and `supervisionMode: "supervised"`, when the task card is rendered on the Kanban board, then it shows a "Review Plan" button that opens the `PreKickoffModal` when clicked.

7. **Task detail sheet integrates with PreKickoffModal** -- Given a task is in `"reviewing_plan"` status, when the user opens the task detail sheet, then a prominent "Review Plan" button is displayed in the header area that opens the `PreKickoffModal`.

## Tasks / Subtasks

- [x] **Task 1: Add "reviewing_plan" to Convex schema and constants** (AC: 5)
  - [x] 1.1 Add `v.literal("reviewing_plan")` to the `status` union in `dashboard/convex/schema.ts` tasks table definition (after `v.literal("planning")`). Currently this status is referenced in `VALID_TRANSITIONS` in `tasks.ts` but NOT in the schema validator -- Convex will reject any write with `status: "reviewing_plan"` until this is added.
  - [x] 1.2 Add `REVIEWING_PLAN: "reviewing_plan"` to the `TASK_STATUS` constant in `dashboard/lib/constants.ts` (after `PLANNING`).
  - [x] 1.3 Add `reviewing_plan` entry to the `STATUS_COLORS` map in `dashboard/lib/constants.ts`. Use an indigo/purple variant to visually distinguish it from "planning": `{ border: "border-l-purple-500", bg: "bg-purple-100 dark:bg-purple-950", text: "text-purple-700 dark:text-purple-300" }`.
  - [x] 1.4 Verify that the `TaskStatus` type (derived from `TASK_STATUS`) automatically includes `"reviewing_plan"` after the constant is updated -- no separate type change needed.
  - [x] 1.5 Add `"reviewing_plan"` to the `VALID_TRANSITIONS` entry as a source: `reviewing_plan: ["planning", "ready"]` in `dashboard/convex/tasks.ts`. Verify the existing entries `planning: ["failed", "reviewing_plan", "ready"]` and `"planning->reviewing_plan": "task_planning"` in `TRANSITION_EVENT_MAP` are correct. Also add `"reviewing_plan->ready": "task_plan_approved"` to the transition event map -- but since `"task_plan_approved"` is NOT in the activities schema yet, add it to the activities `eventType` union in `schema.ts` as well.
  - [x] 1.6 Add `reviewing_plan` to the `listByStatus` query's status union in `dashboard/convex/tasks.ts` so tasks in this status can be queried.

- [x] **Task 2: Create `PreKickoffModal.tsx` component shell** (AC: 1, 2, 3, 4)
  - [x] 2.1 Create `dashboard/components/PreKickoffModal.tsx`. Use the existing ShadCN `Dialog` component from `@/components/ui/dialog` as the base. Override the `DialogContent` className to make it full-screen: `"fixed inset-0 z-50 flex flex-col max-w-none translate-x-0 translate-y-0 rounded-none h-screen w-screen"`. Remove the default max-width, centering transform, and rounded corners. Keep the overlay for focus trapping and backdrop.
  - [x] 2.2 Define the `PreKickoffModalProps` interface:
    ```typescript
    interface PreKickoffModalProps {
      taskId: Id<"tasks"> | null;
      open: boolean;
      onClose: () => void;
    }
    ```
  - [x] 2.3 Inside the modal, load the task data using `useQuery(api.tasks.getById, taskId ? { taskId } : "skip")`. Load the task's messages using `useQuery(api.messages.listByTask, taskId ? { taskId } : "skip")`. Load agents list using `useQuery(api.agents.list)`.
  - [x] 2.4 Implement the modal header as a `div` with `flex items-center justify-between` inside the dialog content (not using `DialogHeader` since we need a custom layout). The header contains:
    - Task title (left-aligned, `text-lg font-semibold`, truncated with `truncate max-w-[400px]`)
    - Status badge showing `"reviewing plan"` with the purple color from `STATUS_COLORS` (centered or right-of-title)
    - "Kick-off" button (`Button variant="default"` with `bg-green-500 hover:bg-green-600 text-white`), disabled with `disabled` prop and `opacity-50 cursor-not-allowed` (this story does not implement the kick-off logic -- that is Story 4.6)
    - Close button (X icon, `DialogClose` from Radix or a manual `onClose` callback)
  - [x] 2.5 Implement the two-panel body layout below the header. Use `flex flex-1 min-h-0 overflow-hidden`:
    - **Left panel (PlanEditor placeholder):** `div` with `flex-[3] min-w-0 border-r border-border overflow-y-auto p-4`. For this story, render the existing `ExecutionPlanTab` component as a read-only plan view. Pass `executionPlan={task.executionPlan}` and `liveSteps={undefined}` (no live steps in reviewing_plan -- steps are not materialized yet). Show a `"Plan Editor"` heading above it.
    - **Right panel (Chat placeholder):** `div` with `flex-[2] min-w-0 flex flex-col overflow-hidden`. For this story, render a simple filtered thread showing only `lead_agent_plan` and `lead_agent_chat` messages from the task's messages. Show a `"Lead Agent Chat"` heading, use `ScrollArea` from ShadCN for the message list, and render each message using the existing `ThreadMessage` component. Below the message list, include a placeholder text input area (disabled in this story with placeholder text "Chat will be available in Story 4.5").
  - [x] 2.6 Handle the close behavior: use the `Dialog` `onOpenChange` prop to call `onClose` when the dialog is closed (Escape key or clicking outside triggers this automatically via Radix). The `onClose` callback should NOT change the task status -- the task remains in `"reviewing_plan"`. No `onPointerDownOutside` prevention is needed; closing is intentional per AC4.
  - [x] 2.7 Add a `DialogTitle` (can be `sr-only` / visually hidden) and `DialogDescription` (also `sr-only`) for accessibility compliance -- Radix will warn in console if these are missing.

- [x] **Task 3: Integrate PreKickoffModal into DashboardLayout** (AC: 1, 4)
  - [x] 3.1 In `dashboard/components/DashboardLayout.tsx`, add state for the pre-kickoff modal: `const [preKickoffTaskId, setPreKickoffTaskId] = useState<Id<"tasks"> | null>(null)`.
  - [x] 3.2 Import and render `PreKickoffModal` at the bottom of the JSX tree (sibling to `TaskDetailSheet`, `SettingsPanel Sheet`, etc.):
    ```tsx
    <PreKickoffModal
      taskId={preKickoffTaskId}
      open={!!preKickoffTaskId}
      onClose={() => setPreKickoffTaskId(null)}
    />
    ```
  - [x] 3.3 Add auto-open logic: use a `useQuery` to subscribe to tasks with status `"reviewing_plan"`. When a new task enters `"reviewing_plan"`, auto-open the modal. Implementation approach:
    - Add `const reviewingPlanTasks = useQuery(api.tasks.listByStatus, { status: "reviewing_plan" as any })` (need the cast since the schema hasn't been redeployed yet with the new status -- or better, use the typed literal after Task 1 is done).
    - Use a `useEffect` to detect when `reviewingPlanTasks` changes from empty to non-empty: if there's a task in `"reviewing_plan"` and the modal is not already open, set `preKickoffTaskId` to the first such task's `_id`.
    - Do NOT auto-open if the user has already manually closed the modal for this task (track dismissed task IDs in a `useRef<Set<string>>`).
  - [x] 3.4 Pass a `onOpenPreKickoff` callback to `KanbanBoard` and `TaskDetailSheet` so they can programmatically open the modal for a specific task.

- [x] **Task 4: Add "Review Plan" button to TaskCard** (AC: 6)
  - [x] 4.1 In `dashboard/components/TaskCard.tsx`, detect when a task has `status === "reviewing_plan"` (or the status that maps to reviewing_plan in the current Kanban column mapping).
  - [x] 4.2 When the task is in `"reviewing_plan"` status, render a "Review Plan" button on the task card. Use `Button variant="outline" size="sm"` with a `FileSearch` or `Eye` icon from lucide-react. The button click should call `onOpenPreKickoff(task._id)` (a new prop passed from `KanbanBoard`).
  - [x] 4.3 Update `KanbanBoard.tsx` to pass the `onOpenPreKickoff` callback down to `KanbanColumn` and then to `TaskCard` components. The callback calls `setPreKickoffTaskId` in `DashboardLayout` (received via the new prop from Task 3.4).
  - [x] 4.4 Update `KanbanBoard.tsx` column mapping: add `"reviewing_plan"` tasks to the appropriate Kanban column. Since `"reviewing_plan"` is a new status, it should appear in the "Inbox" column (as it is the stage before execution begins). Add `|| t.status === "reviewing_plan"` to the inbox column filter, OR create a new dedicated filter. Decision: add it to the "Inbox" column filter alongside `"planning"` status.

- [x] **Task 5: Add "Review Plan" button to TaskDetailSheet** (AC: 7)
  - [x] 5.1 In `dashboard/components/TaskDetailSheet.tsx`, add a `onOpenPreKickoff` prop to `TaskDetailSheetProps`:
    ```typescript
    interface TaskDetailSheetProps {
      taskId: Id<"tasks"> | null;
      onClose: () => void;
      onOpenPreKickoff?: (taskId: Id<"tasks">) => void;
    }
    ```
  - [x] 5.2 When the task is loaded and has `status === "reviewing_plan"`, render a "Review Plan" button in the header area (next to the existing Approve/Deny buttons area, inside the `SheetDescription asChild div`). Use `Button variant="default"` with `className="bg-purple-500 hover:bg-purple-600 text-white text-xs h-7 px-2"`. On click, call `onOpenPreKickoff(task._id)` and then `onClose()` to dismiss the sheet.
  - [x] 5.3 Update `DashboardLayout.tsx` to pass `onOpenPreKickoff={setPreKickoffTaskId}` to `TaskDetailSheet`.

- [x] **Task 6: Write component tests for PreKickoffModal** (AC: 1, 2, 3, 4)
  - [x] 6.1 Create `dashboard/components/PreKickoffModal.test.tsx`. Follow the pattern established in `StepCard.test.tsx` and `FeedItem.test.tsx` for mocking Convex queries.
  - [x] 6.2 Test: `"renders modal with task title and status badge when open"` -- provide a mock task with `status: "reviewing_plan"` and `executionPlan` data. Assert the task title is displayed. Assert a badge with "reviewing plan" text is visible.
  - [x] 6.3 Test: `"renders two-panel layout with plan editor and chat headings"` -- assert "Plan Editor" and "Lead Agent Chat" text is present in the rendered output.
  - [x] 6.4 Test: `"renders Kick-off button as disabled"` -- assert a button with text "Kick-off" is present and has the `disabled` attribute.
  - [x] 6.5 Test: `"calls onClose when dialog is closed"` -- simulate the close action and assert `onClose` was called.
  - [x] 6.6 Test: `"does not render when open is false"` -- render with `open={false}` and assert no modal content is in the DOM.

- [x] **Task 7: Write tests for reviewing_plan schema and constants** (AC: 5)
  - [x] 7.1 In `dashboard/convex/steps.test.ts` (or create a dedicated `dashboard/convex/tasks.test.ts` if one does not exist), add a test verifying that `isValidTransition("planning", "reviewing_plan")` returns `true`.
  - [x] 7.2 In the same test file, verify `isValidTransition("reviewing_plan", "ready")` returns `true` (the transition from plan review to plan approved).
  - [x] 7.3 Verify that `TASK_STATUS.REVIEWING_PLAN` equals `"reviewing_plan"` in a unit test.

## Dev Notes

### Critical Schema Gap: "reviewing_plan" Not in Schema

The most important finding from codebase analysis: **`"reviewing_plan"` is NOT yet a valid value in the Convex schema's task status union** (`dashboard/convex/schema.ts` lines 21-32). The `VALID_TRANSITIONS` map in `tasks.ts` references it (line 8: `planning: ["failed", "reviewing_plan", "ready"]`), and the `kickOff` mutation accepts it (line 349), but the schema validator will REJECT any attempt to write `status: "reviewing_plan"` to a task document. Task 1 MUST be completed first before any other task can work.

Similarly, `"reviewing_plan"` is missing from:
- `TASK_STATUS` constant in `lib/constants.ts` (the `TaskStatus` type won't include it)
- `STATUS_COLORS` map in `lib/constants.ts` (the badge will have no color)
- `listByStatus` query's status union in `tasks.ts`

### Existing Dialog/Modal Infrastructure

The project already has `@radix-ui/react-dialog` installed and a ShadCN Dialog component at `dashboard/components/ui/dialog.tsx`. The default `DialogContent` uses `max-w-lg` and centering transforms (`translate-x-[-50%] translate-y-[-50%]`). For the full-screen modal, the developer must override these classes to use `inset-0`, `h-screen`, `w-screen`, and remove the transforms. The overlay (`DialogOverlay`) already provides `bg-black/80` backdrop and fade animations.

The existing `CronJobsModal.tsx` in the project uses a similar Dialog pattern and can be referenced for the controlled open/close pattern.

### Full-Screen Modal Pattern

Use the ShadCN Dialog primitives but override sizing. The recommended approach:

```tsx
<Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
  <DialogContent className="fixed inset-4 z-50 flex flex-col max-w-none translate-x-0 translate-y-0 rounded-lg border bg-background shadow-lg sm:rounded-lg h-[calc(100vh-2rem)] w-[calc(100vw-2rem)]">
    <DialogTitle className="sr-only">Pre-Kickoff Plan Review</DialogTitle>
    <DialogDescription className="sr-only">Review and edit the execution plan before kick-off</DialogDescription>
    {/* Custom header, body panels */}
  </DialogContent>
</Dialog>
```

Using `inset-4` with `calc(100vh-2rem)` gives a near-full-screen feel with a small margin, which is visually cleaner than true `inset-0`. Adjust if the design calls for true edge-to-edge.

### Two-Panel Layout

The left/right panel split should use flexbox with `flex-[3]` (60%) and `flex-[2]` (40%). On smaller screens (< 1280px but still >= 1024px since the dashboard requires 1024px+), the panels should remain side-by-side but may be slightly narrower. No responsive stacking is needed since the dashboard already blocks mobile/tablet.

### ExecutionPlanTab Reuse

The existing `ExecutionPlanTab` component (`dashboard/components/ExecutionPlanTab.tsx`) already handles rendering execution plan steps with status badges, parallel group grouping, dependency labels, and error messages. For the PreKickoffModal, it can be reused in read-only mode by passing:
- `executionPlan={task.executionPlan}` -- the plan object from the task record
- `liveSteps={undefined}` -- no live step records exist yet (steps are materialized only on kick-off)
- `isPlanning={false}` -- the plan is ready for review, not still being generated

In later stories (4.2, 4.3), the plan editor panel will be replaced with an editable `PlanEditor` component. This story establishes the shell and uses `ExecutionPlanTab` as a placeholder.

### Chat Panel (Right Side) -- Read-Only for This Story

The chat panel shows messages from the task's unified thread, filtered to `type === "lead_agent_plan"` or `type === "lead_agent_chat"`. These are posted by the Lead Agent when it generates or updates the plan. The existing `ThreadMessage` component can render these. For this story, the chat input is disabled -- actual chat interaction with the Lead Agent will be implemented in Story 4.5.

Filter messages like this:
```typescript
const chatMessages = (messages ?? []).filter(
  (msg) => msg.type === "lead_agent_plan" || msg.type === "lead_agent_chat"
);
```

### Auto-Open Logic

The modal should auto-open when a task transitions to `"reviewing_plan"`. The recommended pattern is to subscribe to the list of tasks in this status and use a `useEffect` to detect changes. Important considerations:

1. **Do NOT auto-open if the user manually closed the modal** -- track dismissed task IDs in a `useRef<Set<string>>()`. When the user closes via X/Escape, add the taskId to the set. Clear the set only when the task leaves `"reviewing_plan"` status.
2. **Only auto-open for the FIRST such task** -- if multiple tasks are in `"reviewing_plan"`, open the first one by creation time.
3. **Auto-open should happen once per task** -- not on every re-render.

### Kanban Column Mapping for "reviewing_plan"

The `KanbanBoard.tsx` currently filters tasks into columns based on `task.status`. The new `"reviewing_plan"` status needs to be mapped to a column. Since the task is between planning and execution, it logically fits in the "Inbox" column (waiting for user action). Add it to the inbox column filter:

```typescript
// In the COLUMNS filter logic
if (col.status === "inbox") {
  return t.status === "inbox" || t.status === "reviewing_plan" || t.status === "planning";
}
```

Alternatively, the `regularTasks` filter in `KanbanBoard.tsx` (line 108) might exclude the task if it has no renderable steps. Verify this does not accidentally hide `"reviewing_plan"` tasks.

### Existing TaskCard Component

The `TaskCard.tsx` component will need a `onOpenPreKickoff` prop. Since `TaskCard` is rendered inside `KanbanColumn` which is rendered inside `KanbanBoard`, the callback must be threaded through. Follow the existing `onTaskClick` prop pattern.

### Dialog Accessibility

Radix Dialog automatically:
- Traps focus within the modal
- Closes on Escape keypress
- Manages `aria-modal="true"`
- Requires `DialogTitle` and `DialogDescription` (can be `sr-only` / visually hidden)

Do NOT prevent Escape from closing -- per AC4, the modal should close on Escape while preserving the plan.

### Activity Event for "task_plan_approved"

The `TRANSITION_EVENT_MAP` in `tasks.ts` needs an entry for `"reviewing_plan->ready"`. The logical event type is `"task_plan_approved"`. This event type is NOT currently in the `activities.eventType` schema union. Add it in Task 1.5. If adding a new event type feels premature for the shell story, an alternative is to reuse `"task_planning"` -- but `"task_plan_approved"` is more semantically correct for when the user clicks Kick-off in Story 4.6.

### No Python Changes

This story is entirely frontend (React components + Convex schema extensions). No Python changes are needed. The `"reviewing_plan"` status will be SET by the Python backend (in the Lead Agent planning flow from Story 1.5), but reading and displaying it is purely a dashboard concern.

### Project Structure Notes

**Files to CREATE:**
- `dashboard/components/PreKickoffModal.tsx` -- full-screen pre-kickoff modal component
- `dashboard/components/PreKickoffModal.test.tsx` -- component tests

**Files to MODIFY:**
- `dashboard/convex/schema.ts` -- add `v.literal("reviewing_plan")` to tasks status union; add `v.literal("task_plan_approved")` to activities eventType union
- `dashboard/lib/constants.ts` -- add `REVIEWING_PLAN` to `TASK_STATUS`; add `reviewing_plan` to `STATUS_COLORS`
- `dashboard/convex/tasks.ts` -- add `reviewing_plan` transitions, add to `listByStatus` union, add `"reviewing_plan->ready"` event mapping
- `dashboard/components/DashboardLayout.tsx` -- add `PreKickoffModal` integration, auto-open logic, pass `onOpenPreKickoff` callback
- `dashboard/components/TaskDetailSheet.tsx` -- add `onOpenPreKickoff` prop and "Review Plan" button for `reviewing_plan` tasks
- `dashboard/components/TaskCard.tsx` -- add "Review Plan" button for `reviewing_plan` tasks
- `dashboard/components/KanbanBoard.tsx` -- pass `onOpenPreKickoff` through, map `reviewing_plan` to column
- `dashboard/components/KanbanColumn.tsx` -- pass `onOpenPreKickoff` through to TaskCard

**Files to verify (read-only):**
- `dashboard/convex/tasks.ts` -- confirm existing `VALID_TRANSITIONS` and `kickOff` mutation handle `reviewing_plan` correctly (they do)
- `dashboard/components/ExecutionPlanTab.tsx` -- confirm it renders correctly with `liveSteps={undefined}` (it does -- returns plan-only view)

### Technology Versions

| Package | Version | Notes |
|---------|---------|-------|
| Next.js | ^16.1.5 | App router, "use client" components |
| React | ^19.2.4 | Hooks API, no class components |
| Convex | ^1.31.6 | Reactive queries, typed mutations |
| @radix-ui/react-dialog | (via ShadCN) | Dialog primitives for modal |
| Tailwind CSS | ^3.4.1 | Utility-first styling |
| Motion | ^12.34.3 | Available for animations but not required for this story |
| Vitest | ^4.0.18 | Test runner for component tests |
| lucide-react | (installed) | Icons for buttons and UI elements |

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.1] -- Acceptance criteria (lines 936-958)
- [Source: _bmad-output/planning-artifacts/architecture.md#Pre-Kickoff Modal] -- Two-panel layout: plan editor (left) + Lead Agent chat (right) (lines 333-337)
- [Source: _bmad-output/planning-artifacts/architecture.md#Task Status Values] -- `"reviewing_plan"` status definition (lines 241-249)
- [Source: _bmad-output/planning-artifacts/architecture.md#ExecutionPlan Structure] -- Plan type definition with tempId, title, description, assignedAgent, blockedBy, parallelGroup, order, attachedFiles (lines 213-228)
- [Source: _bmad-output/planning-artifacts/architecture.md#Frontend Architecture] -- Radix Dialog for modal, local React state for plan editing, no additional state library (lines 322-354)
- [Source: _bmad-output/planning-artifacts/architecture.md#Naming Patterns] -- `PreKickoffModal.tsx` (PascalCase), `PreKickoffModalProps` (lines 434-439)
- [Source: _bmad-output/planning-artifacts/prd.md#FR11] -- Pre-kickoff modal showing full execution plan before any step executes (line 330)
- [Source: _bmad-output/planning-artifacts/prd.md#FR18] -- User approves plan and triggers kick-off from pre-kickoff modal (line 337)
- [Source: _bmad-output/planning-artifacts/prd.md#NFR2] -- Pre-kickoff modal renders full plan within 2 seconds (line 377)
- [Source: dashboard/convex/schema.ts] -- Current tasks status union (lines 21-32) -- MISSING "reviewing_plan"
- [Source: dashboard/convex/tasks.ts#VALID_TRANSITIONS] -- Already references `reviewing_plan` (line 8) but schema doesn't support it
- [Source: dashboard/convex/tasks.ts#kickOff] -- Already accepts `reviewing_plan` status (line 349)
- [Source: dashboard/lib/constants.ts#TASK_STATUS] -- Missing `REVIEWING_PLAN` constant
- [Source: dashboard/lib/constants.ts#STATUS_COLORS] -- Missing `reviewing_plan` color entry
- [Source: dashboard/components/ui/dialog.tsx] -- ShadCN Dialog primitives (Radix-based)
- [Source: dashboard/components/ExecutionPlanTab.tsx] -- Reusable plan visualization component
- [Source: dashboard/components/DashboardLayout.tsx] -- Main layout where modal will be mounted
- [Source: dashboard/components/TaskDetailSheet.tsx] -- Task detail panel, needs "Review Plan" button
- [Source: dashboard/components/KanbanBoard.tsx] -- Kanban board, needs column mapping for reviewing_plan

### Previous Story Intelligence

From Epic 3 stories (the most recent completed epic):
- Tests follow co-located pattern: `ComponentName.test.tsx` next to `ComponentName.tsx`
- Vitest with `@testing-library/react` for component tests
- Use `container.querySelector` (not `document.querySelector`) for DOM assertions (fix from Story 3.5 review)
- Mock Convex queries using the established pattern from `StepCard.test.tsx`
- All stories include a verification that tests pass alongside the existing suite (335+ tests across 25+ files)

### Git Intelligence

Recent commits follow the pattern `feat(epic-story): description` for feature work, `review: fix findings for story X-Y` for review fixes, and `chore:` for maintenance. The branch `novo-plano` is the active development branch.

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None -- implementation was straightforward following story specifications.

### Completion Notes List

- Task 1: Added `reviewing_plan` to Convex schema status union, added `task_plan_approved` to activities eventType union, added `REVIEWING_PLAN` to `TASK_STATUS` constant, added `reviewing_plan` to `STATUS_COLORS` with purple variant, added `reviewing_plan` transitions to `VALID_TRANSITIONS` and `TRANSITION_EVENT_MAP`, and added to `listByStatus` query union.
- Task 2: Created `PreKickoffModal.tsx` using ShadCN Dialog with full-screen override (inset-4, calc height/width). Two-panel layout: left panel uses `ExecutionPlanTab` in read-only mode, right panel shows lead_agent_plan/lead_agent_chat messages via `ThreadMessage`. Kick-off button is disabled per story spec (Story 4.6 will enable it). DialogTitle and DialogDescription are sr-only for accessibility.
- Task 3: Integrated `PreKickoffModal` into `DashboardLayout` with auto-open logic using `useQuery` on `reviewing_plan` status. `useRef<Set<string>>` tracks dismissed task IDs. `handleOpenPreKickoff` allows manual re-opening. Passed `onOpenPreKickoff` to `KanbanBoard` and `TaskDetailSheet`.
- Task 4: Added `onOpenPreKickoff` prop to `TaskCard`, threaded through `KanbanBoard` and `KanbanColumn`. "Review Plan" button with Eye icon shown for supervised reviewing_plan tasks. Added `reviewing_plan` (and `planning`) to inbox column filter in KanbanBoard.
- Task 5: Added `onOpenPreKickoff` optional prop to `TaskDetailSheet`. "Review Plan" button displayed for reviewing_plan tasks with purple styling. Click opens modal and closes sheet.
- Task 6: Created 5 component tests for `PreKickoffModal` covering all ACs. All tests pass.
- Task 7: Added 3 tests to `steps.test.ts` verifying `reviewing_plan` transitions and `TASK_STATUS.REVIEWING_PLAN` constant. All tests pass.
- Total: 343 tests pass (8 new added), 0 regressions.

### File List

- `dashboard/components/PreKickoffModal.tsx` (created)
- `dashboard/components/PreKickoffModal.test.tsx` (created)
- `dashboard/convex/schema.ts` (modified)
- `dashboard/lib/constants.ts` (modified)
- `dashboard/convex/tasks.ts` (modified)
- `dashboard/components/DashboardLayout.tsx` (modified)
- `dashboard/components/DashboardLayout.test.tsx` (modified)
- `dashboard/components/TaskDetailSheet.tsx` (modified)
- `dashboard/components/TaskCard.tsx` (modified)
- `dashboard/components/KanbanBoard.tsx` (modified)
- `dashboard/components/KanbanColumn.tsx` (modified)
- `dashboard/convex/steps.test.ts` (modified)

## Senior Developer Review (AI)

**Reviewer:** Ennio (via claude-opus-4-6)
**Date:** 2026-02-25
**Result:** APPROVED with fixes applied

### Findings (5 total: 2 HIGH, 3 MEDIUM)

#### HIGH

1. **Stale `localPlan` state across task switches** (PreKickoffModal.tsx)
   - `useState<ExecutionPlan | null>(null)` for `localPlan` was never reset when `taskId` changed. Opening the modal for task B after editing task A's plan would show task A's stale plan data until an edit was made.
   - **Fix:** Added `useEffect(() => { setLocalPlan(null); }, [taskId])` to reset local plan state on task switch.

2. **Task transition tests in wrong file** (steps.test.ts)
   - The `reviewing_plan` task transition tests (`isValidTransition` and `TASK_STATUS.REVIEWING_PLAN`) were placed in `steps.test.ts` instead of `tasks.test.ts`. Tests for task transitions belong with other task tests for discoverability and organization.
   - **Fix:** Moved all 3 tests to `tasks.test.ts` and added one additional test for `reviewing_plan -> planning` back-transition. Removed from `steps.test.ts`.

#### MEDIUM

3. **Empty string `taskId` passed to PlanEditor** (PreKickoffModal.tsx:89)
   - `taskId={taskId ?? ""}` would pass an empty string to `PlanEditor` when `taskId` is null, which flows down to `StepFileAttachment` for file upload API calls. While the null case is unlikely at runtime (modal only opens with a valid taskId), the fallback masks potential bugs.
   - **Fix:** Changed condition to `executionPlan && taskId` so PlanEditor only renders when both are present. Removed `?? ""` fallback.

4. **Bogus `useState` mock in test** (PreKickoffModal.test.tsx:9)
   - The `convex/react` mock exported `useState: vi.fn()`, but `useState` is a React hook, not a convex/react export. This is dead code that pollutes the mock and shows sloppy mock setup.
   - **Fix:** Removed `useState: vi.fn()` from the convex/react mock.

5. **Test for phantom `"ready"` status** (steps.test.ts, now tasks.test.ts)
   - Test verifies `isValidTransition("reviewing_plan", "ready")` returns true, but `"ready"` is NOT a valid status in the Convex schema (`schema.ts`). The pure function returns true but this transition can never succeed at the DB layer. This is a pre-existing design issue -- `"ready"` was planned but never added to the schema. Test retained as-is since the transition map is intentionally forward-looking, but noted as misleading about actual system behavior.
   - **Fix:** None applied (pre-existing design decision). Documented for awareness.

### AC Verification

| AC | Status | Evidence |
|----|--------|----------|
| AC1: Auto-open on reviewing_plan | IMPLEMENTED | DashboardLayout.tsx:56-74 -- useQuery + useEffect with dismissed tracking |
| AC2: Two-panel layout | IMPLEMENTED | PreKickoffModal.tsx:87-113 -- flex-[3] / flex-[2] split with PlanEditor and PlanChatPanel |
| AC3: Header with disabled Kick-off | IMPLEMENTED | PreKickoffModal.tsx:52-78 -- title, badge, disabled button, close button |
| AC4: Close preserves plan | IMPLEMENTED | PreKickoffModal.tsx:38 -- onClose does NOT change task status |
| AC5: Schema and constants | IMPLEMENTED | schema.ts:23, constants.ts:4,130-134, tasks.ts:9,29 |
| AC6: Review Plan on TaskCard | IMPLEMENTED | TaskCard.tsx:194-207 -- Eye icon button for supervised reviewing_plan tasks |
| AC7: TaskDetailSheet integration | IMPLEMENTED | TaskDetailSheet.tsx:214-226 -- purple Review Plan button |

### Test Results

- All 406 tests pass (69 in modified files verified individually)
- Net test change: +1 (moved 3 from steps.test.ts to tasks.test.ts, added 1 new transition test)
- Pre-existing flaky timeouts in LoginPage.test.tsx do not affect story validation

## Change Log

- 2026-02-25: Implemented Story 4.1 -- Build Pre-Kickoff Modal Shell. Added `reviewing_plan` status to Convex schema, constants, and tasks state machine. Created `PreKickoffModal` full-screen component with two-panel layout (plan editor + lead agent chat). Integrated auto-open logic in `DashboardLayout`. Added "Review Plan" buttons to `TaskCard` and `TaskDetailSheet`. Wrote 8 new tests (5 component + 3 unit). All 343 tests pass.
- 2026-02-25: Code review by claude-opus-4-6. Fixed 4 issues: stale localPlan state across task switches (HIGH), moved task transition tests to correct file (HIGH), removed empty-string taskId fallback (MEDIUM), cleaned bogus useState mock (MEDIUM). All 406 tests pass.
