# Story 22.2: Close Dashboard Feature Convex Boundaries

Status: ready-for-dev

## Story

As a **frontend maintainer**,
I want feature components to stop importing `convex/react` directly,
so that dashboard data access is owned by feature hooks and the architecture guardrails can become fully strict.

## Acceptance Criteria

### AC1: Feature Components Stop Calling Convex Directly

**Given** some feature components still import `useQuery` or `useMutation` directly
**When** this story completes
**Then** affected feature components move that access behind feature hooks or typed action hooks
**And** no feature component imports `convex/react` directly.

### AC2: Dashboard Architecture Guardrail Turns Green

**Given** the current root repository fails `dashboard/tests/architecture.test.ts`
**When** this story completes
**Then** the architecture test passes without feature-component exceptions for direct Convex imports
**And** the failure in `PlanReviewPanel` is resolved through the owning feature hook layer rather than by weakening the test.

### AC3: Task and Plan Flows Preserve Behavior

**Given** the remaining violations are concentrated in task and plan components
**When** this story completes
**Then** `TaskDetailSheet`, `TaskCard`, `ExecutionPlanTab`, and `PlanReviewPanel` preserve their current behavior
**And** task approval, plan editing, kickoff, and plan-chat flows remain functional.

### AC4: Hook Ownership Becomes Clear

**Given** feature hooks are intended to own data access
**When** this story completes
**Then** queries and mutations used by these flows live in `dashboard/features/*/hooks`
**And** component logic becomes primarily compositional and presentational.

### AC5: Story Exit Gate Is Green

**Given** this story changes dashboard interaction paths
**When** the story closes
**Then** typecheck, targeted frontend tests, and `npm run test:architecture` pass
**And** `/code-review` is run
**And** Playwright smoke covers task open, execution plan, plan review, and thread interaction.

## Tasks / Subtasks

- [ ] **Task 1: Lock the boundary in tests** (AC: #1, #2)
  - [ ] 1.1 Remove remaining dashboard architecture-test exceptions for direct feature-component Convex imports
  - [ ] 1.2 Add or adjust focused component tests so behavior is pinned before refactor

- [ ] **Task 2: Move task-detail access behind hooks** (AC: #1, #3, #4)
  - [ ] 2.1 Extract direct `useQuery` and `useMutation` calls from `TaskDetailSheet`
  - [ ] 2.2 Ensure canonical task hooks own the required read and action paths

- [ ] **Task 3: Move plan and task-card mutations behind hooks** (AC: #1, #3, #4)
  - [ ] 3.1 Remove direct Convex access from `ExecutionPlanTab`
  - [ ] 3.2 Remove direct Convex access from `TaskCard`
  - [ ] 3.3 Remove direct Convex access from `PlanReviewPanel`

- [ ] **Task 4: Run the dashboard exit gate** (AC: #2, #3, #5)
  - [ ] 4.1 Run focused tests for task detail, task card, execution plan, and plan-review flows
  - [ ] 4.2 Run `npm run typecheck`
  - [ ] 4.3 Run `npm run test:architecture`
  - [ ] 4.4 Run `/code-review`
  - [ ] 4.5 Run Playwright smoke for task open, thread, execution plan, and plan review

## Dev Notes

### Architecture Patterns

- Feature hooks own Convex access. Feature components render and coordinate.
- Do not solve this by moving the same raw query/mutation logic into root `dashboard/hooks/*`.
- The target is stricter boundaries, not just a green test.

### Project Structure Notes

- The current failing guardrail is a useful red state and should remain strict.
- Keep this work concentrated in `dashboard/features/tasks/*` unless a shared hook is genuinely cross-feature.

### References

- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/tests/architecture.test.ts]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/features/README.md]
- [Source: /Users/ennio/Documents/nanobot-ennio/docs/ARCHITECTURE.md]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
