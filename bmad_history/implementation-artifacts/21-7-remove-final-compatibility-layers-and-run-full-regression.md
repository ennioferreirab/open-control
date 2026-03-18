# Story 21.7: Remove Final Compatibility Layers and Run Full Regression

Status: ready-for-dev

## Story

As a **maintainer**,
I want the final compatibility layers removed and the whole migration closed with full verification,
so that the documented architecture becomes the only architecture and the branch is ready to integrate.

## Acceptance Criteria

### AC1: Final Compatibility Layers Deleted

**Given** previous stories complete the ownership moves
**When** this story completes
**Then** any remaining compatibility-only backend or frontend wrappers are deleted
**And** no imports remain from removed namespaces or deleted root wrappers.

### AC2: Permanent Guardrails Enforced

**Given** the migration target is final
**When** this story completes
**Then** backend and frontend architecture tests treat the new boundaries as permanent rules
**And** temporary exceptions from the migration are removed.

### AC3: Architecture Documentation Matches Reality

**Given** the code structure changed materially
**When** this story completes
**Then** `docs/ARCHITECTURE.md` and any high-level references reflect the final ownership model without transition caveats.

### AC4: Full Regression Green

**Given** this story closes the epic
**When** the wave finishes
**Then** the full backend pytest suite passes
**And** dashboard lint, typecheck, test, and architecture test suites pass
**And** sensitive flows are covered by final smoke validation.

### AC5: Final Review and Smoke Complete

**Given** the branch is intended for integration after this story
**When** the story closes
**Then** `/code-review` is run on the final diff
**And** Playwright smoke covers the main dashboard journey end-to-end
**And** the branch history is ready for merge or PR preparation.

## Tasks / Subtasks

- [ ] **Task 1: Delete remaining compatibility-only code** (AC: #1)
  - [ ] 1.1 Grep for remaining compatibility markers and legacy import paths
  - [ ] 1.2 Remove final backend wrappers
  - [ ] 1.3 Remove final frontend wrappers
  - [ ] 1.4 Re-run focused tests after each deletion batch

- [ ] **Task 2: Harden guardrails to the final architecture** (AC: #2)
  - [ ] 2.1 Remove temporary exceptions from backend architecture tests
  - [ ] 2.2 Remove temporary exceptions from dashboard architecture tests
  - [ ] 2.3 Ensure the tests fail on any reintroduction of deleted paths

- [ ] **Task 3: Finalize docs and references** (AC: #3)
  - [ ] 3.1 Update `docs/ARCHITECTURE.md`
  - [ ] 3.2 Update any root-level references in `README.md` if needed
  - [ ] 3.3 Ensure the implementation plan still matches the final wave outcomes

- [ ] **Task 4: Run the full regression gate** (AC: #4, #5)
  - [ ] 4.1 Run full backend pytest
  - [ ] 4.2 Run dashboard lint, typecheck, test, and architecture test suites
  - [ ] 4.3 Run `/code-review`
  - [ ] 4.4 Run final Playwright smoke on load, board, open task, thread, plan, settings, tags, search, and agent sidebar
  - [ ] 4.5 Record the verification summary

- [ ] **Task 5: Prepare integration** (AC: #5)
  - [ ] 5.1 Review branch history for wave clarity
  - [ ] 5.2 Prepare merge or PR summary organized by stories/waves
  - [ ] 5.3 Commit final cleanup and integration prep

## Dev Notes

### Architecture Patterns

- This story is the “no caveats left” pass. If a wrapper or exception still exists only for migration convenience, delete it here.
- Avoid adding new abstraction for the sole purpose of preserving compatibility; the goal is removal.
- Verification is part of the deliverable, not an afterthought.

### Project Structure Notes

- Grep both backend and frontend for deleted namespace imports before calling the migration complete.
- Keep the dedicated worktree until merge/PR prep is finished; remove it only after integration.

### References

- [Source: docs/plans/2026-03-11-architecture-convergence-plan.md#Task-7-Wave-6---delete-final-compatibility-layers-and-tighten-the-permanent-guardrails]
- [Source: docs/ARCHITECTURE.md]
- [Source: _bmad-output/implementation-artifacts/19-1-legacy-removal-guardrails-regression-hardening.md]
- [Source: dashboard/tests/architecture.test.ts]
- [Source: tests/mc/test_architecture.py]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
