# Story 26.1: Split Dashboard Convex Task Hotspot

Status: ready-for-dev

## Story

As a **dashboard maintainer**,
I want the remaining oversized logic in `dashboard/convex/tasks.ts` split into cohesive helper owners,
so that task data behavior is easier to maintain without changing the public Convex contract.

## Acceptance Criteria

### AC1: A New Cohesive Task Seam Leaves `tasks.ts`

**Given** `dashboard/convex/tasks.ts` still owns too many unrelated responsibilities
**When** this story completes
**Then** at least one cohesive responsibility cluster is extracted into `dashboard/convex/lib/*`
**And** `tasks.ts` becomes thinner without changing the public `api.tasks.*` surface.

### AC2: Architecture Guardrails Reflect the New Seam

**Given** the hotspot split should be durable
**When** this story completes
**Then** the dashboard architecture tests enforce the presence of the extracted seam
**And** `tasks.ts` is prevented from reabsorbing the moved responsibility.

### AC3: Task Behavior Stays Green

**Given** task data behavior is heavily exercised by tests
**When** this story completes
**Then** focused task tests, dashboard typecheck, and dashboard architecture tests pass.

## Tasks / Subtasks

- [ ] **Task 1: Lock the split with tests first** (AC: #1, #2, #3)
  - [ ] 1.1 Add a failing guardrail or focused test for the next seam
  - [ ] 1.2 Confirm red before implementation

- [ ] **Task 2: Extract the next cohesive task seam** (AC: #1)
  - [ ] 2.1 Move the chosen task cluster into `dashboard/convex/lib/*`
  - [ ] 2.2 Keep the public `api.tasks.*` contract stable
  - [ ] 2.3 Reduce top-level coordination in `tasks.ts`

- [ ] **Task 3: Verify and review** (AC: #2, #3)
  - [ ] 3.1 Run focused task tests
  - [ ] 3.2 Run `npm run typecheck`
  - [ ] 3.3 Run `npm run test:architecture`
  - [ ] 3.4 Run `/code-review`

## Dev Notes

- Prefer extraction by ownership, not arbitrary line-count splitting.
- Keep read-models, restore/archive logic, and task mutation coordination in separate helpers when they are cohesive.

## References

- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/convex/tasks.ts]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/convex/tasks.test.ts]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/tests/architecture.test.ts]
