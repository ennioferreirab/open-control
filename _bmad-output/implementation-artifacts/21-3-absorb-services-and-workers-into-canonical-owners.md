# Story 21.3: Absorb Services and Workers into Canonical Owners

Status: ready-for-dev

## Story

As a **backend maintainer**,
I want `services` and legacy `workers` absorbed into their canonical owners,
so that `contexts` and `runtime` become the only real ownership layers for behavior and composition.

## Acceptance Criteria

### AC1: Service Layer Eliminated

**Given** `mc/services/*` duplicates ownership already claimed by canonical packages
**When** this story completes
**Then** service modules are absorbed into `mc.contexts.*` or `mc.infrastructure.*`
**And** no imports remain from `mc.services.*`
**And** the `mc/services` package is removed.

### AC2: Runtime Workers Become Canonical

**Given** worker implementations currently live under a legacy namespace
**When** the migration completes
**Then** all concrete worker implementations live under `mc/runtime/workers/*`
**And** `mc/runtime.orchestrator` imports those canonical workers directly
**And** the legacy `mc/workers/*` package is removed.

### AC3: Runtime Stays Composition-Only

**Given** runtime should compose flows rather than own domain logic
**When** this story completes
**Then** `mc/runtime/gateway.py` and `mc/runtime/orchestrator.py` depend only on canonical contexts/runtime worker modules
**And** no new business logic is added to runtime as part of the move.

### AC4: Regression and Guardrails Pass

**Given** these modules sit on core execution paths
**When** the wave finishes
**Then** worker tests, process-monitor tests, and backend architecture guardrail tests pass from the migration worktree.

### AC5: Wave Exit Quality Gate

**Given** each wave must be reviewable
**When** the story closes
**Then** `/code-review` is run
**And** Playwright smoke confirms the dashboard still renders the board and task list after the backend composition changes.

## Tasks / Subtasks

- [ ] **Task 1: Remove service imports from tests and call sites** (AC: #1)
  - [ ] 1.1 Rewrite `test_module_reorganization` to stop allowing `mc.services.*`
  - [ ] 1.2 Rewrite import sites to use canonical contexts
  - [ ] 1.3 Delete legacy service re-exports

- [ ] **Task 2: Absorb service implementations into owning contexts** (AC: #1, #3)
  - [ ] 2.1 Merge conversation services into `mc.contexts.conversation`
  - [ ] 2.2 Merge plan negotiation into `mc.contexts.planning`
  - [ ] 2.3 Merge crash recovery into `mc.contexts.execution`
  - [ ] 2.4 Merge agent sync into `mc.contexts.agents`
  - [ ] 2.5 Delete `mc/services/*`

- [ ] **Task 3: Move concrete workers under runtime/workers** (AC: #2, #3)
  - [ ] 3.1 Create concrete worker modules under `mc/runtime/workers/*`
  - [ ] 3.2 Update `mc/runtime/orchestrator.py` to use them directly
  - [ ] 3.3 Delete `mc/workers/*`

- [ ] **Task 4: Harden architecture boundaries** (AC: #3, #4)
  - [ ] 4.1 Update backend architecture tests to forbid `mc.services.*`
  - [ ] 4.2 Update module reorganization tests to forbid `mc.workers.*`
  - [ ] 4.3 Refresh `docs/ARCHITECTURE.md` to describe the canonical ownership

- [ ] **Task 5: Run the wave exit gate** (AC: #4, #5)
  - [ ] 5.1 Run focused pytest targets for workers and process-monitor coverage
  - [ ] 5.2 Run backend architecture guardrail tests
  - [ ] 5.3 Run `/code-review`
  - [ ] 5.4 Run a Playwright smoke on board load and task list visibility
  - [ ] 5.5 Commit the wave

## Dev Notes

### Architecture Patterns

- `runtime` composes; `contexts` own behavior. This story exists to make that true in code, not just in docs.
- Avoid creating a new “shared service” layer under another name. If behavior has an owner, move it there.
- Preserve test clarity by rewriting imports first so failures point to missing ownership changes immediately.

### Project Structure Notes

- Delete both `mc/services/*` and `mc/workers/*` by story end.
- Keep `mc/runtime/workers/__init__.py` as a package entry point if needed, but not as a legacy adapter to old modules.

### References

- [Source: docs/plans/2026-03-11-architecture-convergence-plan.md#Task-3-Wave-2---absorb-services-and-workers-into-canonical-owners]
- [Source: docs/ARCHITECTURE.md#Backend-Structure]
- [Source: tests/mc/test_module_reorganization.py]
- [Source: tests/mc/test_process_monitor_decomposition.py]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
