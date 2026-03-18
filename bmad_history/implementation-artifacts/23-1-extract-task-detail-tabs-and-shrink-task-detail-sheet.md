# Story 23.1: Extract Task Detail Tabs and Shrink TaskDetailSheet

Status: done

## Story

As a **frontend maintainer**,
I want `TaskDetailSheet` split into local task-detail owners,
so that the largest remaining dashboard god file becomes easier to reason about and modify without re-spreading responsibility.

## Acceptance Criteria

### AC1: Thread, Config, and Files Tabs Become Explicit Owners

**Given** `dashboard/features/tasks/components/TaskDetailSheet.tsx` still owns too much mixed UI and state wiring
**When** this story completes
**Then** the thread, config, and files sections are extracted into dedicated task-detail subcomponents
**And** those subcomponents own only the behavior for their tab surface.

### AC2: TaskDetailSheet Becomes a Shell for Composition

**Given** `TaskDetailSheet` should coordinate high-level task detail flow rather than render every sub-surface inline
**When** this story completes
**Then** `TaskDetailSheet` primarily composes extracted tab owners and shared hooks
**And** its size and mixed responsibility are materially reduced.

### AC3: Current Epic 22 Boundaries Stay Intact

**Given** Epic 22 already established canonical feature hooks and internal Convex splits
**When** this story completes
**Then** the extraction does not reintroduce root wrappers, root hook aliases, or direct `convex/react` imports into feature components
**And** the current committed Playwright regression remains valid.

### AC4: Architecture Guardrails Reflect the New Structure

**Given** this extraction is part of the convergence cleanup
**When** this story completes
**Then** dashboard architecture tests assert the existence and usage of the new task-detail tab owners
**And** guardrails catch any attempt to collapse those responsibilities back into `TaskDetailSheet`.

### AC5: Story Exit Gate Is Green

**Given** this story changes the task detail surface deeply
**When** the story closes
**Then** targeted dashboard tests, `npm run typecheck`, `npm run test:architecture`, and the committed Playwright regression pass
**And** `/code-review` is run
**And** verification evidence is recorded.

## Tasks / Subtasks

- [ ] **Task 1: Carve out task-detail tab owners** (AC: #1, #2)
  - [ ] 1.1 Extract a thread-tab owner from `TaskDetailSheet`
  - [ ] 1.2 Extract a config-tab owner from `TaskDetailSheet`
  - [ ] 1.3 Extract a files-tab owner from `TaskDetailSheet`

- [ ] **Task 2: Recompose TaskDetailSheet around those seams** (AC: #1, #2, #3)
  - [ ] 2.1 Keep `TaskDetailSheet` responsible for top-level coordination only
  - [ ] 2.2 Preserve current hooks, action flow, and task open behavior
  - [ ] 2.3 Avoid reintroducing root wrappers or direct Convex component coupling

- [ ] **Task 3: Tighten guardrails and tests** (AC: #3, #4, #5)
  - [ ] 3.1 Update dashboard architecture tests to require the new extracted tab owners
  - [ ] 3.2 Update focused tests around task detail tags, thread, files, and config flows
  - [ ] 3.3 Run `/code-review`

- [ ] **Task 4: Run the story exit gate** (AC: #5)
  - [ ] 4.1 Run `npm run typecheck`
  - [ ] 4.2 Run focused task detail tests and `npm run test:architecture`
  - [ ] 4.3 Run `npm run test:e2e`
  - [ ] 4.4 Record verification evidence and residual risks

## Dev Notes

### Architecture Patterns

- Extract by task-detail responsibility, not by visual section alone.
- Keep task detail ownership inside `dashboard/features/tasks/*`.
- Do not collapse the extraction back into generic helpers or shared root modules.

### Project Structure Notes

- Current canonical owner: `/Users/ennio/Documents/nanobot-ennio/dashboard/features/tasks/components/TaskDetailSheet.tsx`
- Preserve Epic 22 seams under `dashboard/features/tasks/hooks/*`.
- The convergence worktree already demonstrated the target split concept; implement it from `main`, not by copying the whole worktree wholesale.

### References

- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/features/tasks/components/TaskDetailSheet.tsx]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/tests/architecture.test.ts]
- [Source: /Users/ennio/Documents/nanobot-ennio/docs/ARCHITECTURE.md]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
