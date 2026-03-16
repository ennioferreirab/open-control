# Agent Soul And Model Authoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make squad-created agents preserve and report canonical `prompt/model/skills/soul`, add editable `Soul` to the agent panel, expose available models to squad authoring, and fix the disabled `Save` regression in the agent detail sheet.

**Architecture:** Keep agent-panel behavior in `dashboard/features/agents/`, extend the squad-authoring context route in `dashboard/app/api/specs/squad/context/route.ts`, and preserve canonical fields through the existing squad publish path. Treat the `Save` bug as a contract/dirty-state problem in `AgentConfigSheet` and cover it with focused component tests.

**Tech Stack:** Next.js App Router, React 19, Convex, TypeScript, Vitest

---

## References

- Design: `docs/plans/2026-03-15-agent-soul-and-model-authoring-design.md`
- Existing story: `_bmad-output/implementation-artifacts/tech-spec-agent-soul-and-model-authoring.md`
- Agent panel: `dashboard/features/agents/components/AgentConfigSheet.tsx`
- Agent panel data hook: `dashboard/features/agents/hooks/useAgentConfigSheetData.ts`
- YAML config API: `dashboard/app/api/agents/[agentName]/config/route.ts`
- Squad context API: `dashboard/app/api/specs/squad/context/route.ts`
- Squad publish path: `dashboard/convex/lib/squadGraphPublisher.ts`

## Delivery Order

1. Lock the scope in a story artifact and documentation.
2. Add failing tests for squad context models and agent-panel save behavior.
3. Implement `Soul` preview/editing and dirty-state fixes in `AgentConfigSheet`.
4. Extend squad context with available models.
5. Update the local `/create-squad-mc` skill contract and summary.
6. Run targeted dashboard verification and commit.

### Task 0: Document the story and plan

**Files:**
- Create: `docs/plans/2026-03-15-agent-soul-and-model-authoring-design.md`
- Create: `docs/plans/2026-03-15-agent-soul-and-model-authoring-implementation-plan.md`
- Create: `_bmad-output/implementation-artifacts/tech-spec-agent-soul-and-model-authoring.md`

**Step 1: Confirm the new docs exist**

Run:

```bash
rg --files docs/plans _bmad-output/implementation-artifacts | rg 'agent-soul-and-model-authoring'
```

Expected: all three artifacts exist.

**Step 2: Commit the documentation baseline**

```bash
git add docs/plans/2026-03-15-agent-soul-and-model-authoring-design.md docs/plans/2026-03-15-agent-soul-and-model-authoring-implementation-plan.md _bmad-output/implementation-artifacts/tech-spec-agent-soul-and-model-authoring.md
git commit -m "docs: add agent soul and model authoring story"
```

### Task 1: Add failing tests for the agent panel regression

**Files:**
- Create: `dashboard/features/agents/components/AgentConfigSheet.test.tsx`
- Modify: `dashboard/features/agents/components/AgentConfigSheet.tsx`

**Step 1: Write the failing tests**

Add tests that prove:

- the panel renders a `Soul` section with preview text when the agent has soul content;
- the `Save` button is disabled initially, then enables after editing prompt;
- the `Save` button enables after changing model configuration;
- saving includes `soul` in the Convex and YAML payloads.

**Step 2: Run the targeted tests and confirm they fail**

```bash
cd dashboard
npm run test -- --run features/agents/components/AgentConfigSheet.test.tsx
```

Expected: FAIL because `Soul` is not rendered and the current dirty-state behavior is incomplete.

**Step 3: Implement the minimal panel changes**

- add `Soul` preview and edit affordance;
- include `soul` in local state, dirty detection, validation, and save payloads;
- make dirty-state comparison reflect persisted model values correctly.

**Step 4: Re-run the targeted tests**

Run the same command and expect PASS.

**Step 5: Commit**

```bash
git add dashboard/features/agents/components/AgentConfigSheet.tsx dashboard/features/agents/components/AgentConfigSheet.test.tsx
git commit -m "feat: add soul editing to agent config sheet"
```

### Task 2: Add failing tests for squad authoring context models

**Files:**
- Modify: `dashboard/app/api/specs/squad/context/route.test.ts`
- Modify: `dashboard/app/api/specs/squad/context/route.ts`

**Step 1: Write the failing tests**

Add tests that prove:

- the route returns `availableModels`;
- models come from the `connected_models` setting;
- existing `activeAgents` and `availableSkills` behavior stays intact.

**Step 2: Run the targeted tests and confirm they fail**

```bash
cd dashboard
npm run test -- --run app/api/specs/squad/context/route.test.ts
```

Expected: FAIL because the route does not return `availableModels` yet.

**Step 3: Implement the minimal route change**

- query `settings:get` with `connected_models`;
- parse the JSON safely;
- return `availableModels` in the response payload.

**Step 4: Re-run the targeted tests**

Run the same command and expect PASS.

**Step 5: Commit**

```bash
git add dashboard/app/api/specs/squad/context/route.ts dashboard/app/api/specs/squad/context/route.test.ts
git commit -m "feat: expose available models for squad authoring"
```

### Task 3: Update the local squad-authoring skill contract

**Files:**
- Modify: `/Users/ennio/.claude/skills/create-squad-mc/SKILL.md`

**Step 1: Update the skill**

- fetch and describe `availableModels`;
- require explicit model choice for each new squad agent;
- state that agent specs include `prompt`, `model`, `skills`, and `soul`;
- include chosen model and a short soul preview in the final report.

**Step 2: Sanity-check the updated instructions**

Run:

```bash
rg -n "availableModels|soul preview|model" /Users/ennio/.claude/skills/create-squad-mc/SKILL.md
```

Expected: the updated skill text includes all required fields and the final report output.

### Task 4: Final verification

**Files:**
- Modify: `dashboard/features/agents/components/AgentConfigSheet.tsx`
- Modify: `dashboard/features/agents/components/AgentConfigSheet.test.tsx`
- Modify: `dashboard/app/api/specs/squad/context/route.ts`
- Modify: `dashboard/app/api/specs/squad/context/route.test.ts`

**Step 1: Run targeted tests**

```bash
cd dashboard
npm run test -- --run features/agents/components/AgentConfigSheet.test.tsx app/api/specs/squad/context/route.test.ts features/agents/hooks/useCreateSquadDraft.test.tsx convex/lib/squadGraphPublisher.test.ts
```

Expected: PASS.

**Step 2: Run required dashboard checks**

```bash
cd dashboard
npm run format:file:check -- features/agents/components/AgentConfigSheet.tsx features/agents/components/AgentConfigSheet.test.tsx app/api/specs/squad/context/route.ts app/api/specs/squad/context/route.test.ts
npm run lint:file -- features/agents/components/AgentConfigSheet.tsx features/agents/components/AgentConfigSheet.test.tsx app/api/specs/squad/context/route.ts app/api/specs/squad/context/route.test.ts
npm run test:architecture
```

Expected: all commands pass.
