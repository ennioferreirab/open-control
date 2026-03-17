# Story 31.8: Preserve Human Routing and Explicit Agent Ownership

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want explicit dashboard-to-agent assignment to bypass lead-agent routing,
so that operator intent and routing provenance remain correct.

## Overall Objective

Restore the `routingMode="human"` contract for explicitly assigned tasks and
make that operator-directed target authoritative at runtime.

## Acceptance Criteria

1. Tasks created with explicit `assignedAgent` and `routingMode="human"` do not
   invoke `DirectDelegationRouter`.
2. Runtime never rewrites a human-routed task to `routingMode="lead_agent"`.
3. Human-routed tasks keep `reason`, `reasonCode`, and `registrySnapshot`
   unset unless an explicit future contract says otherwise.
4. Explicit operator assignment is never silently replaced by board filtering or
   least-loaded lead-agent routing.
5. Lead-agent-routed `direct_delegate` tasks continue to persist
   `routingMode="lead_agent"` with routing decision metadata.
6. Focused dashboard and Python tests prove the `human` vs `lead_agent`
   runtime split.

## Files To Change

- `dashboard/convex/lib/taskMetadata.ts`
- `dashboard/convex/tasks.ts`
- `mc/runtime/workers/inbox.py`
- `mc/contexts/routing/router.py`
- `tests/mc/workers/test_direct_delegate_routing.py`
- `tests/mc/contexts/routing/test_router.py`
- `dashboard/convex/tasks.test.ts`

## Tasks / Subtasks

- [ ] Task 1: Make human routing authoritative
  - [ ] 1.1 Detect explicit human-routed tasks before lead-agent routing
  - [ ] 1.2 Preserve `assignedAgent` without router mediation
  - [ ] 1.3 Keep routing-decision fields unset for human routing

- [ ] Task 2: Protect operator intent from silent reassignment
  - [ ] 2.1 Ensure board filtering cannot replace an explicit assignment
  - [ ] 2.2 Keep lead-agent routing only for tasks that actually require it
  - [ ] 2.3 Preserve existing direct-delegate auto-title behavior

- [ ] Task 3: Add regression coverage
  - [ ] 3.1 Prove explicit dashboard assignment keeps `routingMode="human"`
  - [ ] 3.2 Prove inbox bypasses lead-agent routing for human tasks
  - [ ] 3.3 Prove lead-agent-routed tasks still store routing metadata

## Dev Notes

- Treat `routingMode="human"` as authoritative operator intent, not as a hint.
- If an explicitly assigned agent is invalid, fail explicitly; do not silently
  reroute.

## References

- [Source: review findings on March 17, 2026]
- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-design.md`]

