# Story: Chat-First Create Squad and Graph Persistence

Status: ready-for-dev

## Story

As a Mission Control user,
I want `Create Squad` to behave like an architect that interviews me, proposes
the squad, and saves the complete blueprint,
so that I do not lose agents and workflows after completing the flow.

## Problems Found

- The current `Create Squad` UI is form-first and does not use the authoring
  API as the primary driver.
- The current publish path only creates a `squadSpec` shell.
- Agents and workflows are not persisted, which causes empty squad detail views.

## Solution

Replace the current squad flow with:

- architect-style conversation
- live squad graph preview
- publish orchestration that persists:
  - child `agentSpecs`
  - child `workflowSpecs`
  - optional `reviewSpecs`
  - final `squadSpec` links

## Acceptance Criteria

1. `Create Squad` uses the shared authoring engine as the primary interaction
   model.
2. The assistant proposes squad structure dynamically, including agents and
   workflows.
3. The UI preview reflects the inferred graph during the conversation.
4. Publish persists the complete blueprint graph rather than only the squad
   shell.
5. Saved squad detail views show real agent and workflow counts after publish.
6. Squad creation still does not create a task or execute a workflow.

## Tasks / Subtasks

- [ ] Task 1: Replace the manual squad shell with a chat-first shell
- [ ] Task 2: Bind the shell to the shared authoring engine
- [ ] Task 3: Implement publish orchestration for the full squad graph
- [ ] Task 4: Validate squad detail rendering against persisted records
- [ ] Task 5: Add focused tests for squad authoring and persistence

## Dev Notes

- Do not publish a shell-only `squadSpec` from the main flow.
- Do not add more fields to the manual form as a substitute for architect logic.
- Keep squads as blueprints; no `Run Squad` in this story.

### References

- [Source: docs/plans/2026-03-14-llm-first-authoring-remediation-plan.md]
- [Source: dashboard/features/agents/components/SquadAuthoringWizard.tsx]
- [Source: dashboard/features/agents/hooks/useCreateSquadDraft.ts]
- [Source: dashboard/features/agents/components/SquadDetailSheet.tsx]
- [Source: dashboard/app/api/authoring/squad-wizard/route.ts]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

