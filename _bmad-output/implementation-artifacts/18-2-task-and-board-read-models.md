# Story 18.2: Task and Board Read Models

Status: ready-for-dev

## Story

As a **dashboard maintainer**,
I want aggregated read models,
so that the UI consumes view data instead of rebuilding domain state client-side.

## Acceptance Criteria

### AC1: tasks.getDetailView Query

**Given** the dashboard currently combines multiple queries to build task detail
**When** the read model is created
**Then** `tasks.getDetailView({ taskId })` returns a single aggregated object:
```typescript
{
  task, board, thread, steps, plan, files, tags, tagAttributes,
  uiFlags: { isAwaitingKickoff, isPaused, isManual, isPlanEditable },
  allowedActions: { approve, kickoff, pause, resume, retry, savePlan, startInbox, sendMessage }
}
```
**And** `uiFlags` are computed server-side based on task status and config
**And** `allowedActions` are computed server-side based on task status, board config, and user permissions

### AC2: boards.getBoardView Query

**Given** the dashboard currently assembles board view from multiple queries
**When** the read model is created
**Then** `boards.getBoardView({ boardId, freeText?, tagFilters?, attributeFilters? })` returns:
```typescript
{
  board, columns, groupedItems, favorites, deletedCount, hitlCount, searchMeta
}
```
**And** filtering by text, tags, and attributes is resolved server-side
**And** `columns` maps statuses to arrays of task/step cards
**And** `groupedItems` includes step-to-column mapping

### AC3: Backward Compatibility

**Given** existing queries still work
**When** the new read models are added
**Then** existing per-entity queries (tasks.get, steps.list, messages.list, etc.) continue to work
**And** no existing frontend code breaks
**And** the new queries are ADDITIONS, not replacements (yet)

### AC4: Performance

**Given** the aggregated queries
**When** they are called
**Then** they use efficient Convex indexing
**And** boards.getBoardView does NOT do N+1 queries for steps per task
**And** the queries use the internal modules from story 18.1

## Tasks / Subtasks

- [ ] **Task 1: Design read model schemas** (AC: #1, #2)
  - [ ] 1.1 Read current dashboard task detail components to understand data requirements
  - [ ] 1.2 Read current board/kanban components to understand data requirements
  - [ ] 1.3 Define TypeScript interfaces for TaskDetailView and BoardView return types
  - [ ] 1.4 Define uiFlags and allowedActions computation rules

- [ ] **Task 2: Implement tasks.getDetailView** (AC: #1)
  - [ ] 2.1 Create the query in `dashboard/convex/tasks.ts` (or a new read-model file)
  - [ ] 2.2 Aggregate: task + board + thread messages + steps + plan + files + tags + tagAttributes
  - [ ] 2.3 Compute uiFlags based on task status and board config
  - [ ] 2.4 Compute allowedActions based on task status, step states, and permissions
  - [ ] 2.5 Write tests for the query

- [ ] **Task 3: Implement boards.getBoardView** (AC: #2)
  - [ ] 3.1 Create the query in `dashboard/convex/boards.ts`
  - [ ] 3.2 Aggregate: board + all tasks + steps + favorites + deleted count + HITL count
  - [ ] 3.3 Implement server-side text search filtering
  - [ ] 3.4 Implement server-side tag and attribute filtering
  - [ ] 3.5 Implement step-to-column grouping
  - [ ] 3.6 Write tests for the query

- [ ] **Task 4: Verify backward compatibility** (AC: #3, #4)
  - [ ] 4.1 Verify existing queries unchanged
  - [ ] 4.2 Run full Convex test suite
  - [ ] 4.3 Run TypeScript type checking
  - [ ] 4.4 Verify no N+1 patterns in board query

## Dev Notes

### Architecture Patterns

**Read Model Pattern (CQRS-lite):** Read models are specialized queries that aggregate data for specific UI views. They don't replace the existing mutations or per-entity queries. They are ADDITIONS that the dashboard will progressively adopt.

**Uses internal modules from 18.1:** The read models should use the lifecycle helpers and workflow modules extracted in 18.1 for computing uiFlags and allowedActions.

**Key Files to Read First:**
- `dashboard/convex/tasks.ts` -- existing task queries
- `dashboard/convex/boards.ts` -- existing board queries
- `dashboard/convex/steps.ts` -- step queries
- `dashboard/convex/messages.ts` -- message queries
- `dashboard/convex/lib/` -- internal modules from 18.1
- Dashboard components that consume these queries

### Project Structure Notes

**Files to MODIFY:**
- `dashboard/convex/tasks.ts` -- add getDetailView query
- `dashboard/convex/boards.ts` -- add getBoardView query

**Files that may need creation:**
- Type definition files for read model return types

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log
