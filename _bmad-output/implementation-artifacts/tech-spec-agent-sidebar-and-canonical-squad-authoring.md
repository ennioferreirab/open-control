# Story: Agent Sidebar And Canonical Squad Authoring

Status: ready-for-dev

## Story

As a Mission Control operator,
I want the Agents sidebar and squad authoring flow to scale cleanly and use the
same canonical global agent records,
so that I can find agents quickly, understand squad membership, and avoid
creating inconsistent or duplicate agents.

## Problems Found

- The Agents sidebar has no text search across agents and squads.
- `Registered` is not collapsible while the other sections already use
  collapsible affordances.
- Long sections grow unbounded instead of keeping a fixed-height list with
  internal scroll.
- Opening an agent does not show which active squads reference it.
- Agents created through `Create Squad` do not persist the same canonical data
  as agents created through `Create Agent`, including `model`, `prompt`, and
  `soul`.
- `Create Squad` does not inspect active registered agents for reuse
  opportunities before creating new ones.

## Solution

Unify the sidebar and authoring behavior around the canonical global `agents`
registry:

- add a global text filter to the Agents sidebar
- search across `Squads`, `Registered`, `System`, and `Remoto`
- make `Registered` collapsible and apply the same collapsible plus bounded
  scroll pattern to every section
- show active squad memberships inside agent detail and open squad detail on
  click
- make squad publish preserve the same canonical agent payload as direct agent
  creation
- make squad authoring consult active registered agents and ask the user
  whether to reuse matching candidates

## Acceptance Criteria

1. The Agents sidebar has one text filter that searches all visible sections.
2. Agent filtering matches `displayName`, `name`, and `@name`.
3. Squad filtering matches `displayName` and `name`.
4. `Registered`, `System`, `Remoto`, and `Squads` all render as bounded
   section lists with internal scroll when they exceed 10 visible items.
5. `Registered` is collapsible in the same style as the other sections.
6. Opening an agent shows only active squads that reference that agent.
7. Clicking a squad from the agent detail opens the squad detail sheet.
8. Agents created through `Create Squad` persist the same canonical fields as
   `Create Agent`, including `prompt`, `model`, `skills`, and `soul`.
9. When squad authoring finds an active registered agent with a similar role,
   prompt, display name, or name, it asks the user whether to reuse that agent
   for the proposed squad role.
10. Accepting reuse references the existing global agent instead of creating a
    duplicate.

## Tasks / Subtasks

- [ ] Task 1: Add failing tests for sidebar search, collapsibles, and bounded
      section lists
- [ ] Task 2: Implement sidebar search and per-section scroll windows
- [ ] Task 3: Add active squad membership loading and navigation to agent
      detail
- [ ] Task 4: Add failing tests for canonical squad-agent publish fields and
      reuse behavior
- [ ] Task 5: Implement canonical squad-agent publish with `prompt`, `model`,
      `skills`, and `soul`
- [ ] Task 6: Extend squad authoring to inspect active registered agents and
      confirm reuse candidates with the user
- [ ] Task 7: Run targeted dashboard checks, browser validation, and capture
      evidence

## Dev Notes

- Keep sidebar behavior in `dashboard/features/agents/`.
- Keep canonical global-agent persistence in the Convex squad publish path.
- Keep authoring flow changes aligned with `mc/contexts/agents/authoring_assist.py`
  and the frontend authoring contract.
- Do not treat `Create Squad` as a separate agent model. It must publish or
  reference the same global `agents` records used everywhere else.
- Only active registered agents are candidates for squad-authoring reuse.
- Agent detail squad membership must exclude archived squads.

### Project Structure Notes

- UI components and hooks stay under `dashboard/features/agents/`
- Convex-facing data access stays under `dashboard/convex/`
- authoring backend behavior stays under `mc/contexts/`
- preserve the boundaries documented in `docs/ARCHITECTURE.md`

### References

- [Source: docs/plans/2026-03-15-agent-sidebar-and-squad-authoring-design.md]
- [Source: docs/plans/2026-03-15-agent-sidebar-and-squad-authoring-implementation-plan.md]
- [Source: docs/ARCHITECTURE.md]
- [Source: dashboard/features/agents/components/AgentSidebar.tsx]
- [Source: dashboard/features/agents/components/AgentConfigSheet.tsx]
- [Source: dashboard/features/agents/components/SquadSidebarSection.tsx]
- [Source: dashboard/features/agents/hooks/useCreateSquadDraft.ts]
- [Source: dashboard/convex/lib/squadGraphPublisher.ts]
- [Source: mc/contexts/agents/authoring_assist.py]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List

### File List
