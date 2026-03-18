# Story 21.5: Migrate Dashboard Tasks, Boards and Thread Ownership

Status: ready-for-dev

## Story

As a **frontend maintainer**,
I want `tasks`, `boards`, and `thread` to become fully feature-owned,
so that the dashboard stops depending on root wrappers and large feature shells stop owning raw data access directly.

## Acceptance Criteria

### AC1: Core Task Feature Ownership

**Given** task-related UI still depends on large feature shells and root wrapper imports
**When** this story completes
**Then** `TaskDetailSheet`, `TaskCard`, `ExecutionPlanTab`, and `TaskInput` are owned under `dashboard/features/tasks/*`
**And** root wrapper files for those entry points are removed.

### AC2: Board and Thread Ownership

**Given** `boards` and `thread` are part of the same dashboard shell
**When** this story completes
**Then** `KanbanBoard`, `ThreadInput`, and `ThreadMessage` are imported from feature-owned locations only
**And** the dashboard shell composes them directly from `dashboard/features/*`.

### AC3: Feature Components Stop Owning Raw Convex Calls

**Given** the architecture intent is for feature hooks/view-models to own data access
**When** this story completes
**Then** direct `convex/react` usage is removed from affected feature components
**And** those calls move behind feature hooks or typed view/action hooks.

### AC4: UI Behavior Remains Intact

**Given** this is a structural migration
**When** the story completes
**Then** the dashboard preserves current task, plan, thread, and board behavior without a visual redesign.

### AC5: Wave Exit Quality Gate

**Given** the wave changes primary dashboard flows
**When** the story closes
**Then** frontend tests, typecheck, and architecture tests pass
**And** `/code-review` is run
**And** Playwright smoke validates board render, task open, thread reachability, and plan-tab reachability.

## Tasks / Subtasks

- [ ] **Task 1: Lock direct feature ownership in tests** (AC: #1, #2, #3)
  - [ ] 1.1 Update architecture tests to fail if root wrappers remain for tasks, boards, or thread
  - [ ] 1.2 Update component tests to import canonical feature paths directly

- [ ] **Task 2: Split the task-heavy feature shell** (AC: #1, #3, #4)
  - [ ] 2.1 Split `TaskDetailSheet` into feature-local subcomponents
  - [ ] 2.2 Move remaining direct Convex calls behind feature hooks
  - [ ] 2.3 Keep UI behavior and layout unchanged

- [ ] **Task 3: Migrate board and thread entry points** (AC: #2, #4)
  - [ ] 3.1 Update dashboard composition to import `KanbanBoard` from `features/boards`
  - [ ] 3.2 Update dashboard composition to import `ThreadInput` and `ThreadMessage` from `features/thread`
  - [ ] 3.3 Delete the corresponding root wrapper files

- [ ] **Task 4: Update the dashboard shell** (AC: #1, #2, #4)
  - [ ] 4.1 Make `DashboardLayout` compose feature entry points directly
  - [ ] 4.2 Remove any root-level alias imports for tasks, boards, and thread

- [ ] **Task 5: Run the wave exit gate** (AC: #5)
  - [ ] 5.1 Run focused frontend tests for task detail, task card, execution plan, board, and thread flows
  - [ ] 5.2 Run `npm run typecheck` and `npm run test:architecture`
  - [ ] 5.3 Run `/code-review`
  - [ ] 5.4 Run Playwright smoke on board load, task open, thread, and plan tab
  - [ ] 5.5 Commit the wave

## Dev Notes

### Architecture Patterns

- This story extends the earlier task-detail migration work by finishing ownership rather than leaving wrappers in place.
- Feature hooks should own Convex calls; feature components should be primarily presentational/compositional.
- Preserve the existing UX. No visual redesign is allowed in this migration story.

### Project Structure Notes

- Canonical roots: `dashboard/features/tasks`, `dashboard/features/boards`, `dashboard/features/thread`
- Root `dashboard/components/*` files for these entry points should be deleted, not left as permanent aliases.

### References

- [Source: docs/plans/2026-03-11-architecture-convergence-plan.md#Task-5-Wave-4---migrate-dashboard-ownership-for-tasks-boards-and-thread]
- [Source: _bmad-output/implementation-artifacts/18-3-task-detail-thread-plan-feature-migration.md]
- [Source: _bmad-output/implementation-artifacts/18-4-board-feature-migration.md]
- [Source: dashboard/tests/architecture.test.ts]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
