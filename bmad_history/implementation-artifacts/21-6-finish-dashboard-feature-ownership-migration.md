# Story 21.6: Finish Dashboard Feature Ownership Migration

Status: ready-for-dev

## Story

As a **frontend maintainer**,
I want the remaining dashboard features migrated to real feature ownership,
so that `app/*` becomes a thin shell and root `components`/`hooks` stop acting as a second architecture.

## Acceptance Criteria

### AC1: Remaining Feature Entry Points Moved

**Given** `agents`, `settings`, `search`, `activity`, and related flows still depend on root wrappers
**When** this story completes
**Then** those feature entry points are imported from `dashboard/features/*` directly
**And** their root wrapper files are removed.

### AC2: App Shell Becomes Thin

**Given** `DashboardLayout` still coordinates many root-level imports
**When** this story completes
**Then** the dashboard shell composes canonical feature entry points only
**And** no feature logic is reintroduced into `app/*` or root `components/*`.

### AC3: Root Hooks No Longer Own Feature Behavior

**Given** root hooks currently mirror feature ownership for several flows
**When** this story completes
**Then** those root hooks are deleted
**And** canonical hooks live only under their owning feature folders.

### AC4: Shared Root Surface Is Reduced

**Given** some root directories remain legitimate shared layers
**When** this story completes
**Then** root `dashboard/components/*` is limited to `ui/*`, `viewers/*`, and truly shared shell helpers
**And** root `dashboard/hooks/*` contains only non-feature shared utilities.

### AC5: Wave Exit Quality Gate

**Given** this wave changes broad dashboard composition
**When** it closes
**Then** lint, typecheck, tests, and architecture tests pass
**And** `/code-review` is run
**And** Playwright smoke validates settings, tags, search, and agent-sidebar flows.

## Tasks / Subtasks

- [ ] **Task 1: Update architecture tests to forbid remaining wrappers** (AC: #1, #3, #4)
  - [ ] 1.1 Tighten `dashboard/tests/architecture.test.ts`
  - [ ] 1.2 Remove accepted root wrapper paths for remaining features

- [ ] **Task 2: Migrate remaining feature entry points** (AC: #1, #2)
  - [ ] 2.1 Move agents entry points to canonical feature imports
  - [ ] 2.2 Move settings and tags entry points to canonical feature imports
  - [ ] 2.3 Move search and activity entry points to canonical feature imports
  - [ ] 2.4 Delete root wrapper components once imports are rewritten

- [ ] **Task 3: Delete root feature hooks** (AC: #3, #4)
  - [ ] 3.1 Remove root hooks that only proxy to feature hooks
  - [ ] 3.2 Update all imports to feature-owned hooks
  - [ ] 3.3 Keep only truly shared non-feature hooks at the root

- [ ] **Task 4: Slim the dashboard shell** (AC: #2, #4)
  - [ ] 4.1 Update `DashboardLayout` to compose feature entry points only
  - [ ] 4.2 Verify `app/page.tsx` remains a shell rather than a behavior owner

- [ ] **Task 5: Run the wave exit gate** (AC: #5)
  - [ ] 5.1 Run frontend lint, typecheck, tests, and architecture tests
  - [ ] 5.2 Run `/code-review`
  - [ ] 5.3 Run Playwright smoke on settings, tags, search, and agent sidebar
  - [ ] 5.4 Commit the wave

## Dev Notes

### Architecture Patterns

- The frontend target is a real feature-first structure, not a feature-first structure hidden behind root aliases.
- Preserve `components/ui/*` and `components/viewers/*` as shared primitives; do not push those into feature folders.
- Treat root `hooks/*` as suspicious by default; a root hook must justify being shared.

### Project Structure Notes

- Canonical locations are under `dashboard/features/*`.
- Delete wrappers when the migration is done; do not leave “temporary” aliases for future cleanup.

### References

- [Source: docs/plans/2026-03-11-architecture-convergence-plan.md#Task-6-Wave-5---finish-feature-ownership-for-the-remaining-dashboard-areas]
- [Source: dashboard/README.md#Ownership-Model]
- [Source: dashboard/tests/architecture.test.ts]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
