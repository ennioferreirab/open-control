# Story 18.3: Task Detail, Thread and Plan Feature Migration

Status: ready-for-dev

## Story

As a **frontend maintainer**,
I want task detail split into feature hooks and panels,
so that the UI stops owning domain logic.

## Acceptance Criteria

### AC1: Feature Hooks

**Given** TaskDetailSheet currently calls useQuery/useMutation directly
**When** the migration is complete
**Then** feature hooks exist:
- `useTaskDetailView(taskId)` -- wraps tasks.getDetailView, returns typed view data
- `useTaskDetailActions(taskId)` -- wraps task mutations (approve, kickoff, pause, resume, retry, etc.)
- `useThreadComposer(taskId)` -- thread input state, send logic, mention detection
- `usePlanEditorState(taskId)` -- plan editing state, save, validate
**And** the hooks encapsulate all Convex interactions

### AC2: TaskDetailSheet Becomes Presentational

**Given** TaskDetailSheet is a large monolithic component
**When** the migration is complete
**Then** TaskDetailSheet is composed of panels:
- Thread panel
- Plan/execution panel
- Config panel
- Files panel
**And** each panel receives data via props from hooks (not direct Convex calls)
**And** the component is mostly presentational (layout, composition)

### AC3: Composer Logic Extracted

**Given** ThreadInput currently manages its own state and mutations
**When** the migration is complete
**Then** useThreadComposer handles:
- Message draft state
- Send logic (mutation call)
- Mention detection and autocomplete
- Optimistic updates
**And** ThreadInput becomes a presentational component

### AC4: Plan Actions Extracted

**Given** plan editing logic is currently in the component
**When** the migration is complete
**Then** usePlanEditorState handles:
- Plan data loading
- Plan edit state (draft vs saved)
- Save mutation
- Validation
**And** ExecutionPlanTab becomes presentational

### AC5: No UI Redesign

**Given** this is a structural refactor
**When** the migration is complete
**Then** the user-visible UI is identical
**And** no layout, styling, or interaction changes occur

## Tasks / Subtasks

- [ ] **Task 1: Analyze TaskDetailSheet** (AC: #1, #2)
  - [ ] 1.1 Read `dashboard/components/TaskDetailSheet.tsx` completely
  - [ ] 1.2 Identify all useQuery and useMutation calls
  - [ ] 1.3 Identify all state management logic
  - [ ] 1.4 Map which queries/mutations belong to which feature hook

- [ ] **Task 2: Create useTaskDetailView hook** (AC: #1)
  - [ ] 2.1 Create `dashboard/hooks/useTaskDetailView.ts`
  - [ ] 2.2 Wrap tasks.getDetailView query (from 18.2)
  - [ ] 2.3 Provide typed return value with loading/error states
  - [ ] 2.4 Write tests

- [ ] **Task 3: Create useTaskDetailActions hook** (AC: #1)
  - [ ] 3.1 Create `dashboard/hooks/useTaskDetailActions.ts`
  - [ ] 3.2 Wrap all task action mutations (approve, kickoff, pause, resume, retry, delete, restore)
  - [ ] 3.3 Provide status-aware action availability (using allowedActions from view)
  - [ ] 3.4 Write tests

- [ ] **Task 4: Create useThreadComposer hook** (AC: #3)
  - [ ] 4.1 Create `dashboard/hooks/useThreadComposer.ts`
  - [ ] 4.2 Extract message draft state management
  - [ ] 4.3 Extract send logic and mention detection
  - [ ] 4.4 Write tests

- [ ] **Task 5: Create usePlanEditorState hook** (AC: #4)
  - [ ] 5.1 Create `dashboard/hooks/usePlanEditorState.ts`
  - [ ] 5.2 Extract plan editing state, save, validate
  - [ ] 5.3 Write tests

- [ ] **Task 6: Refactor TaskDetailSheet into panels** (AC: #2, #5)
  - [ ] 6.1 Refactor TaskDetailSheet to use feature hooks
  - [ ] 6.2 Extract thread panel as sub-component
  - [ ] 6.3 Extract plan/execution panel as sub-component
  - [ ] 6.4 Make ThreadInput presentational (uses useThreadComposer)
  - [ ] 6.5 Make ExecutionPlanTab presentational (uses usePlanEditorState)
  - [ ] 6.6 Verify UI is visually identical
  - [ ] 6.7 Run tests

## Dev Notes

### Architecture Patterns

**Feature Hook Pattern:** Each hook encapsulates one feature's data and actions. Components receive data via hooks or props, not direct Convex calls. This makes components testable and reusable.

**Depends on 18.2:** The useTaskDetailView hook wraps the getDetailView read model from 18.2. If 18.2 isn't merged yet, the hook can aggregate multiple existing queries as a temporary measure.

**Key Files to Read First:**
- `dashboard/components/TaskDetailSheet.tsx` -- the main component
- `dashboard/components/ThreadInput.tsx` or equivalent -- thread input component
- `dashboard/hooks/` -- existing hooks directory for patterns

### Project Structure Notes

**Files to CREATE:**
- `dashboard/hooks/useTaskDetailView.ts`
- `dashboard/hooks/useTaskDetailActions.ts`
- `dashboard/hooks/useThreadComposer.ts`
- `dashboard/hooks/usePlanEditorState.ts`

**Files to MODIFY:**
- `dashboard/components/TaskDetailSheet.tsx` -- major refactor
- Thread input component -- make presentational
- Execution plan component -- make presentational

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log
