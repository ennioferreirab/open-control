# Story 31.5: Persist Direct Delegation and Human Routing from the Dashboard

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want dashboard task creation to persist the new routing contract,
so that runtime behavior starts from explicit task metadata instead of backend
guesswork.

## Overall Objective

Update dashboard task creation and explicit agent-routing plumbing so tasks are
created as `direct_delegate` by default and explicit operator assignment can
persist `routingMode="human"`.

## Acceptance Criteria

1. Standard dashboard task creation sends or defaults to
   `workMode="direct_delegate"`.
2. Explicit operator-to-agent routing can persist `routingMode="human"`.
3. Existing task-input support for tags, files, board selection, and auto-title
   remains intact.
4. No new UI surface is required to ship this story; the contract can be wired
   through the existing shell.
5. Focused dashboard tests prove the new payload behavior.

## Files To Change

- `dashboard/features/tasks/components/TaskInput.tsx`
- `dashboard/features/tasks/hooks/useTaskInputData.ts`
- `dashboard/convex/tasks.ts`
- `dashboard/convex/lib/taskMetadata.ts`
- `dashboard/components/TaskInput.test.tsx`

## Tasks / Subtasks

- [ ] Task 1: Update task-input creation arguments
  - [ ] 1.1 Add support for `workMode`
  - [ ] 1.2 Add support for `routingMode`
  - [ ] 1.3 Keep backward compatibility for existing callers

- [ ] Task 2: Wire standard task creation to direct delegation
  - [ ] 2.1 Default normal task creation to `direct_delegate`
  - [ ] 2.2 Preserve auto-title and description behavior
  - [ ] 2.3 Keep manual/human task flags coherent with the new routing fields

- [ ] Task 3: Wire explicit dashboard assignment to human routing
  - [ ] 3.1 Persist `routingMode="human"` where the dashboard explicitly targets
        an agent
  - [ ] 3.2 Keep `reason` and `reasonCode` optional and unset
  - [ ] 3.3 Do not introduce fake lead-agent metadata

- [ ] Task 4: Add focused regression tests
  - [ ] 4.1 Extend `TaskInput.test.tsx`
  - [ ] 4.2 Prove standard tasks become `direct_delegate`
  - [ ] 4.3 Prove explicit agent routing can persist `human`

## Dev Notes

- This story is about persistence and payload shape, not a visible redesign of
  task creation.
- Keep the current task-input UX stable unless tests force a small adjustment.

## References

- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-design.md`]
- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-implementation-plan.md`]
