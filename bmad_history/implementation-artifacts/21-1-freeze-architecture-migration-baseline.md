# Story 21.1: Freeze Architecture Migration Baseline

Status: ready-for-dev

## Story

As a **maintainer**,
I want a dedicated architecture-migration worktree and stricter baseline guardrails,
so that the aggressive refactor can proceed in isolation without new legacy regressions entering the main workspace.

## Acceptance Criteria

### AC1: Dedicated Migration Worktree

**Given** the migration will span multiple waves
**When** work begins
**Then** implementation happens in a dedicated git worktree on branch `codex/architecture-convergence`
**And** the worktree location is verified as ignored before creation
**And** the plan references the canonical worktree path.

### AC2: Baseline Verification Locked

**Given** the migration depends on tests rather than compatibility
**When** the wave starts
**Then** backend architecture tests and dashboard architecture tests are run from the fresh worktree
**And** the current baseline is recorded before code movement.

### AC3: Legacy Freeze Guardrails

**Given** the target is to eliminate legacy namespaces
**When** this story completes
**Then** new or strengthened tests forbid adding new imports against:
- `mc/services`
- `mc/workers`
- `mc/ask_user`
- `mc/mentions`
- root dashboard feature wrappers under `dashboard/components/*` and `dashboard/hooks/*`

### AC4: Migration Artifacts Published

**Given** the architecture convergence effort is approved
**When** this story completes
**Then** the design and implementation plan are saved under `docs/plans/`
**And** the wave-to-story mapping is visible in the implementation plan
**And** sprint tracking reflects the new epic and story set.

### AC5: Wave Exit Quality Gate

**Given** this is the setup wave
**When** the wave closes
**Then** the branch passes the baseline backend and frontend architecture suites
**And** `/code-review` is run on the setup diff
**And** a minimal Playwright smoke confirms the dashboard still loads from the migration worktree.

## Tasks / Subtasks

- [ ] **Task 1: Create and verify the dedicated worktree** (AC: #1)
  - [ ] 1.1 Verify `.worktrees` exists and is ignored by git
  - [ ] 1.2 Create `.worktrees/architecture-convergence` on `codex/architecture-convergence`
  - [ ] 1.3 Record the canonical worktree path in the migration plan

- [ ] **Task 2: Capture the clean baseline** (AC: #2)
  - [ ] 2.1 Run backend architecture guardrail tests from the worktree
  - [ ] 2.2 Run dashboard architecture tests from the worktree
  - [ ] 2.3 Run dashboard typecheck to catch baseline drift early

- [ ] **Task 3: Freeze new legacy usage** (AC: #3)
  - [ ] 3.1 Tighten `tests/mc/test_architecture.py`
  - [ ] 3.2 Tighten `tests/mc/test_module_reorganization.py`
  - [ ] 3.3 Tighten `dashboard/tests/architecture.test.ts`
  - [ ] 3.4 Update `docs/ARCHITECTURE.md` with migration intent where needed

- [ ] **Task 4: Publish migration artifacts and tracking** (AC: #4)
  - [ ] 4.1 Save the design document under `docs/plans/`
  - [ ] 4.2 Save the implementation plan under `docs/plans/`
  - [ ] 4.3 Add story decomposition to the plan
  - [ ] 4.4 Register Epic 21 in `_bmad-output/implementation-artifacts/sprint-status.yaml`

- [ ] **Task 5: Close the setup wave** (AC: #5)
  - [ ] 5.1 Re-run the baseline architecture suites
  - [ ] 5.2 Run `/code-review`
  - [ ] 5.3 Run a Playwright smoke that opens the dashboard from the worktree
  - [ ] 5.4 Commit the setup wave

## Dev Notes

### Architecture Patterns

- This story establishes the quality gate for the rest of Epic 21. No later story should begin without using the dedicated worktree.
- The guardrail-first approach matches the direction already documented in `docs/ARCHITECTURE.md` and the recent architecture cleanup work.
- Keep the worktree path stable across all Epic 21 stories: `/Users/ennio/Documents/nanobot-ennio/.worktrees/architecture-convergence`.

### Project Structure Notes

- Modify existing architecture test files rather than creating parallel guardrail suites.
- Keep story and plan artifacts under `docs/plans/` and `_bmad-output/implementation-artifacts/` only.
- Do not create a second migration worktree for this epic.

### References

- [Source: docs/plans/2026-03-11-architecture-convergence-design.md]
- [Source: docs/plans/2026-03-11-architecture-convergence-plan.md]
- [Source: docs/ARCHITECTURE.md#Overview]
- [Source: tests/mc/test_architecture.py]
- [Source: dashboard/tests/architecture.test.ts]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
