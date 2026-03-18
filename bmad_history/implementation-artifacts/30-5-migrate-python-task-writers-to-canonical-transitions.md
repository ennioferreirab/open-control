# Story 30.5: Migrate Python Task Writers to Canonical Transitions

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want runtime workers and Python services to use the canonical task transition
contract,
so that Python stops acting like an independent lifecycle owner.

## Overall Objective

Change the bridge and runtime writers to call `tasks:transition` with explicit
expected versions and conflict handling instead of plain `tasks:updateStatus`.

## Acceptance Criteria

1. The Python bridge exposes a task-transition API that includes
   `expectedStateVersion`, `reviewPhase`, `reason`, and `idempotencyKey`.
2. Inbox, planning, kickoff, executor, dispatcher, ask-user, and interactive
   supervision code paths stop using raw `update_task_status` writes for normal
   lifecycle changes.
3. Stale-snapshot conflicts are handled explicitly as no-op, retry, or warning;
   they are not silently overwritten.
4. Focused tests cover at least inbox routing, supervised planning review,
   execution completion, and interactive pause/resume using the new transition
   contract.

## Files To Change

- `mc/bridge/repositories/tasks.py:26-90`
- `mc/bridge/facade_mixins.py:12-23`
- `mc/runtime/workers/inbox.py:101-129`
- `mc/runtime/workers/planning.py:227-285`
- `mc/runtime/workers/kickoff.py:171-190`
- `mc/contexts/execution/executor.py:626-636`
- `mc/contexts/execution/step_dispatcher.py:257-295`
- `mc/contexts/execution/executor_routing.py:43-49`
- `mc/contexts/conversation/ask_user/handler.py:73-118`
- `mc/contexts/interactive/supervisor.py:183-279`

## Tasks / Subtasks

- [ ] Task 1: Upgrade the Python bridge API
  - [ ] 1.1 Add a canonical task-transition method in `TaskRepository`
  - [ ] 1.2 Thread the new method through `BridgeRepositoryFacadeMixin`
  - [ ] 1.3 Preserve a compatibility wrapper only if needed for temporary
        callers

- [ ] Task 2: Migrate orchestrator and execution writers
  - [ ] 2.1 Update inbox and planning workers
  - [ ] 2.2 Update kickoff and executor completion paths
  - [ ] 2.3 Update dispatcher task-level state changes

- [ ] Task 3: Migrate human-intervention writers
  - [ ] 3.1 Update ask-user pause/resume handling
  - [ ] 3.2 Update interactive supervision lifecycle projection

- [ ] Task 4: Add conflict-aware handling
  - [ ] 4.1 Log stale or duplicate transitions clearly
  - [ ] 4.2 Decide per call-site whether to retry, skip, or hard-fail

- [ ] Task 5: Add focused tests
  - [ ] 5.1 Extend `tests/mc/bridge/test_repositories.py`
  - [ ] 5.2 Extend `tests/mc/runtime/test_inbox_worker_ai_workflow.py`
  - [ ] 5.3 Extend `tests/mc/runtime/test_planning_worker_ai_workflow.py`
  - [ ] 5.4 Extend `tests/mc/services/test_conversation_gateway_integration.py`

## Dev Notes

- The goal is not to remove polling yet; the goal is to remove Python as a
  direct task-status patcher.
- This story should leave the bridge capable of surfacing conflict/no-op return
  types without raising opaque generic errors.

## References

- [Source: `docs/plans/2026-03-16-task-lifecycle-hardening-plan.md`]
- [Source: `dashboard/convex/lib/taskTransitions.ts` from Story 30.3]
