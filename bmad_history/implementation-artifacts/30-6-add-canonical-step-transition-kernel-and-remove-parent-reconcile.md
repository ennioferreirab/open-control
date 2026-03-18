# Story 30.6: Add Canonical Step Transition Kernel and Remove Parent Reconcile

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want step lifecycle changes to use the same CAS discipline as task lifecycle,
so that child-step code no longer rewrites the parent task state directly.

## Overall Objective

Add `stateVersion` and a canonical step transition kernel, stop using
`step.status="review"` as a generic pause bucket, and remove direct parent-task
status reconciliation from `dashboard/convex/steps.ts`.

## Acceptance Criteria

1. The `steps` schema has `stateVersion: number`, initialized for every created
   step.
2. A new canonical step transition path owns `step.status`, `startedAt`,
   `completedAt`, `errorMessage`, and `stateVersion`.
3. `dashboard/convex/steps.ts` no longer patches `task.status` directly inside
   child-step reconciliation.
4. Ask-user and interactive pause flows use `waiting_human` instead of
   `step.status="review"`.
5. Workflow review semantics remain on `workflowStepType="review"` and are not
   conflated with the generic step lifecycle status.

## Files To Change

- `dashboard/convex/schema.ts:168-199`
- `dashboard/convex/lib/stepTransitions.ts`
- `dashboard/convex/steps.ts:21-168`
- `dashboard/convex/steps.ts:328-413`
- `dashboard/convex/steps.ts:463-660`
- `dashboard/convex/lib/stepLifecycle.ts:20-64`
- `mc/bridge/repositories/steps.py:59-91`
- `mc/bridge/facade_mixins.py:67-71`
- `mc/contexts/execution/step_dispatcher.py:377-546`
- `mc/contexts/interaction/service.py:268-343`
- `mc/contexts/conversation/ask_user/handler.py:73-118`
- `mc/contexts/interactive/supervisor.py:183-279`

## Tasks / Subtasks

- [ ] Task 1: Add `stateVersion` to the step model
  - [ ] 1.1 Update `dashboard/convex/schema.ts`
  - [ ] 1.2 Initialize the field in step creation paths
  - [ ] 1.3 Add schema tests for default initialization

- [ ] Task 2: Create the canonical step transition kernel
  - [ ] 2.1 Create `dashboard/convex/lib/stepTransitions.ts`
  - [ ] 2.2 Move transition validation and bookkeeping into the kernel
  - [ ] 2.3 Return explicit conflict/no-op outcomes

- [ ] Task 3: Remove parent-task reconciliation authority from `steps.ts`
  - [ ] 3.1 Stop writing `task.status` directly in
        `reconcileParentTaskAfterStepChange`
  - [ ] 3.2 If a step transition implies a parent transition, emit an intent
        that goes through the canonical task transition kernel

- [ ] Task 4: Replace generic step-review pause usage
  - [ ] 4.1 Update ask-user flow to use `waiting_human`
  - [ ] 4.2 Update interactive supervision flow to use `waiting_human`
  - [ ] 4.3 Keep workflow review steps functioning through
        `workflowStepType="review"`

- [ ] Task 5: Add focused tests
  - [ ] 5.1 Extend `dashboard/convex/steps.test.ts`
  - [ ] 5.2 Extend `tests/mc/test_interactive_runtime.py`
  - [ ] 5.3 Extend `tests/mc/application/execution/test_post_processing.py`

## Dev Notes

- This story is not complete if `steps.ts` still contains any direct patch of
  the parent task lifecycle for normal execution transitions.
- `waiting_human` is the pause bucket; `review` on steps should not remain the
  generic answer for human intervention.

## References

- [Source: `docs/plans/2026-03-16-task-lifecycle-hardening-plan.md`]
- [Source: `dashboard/convex/lib/taskTransitions.ts` from Stories 30.3-30.5]
