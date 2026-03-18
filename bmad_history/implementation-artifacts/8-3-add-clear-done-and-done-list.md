# Story 8.3: Add Clear Done and Done List

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want a "Clear" button on the Done column to bulk-remove completed tasks and a button to browse all completed tasks,
so that I can keep my Kanban board clean while still having access to my full task completion history.

## Acceptance Criteria

1. **Given** tasks exist in the Done column, **when** the user clicks the "Clear" button in the Done column header, **then** an inline confirmation prompt appears asking "Clear all done tasks?" with "Yes" and "Cancel" buttons.

2. **Given** the user confirms the clear action, **when** the bulk clear executes, **then** all tasks with status `"done"` are soft-deleted (status → `"deleted"`, `previousStatus` → `"done"`, `deletedAt` set), a single `bulk_clear_done` activity event is logged with the count of cleared tasks, and the tasks disappear from the Done column in real-time.

3. **Given** no tasks exist in the Done column, **when** the board renders, **then** the "Clear" button is hidden or disabled (not clickable).

4. **Given** the user clicks the "View All Done" button in the Done column header, **when** the Sheet opens, **then** it displays ALL tasks that have ever reached done status — both currently-done tasks on the board AND previously-cleared tasks (soft-deleted with `previousStatus === "done"`).

5. **Given** the Done Tasks Sheet is open, **when** the user views a task entry, **then** each entry shows: task title, assigned agent name, completion date (`updatedAt`), and current location indicator (either "On board" badge for active done tasks, or "Cleared" badge for soft-deleted ones).

6. **Given** the Done Tasks Sheet shows a cleared task, **when** the user clicks "Restore", **then** the task is restored to `"done"` status on the Kanban board (using existing `restore` mutation with `mode: "previous"`), and it reappears in the Done column in real-time.

7. **Given** the bulk clear completes, **when** the user opens the Trash Bin (existing feature), **then** the newly cleared tasks appear there alongside any other deleted tasks, each showing `previousStatus: "done"`.

8. **Given** the Done Tasks Sheet is open and shows both active and cleared tasks, **when** a task is cleared or restored, **then** the Sheet updates in real-time without requiring manual refresh (Convex reactivity).

## Tasks / Subtasks

- [ ] Task 1: Add `clearAllDone` mutation and `listDoneHistory` query to Convex (AC: #2, #4)
  - [ ] 1.1: Add `bulk_clear_done` to activity event type union in `convex/schema.ts` and `lib/constants.ts`
  - [ ] 1.2: Add `clearAllDone` mutation to `convex/tasks.ts` — iterates done tasks, patches each to `"deleted"` with `previousStatus: "done"`, writes single `bulk_clear_done` activity event with count
  - [ ] 1.3: Add `listDoneHistory` query to `convex/tasks.ts` — returns union of tasks with `status === "done"` AND tasks with `status === "deleted"` where `previousStatus === "done"`, sorted by `updatedAt` descending

- [ ] Task 2: Add "Clear" button with inline confirmation to Done column header (AC: #1, #2, #3)
  - [ ] 2.1: Extend `KanbanColumn` props with optional `onClear` callback and `clearDisabled` boolean
  - [ ] 2.2: Render "Clear" button (Eraser or X icon) in Done column header, after count badge — only when `onClear` is provided
  - [ ] 2.3: Add inline confirmation using Framer Motion expand/collapse (same pattern as TaskCard delete): "Clear all done tasks?" → "Yes" / "Cancel"
  - [ ] 2.4: Wire `KanbanBoard.tsx` to pass `onClear` callback (calling `clearAllDone` mutation) and `clearDisabled` (when done tasks count === 0) to the Done column

- [ ] Task 3: Create DoneTasksSheet component (AC: #4, #5, #6, #8)
  - [ ] 3.1: Create `components/DoneTasksSheet.tsx` following `TrashBinSheet` / `TaskDetailSheet` pattern (Sheet, side="right", 480px)
  - [ ] 3.2: Use `useQuery(api.tasks.listDoneHistory)` for reactive data
  - [ ] 3.3: Render task entries with: title, agent name, completion date, location badge ("On board" green / "Cleared" gray)
  - [ ] 3.4: For cleared tasks, show "Restore" button (Undo2 icon) calling `restore({ taskId, mode: "previous" })`
  - [ ] 3.5: Show empty state: "No completed tasks yet" when no done history exists

- [ ] Task 4: Add "View All Done" button to Done column header and wire DoneTasksSheet (AC: #4)
  - [ ] 4.1: Extend `KanbanColumn` props with optional `onViewAll` callback
  - [ ] 4.2: Render "View All" button (List or Archive icon) in Done column header, after Clear button
  - [ ] 4.3: Add `doneSheetOpen` state to `KanbanBoard.tsx` and wire to `DoneTasksSheet`
  - [ ] 4.4: Pass `onViewAll` callback to Done column that opens the sheet

## Dev Notes

### Architecture Patterns and Constraints

- **Transactional activity logging**: Every task state change MUST write an activity event in the same Convex mutation. For bulk clear, a SINGLE `bulk_clear_done` event with count is preferred over N individual `task_deleted` events, to avoid flooding the activity feed.
- **State machine**: `"deleted"` is already in `UNIVERSAL_TARGETS` — the transition `done → deleted` is already valid. No state machine changes needed.
- **Soft-delete semantics**: The `clearAllDone` mutation reuses the same `previousStatus` + `deletedAt` pattern from the existing `softDelete` mutation. Cleared tasks are indistinguishable from individually-deleted done tasks in the Trash Bin.
- **Reactive queries**: All components use `useQuery()` — the new `listDoneHistory` query will auto-update when tasks are cleared or restored.
- **500-line module limit**: `convex/tasks.ts` is approaching limits — keep the new mutations compact.

### Source Tree Components to Touch

| File | Action |
| ---- | ------ |
| `convex/schema.ts` | Add `v.literal("bulk_clear_done")` to activities `eventType` union |
| `convex/tasks.ts` | Add `clearAllDone` mutation + `listDoneHistory` query |
| `convex/activities.ts` | Update `eventType` type cast to include `"bulk_clear_done"` |
| `lib/constants.ts` | Add `BULK_CLEAR_DONE: "bulk_clear_done"` to `ACTIVITY_EVENT_TYPE` |
| `components/KanbanColumn.tsx` | Add optional `onClear`, `clearDisabled`, `onViewAll` props + header buttons + inline confirmation |
| `components/KanbanBoard.tsx` | Wire Clear and View All callbacks to Done column, add `DoneTasksSheet` state |
| `components/DoneTasksSheet.tsx` | **NEW** — Sheet listing all done task history with restore action |

### Testing Standards

- Vitest for dashboard component tests
- Test inline confirmation expand/collapse behavior
- Test bulk clear mutation logic (soft-delete all done tasks)
- Test `listDoneHistory` query returns both active done and cleared tasks
- Test empty state when no done tasks exist
- Test restore from DoneTasksSheet

### Existing Patterns to Follow

- **Inline confirmation**: Copy pattern from `TaskCard.tsx` lines 145-181 (Framer Motion expand/collapse with Yes/No buttons)
- **Sheet component**: Copy pattern from `TrashBinSheet.tsx` (480px right slide-out, ScrollArea, task list with action buttons)
- **Column header**: Follow `KanbanColumn.tsx` header pattern (flex row with dot + title + badge + conditional elements)
- **Activity event creation**: Follow `softDelete` mutation pattern in `tasks.ts` (insert activity with taskId, eventType, description, timestamp)
- **Icon styling**: Use same `h-3.5 w-3.5 text-muted-foreground hover:text-foreground transition-colors cursor-pointer` pattern from TaskCard icons

### Project Structure Notes

- All dashboard components in `dashboard/components/`
- Convex functions in `dashboard/convex/`
- Constants and utilities in `dashboard/lib/`
- Component tests co-located next to components (e.g., `KanbanColumn.test.tsx`)

### Implementation Sequence

Tasks 1 (backend) must complete before Tasks 2-4 (frontend), as the frontend depends on the new mutation and query. Tasks 2 and 3 can be developed in parallel. Task 4 wires everything together and depends on Tasks 2 and 3.

### References

- [Source: convex/tasks.ts — softDelete mutation] Pattern reference for individual soft-delete
- [Source: convex/tasks.ts — listDeleted query] Pattern reference for status-filtered queries
- [Source: components/TaskCard.tsx:145-181] Inline confirmation Framer Motion pattern
- [Source: components/KanbanColumn.tsx:42-56] Column header layout pattern
- [Source: components/TrashBinSheet.tsx] Sheet-based list with restore actions pattern
- [Source: lib/constants.ts:28-48] Activity event type constants
- [Source: tech-spec-task-soft-delete-and-restore.md] Foundation tech spec for soft-delete feature

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
