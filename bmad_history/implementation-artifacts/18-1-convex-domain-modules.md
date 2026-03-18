# Story 18.1: Convex Domain Modules

Status: ready-for-dev

## Story

As a **maintainer**,
I want Convex business logic split by capability,
so that tasks.ts and steps.ts stop being monoliths.

## Acceptance Criteria

### AC1: Task Lifecycle Module

**Given** `dashboard/convex/tasks.ts` contains monolithic business logic
**When** the split is complete
**Then** `dashboard/convex/lib/taskLifecycle.ts` contains:
- Task status validation logic (extracted from mutations)
- Task status transition helpers
- Activity event creation for task status changes
**And** `tasks.ts` mutations delegate to these helpers
**And** all mutation names remain unchanged (public API preserved)

### AC2: Step Lifecycle Module

**Given** `dashboard/convex/steps.ts` contains monolithic business logic
**When** the split is complete
**Then** `dashboard/convex/lib/stepLifecycle.ts` contains:
- Step status validation logic
- Step status transition helpers
- Activity event creation for step status changes
**And** `steps.ts` mutations delegate to these helpers
**And** all mutation names remain unchanged

### AC3: Shared Workflow Helpers

**Given** tasks and steps share validation patterns
**When** the split is complete
**Then** `dashboard/convex/lib/workflowHelpers.ts` contains:
- Shared status validation utilities
- Activity logger (unified activity event creation)
- Common validation patterns (e.g., entity exists check, permission check)
**And** both taskLifecycle and stepLifecycle use these shared helpers

### AC4: Thread Mutation Module

**Given** `dashboard/convex/messages.ts` contains thread-related logic mixed with general message handling
**When** the split is complete
**Then** thread rules and thread mutation logic are organized in `dashboard/convex/lib/threadRules.ts`
**And** `messages.ts` remains the public entrypoint but delegates complex logic

### AC5: Public API Preserved

**Given** this is an internal refactor
**When** all modules are extracted
**Then** ALL current mutation and query names in `tasks.ts`, `steps.ts`, and `messages.ts` remain unchanged
**And** no external consumer (frontend or Python backend) needs to change
**And** all existing tests pass without modification

### AC6: Unified Status Change Pattern

**Given** the extracted modules
**When** any mutation changes task or step status
**Then** it uses a single unified pattern: validate transition → apply change → log activity event
**And** this pattern is enforced through the shared helpers

## Tasks / Subtasks

- [ ] **Task 1: Analyze current Convex monoliths** (AC: #1, #2, #4)
  - [ ] 1.1 Read `dashboard/convex/tasks.ts` completely -- categorize: status mutations, CRUD, validation, activity logging
  - [ ] 1.2 Read `dashboard/convex/steps.ts` completely -- same categorization
  - [ ] 1.3 Read `dashboard/convex/messages.ts` completely -- identify thread rules vs general messaging
  - [ ] 1.4 Read `dashboard/convex/activities.ts` -- understand activity logging patterns
  - [ ] 1.5 Document what goes into each new module

- [ ] **Task 2: Create shared workflow helpers** (AC: #3, #6)
  - [ ] 2.1 Create `dashboard/convex/lib/` directory (if not exists)
  - [ ] 2.2 Create `dashboard/convex/lib/workflowHelpers.ts` with shared validation utilities
  - [ ] 2.3 Create unified activity logger helper
  - [ ] 2.4 Create common validation patterns (entity exists, valid transition)
  - [ ] 2.5 Write tests for shared helpers

- [ ] **Task 3: Extract task lifecycle** (AC: #1)
  - [ ] 3.1 Create `dashboard/convex/lib/taskLifecycle.ts`
  - [ ] 3.2 Extract task status validation from `tasks.ts` mutations
  - [ ] 3.3 Extract task status transition helpers
  - [ ] 3.4 Extract task activity event creation
  - [ ] 3.5 Update `tasks.ts` to delegate to taskLifecycle
  - [ ] 3.6 Write tests for task lifecycle module
  - [ ] 3.7 Verify all task mutation names unchanged

- [ ] **Task 4: Extract step lifecycle** (AC: #2)
  - [ ] 4.1 Create `dashboard/convex/lib/stepLifecycle.ts`
  - [ ] 4.2 Extract step status validation from `steps.ts` mutations
  - [ ] 4.3 Extract step status transition helpers
  - [ ] 4.4 Extract step activity event creation
  - [ ] 4.5 Update `steps.ts` to delegate to stepLifecycle
  - [ ] 4.6 Write tests for step lifecycle module
  - [ ] 4.7 Verify all step mutation names unchanged

- [ ] **Task 5: Extract thread rules** (AC: #4)
  - [ ] 5.1 Create `dashboard/convex/lib/threadRules.ts`
  - [ ] 5.2 Extract thread mutation logic and validation rules
  - [ ] 5.3 Update `messages.ts` to delegate to threadRules
  - [ ] 5.4 Write tests for thread rules

- [ ] **Task 6: Final verification** (AC: #5)
  - [ ] 6.1 Run full Convex test suite (npx vitest or equivalent)
  - [ ] 6.2 Verify ALL public mutation/query names unchanged via grep
  - [ ] 6.3 Run TypeScript type checking
  - [ ] 6.4 Verify no frontend changes needed

## Dev Notes

### Architecture Patterns

**Internal Module Pattern:** The `lib/` directory contains INTERNAL modules that are NOT directly exposed as Convex functions. Only the top-level files (tasks.ts, steps.ts, messages.ts) register Convex queries/mutations. The lib modules are pure TypeScript helpers.

**Depends on Story 15.1:** If the shared workflow contract from 15.1 is merged, the lifecycle modules should use `workflowContract.ts` for transition validation instead of hardcoded maps. If not yet merged, use local validation that can be easily swapped later.

**Testing in Convex:** Convex tests typically use `convex-test` library. Check `dashboard/convex/*.test.ts` for existing patterns.

**Key Files to Read First:**
- `dashboard/convex/tasks.ts` -- task monolith
- `dashboard/convex/steps.ts` -- step monolith
- `dashboard/convex/messages.ts` -- message/thread logic
- `dashboard/convex/activities.ts` -- activity logging
- `dashboard/convex/lib/` -- check if lib/ already exists with anything

### Project Structure Notes

**Files to CREATE:**
- `dashboard/convex/lib/workflowHelpers.ts`
- `dashboard/convex/lib/taskLifecycle.ts`
- `dashboard/convex/lib/stepLifecycle.ts`
- `dashboard/convex/lib/threadRules.ts`
- Test files for each module

**Files to MODIFY:**
- `dashboard/convex/tasks.ts` -- delegate to lifecycle module
- `dashboard/convex/steps.ts` -- delegate to lifecycle module
- `dashboard/convex/messages.ts` -- delegate to thread rules

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log
