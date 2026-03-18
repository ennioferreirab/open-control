# Story 21.4: Split Backend Runtime and Execution Hotspots

Status: ready-for-dev

## Story

As a **backend maintainer**,
I want the large runtime, execution, and bridge hotspots split by responsibility,
so that backend cohesion improves and Convex access stops leaking across unrelated concerns.

## Acceptance Criteria

### AC1: Gateway Responsibilities Reduced

**Given** `mc/runtime/gateway.py` currently mixes polling config, cron delivery, task requeue, and lifecycle wiring
**When** this story completes
**Then** those concerns are extracted into focused runtime modules
**And** `gateway.py` remains a composition root instead of a god module.

### AC2: Executor Responsibilities Reduced

**Given** `mc/contexts/execution/executor.py` owns multiple unrelated helpers
**When** this story completes
**Then** provider-error policy, agent-run plumbing, message building, and session-key logic live in focused execution modules
**And** the executor becomes materially smaller and easier to reason about.

### AC3: Bridge Surface Becomes Thinner

**Given** `mc/bridge/__init__.py` behaves as a giant super-facade
**When** this story completes
**Then** focused repositories and adapters own data-access responsibilities
**And** the package facade becomes thinner without reintroducing raw Convex imports elsewhere.

### AC4: Backend Full Suite Passes

**Given** these modules affect core orchestration paths
**When** the refactor completes
**Then** the backend pytest suite passes from the migration worktree.

### AC5: Wave Exit Quality Gate

**Given** the wave touches critical runtime code
**When** the story closes
**Then** `/code-review` is run
**And** Playwright smoke confirms the dashboard still loads and basic task open flows survive the backend refactor.

## Tasks / Subtasks

- [ ] **Task 1: Lock the hotspot split in tests** (AC: #1, #2, #3)
  - [ ] 1.1 Add or strengthen architecture assertions around gateway responsibilities
  - [ ] 1.2 Add or strengthen architecture assertions around executor helper leakage
  - [ ] 1.3 Add or strengthen architecture assertions around bridge package surface

- [ ] **Task 2: Split runtime gateway responsibilities** (AC: #1)
  - [ ] 2.1 Extract polling settings logic
  - [ ] 2.2 Extract cron delivery logic
  - [ ] 2.3 Extract task requeue helpers
  - [ ] 2.4 Keep `mc/runtime/gateway.py` as orchestration-only composition

- [ ] **Task 3: Split execution responsibilities** (AC: #2)
  - [ ] 3.1 Extract provider error policy
  - [ ] 3.2 Extract agent-run plumbing
  - [ ] 3.3 Extract task message and session-key helpers
  - [ ] 3.4 Update execution imports to use the focused modules

- [ ] **Task 4: Thin the bridge facade** (AC: #3)
  - [ ] 4.1 Move settings/data-access helpers into focused bridge modules
  - [ ] 4.2 Reduce `mc/bridge/__init__.py` to package-level composition and re-export only what is still necessary
  - [ ] 4.3 Ensure no raw Convex SDK imports leak outside `mc/bridge/*`

- [ ] **Task 5: Run the wave exit gate** (AC: #4, #5)
  - [ ] 5.1 Run focused pytest targets for gateway, architecture, state-machine, and runtime integration
  - [ ] 5.2 Run full backend pytest suite
  - [ ] 5.3 Run `/code-review`
  - [ ] 5.4 Run a Playwright smoke on dashboard load and task open
  - [ ] 5.5 Commit the wave

## Dev Notes

### Architecture Patterns

- This is a structural split, not a behavior redesign. Preserve existing runtime semantics while making ownership explicit.
- Use focused modules rather than a new generic “utils” dumping ground.
- Keep `mc/bridge/*` as the only backend Convex SDK boundary.

### Project Structure Notes

- Prefer `mc/runtime/*`, `mc/contexts/execution/*`, and `mc/bridge/*` as destinations.
- Keep new module names aligned with responsibilities called out in the migration plan: polling, delivery, requeue, runner, provider errors, message builder, session keys.

### References

- [Source: docs/plans/2026-03-11-architecture-convergence-plan.md#Task-4-Wave-3---split-the-backend-hotspots-by-responsibility]
- [Source: docs/ARCHITECTURE.md#Shared-Base-Layers]
- [Source: _bmad-output/implementation-artifacts/15-3-bridge-split-into-client-repositories-subscriptions.md]
- [Source: _bmad-output/implementation-artifacts/20-5-decompose-process-monitor.md]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
