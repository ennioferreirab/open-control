# Story 31.2: Add Active Agent Registry View and Agent Metric Fields

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want a routing-grade view of active agents plus durable execution metrics,
so that lead-agent delegation decisions use a real backend contract instead of
ad-hoc agent listing.

## Overall Objective

Add persistent metric fields to agents and expose an
`agents:listActiveRegistryView` query that returns the active delegatable roster
with role, skills, squads, and metric context.

## Acceptance Criteria

1. The `agents` schema exposes `tasksExecuted`, `stepsExecuted`,
   `lastTaskExecutedAt`, and `lastStepExecutedAt`.
2. Convex exposes a query that returns only active delegatable agents for
   routing.
3. The registry result includes `name`, `displayName`, `role`, `skills`,
   `squads`, `enabled`, `status`, metric fields, and `lastActiveAt`.
4. The bridge exposes a Python-facing method to read the active registry view.
5. No non-delegatable runtime surface such as hidden/system-only routing
   fallbacks is misrepresented as a normal registry candidate.

## Files To Change

- `dashboard/convex/schema.ts`
- `dashboard/convex/agents.ts`
- `dashboard/convex/agents.test.ts`
- `mc/bridge/repositories/agents.py`
- `mc/bridge/facade_mixins.py`

## Tasks / Subtasks

- [ ] Task 1: Add metric fields to the agent schema
  - [ ] 1.1 Add task and step counters
  - [ ] 1.2 Add last-execution timestamps
  - [ ] 1.3 Keep existing agent-upsert behavior compatible

- [ ] Task 2: Build the active registry read model
  - [ ] 2.1 Add `agents:listActiveRegistryView`
  - [ ] 2.2 Exclude soft-deleted and non-delegatable agents
  - [ ] 2.3 Resolve squad membership for display/routing context

- [ ] Task 3: Expose the registry through the bridge
  - [ ] 3.1 Add a repository method in Python
  - [ ] 3.2 Re-export it through the facade mixin
  - [ ] 3.3 Keep naming aligned with the Convex query

- [ ] Task 4: Add focused regression tests
  - [ ] 4.1 Prove the query filters correctly
  - [ ] 4.2 Prove the returned shape includes metric fields
  - [ ] 4.3 Prove the Python bridge can fetch the view

## Dev Notes

- This story adds metric fields but does not yet increment them on completion.
- The registry view should be the future authoritative routing input. Do not
  optimize for current UI-only consumers.

## References

- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-design.md`]
- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-implementation-plan.md`]
