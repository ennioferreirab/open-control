# Story 31.3: Route Normal Tasks Through Lead-Agent Direct Delegation

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want normal tasks to be assigned through a lead-agent routing decision instead
of a generated execution plan,
so that standard task execution becomes simpler and less ambiguous.

## Overall Objective

Introduce a focused routing context for lead-agent direct delegation and move
normal-task runtime handling onto that path, while keeping workflow execution
separate.

## Acceptance Criteria

1. Normal tasks with `workMode="direct_delegate"` do not enter the
   lead-agent planner path.
2. Runtime resolves a target agent from the active registry view and stores a
   routing decision before assignment.
3. Direct-delegate tasks transition to `assigned` without creating an
   `executionPlan`.
4. Workflow tasks continue to use the existing workflow execution path and are
   not misrouted through direct delegation.
5. Focused runtime tests prove the routing split and bridge contract.

## Files To Change

- `mc/runtime/workers/inbox.py`
- `mc/runtime/workers/planning.py`
- `mc/runtime/orchestrator.py`
- `mc/contexts/routing/router.py`
- `tests/mc/workers/test_direct_delegate_routing.py`
- `tests/mc/contexts/routing/test_router.py`

## Tasks / Subtasks

- [ ] Task 1: Add a focused routing context
  - [ ] 1.1 Create `mc/contexts/routing/router.py`
  - [ ] 1.2 Fetch the active registry through the bridge
  - [ ] 1.3 Return a routing decision payload with target agent and metadata

- [ ] Task 2: Split inbox/runtime handling by work mode
  - [ ] 2.1 Make inbox worker branch between workflow and direct delegation
  - [ ] 2.2 Keep auto-title behavior intact for normal tasks
  - [ ] 2.3 Move only workflow tasks toward workflow planning/materialization

- [ ] Task 3: Store routing results and assign the task
  - [ ] 3.1 Persist `routingMode="lead_agent"` for routed tasks
  - [ ] 3.2 Persist target-agent metadata
  - [ ] 3.3 Transition the task to `assigned`

- [ ] Task 4: Add focused regression tests
  - [ ] 4.1 Add router unit tests
  - [ ] 4.2 Add inbox/runtime tests for direct delegation
  - [ ] 4.3 Add a regression proving workflow tasks bypass this path

## Dev Notes

- Do not reuse `TaskPlanner` or plan parsing for this story.
- The lead-agent remains a router, not an executor and not a planner, in this
  flow.

## References

- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-design.md`]
- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-implementation-plan.md`]
