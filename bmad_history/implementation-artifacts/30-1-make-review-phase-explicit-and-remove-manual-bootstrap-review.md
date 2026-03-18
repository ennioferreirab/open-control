# Story 30.1: Make Review Phase Explicit and Remove Manual Bootstrap from Review

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want the meaning of `task.status="review"` to be explicit,
so that pre-kickoff review, execution pause, and final approval no longer rely
on heuristics or manual-task special cases.

## Overall Objective

Introduce `reviewPhase` as the canonical discriminator for review behavior and
remove the current manual-task bootstrap path that uses `review` before any real
plan exists.

## Acceptance Criteria

1. The `tasks` schema exposes `reviewPhase` as an optional union with exactly
   `plan_review`, `execution_pause`, and `final_approval`.
2. `planning -> review` transitions set `reviewPhase="plan_review"` instead of
   relying on `awaitingKickoff` alone.
3. The completion pipeline requests `reviewPhase="final_approval"` instead of
   returning a bare `TaskStatus.REVIEW`.
4. Manual tasks without a concrete execution plan no longer use
   `task.status="review"` as a bootstrap holding state.
5. Read models and intent resolution use `reviewPhase` as the primary source of
   truth; `awaitingKickoff` remains only as a migration compatibility shim.

## Files To Change

- `dashboard/convex/schema.ts:108-199`
  - Add `reviewPhase` to the `tasks` table validator
- `mc/types.py:84-110`
  - Add Python-side typing/constants for `reviewPhase`
- `dashboard/convex/lib/readModels.ts:84-116`
  - Replace current `awaitingKickoff + step presence` inference with
    `reviewPhase`
- `mc/runtime/workers/planning.py:255-285`
  - Set `reviewPhase="plan_review"` when supervised planning enters review
- `mc/application/execution/completion_status.py:10-16`
  - Stop returning a bare review outcome without explicit phase
- `mc/contexts/planning/negotiation.py:571-855`
  - Remove the `review + no plan` manual bootstrap path
- `mc/contexts/conversation/intent.py:53-159`
  - Reclassify plan-chat eligibility using `reviewPhase`
- `dashboard/features/tasks/components/PlanReviewPanel.tsx:120-137`
  - Switch panel copy and affordances to `reviewPhase`
- `dashboard/features/tasks/components/TaskCard.tsx:53-65`
  - Display review badges from `reviewPhase`

## Tasks / Subtasks

- [ ] Task 1: Add the explicit review-phase field to the shared model
  - [ ] 1.1 Add `reviewPhase` to `dashboard/convex/schema.ts`
  - [ ] 1.2 Add Python typing/constants in `mc/types.py`
  - [ ] 1.3 Ensure task creation and mission launch initialize the field to
        `undefined`

- [ ] Task 2: Make planning and completion write explicit review phases
  - [ ] 2.1 Update `mc/runtime/workers/planning.py` so supervised plan review
        writes `reviewPhase="plan_review"`
  - [ ] 2.2 Update `mc/application/execution/completion_status.py` so final
        approval uses `reviewPhase="final_approval"`
  - [ ] 2.3 Do not add any new logic that derives meaning from
        `awaitingKickoff`

- [ ] Task 3: Remove the manual no-plan review bootstrap
  - [ ] 3.1 Choose a single non-review home for manual tasks with no plan yet:
        `inbox` or `planning`
  - [ ] 3.2 Update `mc/contexts/planning/negotiation.py` to stop treating
        `review + no plan` as a bootstrap state
  - [ ] 3.3 Update `mc/contexts/conversation/intent.py` so plan-chat intent no
        longer depends on that bootstrap hack

- [ ] Task 4: Migrate read-model and UI interpretation to `reviewPhase`
  - [ ] 4.1 Update `dashboard/convex/lib/readModels.ts`
  - [ ] 4.2 Update `PlanReviewPanel.tsx`
  - [ ] 4.3 Update `TaskCard.tsx`

- [ ] Task 5: Add focused regression tests
  - [ ] 5.1 Extend `dashboard/convex/lib/readModels.test.ts`
  - [ ] 5.2 Extend `dashboard/convex/tasks.test.ts`
  - [ ] 5.3 Extend `tests/mc/services/test_conversation_intent.py`
  - [ ] 5.4 Add a runtime regression proving manual no-plan tasks do not enter
        `review`

## Dev Notes

- Do not add a new top-level board status in this story.
- Do not remove `awaitingKickoff` entirely in this story; keep it only as a
  temporary compatibility field.
- The manual no-plan bootstrap case must leave `review` entirely. This story is
  not done if there is still any branch that treats `review` with no plan as a
  valid bootstrap state.

## References

- [Source: `docs/plans/2026-03-16-task-lifecycle-hardening-plan.md`]
- [Source: `_bmad-output/planning-artifacts/2026-03-16-task-convex-rigidity-report.md`]
