# Story: LLM-First Authoring Stabilization and Rollout

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want explicit rollout gates for the new LLM-first authoring flows,
so that the system is validated against the real failure mode before we treat it
as the default creation experience.

## Problems Found

- The current bug only becomes obvious after persistence and detail rendering.
- It is easy to validate the happy-path preview and miss the saved-record bug.
- The old manual flows can mask incomplete migration to the new path.

## Solution

Validate the new flows against the full lifecycle:

1. conversation
2. preview
3. publish
4. persisted records
5. detail rendering

## Acceptance Criteria

1. Full-stack validation confirms that the previewed graph matches the persisted
   graph.
2. Saved squads show real agent and workflow counts after publication.
3. Saved agents and squads remain compatible with the existing runtime
   projection path.
4. Validation is run through the full MC stack, not only through a frontend dev
   server.
5. Remaining follow-ups, including future `Run Squad`, are documented cleanly.

## Tasks / Subtasks

- [ ] Task 1: Validate publish-to-detail correctness for Create Agent
- [ ] Task 2: Validate publish-to-detail correctness for Create Squad
- [ ] Task 3: Run focused backend and dashboard regression checks
- [ ] Task 4: Validate the real UI through the full MC stack
- [ ] Task 5: Document remaining follow-up scope

## Dev Notes

- This story is not a place to add new feature scope.
- If persisted data does not match preview data, fix publish orchestration before
  rollout.
- Do not claim success without checking the saved records.

### References

- [Source: docs/plans/2026-03-14-llm-first-authoring-remediation-plan.md]
- [Source: dashboard/features/agents/components/SquadDetailSheet.tsx]
- [Source: dashboard/features/agents/components/AgentAuthoringWizard.tsx]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
