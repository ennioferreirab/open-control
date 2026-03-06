# Story 18.4: Board Feature Migration

Status: ready-for-dev

## Story

As a **frontend maintainer**,
I want the board page backed by a board view model,
so that kanban search/filter/grouping stops living inside the component tree.

## Acceptance Criteria

### AC1: useBoardView Hook

**Given** KanbanBoard currently assembles board data from multiple queries
**When** the migration is complete
**Then** `useBoardView(boardId)` wraps `boards.getBoardView` query (from 18.2)
**And** returns typed board view with columns, grouped items, favorites, counts
**And** handles loading and error states

### AC2: useBoardFilters Hook

**Given** search and filter logic lives inside the KanbanBoard component
**When** the migration is complete
**Then** `useBoardFilters()` manages:
- Free text search state
- Tag filter state
- Attribute filter state
- Filter application (sends filter params to getBoardView)
**And** filters are passed as query parameters to the read model

### AC3: useBoardColumns Hook

**Given** step-to-column mapping and column assembly is complex component logic
**When** the migration is complete
**Then** `useBoardColumns(boardView)` handles:
- Column arrangement from board view data
- Step-to-column grouping
- Task card preparation
**And** the component just renders what the hook provides

### AC4: KanbanBoard Becomes Presentational

**Given** KanbanBoard currently contains data assembly, search, filtering, and multi-query orchestration
**When** the migration is complete
**Then** KanbanBoard is primarily presentational:
- Renders columns from useBoardColumns
- Renders filter UI from useBoardFilters
- Delegates actions to hooks
**And** it does NOT directly call useQuery or useMutation for board data

### AC5: Behavior Preserved

**Given** this is a structural refactor
**When** the migration is complete
**Then** current behavior is preserved:
- Favorites display and toggle
- Trash/deleted tasks handling
- Done sheet behavior
- Board selection/switching
- HITL indicators
- Real-time updates
**And** no UI changes are visible to users

## Tasks / Subtasks

- [ ] **Task 1: Analyze KanbanBoard** (AC: #1, #4)
  - [ ] 1.1 Read the main KanbanBoard component completely
  - [ ] 1.2 Identify all useQuery/useMutation calls
  - [ ] 1.3 Identify search/filter/grouping logic
  - [ ] 1.4 Map which logic goes to which hook

- [ ] **Task 2: Create useBoardView hook** (AC: #1)
  - [ ] 2.1 Create `dashboard/hooks/useBoardView.ts`
  - [ ] 2.2 Wrap boards.getBoardView query (from 18.2)
  - [ ] 2.3 Provide typed return value with loading/error states
  - [ ] 2.4 Write tests

- [ ] **Task 3: Create useBoardFilters hook** (AC: #2)
  - [ ] 3.1 Create `dashboard/hooks/useBoardFilters.ts`
  - [ ] 3.2 Manage filter state (text, tags, attributes)
  - [ ] 3.3 Integrate filter params with getBoardView query
  - [ ] 3.4 Write tests

- [ ] **Task 4: Create useBoardColumns hook** (AC: #3)
  - [ ] 4.1 Create `dashboard/hooks/useBoardColumns.ts`
  - [ ] 4.2 Extract column arrangement and grouping logic
  - [ ] 4.3 Write tests

- [ ] **Task 5: Refactor KanbanBoard** (AC: #4, #5)
  - [ ] 5.1 Replace direct queries with hook usage
  - [ ] 5.2 Remove step-to-column logic from component
  - [ ] 5.3 Remove search/filter assembly from component
  - [ ] 5.4 Preserve favorites, trash, done sheet, board selection, HITL
  - [ ] 5.5 Verify UI is visually identical
  - [ ] 5.6 Run tests

## Dev Notes

### Architecture Patterns

**Feature Hook Pattern:** Same pattern as 18.3 but for the board page. Hooks own data and logic; components own rendering.

**Depends on 18.2:** The useBoardView hook wraps the getBoardView read model from 18.2.

**Key Files to Read First:**
- Main KanbanBoard component (find via grep for "KanbanBoard")
- Board-related components in `dashboard/components/`
- `dashboard/convex/boards.ts` -- board queries
- `dashboard/hooks/` -- existing hook patterns

### Project Structure Notes

**Files to CREATE:**
- `dashboard/hooks/useBoardView.ts`
- `dashboard/hooks/useBoardFilters.ts`
- `dashboard/hooks/useBoardColumns.ts`

**Files to MODIFY:**
- KanbanBoard component -- major refactor to use hooks

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log
