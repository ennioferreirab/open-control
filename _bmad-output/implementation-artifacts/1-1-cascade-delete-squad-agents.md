# Story 1.1: Cascade Delete Squad with Agent Selector

Status: done

## Story

As a user,
I want to see a selector with all squad agents pre-checked when deleting a squad,
so that I can choose which agents to delete alongside the squad, with clear warnings about agents shared with other squads.

## Acceptance Criteria

1. When the user triggers squad deletion (via bulk delete mode), a **DeleteSquadDialog** opens instead of the generic bulk-delete confirmation.
2. The dialog lists **every agent** in the squad's `agentIds` array, each with a **checkbox pre-checked** for deletion.
3. For any agent that belongs to **more than one published squad**, a warning badge is shown indicating which other squads the agent belongs to (e.g., "Also in: Squad Y, Squad D").
4. The user can **uncheck** agents they do not want to delete.
5. On confirm: the squad is archived **and** all checked agents are soft-deleted.
6. If **all agents are unchecked**, only the squad is archived (no agents deleted).
7. System agents (`isSystem: true`) must **never** appear as deletable — they are filtered out of the selector.

## Tasks / Subtasks

- [x] Task 1: New Convex query — resolve agent memberships (AC: #3)
  - [x] 1.1 Add `getSquadAgentsWithMemberships` query in `dashboard/convex/squadSpecs.ts`
  - [x] 1.2 Accepts `squadSpecId`, returns array of `{ agentId, name, displayName, otherSquads: { id, displayName }[] }`
  - [x] 1.3 Resolves by: load target squad → load its agents via `agentIds` → for each agent, scan all other published squads to find membership

- [x] Task 2: New component `DeleteSquadDialog` (AC: #1, #2, #3, #4, #6, #7)
  - [x] 2.1 Create `dashboard/features/agents/components/DeleteSquadDialog.tsx`
  - [x] 2.2 Props: `squadId: Id<"squadSpecs"> | null`, `onClose`, `onDeleted`
  - [x] 2.3 Uses `useQuery(api.squadSpecs.getSquadAgentsWithMemberships, { squadSpecId })` to load agent list
  - [x] 2.4 Renders AlertDialog with:
    - Squad name in title
    - Checkbox list of non-system agents, all pre-checked
    - For multi-squad agents: amber warning text below agent name listing other squads
    - Footer with Cancel / Delete buttons
  - [x] 2.5 On confirm: calls `archiveSquad` + `softDeleteAgent` for each checked agent

- [x] Task 3: Wire `DeleteSquadDialog` into `AgentSidebar` (AC: #1, #5)
  - [x] 3.1 When bulk delete includes **exactly one squad and zero agents**, open `DeleteSquadDialog` instead of generic bulk-delete dialog
  - [x] 3.2 When bulk delete includes squads + agents (mixed), keep current behavior (generic dialog)
  - [x] 3.3 Add state `deleteSquadTarget: Id<"squadSpecs"> | null` to `AgentSidebar`
  - [x] 3.4 On `DeleteSquadDialog.onDeleted`: clear selection, exit delete mode

- [ ] Task 4: Tests (AC: all) — skipped per user request
  - [ ] 4.1 Unit test for `getSquadAgentsWithMemberships` query
  - [ ] 4.2 Component test for `DeleteSquadDialog`

## Dev Notes

### Current Delete Flow

The existing delete flow uses a **bulk mode** pattern in `AgentSidebar.tsx`:
- User enters delete mode via trash icon → checkboxes appear on agents and squads
- User selects items → "Delete selected" button appears in footer
- Clicking opens a generic `AlertDialog` listing all selected items
- `handleBulkDelete` calls `archiveSquad` for squads, `softDeleteAgent` for agents

This story **adds a squad-specific dialog** that triggers when the user selects a single squad for deletion. The generic dialog is untouched for mixed selections.

### Data Model

- `squadSpecs.agentIds`: `Id<"agents">[]` — the direct list of agents in a squad
- `agents.isSystem`: boolean — system agents must not be deletable
- `agents.deletedAt`: soft-delete timestamp
- `squadSpecs.status`: `"draft" | "published" | "archived"`
- To find an agent's squad memberships: scan all published squadSpecs checking if `agentIds` includes the agent's ID

### Key Files to Modify

| File | Change |
|------|--------|
| `dashboard/convex/squadSpecs.ts` | Add `getSquadAgentsWithMemberships` query |
| `dashboard/features/agents/components/DeleteSquadDialog.tsx` | **New file** — the agent selector dialog |
| `dashboard/features/agents/components/AgentSidebar.tsx` | Wire dialog: detect single-squad selection, open `DeleteSquadDialog` |

### Existing Patterns to Follow

- Use `AlertDialog` from `@/components/ui/alert-dialog` (same as existing bulk delete dialog)
- Use `Checkbox` from `@/components/ui/checkbox` (same as `SquadSidebarSection`)
- Use `useMutation` / `useQuery` from `convex/react`
- Mutation calls: `api.squadSpecs.archiveSquad`, `api.agents.softDeleteAgent`
- Color scheme for warnings: use `text-amber-500` for shared-agent warnings (consistent with the codebase warning palette)

### Architecture Compliance

- The new Convex query is an **internal query** (`internalQuery`) since it's only called from the dashboard and doesn't need public API exposure. Actually — if the React component calls it via `useQuery`, it needs to be a regular `query` (exported via `api`).
- No new tables needed; this reads existing `squadSpecs` and `agents` tables.
- Soft-delete for agents (`deletedAt` field) and archive for squads (`status: "archived"`) are already the established patterns.

### Project Structure Notes

- New component goes in `dashboard/features/agents/components/` alongside existing squad/agent components
- Follow the existing pattern of colocating related components in the features directory
- Convex query added to `squadSpecs.ts` where other squad queries live

### References

- [Source: dashboard/convex/schema.ts] — `squadSpecs` table (agentIds field), `agents` table (isSystem, deletedAt)
- [Source: dashboard/convex/squadSpecs.ts] — `archiveSquad` mutation pattern
- [Source: dashboard/convex/agents.ts] — `softDeleteAgent` mutation, `listByIds` query
- [Source: dashboard/features/agents/components/AgentSidebar.tsx] — existing bulk delete flow (lines 123-144, 421-456)
- [Source: dashboard/features/agents/components/SquadSidebarSection.tsx] — Checkbox usage pattern in delete mode

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (coordinator) + Claude Sonnet (dev agents)

### Debug Log References

### Completion Notes List

- Review fix: added `deletedAt` filter to query to exclude already-deleted agents
- Review fix: added catch block for error handling consistency
- Review fix: removed redundant `isSystem` field from query return + component filter
- Review fix: replaced unsafe type assertion with proper type guard in AgentSidebar

### File List

- `dashboard/convex/squadSpecs.ts` — added `getSquadAgentsWithMemberships` query
- `dashboard/features/agents/components/DeleteSquadDialog.tsx` — new component
- `dashboard/features/agents/components/AgentSidebar.tsx` — wired DeleteSquadDialog
