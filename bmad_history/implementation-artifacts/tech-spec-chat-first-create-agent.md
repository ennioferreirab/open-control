# Story: Chat-First Create Agent

Status: ready-for-dev

## Story

As a Mission Control user,
I want `Create Agent` to feel like an architect conversation,
so that the system asks intelligent follow-up questions and builds the agent
spec dynamically instead of making me fill a long manual form.

## Problems Found

- The current `Create Agent` UI is still form-first.
- The authoring backend exists, but it is not the real driver of the UI.
- The product promise of “same powerful LLM” is not actually reflected in the
  shipped flow.

## Solution

Replace the current manual primary flow with a chat-first shell:

- chat on the left
- live agent preview on the right
- manual editing only as a secondary detail editor

## Acceptance Criteria

1. `Create Agent` uses the shared authoring engine as the primary interaction
   model.
2. The UI is chat-first, not form-first.
3. The assistant asks coherent, phase-appropriate follow-up questions.
4. The preview updates live from structured draft patches.
5. Publish creates the final `agentSpec` and runtime projection after approval.

## Tasks / Subtasks

- [ ] Task 1: Replace the manual create-agent shell with a chat-first shell
- [ ] Task 2: Bind the shell to the shared authoring engine
- [ ] Task 3: Show live preview and approval state
- [ ] Task 4: Keep manual editing only as a secondary affordance
- [ ] Task 5: Add focused UI and authoring tests

## Dev Notes

- Do not keep the old phase form as the primary path.
- Do not regress to YAML-centric creation.
- Keep the preview readable and structured for fast approval.

### References

- [Source: docs/plans/2026-03-14-llm-first-authoring-remediation-plan.md]
- [Source: dashboard/features/agents/components/AgentAuthoringWizard.tsx]
- [Source: dashboard/app/api/authoring/agent-wizard/route.ts]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

