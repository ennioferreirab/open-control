# Story 31.6: Scope Task Detail Plan Review UI to Workflow

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want task detail to reserve lead-agent plan-review UI for workflow tasks,
so that direct-delegate and human-routed tasks stop showing misleading planning
affordances.

## Overall Objective

Keep the `Execution Plan` tab shell in task detail, but limit plan-review and
lead-agent plan-conversation UI to workflow-owned tasks only.

## Acceptance Criteria

1. Direct-delegate tasks still render the `Execution Plan` tab shell.
2. Human-routed tasks still render the `Execution Plan` tab shell.
3. Only workflow tasks render lead-agent plan review affordances.
4. Non-workflow tasks do not render `PlanReviewPanel` or workflow-only copy in
   task detail.
5. Focused read-model and component tests prove the workflow-only UI boundary.

## Files To Change

- `dashboard/convex/lib/readModels.ts`
- `dashboard/features/tasks/components/TaskDetailSheet.tsx`
- `dashboard/features/tasks/components/PlanReviewPanel.tsx`
- `dashboard/features/tasks/hooks/useTaskDetailView.ts`
- `dashboard/features/tasks/components/TaskDetailSheet.test.tsx`
- `dashboard/features/tasks/components/PlanReviewPanel.test.tsx`
- `dashboard/features/tasks/hooks/useTaskDetailView.test.ts`

## Tasks / Subtasks

- [ ] Task 1: Update read models to understand workflow ownership
  - [ ] 1.1 Add workflow-aware UI flags
  - [ ] 1.2 Stop keying plan-review UI off generic task review state alone
  - [ ] 1.3 Preserve existing plan-tab read model shape

- [ ] Task 2: Scope task-detail rendering
  - [ ] 2.1 Keep the tab visible for all tasks
  - [ ] 2.2 Render `PlanReviewPanel` only for workflow tasks
  - [ ] 2.3 Keep normal thread behavior for non-workflow tasks

- [ ] Task 3: Add focused regression tests
  - [ ] 3.1 Extend `TaskDetailSheet.test.tsx`
  - [ ] 3.2 Extend `PlanReviewPanel.test.tsx`
  - [ ] 3.3 Extend `useTaskDetailView.test.ts`

## Dev Notes

- This story must not hide the plan tab entirely for non-workflow tasks.
- The goal is accurate affordances, not removal of the current tab shell.

## References

- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-design.md`]
- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-implementation-plan.md`]
