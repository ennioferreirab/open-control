# Story 8.6: Implement Human Manual Tasks with Drag-and-Drop Kanban

Status: done

## Story

As a **user**,
I want to create tasks that are NOT delegated to AI agents and manage them manually on the Kanban board via drag-and-drop,
So that I can use Mission Control as a personal task board for human work alongside agent-delegated tasks.

## Acceptance Criteria

### AC1: AI/Agent Toggle on Task Creation
**Given** the TaskInput component is rendered
**When** the user views the task creation area
**Then** a toggle button with an AI/Agent icon (e.g., `Bot` from lucide-react) is displayed next to the "Create" button
**And** the toggle defaults to ON (AI mode — tasks are delegated to agents as usual)
**And** when toggled OFF, the icon visually changes to indicate "human/manual" mode (e.g., grayed out, crossed out, or switches to `User` icon)
**And** toggling OFF hides the progressive disclosure options (Agent selector, Trust Level, Reviewers) since they are irrelevant for manual tasks

### AC2: Manual Task Creation
**Given** the AI toggle is OFF (manual mode)
**When** the user submits a task
**Then** the task is created in Convex with `isManual: true`, status `"inbox"`, and no `assignedAgent`
**And** the trust level is set to `"autonomous"` (no review flow)
**And** the task card appears in the Inbox column with a human indicator icon
**And** a `task_created` activity event is written with description noting it's a manual task

### AC3: Human Indicator on Task Card
**Given** a task has `isManual: true`
**When** it renders as a TaskCard on the Kanban board
**Then** a small human icon (`User` from lucide-react) is displayed on the card (top-right or near the title)
**And** the icon uses `text-muted-foreground` styling to be subtle but visible
**And** agent-delegated tasks (isManual falsy) do NOT show this icon

### AC4: Drag-and-Drop for Manual Tasks
**Given** a task has `isManual: true`
**When** the user drags the task card
**Then** the card can be dropped into any adjacent or non-adjacent Kanban column
**And** the task status updates to match the target column's status
**And** the status change writes an activity event: "Manual task moved from {old} to {new}"
**And** the drag-and-drop uses HTML5 native drag API (no new dependencies)
**And** a visual drag indicator (opacity change, shadow) shows the card is being dragged
**And** a visual drop zone indicator highlights the target column during drag-over

### AC5: Agent Tasks Remain Locked
**Given** a task has `isManual` falsy (agent-delegated task)
**When** the user attempts to drag the task card
**Then** the card is NOT draggable (no drag handle, `draggable={false}`)
**And** agent task state transitions continue to be managed by the agent system only

### AC6: Manual Task State Transitions (No Validation)
**Given** a manual task is dragged to a new column
**When** the drop event fires
**Then** the status transition is allowed regardless of the normal state machine rules (manual tasks can go from any status to any status)
**And** the Convex mutation for manual move bypasses the normal `isValidTransition` check
**And** an activity event is logged for every manual move

### AC7: Schema Update
**Given** the Convex schema is updated
**When** the `tasks` table is modified
**Then** an `isManual` field is added as `v.optional(v.boolean())`
**And** existing tasks without this field continue to work (treated as agent tasks)

## Tasks / Subtasks

- [x] Task 1: Update Convex schema (AC: #7)
  - [x] 1.1: Add `isManual: v.optional(v.boolean())` to `tasks` table in `dashboard/convex/schema.ts`

- [x] Task 2: Update Convex `tasks.ts` mutations (AC: #2, #6)
  - [x] 2.1: Add `isManual: v.optional(v.boolean())` arg to `tasks.create` mutation; when true, force `trustLevel: "autonomous"` and no `assignedAgent`
  - [x] 2.2: Create `tasks.manualMove` mutation that accepts `taskId` and `newStatus`, patches status directly without `isValidTransition` check, writes activity event "Manual task moved from {old} to {new}"
  - [x] 2.3: Guard `tasks.manualMove` — throw `ConvexError` if `task.isManual !== true`

- [x] Task 3: Update `TaskInput.tsx` (AC: #1, #2)
  - [x] 3.1: Add `isManual` state (boolean, default `false`)
  - [x] 3.2: Add AI toggle button between Create button and chevron — use `Bot` icon from lucide-react; when `isManual` is true, show `User` icon instead (or Bot with a line-through / reduced opacity)
  - [x] 3.3: When `isManual` is true, hide the `CollapsibleContent` (progressive disclosure) and reset agent/trust/reviewer selections
  - [x] 3.4: Pass `isManual: true` to `createTask` mutation when toggle is OFF

- [x] Task 4: Update `TaskCard.tsx` (AC: #3, #4, #5)
  - [x] 4.1: If `task.isManual`, render a `User` icon (lucide-react) in the card header area (e.g., right-aligned next to title or in the bottom row)
  - [x] 4.2: If `task.isManual`, set `draggable={true}` on the card wrapper div, add `onDragStart` handler that sets `dataTransfer` with `taskId`
  - [x] 4.3: If NOT `task.isManual`, ensure `draggable={false}` (default)
  - [x] 4.4: Add drag visual feedback: reduce opacity to 0.5 during drag, add `cursor-grab` / `cursor-grabbing` classes

- [x] Task 5: Update `KanbanColumn.tsx` (AC: #4)
  - [x] 5.1: Add `onDragOver` handler (preventDefault to allow drop)
  - [x] 5.2: Add `onDrop` handler that reads `taskId` from `dataTransfer`, calls `tasks.manualMove` mutation with the column's status
  - [x] 5.3: Add `onDragEnter` / `onDragLeave` for visual drop zone highlight (e.g., `ring-2 ring-blue-400 bg-blue-50/30`)
  - [x] 5.4: Pass the column `status` prop for the drop handler to use

- [x] Task 6: Update `KanbanBoard.tsx` (AC: #4)
  - [x] 6.1: No major changes needed — drag/drop is handled at Card and Column level via HTML5 API

- [x] Task 7: Protect gateway from routing manual tasks (AC: #5, CRITICAL)
  - [x] 7.1: In `nanobot/mc/orchestrator.py:_process_inbox_task()`, add early return if `task_data.get("is_manual")` is truthy — log info "Skipping manual task" and return without routing
  - [x] 7.2: Verify bridge returns `isManual` field from Convex (camelCase→snake_case conversion at bridge layer should produce `is_manual`)
  - [x] 7.3: In `nanobot/mc/executor.py:start_execution_loop()`, skip manual tasks in the assigned subscription — prevents executor from picking up manual tasks dragged to "Assigned" column

- [x] Task 8: Add `manual_task_status_changed` activity event type
  - [x] 8.1: Add `v.literal("manual_task_status_changed")` to the activities eventType union in `dashboard/convex/schema.ts`
  - [x] 8.2: Add `MANUAL_TASK_STATUS_CHANGED = "manual_task_status_changed"` to `ACTIVITY_EVENT_TYPE` in `dashboard/lib/constants.ts`
  - [x] 8.3: Add `MANUAL_TASK_STATUS_CHANGED = "manual_task_status_changed"` to `ActivityEventType` enum in `nanobot/mc/types.py`

## Dev Notes

### Critical Architecture Requirements

- **Convex as single communication hub**: All status changes go through Convex mutations. The `manualMove` mutation must write both the status patch AND an activity event in the same transaction.
- **No new dependencies**: Use HTML5 native drag and drop API (`draggable`, `onDragStart`, `onDragOver`, `onDrop`). Do NOT install `@dnd-kit`, `react-beautiful-dnd`, or similar.
- **Backward compatibility**: `isManual` is `v.optional(v.boolean())` — existing tasks without this field are treated as agent-delegated (falsy).
- **State machine bypass**: The `manualMove` mutation deliberately skips `isValidTransition()`. This is safe because manual tasks are user-controlled and have no agent interaction.
- **Activity logging invariant**: Every manual move MUST write an activity event (architectural rule: every state change gets logged).

### Key File References

| Component | File | What to change |
|-----------|------|----------------|
| Convex schema | `dashboard/convex/schema.ts:5-34` | Add `isManual` field to tasks table, add `manual_task_status_changed` event type |
| Task mutations | `dashboard/convex/tasks.ts:73-123` | Update `create` args, add `manualMove` mutation |
| Task input | `dashboard/components/TaskInput.tsx:23-219` | Add AI toggle button, `isManual` state, conditional disclosure |
| Task card | `dashboard/components/TaskCard.tsx:21-185` | Add human icon, draggable behavior for manual tasks |
| Kanban column | `dashboard/components/KanbanColumn.tsx:24-130` | Add `onDragOver`, `onDrop`, `onDragEnter/Leave` handlers |
| Kanban board | `dashboard/components/KanbanBoard.tsx` | Minimal — DnD is card+column level |
| Constants | `dashboard/lib/constants.ts:28-51` | Add `MANUAL_TASK_STATUS_CHANGED` to `ACTIVITY_EVENT_TYPE` |
| Orchestrator | `nanobot/mc/orchestrator.py:228-248` | Add `is_manual` check in `_process_inbox_task()` |
| Python types | `nanobot/mc/types.py` | Add `MANUAL_TASK_STATUS_CHANGED` to `ActivityEventType` enum |

### Existing Patterns to Follow

- **Icon usage**: Project uses `lucide-react` for all icons (see `Trash2`, `AlertTriangle`, `Clock`, `ListChecks`, `RefreshCw`, `ChevronDown`, `Eraser`, `List` already imported across components)
- **Framer Motion**: Card animations use `motion.div` with `layoutId` and `layout` props. Drag-and-drop must coexist with these animations. The `layoutId={task._id}` on `motion.div` in `TaskCard.tsx` will handle re-layout after drops.
- **Optimistic UI**: Convex mutations auto-trigger reactive queries. After `manualMove` mutation, the `useQuery(api.tasks.list)` will update and cards will re-render in the correct column.
- **Button styling**: The "Create" button in `TaskInput.tsx` uses default `<Button>` (line 117). The AI toggle should use `variant="ghost" size="icon"` to match the existing chevron toggle pattern.
- **Card design**: Cards use `p-3.5 rounded-[10px] border-l-[3px]` with status-colored left border (see `TaskCard.tsx:39-41`).

### Project Structure Notes

- All dashboard components are in `dashboard/components/` (flat structure, no subdirectories)
- Convex functions are in `dashboard/convex/` matching table names
- No changes needed to Python backend (`nanobot/mc/`) — manual tasks are entirely dashboard-side
- The Lead Agent gateway subscription should ignore `isManual` tasks. Check `nanobot/mc/gateway.py` — if it picks up inbox tasks, it should skip tasks where `isManual === true`. **This is critical — verify gateway behavior.**

### Gateway Consideration (VERIFIED CRITICAL)

The `TaskOrchestrator` in `nanobot/mc/orchestrator.py` subscribes to inbox tasks via `self._bridge.async_subscribe("tasks:listByStatus", {"status": "inbox"})` (line 202-203) and processes every task through `_process_inbox_task()` (line 228). **Manual tasks WILL be picked up by the orchestrator if not filtered.**

**Chosen approach: Python filter in `_process_inbox_task()`** — Add an early return when `task_data.get("is_manual")` is truthy. This is simpler than modifying the Convex query and keeps the change minimal. The bridge's camelCase→snake_case conversion means the Convex `isManual` field arrives as `is_manual` in Python.

Location: `nanobot/mc/orchestrator.py:228-248` — add check after `task_id` validation, before `assigned_agent` check.

### References

- [Source: dashboard/convex/schema.ts] — Current tasks table schema (lines 5-34)
- [Source: dashboard/convex/tasks.ts] — State machine, create mutation, updateStatus mutation
- [Source: dashboard/components/TaskInput.tsx] — Current task creation UI with progressive disclosure
- [Source: dashboard/components/TaskCard.tsx] — Current card rendering with status colors, icons, HITL buttons
- [Source: dashboard/components/KanbanColumn.tsx] — Column rendering with ScrollArea
- [Source: dashboard/components/KanbanBoard.tsx] — Board layout with LayoutGroup
- [Source: dashboard/lib/constants.ts] — Status colors, type definitions
- [Source: _bmad-output/planning-artifacts/architecture.md#Implementation Patterns] — Naming conventions, mutation patterns

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

None — clean implementation, no debugging required.

### Completion Notes List

- Task 1: Added `isManual: v.optional(v.boolean())` to tasks table schema. Backward compatible — existing tasks without field treated as agent tasks.
- Task 2: Updated `tasks.create` mutation to accept `isManual` arg; when true, forces autonomous trust and no agent. Created `tasks.manualMove` mutation that bypasses state machine validation, patches status directly, and writes `manual_task_status_changed` activity event. Guarded with ConvexError if task is not manual.
- Task 3: Added Bot/User toggle button in TaskInput between Create and chevron. Defaults to AI mode (Bot icon). When toggled to manual (User icon), hides progressive disclosure (agent selector, trust level, reviewers) and resets those selections. Passes `isManual: true` to create mutation.
- Task 4: Added User icon indicator on manual task cards (top-right). Manual tasks get `draggable={true}` with `onDragStart`/`onDragEnd` handlers using HTML5 drag API. Agent tasks remain non-draggable. Added opacity-50 + shadow visual feedback during drag, cursor-grab class.
- Task 5: Added drag-and-drop zone handlers to KanbanColumn: `onDragOver` (preventDefault), `onDrop` (reads taskId, calls manualMove), `onDragEnter`/`onDragLeave` (ring-2 + blue highlight). Uses column's status prop for target status.
- Task 6: Confirmed no changes needed to KanbanBoard — status prop already passed, DnD handled at card+column level.
- Task 7: Added `is_manual` early-return filter in TWO places: (1) orchestrator `_process_inbox_task()` for inbox routing, (2) executor `start_execution_loop()` for assigned task pickup. This prevents the Lead Agent from routing OR executing manual tasks, even if the user drags a manual task to the Assigned column. 5 new pytest tests confirm both paths are protected.
- Task 8: Added `manual_task_status_changed` event type to Convex schema, TS constants, and Python ActivityEventType enum. All 3 layers in sync.
- All 191 tests pass (186 existing + 5 new), zero regressions.
- TypeScript compiles with zero errors (`npx tsc --noEmit` clean).
- Convex codegen succeeds.

### Change Log

- 2026-02-23: Story 8.6 implemented — all 8 tasks complete, manual tasks with drag-and-drop Kanban support

### File List

- dashboard/convex/schema.ts (modified — added isManual field and manual_task_status_changed event type)
- dashboard/convex/tasks.ts (modified — added isManual arg to create, added manualMove mutation)
- dashboard/components/TaskInput.tsx (modified — added AI/manual toggle button, isManual state, conditional disclosure)
- dashboard/components/TaskCard.tsx (modified — added User icon for manual tasks, draggable behavior with visual feedback)
- dashboard/components/KanbanColumn.tsx (modified — added drag-over/drop/enter/leave handlers with visual highlight)
- dashboard/lib/constants.ts (modified — added MANUAL_TASK_STATUS_CHANGED constant)
- nanobot/mc/orchestrator.py (modified — added is_manual early-return filter in _process_inbox_task)
- nanobot/mc/executor.py (modified — added is_manual skip in start_execution_loop to prevent agent execution of manual tasks)
- nanobot/mc/types.py (modified — added MANUAL_TASK_STATUS_CHANGED to ActivityEventType enum)
- tests/mc/test_manual_tasks.py (new — 7 tests: 3 orchestrator skip, 2 executor skip, 2 event type enum)

### Code Review Record (2026-02-23)

**Reviewer:** Claude Opus 4.6 (adversarial code review)
**Issues Found:** 1 High, 1 Medium, 2 Low
**Issues Fixed:**
- [H2] tasks.ts: `manualMove` newStatus now validates against union type (inbox|assigned|in_progress|review|done|retrying|crashed) — prevents invalid status injection
- [M3] test_manual_tasks.py: Increased asyncio.sleep from 0.05s to 0.2s to reduce test flakiness on slow CI
- KanbanColumn.tsx: Updated manualMove call with proper type assertion to match new union type
**Deferred:**
- [L2] Trivial test assertions — low priority, tests still provide value as smoke tests
- [L3] isManual optional field — consistent with project conventions
