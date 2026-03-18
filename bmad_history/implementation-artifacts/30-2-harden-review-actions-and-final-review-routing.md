# Story 30.2: Harden Review Actions and Final Review Routing

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want pause, resume, and approve flows to be semantically disjoint,
so that paused execution cannot be mistaken for final approval and completed
planned tasks still go through real review routing.

## Overall Objective

Use `reviewPhase` to separate `execution_pause` from `final_approval`, fix the
current `approve`/`resume` overlap, and make `ReviewWorker` route final review
even when a task has materialized steps.

## Acceptance Criteria

1. `approve` is only allowed for `reviewPhase="final_approval"` and is rejected
   for `reviewPhase="execution_pause"`.
2. `resume` is only allowed for `reviewPhase="execution_pause"` and never for
   `plan_review` or `final_approval`.
3. `pause` writes `reviewPhase="execution_pause"` everywhere the system pauses
   execution for human input or intervention.
4. `ReviewWorker` routes `final_approval` tasks to reviewers or HITL even when
   materialized steps exist.
5. Transition logging and activity emission do not hide semantic changes as
   silent `review -> review` toggles.

## Files To Change

- `dashboard/convex/lib/taskStatus.ts:8-134`
  - Restrict pause/resume/kickoff behavior by `reviewPhase`
- `dashboard/convex/lib/taskReview.ts:102-249`
  - Reject final approval on paused tasks and require explicit phase
- `dashboard/convex/lib/readModels.ts:99-116`
  - Make `approve`, `kickoff`, and `resume` mutually exclusive
- `dashboard/features/tasks/components/TaskDetailSheet.tsx`
  - Render header actions from `reviewPhase`
- `mc/runtime/workers/review.py:48-123`
  - Stop treating "has steps" as synonymous with "paused task"
- `mc/contexts/execution/step_dispatcher.py:271-295`
  - Request `final_approval` explicitly after all steps complete
- `mc/contexts/interaction/service.py:268-343`
  - Set `reviewPhase="execution_pause"` for ask-user pauses
- `mc/contexts/conversation/ask_user/handler.py:73-118`
  - Preserve execution-pause semantics on pause/resume
- `mc/contexts/interactive/supervisor.py:220-260`
  - Project interactive pauses to `execution_pause`

## Tasks / Subtasks

- [ ] Task 1: Make dashboard actions phase-aware
  - [ ] 1.1 Update `computeAllowedActions` in `readModels.ts`
  - [ ] 1.2 Update `TaskDetailSheet.tsx` button gating
  - [ ] 1.3 Add regression coverage for `approve` and `resume` never being true
        together

- [ ] Task 2: Enforce phase-aware review mutations
  - [ ] 2.1 Update `pauseTaskExecution` to stamp `execution_pause`
  - [ ] 2.2 Update `resumeTaskExecution` to require `execution_pause`
  - [ ] 2.3 Update `approveTask` to require `final_approval`
  - [ ] 2.4 Preserve `plan_review` for kickoff-only flows

- [ ] Task 3: Fix runtime review routing
  - [ ] 3.1 Update `step_dispatcher.py` to request `final_approval`
  - [ ] 3.2 Update `ReviewWorker` to route `final_approval` even when steps
        exist
  - [ ] 3.3 Keep ask-user and interactive pauses on `execution_pause`

- [ ] Task 4: Restore auditability for review semantic changes
  - [ ] 4.1 Emit explicit activity/logging for review-phase changes
  - [ ] 4.2 Remove silent semantic toggles hidden behind `review -> review`
        special cases

- [ ] Task 5: Add focused tests
  - [ ] 5.1 Extend `dashboard/convex/lib/readModels.test.ts`
  - [ ] 5.2 Extend `dashboard/convex/lib/taskReview.test.ts`
  - [ ] 5.3 Extend `dashboard/convex/tasks.test.ts`
  - [ ] 5.4 Add runtime coverage for completed planned tasks entering final
        review and still reaching reviewer/HITL routing

## Dev Notes

- This story must close the known bug where a paused task can be approved and
  force-complete the whole plan.
- This story must also close the bug where `ReviewWorker` ignores final review
  for planned tasks just because steps exist.
- Do not mix the kickoff path back into `resume`.

## References

- [Source: `docs/plans/2026-03-16-task-lifecycle-hardening-plan.md`]
- [Source: `_bmad-output/planning-artifacts/2026-03-16-runtime-state-capture-and-race-report.md`]
