# Story 26.2: Reduce Dashboard Shared Convex Coupling

Status: ready-for-dev

## Story

As a **frontend maintainer**,
I want shared/root dashboard components to stop talking to Convex directly where ownership is clearly feature-specific,
so that UI layers stay simpler and feature hooks remain the main data boundary.

## Acceptance Criteria

### AC1: Shared/Root Components Lose Avoidable Direct Convex Access

**Given** some shared/root dashboard components still import `convex/react` directly
**When** this story completes
**Then** the clearly avoidable feature-owned cases are moved into feature hooks
**And** the touched shared/root components become thinner.

### AC2: Architecture Tests Harden the Intended Boundary

**Given** this cleanup should not regress
**When** this story completes
**Then** dashboard architecture tests explicitly guard the touched ownership boundaries.

### AC3: UI Behavior Stays Stable

**Given** the affected components already have test coverage
**When** this story completes
**Then** focused component/hook tests, dashboard typecheck, and dashboard architecture tests pass.

## Tasks / Subtasks

- [ ] **Task 1: Select and lock the next coupling targets** (AC: #1, #2, #3)
  - [ ] 1.1 Add failing architecture assertions for the next shared/root targets
  - [ ] 1.2 Confirm red before implementation

- [ ] **Task 2: Move feature-owned Convex access into feature hooks** (AC: #1)
  - [ ] 2.1 Extract the chosen direct queries/mutations from shared/root components
  - [ ] 2.2 Update call sites to consume the new feature hooks
  - [ ] 2.3 Keep shared/root components as pure renderers or minimal shells

- [ ] **Task 3: Verify and review** (AC: #2, #3)
  - [ ] 3.1 Run focused dashboard tests for touched components/hooks
  - [ ] 3.2 Run `npm run typecheck`
  - [ ] 3.3 Run `npm run test:architecture`
  - [ ] 3.4 Run `/code-review`

## Dev Notes

- Only move cases that are clearly feature-owned.
- Do not force all `convex/react` usage out of every component if the component is itself a data boundary.

## References

- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/components]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/features]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/tests/architecture.test.ts]
