# Story: Canonical Agent Registry For Squads

Status: ready-for-dev

## Story

As a Mission Control user,
I want every squad member to be a normal registered agent,
so that squads reuse the same global agents and do not create a second agent identity.

## Problems Found

- `squadSpecs` currently stores `agentSpecIds`, which makes squad membership
  depend on a squad-local authoring entity instead of the canonical `agents`
  registry.
- `workflowSpecs.steps` currently stores `agentSpecId`, which ties workflow
  ownership to the same parallel model.
- `Create Squad` currently publishes child `agentSpecs`, which makes it look as
  if squads own distinct agents.
- The same logical agent cannot be cleanly reused across multiple squads
  without duplicating records.

## Solution

Make `agents` the only canonical identity:

- squads store `agentIds`
- workflow steps store `agentId`
- squad publish reuses an existing global agent by name or creates a normal
  global agent when missing
- squad detail reads and edits the same global agents shown everywhere else

## Acceptance Criteria

1. `squadSpecs` stores `agentIds: Id<"agents">[]` instead of `agentSpecIds`.
2. `workflowSpecs.steps` stores `agentId: Id<"agents">` instead of
   `agentSpecId`.
3. Publishing a squad graph never inserts child `agentSpecs`.
4. Publishing a squad graph reuses an existing global agent when the proposed
   agent `name` already exists.
5. Publishing a squad graph creates a normal global `agents` record when the
   proposed agent does not exist yet.
6. Squad detail surfaces load global agents from `agentIds`.
7. Editing an agent from squad context updates the same global agent record.

## Tasks / Subtasks

- [ ] Task 1: Replace squad and workflow agent references in Convex schema
- [ ] Task 2: Update squad publish to reuse or create canonical global agents
- [ ] Task 3: Update squad detail queries and views to load global agents
- [ ] Task 4: Route squad-context edits through the normal global agent update path
- [ ] Task 5: Add focused Convex and React tests for the new canonical-agent flow

## Dev Notes

- Do not keep `agentSpecs` as the canonical identity for squad membership.
- Do not introduce squad-local agent overrides.
- Prefer one coherent global agent model even if that removes richer local
  squad-only authoring fields.
- Reuse existing global agents by canonical `name`.
- Because current squads can be ignored, no compatibility layer is required for
  deleted squad records.

### Project Structure Notes

- Convex schema and mutations stay under `dashboard/convex/`
- squad UI and hooks stay under `dashboard/features/agents/`
- avoid recreating dashboard-level wrappers outside canonical feature ownership

### References

- [Source: docs/plans/2026-03-15-agent-squad-unification-design.md]
- [Source: docs/plans/2026-03-15-agent-squad-unification-implementation-plan.md]
- [Source: docs/ARCHITECTURE.md#mc.contexts.agents]
- [Source: dashboard/convex/lib/squadGraphPublisher.ts]
- [Source: dashboard/convex/squadSpecs.ts]
- [Source: dashboard/convex/workflowSpecs.ts]
- [Source: dashboard/features/agents/hooks/useSquadDetailData.ts]
- [Source: dashboard/features/agents/components/SquadDetailSheet.tsx]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
