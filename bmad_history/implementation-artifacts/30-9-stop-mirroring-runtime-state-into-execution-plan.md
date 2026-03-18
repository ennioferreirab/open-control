# Story 30.9: Stop Mirroring Runtime State into Execution Plan

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want `executionPlan` to describe intended work only,
so that live runtime state has a single source of truth in `steps`.

## Overall Objective

Remove the current practice of copying live step status into
`executionPlan.steps[*].status` and make dashboard read models overlay live
progress from `steps`.

## Acceptance Criteria

1. `dashboard/convex/steps.ts` no longer writes live status into
   `executionPlan.steps[*].status`.
2. `dashboard/convex/lib/taskLifecycle.ts` no longer force-marks every plan step
   as `completed` when a task finishes.
3. Task-card and task-detail progress views derive live status from `steps`
   rather than persisted plan-step status.
4. `ExecutionPlanTab` continues to show current progress by overlaying live-step
   state on top of the desired plan structure.
5. Focused tests prove dashboard read models remain correct without stored
   plan-step runtime state.

## Files To Change

- `dashboard/convex/steps.ts:21-55`
- `dashboard/convex/steps.ts:119-125`
- `dashboard/convex/steps.ts:509-519`
- `dashboard/convex/lib/taskLifecycle.ts:198-217`
- `dashboard/convex/lib/taskDetailView.ts`
- `dashboard/features/tasks/components/TaskCard.tsx:58-63`
- `dashboard/features/tasks/components/ExecutionPlanTab.tsx:315-325`
- `dashboard/features/tasks/hooks/useTaskDetailView.ts:137-177`

## Tasks / Subtasks

- [ ] Task 1: Remove plan-status mirroring from backend writes
  - [ ] 1.1 Remove status syncing from `steps.ts`
  - [ ] 1.2 Remove blanket completion marking from `taskLifecycle.ts`

- [ ] Task 2: Move progress computation to read models
  - [ ] 2.1 Update `taskDetailView.ts`
  - [ ] 2.2 Update `useTaskDetailView.ts`
  - [ ] 2.3 Keep desired plan structure separate from live overlay data

- [ ] Task 3: Update UI consumers
  - [ ] 3.1 Update `TaskCard.tsx`
  - [ ] 3.2 Update `ExecutionPlanTab.tsx`

- [ ] Task 4: Add focused tests
  - [ ] 4.1 Extend `dashboard/convex/lib/readModels.test.ts`
  - [ ] 4.2 Extend `dashboard/convex/tasks.test.ts`
  - [ ] 4.3 Add a regression proving live progress still renders without stored
        plan-step status

## Dev Notes

- This story should be scheduled after Stories 30.1 through 30.8 so the live
  lifecycle model is already stable.
- `executionPlan` remains important for desired structure, ordering, and
  authorship metadata; only live runtime state should leave it.

## References

- [Source: `docs/plans/2026-03-16-task-lifecycle-hardening-plan.md`]
- [Source: `_bmad-output/planning-artifacts/2026-03-16-task-usercase-flow-map.md`]
