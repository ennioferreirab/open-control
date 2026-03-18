# Story: Agent Soul And Model Authoring

Status: ready-for-dev

## Story

As a Mission Control operator,
I want squad-created agents and the agent detail panel to expose the same full
authoring contract,
so that I can inspect and edit prompt, model, skills, and soul consistently and
see which model each squad agent will use.

## Problems Found

- The agent detail panel does not show `Soul`.
- `Soul` cannot be edited from the panel.
- The `Save` button can remain disabled after changing prompt or model.
- The squad-authoring context does not expose available models.
- The final squad summary does not clearly report chosen models or a readable
  soul preview per agent.

## Solution

- add editable `Soul` support to the agent detail panel
- fix dirty-state and save enablement for prompt/model/soul edits
- expose `availableModels` in the squad-authoring context
- keep squad-created agents aligned with the canonical authoring contract:
  `prompt`, `model`, `skills`, and `soul`
- update the local `/create-squad-mc` skill to request those fields explicitly
  and report the chosen model and soul preview in the final summary

## Acceptance Criteria

1. Opening an agent shows a `Soul` section with a short preview.
2. The operator can edit and save `Soul` from the agent panel.
3. Changing `Prompt`, `Model`, or `Soul` enables the `Save` button.
4. Saving agent changes persists `Soul` in Convex and the YAML config.
5. `GET /api/specs/squad/context` returns `availableModels` from the connected
   model registry.
6. `/create-squad-mc` explicitly asks for a model when defining a new squad
   agent.
7. The final squad summary lists the chosen model for each agent.
8. The final squad summary shows a short preview of each agent `Soul`.
9. Agents created through the squad flow continue to preserve canonical
   `prompt`, `model`, `skills`, and `soul`.

## Tasks / Subtasks

- [ ] Task 1: Add failing tests for missing `Soul` panel support and save-state
      regression
- [ ] Task 2: Implement `Soul` preview/editing and save enablement fixes in the
      agent panel
- [ ] Task 3: Add failing tests for squad context model exposure
- [ ] Task 4: Implement `availableModels` in squad-authoring context
- [ ] Task 5: Update `/create-squad-mc` instructions and final summary format
- [ ] Task 6: Run targeted dashboard verification

## Dev Notes

- Keep panel state and UI changes inside `dashboard/features/agents/`.
- Keep squad context changes in `dashboard/app/api/specs/squad/context/route.ts`.
- The squad publish path already persists canonical fields when they arrive; do
  not weaken that contract.
- `Soul` previews should stay short in the panel and in the squad summary.

### References

- [Source: docs/plans/2026-03-15-agent-soul-and-model-authoring-design.md]
- [Source: docs/plans/2026-03-15-agent-soul-and-model-authoring-implementation-plan.md]
- [Source: dashboard/features/agents/components/AgentConfigSheet.tsx]
- [Source: dashboard/app/api/specs/squad/context/route.ts]
- [Source: dashboard/convex/lib/squadGraphPublisher.ts]
