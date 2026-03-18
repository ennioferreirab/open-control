# Story: Authoring Engine and Draft Graph Foundation

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want a shared LLM-first authoring engine and a structured draft graph model,
so that agent and squad creation can evolve through coherent conversation
instead of disconnected form phases.

## Problems Found

- The current backend for squad authoring stores flat strings per phase.
- The current phase naming differs between UI and backend.
- The current response contract is too weak to drive dynamic architect behavior.

## Solution

Introduce a shared authoring session contract that:

- uses canonical phases like `discovery`, `proposal`, `refinement`, `approval`
- returns structured graph patches instead of flat phase text
- includes unresolved questions and readiness
- can support both agent and squad modes

## Acceptance Criteria

1. A shared authoring engine exists for both agent and squad authoring.
2. Squad authoring returns structured graph patches for:
   - squad metadata
   - agents
   - workflows
   - review policy
   - unresolved questions
3. Agent authoring returns structured graph patches aligned to the same phase
   model.
4. Frontend and backend use the same canonical phase model.
5. Focused tests cover the new response contract and phase advancement logic.

## Tasks / Subtasks

- [ ] Task 1: Define the shared authoring response contract
- [ ] Task 2: Replace flat squad phase strings with structured graph patches
- [ ] Task 3: Unify phase semantics across frontend and backend
- [ ] Task 4: Add readiness and unresolved-question semantics
- [ ] Task 5: Add focused tests for agent and squad authoring responses

## Dev Notes

- Do not wire the final UI here yet; this story is the foundation.
- Keep the response contract explicit and versionable.
- Treat the current manual wizard phases as transitional.

### References

- [Source: docs/plans/2026-03-14-llm-first-authoring-remediation-plan.md]
- [Source: mc/contexts/agents/authoring_assist.py]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

