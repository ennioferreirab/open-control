# Agent Sidebar and Squad Authoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add scalable navigation to the Agents sidebar and make squad authoring reuse or create canonical global agents with the same persisted fields as direct agent creation.

**Architecture:** Keep sidebar UX changes in `dashboard/features/agents/` and keep canonical publish logic in the Convex authoring path. Sidebar filtering stays client-side and section-local, while active squad membership and squad-authoring reuse rely on explicit data queries and a richer canonical squad graph payload.

**Tech Stack:** Next.js App Router, React 19, Convex, TypeScript, Vitest, Mission Control authoring flows

---

## References

- Design: `docs/plans/2026-03-15-agent-sidebar-and-squad-authoring-design.md`
- Architecture: `docs/ARCHITECTURE.md`
- Sidebar container: `dashboard/features/agents/components/AgentSidebar.tsx`
- Agent detail sheet: `dashboard/features/agents/components/AgentConfigSheet.tsx`
- Squad sidebar section: `dashboard/features/agents/components/SquadSidebarSection.tsx`
- Squad publish path: `dashboard/convex/lib/squadGraphPublisher.ts`
- Squad draft extraction: `dashboard/features/agents/hooks/useCreateSquadDraft.ts`
- Authoring backend contract: `mc/contexts/agents/authoring_assist.py`
- Story prerequisite: `_bmad-output/implementation-artifacts/tech-spec-agent-sidebar-and-canonical-squad-authoring.md`

## Execution Setup

- Execute only inside `.worktrees/codex/agent-sidebar-squad-authoring`.
- Install dashboard dependencies inside the worktree before test execution.
- Validate UI/runtime work from the worktree root with `PORT=3001 uv run nanobot mc start` when browser validation is needed.
- Do not use a frontend-only dev server for final validation.

## Delivery Order

1. Lock the combined scope in a ready-for-dev story artifact.
2. Add sidebar and agent-detail tests that fail on the current UX.
3. Implement sidebar search, collapsibles, and bounded section scrolling.
4. Add active squad membership data and navigation to agent detail.
5. Add failing tests for canonical squad-agent publish and reuse behavior.
6. Implement canonical squad publish and reuse prompts.
7. Run targeted guardrails and browser validation from the worktree.

### Task 0: Confirm the story artifact

**Files:**
- Create: `_bmad-output/implementation-artifacts/tech-spec-agent-sidebar-and-canonical-squad-authoring.md`
- Reference: `docs/plans/2026-03-15-agent-sidebar-and-squad-authoring-design.md`

**Step 1: Confirm there is a ready-for-dev artifact**

Run:

```bash
rg --files _bmad-output/implementation-artifacts | rg 'agent-sidebar|squad-authoring|canonical-squad-authoring'
```

Expected: the new story artifact exists before implementation starts.

**Step 2: Commit the documentation baseline**

```bash
git add docs/plans/2026-03-15-agent-sidebar-and-squad-authoring-design.md docs/plans/2026-03-15-agent-sidebar-and-squad-authoring-implementation-plan.md _bmad-output/implementation-artifacts/tech-spec-agent-sidebar-and-canonical-squad-authoring.md
git commit -m "docs: add agent sidebar and squad authoring story"
```

### Task 1: Add failing tests for sidebar search and bounded sections

**Files:**
- Modify: `dashboard/features/agents/components/AgentSidebar.test.tsx`
- Modify: `dashboard/features/agents/components/SquadSidebarSection.tsx`
- Modify: `dashboard/features/agents/components/AgentSidebar.tsx`
- Modify: `dashboard/features/agents/hooks/useAgentSidebarData.ts`
- Modify: `dashboard/features/agents/hooks/useSquadSidebarData.ts`

**Step 1: Write the failing tests**

Add tests that prove:

- search matches agent `displayName`
- search matches `@name`
- search includes squads
- `Registered` is collapsible
- each section exposes a scroll container / max-height pattern when there are more than 10 items

Example assertion shape:

```tsx
expect(screen.getByPlaceholderText(/search agents/i)).toBeInTheDocument();
expect(screen.getByText("Writer Squad")).toBeInTheDocument();
expect(screen.queryByText("Hidden Agent")).not.toBeInTheDocument();
```

**Step 2: Run the targeted tests and confirm they fail**

```bash
cd dashboard
npm run test -- features/agents/components/AgentSidebar.test.tsx
```

Expected: FAIL because the current sidebar has no search input, no registered collapsible, and no bounded section behavior.

**Step 3: Implement the minimal sidebar changes**

- add a global search input at the top of `AgentSidebar`
- derive filtered lists for `Squads`, `Registered`, `System`, and `Remoto`
- convert `Registered` to the same collapsible pattern as the other sections
- add a shared section-body container with a 10-row visible window and internal scroll
- preserve existing delete-mode selection behavior through filtering

**Step 4: Re-run the targeted tests**

Run the same command and expect PASS.

**Step 5: Commit**

```bash
git add dashboard/features/agents/components/AgentSidebar.tsx dashboard/features/agents/components/AgentSidebar.test.tsx dashboard/features/agents/components/SquadSidebarSection.tsx dashboard/features/agents/hooks/useAgentSidebarData.ts dashboard/features/agents/hooks/useSquadSidebarData.ts
git commit -m "feat: add agent sidebar search and bounded sections"
```

### Task 2: Add active squad membership to agent detail

**Files:**
- Modify: `dashboard/features/agents/components/AgentConfigSheet.tsx`
- Create: `dashboard/features/agents/hooks/useActiveSquadsForAgent.ts`
- Create: `dashboard/features/agents/hooks/useActiveSquadsForAgent.test.tsx`
- Modify: `dashboard/convex/squadSpecs.ts`
- Modify: `dashboard/convex/squadSpecs.test.ts`
- Modify: `dashboard/features/agents/components/AgentSidebar.tsx`

**Step 1: Write the failing tests**

Add tests that prove:

- the selected agent detail loads only active squads that include the agent id
- archived squads are excluded
- clicking a squad from `Active Squads` opens the squad detail sheet

Example assertion shape:

```tsx
expect(screen.getByText("Active Squads")).toBeInTheDocument();
expect(screen.getByRole("button", { name: /content squad/i })).toBeInTheDocument();
expect(screen.queryByText("Archived Squad")).not.toBeInTheDocument();
```

**Step 2: Run the targeted tests and confirm they fail**

```bash
cd dashboard
npm run test -- features/agents/components/AgentSidebar.test.tsx features/agents/hooks/useActiveSquadsForAgent.test.tsx
```

Expected: FAIL because there is no active-squad query or UI in the agent detail sheet.

**Step 3: Implement the minimal data/UI changes**

- add a Convex query or derived hook for active squads by agent id
- render `Active Squads` inside `AgentConfigSheet`
- wire squad row clicks back into the existing `selectedSquadId` / `SquadDetailSheet` flow

**Step 4: Re-run the targeted tests**

Run the same command and expect PASS.

**Step 5: Commit**

```bash
git add dashboard/features/agents/components/AgentConfigSheet.tsx dashboard/features/agents/hooks/useActiveSquadsForAgent.ts dashboard/features/agents/hooks/useActiveSquadsForAgent.test.tsx dashboard/convex/squadSpecs.ts dashboard/convex/squadSpecs.test.ts dashboard/features/agents/components/AgentSidebar.tsx
git commit -m "feat: show active squad membership in agent detail"
```

### Task 3: Add failing tests for canonical squad-agent publish fields

**Files:**
- Modify: `dashboard/convex/lib/squadGraphPublisher.test.ts`
- Modify: `dashboard/features/agents/hooks/useCreateSquadDraft.test.tsx`
- Modify: `dashboard/convex/squadSpecs.test.ts`

**Step 1: Write the failing tests**

Add tests that prove:

- a newly created agent from squad publish persists `prompt`, `model`, `skills`, and `soul`
- direct squad publish does not drop these fields from the graph
- an existing active agent is reused instead of duplicated when the user chose reuse

Example assertion shape:

```ts
expect(agentInsert.value.model).toBe("cc/claude-sonnet-4-6");
expect(agentInsert.value.prompt).toContain("Prompt guia");
expect(agentInsert.value.soul).toContain("SOUL.md");
expect(agentInserts).toHaveLength(0);
```

**Step 2: Run the targeted tests and confirm they fail**

```bash
cd dashboard
npm run test -- convex/lib/squadGraphPublisher.test.ts features/agents/hooks/useCreateSquadDraft.test.tsx convex/squadSpecs.test.ts
```

Expected: FAIL because squad publish currently stores only a reduced agent payload.

**Step 3: Implement the draft extraction changes**

- extend `useCreateSquadDraft` to preserve canonical agent fields from the draft graph
- extend the Convex mutation validator for squad graph agent payloads

**Step 4: Re-run the targeted tests**

Run the same command and expect PASS.

**Step 5: Commit**

```bash
git add dashboard/features/agents/hooks/useCreateSquadDraft.ts dashboard/features/agents/hooks/useCreateSquadDraft.test.tsx dashboard/convex/squadSpecs.test.ts dashboard/convex/lib/squadGraphPublisher.test.ts
git commit -m "test: lock canonical squad agent publish fields"
```

### Task 4: Implement canonical squad publish

**Files:**
- Modify: `dashboard/convex/lib/squadGraphPublisher.ts`
- Modify: `dashboard/convex/squadSpecs.ts`
- Modify: `dashboard/convex/agents.ts`
- Modify: `dashboard/features/agents/hooks/useAgentConfigSheetData.ts`

**Step 1: Implement the minimal publish changes**

- when reusing an existing agent, reference its id and keep its canonical data
- when creating a new agent from squad publish, persist the canonical fields:
  `name`, `displayName`, `role`, `prompt`, `model`, `skills`, `soul`
- keep squad membership on canonical `agents`

**Step 2: Run the targeted tests**

```bash
cd dashboard
npm run test -- convex/lib/squadGraphPublisher.test.ts features/agents/hooks/useCreateSquadDraft.test.tsx convex/squadSpecs.test.ts
```

Expected: PASS.

**Step 3: Run dashboard file checks and commit**

```bash
cd dashboard
npm run format:file:check -- convex/lib/squadGraphPublisher.ts convex/squadSpecs.ts convex/agents.ts features/agents/hooks/useCreateSquadDraft.ts features/agents/hooks/useAgentConfigSheetData.ts
npm run lint:file -- convex/lib/squadGraphPublisher.ts convex/squadSpecs.ts convex/agents.ts features/agents/hooks/useCreateSquadDraft.ts features/agents/hooks/useAgentConfigSheetData.ts
git add dashboard/convex/lib/squadGraphPublisher.ts dashboard/convex/squadSpecs.ts dashboard/convex/agents.ts dashboard/features/agents/hooks/useCreateSquadDraft.ts dashboard/features/agents/hooks/useAgentConfigSheetData.ts
git commit -m "feat: persist canonical agents from squad publish"
```

### Task 5: Add active-agent reuse support to squad authoring

**Files:**
- Modify: `mc/contexts/agents/authoring_assist.py`
- Modify: `dashboard/app/api/authoring/squad-wizard/route.ts`
- Modify: `dashboard/app/api/authoring/squad-wizard/route.test.ts`
- Modify: `dashboard/features/agents/lib/authoringContract.ts`
- Modify: `dashboard/features/agents/hooks/useAuthoringSession.ts`
- Modify: `dashboard/features/agents/hooks/useAuthoringSession.test.tsx`

**Step 1: Write the failing tests**

Add tests that prove:

- the squad authoring route receives active registered-agent context
- the authoring response can carry reuse suggestions or explicit reuse decisions
- accepted reuse results in a graph that references the existing global agent rather than a duplicate

Example assertion shape:

```ts
expect(result.current.draftGraph.agents[0]).toMatchObject({
  reuseCandidateAgentName: "post-writer",
});
```

**Step 2: Run the targeted tests and confirm they fail**

```bash
cd dashboard
npm run test -- app/api/authoring/squad-wizard/route.test.ts features/agents/hooks/useAuthoringSession.test.tsx
```

Expected: FAIL because the authoring flow currently has no reuse-candidate support.

**Step 3: Implement the minimal reuse flow**

- load active registered agents into the squad-authoring backend context
- update the squad authoring prompt/contract so it can ask about reuse candidates
- preserve the chosen reuse decision in the draft graph returned to the frontend

**Step 4: Re-run the targeted tests**

Run the same command and expect PASS.

**Step 5: Commit**

```bash
git add mc/contexts/agents/authoring_assist.py dashboard/app/api/authoring/squad-wizard/route.ts dashboard/app/api/authoring/squad-wizard/route.test.ts dashboard/features/agents/lib/authoringContract.ts dashboard/features/agents/hooks/useAuthoringSession.ts dashboard/features/agents/hooks/useAuthoringSession.test.tsx
git commit -m "feat: add squad authoring agent reuse prompts"
```

### Task 6: Full verification and browser validation

**Files:**
- Modify as needed from prior tasks only

**Step 1: Run dashboard checks for touched files**

```bash
cd dashboard
npm run format:file:check -- features/agents/components/AgentSidebar.tsx features/agents/components/AgentSidebar.test.tsx features/agents/components/AgentConfigSheet.tsx features/agents/components/SquadSidebarSection.tsx features/agents/hooks/useActiveSquadsForAgent.ts features/agents/hooks/useActiveSquadsForAgent.test.tsx features/agents/hooks/useCreateSquadDraft.ts features/agents/hooks/useCreateSquadDraft.test.tsx features/agents/lib/authoringContract.ts features/agents/hooks/useAuthoringSession.ts features/agents/hooks/useAuthoringSession.test.tsx convex/squadSpecs.ts convex/squadSpecs.test.ts convex/lib/squadGraphPublisher.ts convex/lib/squadGraphPublisher.test.ts app/api/authoring/squad-wizard/route.ts app/api/authoring/squad-wizard/route.test.ts
npm run lint:file -- features/agents/components/AgentSidebar.tsx features/agents/components/AgentSidebar.test.tsx features/agents/components/AgentConfigSheet.tsx features/agents/components/SquadSidebarSection.tsx features/agents/hooks/useActiveSquadsForAgent.ts features/agents/hooks/useActiveSquadsForAgent.test.tsx features/agents/hooks/useCreateSquadDraft.ts features/agents/hooks/useCreateSquadDraft.test.tsx features/agents/lib/authoringContract.ts features/agents/hooks/useAuthoringSession.ts features/agents/hooks/useAuthoringSession.test.tsx convex/squadSpecs.ts convex/squadSpecs.test.ts convex/lib/squadGraphPublisher.ts convex/lib/squadGraphPublisher.test.ts app/api/authoring/squad-wizard/route.ts app/api/authoring/squad-wizard/route.test.ts
npm run test -- features/agents/components/AgentSidebar.test.tsx features/agents/hooks/useActiveSquadsForAgent.test.tsx features/agents/hooks/useCreateSquadDraft.test.tsx features/agents/hooks/useAuthoringSession.test.tsx app/api/authoring/squad-wizard/route.test.ts convex/lib/squadGraphPublisher.test.ts convex/squadSpecs.test.ts
npm run test:architecture
```

**Step 2: Run MC preview validation**

From the worktree root:

```bash
cp /Users/ennio/Documents/nanobot-ennio/dashboard/.env.local /Users/ennio/Documents/nanobot-ennio/.worktrees/codex/agent-sidebar-squad-authoring/dashboard/.env.local
PORT=3001 uv run nanobot mc start
```

Then validate:

- sidebar search across all sections
- `Registered` collapsible
- scroll window in each section
- agent detail shows active squads and squad click opens squad detail
- `Create Squad` shows reuse prompt behavior and published agents retain model/prompt/soul

**Step 3: Commit final implementation**

```bash
git add -A
git commit -m "feat: unify agent sidebar and canonical squad authoring"
```
