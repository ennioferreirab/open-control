# Story 31.9: Fail Safe When Direct Delegation Has No Valid Candidate

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want unroutable direct-delegate tasks to fail in an explicit recoverable way,
so that they never disappear into planning.

## Overall Objective

Remove the current fallback that sends unroutable `direct_delegate` tasks toward
planning and replace it with a visible failure path that operators can recover
from.

## Acceptance Criteria

1. A `direct_delegate` task with no valid lead-agent routing candidate never
   transitions to `planning`.
2. Unroutable direct-delegate tasks transition to an explicit operator-visible
   failure state using existing lifecycle semantics.
3. The task receives an activity or system message that explains no delegatable
   agent was available.
4. Human-routed tasks with explicit `assignedAgent` are not affected by this
   fallback path.
5. Planning worker invariants remain intact: `direct_delegate` tasks still do
   not execute planning.
6. Focused runtime tests cover empty registry, post-filter-empty candidates, and
   recovery expectations.

## Files To Change

- `mc/runtime/workers/inbox.py`
- `mc/runtime/workers/planning.py`
- `mc/contexts/routing/router.py`
- `tests/mc/workers/test_direct_delegate_routing.py`
- `tests/mc/contexts/routing/test_router.py`

## Tasks / Subtasks

- [ ] Task 1: Replace planning fallback with explicit failure handling
  - [ ] 1.1 Detect unroutable direct-delegate tasks in inbox
  - [ ] 1.2 Transition them to a recoverable failure state
  - [ ] 1.3 Attach an operator-visible explanation

- [ ] Task 2: Keep runtime invariants sharp
  - [ ] 2.1 Preserve the planning worker guard against `direct_delegate`
  - [ ] 2.2 Avoid any implicit planner retry behavior
  - [ ] 2.3 Keep workflow routing behavior unchanged

- [ ] Task 3: Add regression coverage
  - [ ] 3.1 Prove empty registry does not send task to planning
  - [ ] 3.2 Prove board filtering to zero candidates fails safely
  - [ ] 3.3 Prove existing recovery surfaces can see the failure reason

## Dev Notes

- Reusing an existing terminal task state is preferred over inventing a new
  status.
- Do not reintroduce lead-agent planning as a recovery mechanism for normal
  tasks.

## References

- [Source: review findings on March 17, 2026]
- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-implementation-plan.md`]

