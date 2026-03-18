# Epic 2 Wave Plan: Live Tab Visualization

## Objective

Execute Epic 2 with minimal merge contention while preserving the structural dependency that the canonical Live contract must land before grouped rendering is considered complete.

## Story Inventory

| Story | Title | Scope | Primary Write Surface |
|------|-------|-------|------------------------|
| 2.1 | Canonical Live Event Contract and Storage | Backend/Convex contract + docs | `mc/*`, `dashboard/convex/*`, contract docs |
| 2.2 | Live Step and Session Navigation | Selector model + TaskDetailSheet wiring | `dashboard/features/interactive/hooks/useTaskInteractiveSession.ts`, `dashboard/features/tasks/components/TaskDetailSheet.tsx` |
| 2.3 | Chronological Grouped Live Rendering | Shared normalizer + Live panel rendering | `dashboard/features/interactive/lib/providerLiveEvents.ts`, `dashboard/features/interactive/components/*` |

## Wave Breakdown

### Wave 1: Foundation

**Stories:** 2.1

**Why first**

- Defines the canonical metadata contract used by later Live grouping work.
- Carries the structural documentation changes that unblock downstream implementation.

**Exit Criteria**

- Canonical metadata fields exist in schema and persistence.
- Claude Code persistence writes them where available.
- Fallback behavior for legacy rows is covered by tests.

### Wave 2: Parallel UI Delivery

**Stories:** 2.2 and 2.3

**Parallelism rules**

- Story 2.2 owns session-choice modeling and `TaskDetailSheet` selector wiring.
- Story 2.3 owns the grouped timeline model and Live panel internals.
- Avoid overlapping edits in `TaskDetailSheet.tsx` beyond selector prop wiring; if needed, sequence the final integration commit after both branches are reviewed.

**Why parallel**

- The session selector and grouped renderer are logically independent once the Live contract/fallback rules are fixed.
- This wave maximizes throughput while keeping ownership boundaries clear.

**Exit Criteria**

- Selector supports active and historical choices.
- Grouped chronology renders correctly and legacy rows still show.
- Updated tests pass in the `dashboard` layer.

### Wave 3: Integration and Validation

**Stories:** no new story; integrate Epic 2 outputs

**Activities**

- Reconcile any `TaskDetailSheet` / Live panel integration friction.
- Run targeted `dashboard` tests, lint, and typecheck.
- Perform manual Live smoke test with active and historical sessions.
- Prepare for code review and `make validate` during execution phase.

## Recommended Staffing

- Story 2.1: 1 senior full-stack dev familiar with Convex + Python bridge behavior
- Story 2.2: 1 frontend dev focused on hook/view-model + TaskDetailSheet integration
- Story 2.3: 1 frontend dev focused on pure normalizer + Live rendering

## Risks and Mitigations

- **Risk:** Story 2.3 starts before Story 2.1 stabilizes field names.
  - **Mitigation:** Treat Story 2.1 field names as locked before Wave 2 begins.

- **Risk:** `TaskDetailSheet.tsx` becomes a merge hotspot.
  - **Mitigation:** Keep Story 2.2 as the sole owner of sheet-level selector state; Story 2.3 should stay within Live panel internals.

- **Risk:** Legacy rows render poorly after grouping.
  - **Mitigation:** Explicit fallback tests are mandatory in Story 2.1 and Story 2.3.

## Done Definition for the Epic

- All three stories reach `review` or `done` through the BMAD workflow.
- Structural docs are updated.
- Targeted dashboard test suite passes.
- Manual Live verification covers active step, historical step, and legacy-row fallback.
