# Story 31.1: Add Task Work and Routing Modes

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want tasks to declare explicit work and routing modes,
so that workflow execution, lead-agent delegation, and human assignment no
longer rely on implicit branching.

## Overall Objective

Add `workMode` and `routingMode` to task persistence and creation paths so the
runtime and dashboard can distinguish:

- workflow-owned tasks
- lead-agent direct delegation
- explicit human-to-agent routing

## Acceptance Criteria

1. The `tasks` schema exposes `workMode` as an optional union with exactly
   `direct_delegate` and `ai_workflow`.
2. The `tasks` schema exposes `routingMode` as an optional union with exactly
   `lead_agent`, `workflow`, and `human`.
3. Standard task creation defaults to `workMode="direct_delegate"`.
4. Workflow mission launch persists `workMode="ai_workflow"` and
   `routingMode="workflow"`.
5. The new fields do not force `executionPlan` onto direct-delegate tasks.

## Files To Change

- `dashboard/convex/schema.ts`
- `dashboard/convex/lib/taskMetadata.ts`
- `dashboard/convex/tasks.ts`
- `dashboard/convex/lib/squadMissionLaunch.ts`
- `dashboard/convex/tasks.test.ts`

## Tasks / Subtasks

- [ ] Task 1: Add the new task-mode fields to the schema
  - [ ] 1.1 Add `workMode` to the `tasks` table validator
  - [ ] 1.2 Add `routingMode` to the `tasks` table validator
  - [ ] 1.3 Keep both fields optional for migration compatibility

- [ ] Task 2: Make normal task creation default to direct delegation
  - [ ] 2.1 Update `createTask` in `taskMetadata.ts`
  - [ ] 2.2 Ensure `TaskInput` callers do not need a new required argument yet
  - [ ] 2.3 Keep board, file, and tag behavior unchanged

- [ ] Task 3: Make workflow launch persist workflow ownership explicitly
  - [ ] 3.1 Update squad mission launch writes
  - [ ] 3.2 Persist `routingMode="workflow"` when workflow creates the task
  - [ ] 3.3 Preserve current workflow `executionPlan` behavior

- [ ] Task 4: Add focused regression tests
  - [ ] 4.1 Extend `dashboard/convex/tasks.test.ts` for direct delegation
  - [ ] 4.2 Extend `dashboard/convex/tasks.test.ts` for workflow launch
  - [ ] 4.3 Prove direct-delegate tasks can exist without `executionPlan`

## Dev Notes

- Do not add fake one-step plans to satisfy old assumptions.
- This story only adds the contract. It does not yet route runtime behavior to
  the new modes.

## References

- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-design.md`]
- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-implementation-plan.md`]
