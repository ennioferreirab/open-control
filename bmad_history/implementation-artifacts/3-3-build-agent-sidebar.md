# Story 3.3: Build Agent Sidebar

Status: done

## Story

As a **user**,
I want to see all registered agents and their current status on the dashboard sidebar,
So that I know which agents are available and what they're doing.

## Acceptance Criteria

1. **Given** agents exist in the Convex `agents` table, **When** the dashboard loads, **Then** the Agent Sidebar displays each agent as an `AgentSidebarItem` with: avatar (32px, colored, 2-letter initials), name (`text-sm`, `font-medium`), role (`text-xs`, muted), status dot (8px circle)
2. **Given** agents are displayed, **Then** status dots use correct colors: blue with glow ring (active), gray (idle), red with glow ring (crashed)
3. **Given** agents exist in Convex, **Then** agent status updates in real-time via Convex reactive queries
4. **Given** the sidebar is in collapsed mode (64px), **When** the user views the sidebar, **Then** only agent avatars (36px) are shown with status dot overlaid at bottom-right
5. **Given** the sidebar is collapsed, **When** the user hovers an avatar, **Then** a ShadCN Tooltip shows: name, role, status
6. **Given** no agents are registered, **When** the sidebar renders, **Then** it displays: "No agents found. Add a YAML config to `~/.nanobot/agents/`"
7. **And** `AgentSidebar.tsx` and `AgentSidebarItem.tsx` components are created
8. **And** the sidebar uses Convex `agents.ts` `list` query for reactive data (created in Story 3.2)
9. **And** status dot color transitions use CSS transition (200ms)

## Tasks / Subtasks

- [ ] Task 1: Create the AgentSidebarItem component (AC: #1, #2, #4, #5, #9)
  - [ ] 1.1: Create `dashboard/components/AgentSidebarItem.tsx` with `"use client"` directive
  - [ ] 1.2: Accept props: `agent` object (matching Convex agent document shape from `Doc<"agents">`)
  - [ ] 1.3: Render expanded variant: avatar (32px circle with colored background, 2-letter initials from display name) + name (`text-sm font-medium`) + role (`text-xs text-slate-500`) + status dot (8px)
  - [ ] 1.4: Render collapsed variant: avatar only (36px) with status dot overlaid at bottom-right corner (absolute positioned)
  - [ ] 1.5: Implement status dot colors: `bg-blue-500` with `shadow-[0_0_6px_rgba(59,130,246,0.5)]` (active), `bg-slate-400` (idle), `bg-red-500` with `shadow-[0_0_6px_rgba(239,68,68,0.5)]` (crashed)
  - [ ] 1.6: Add CSS transition on status dot: `transition-colors duration-200`
  - [ ] 1.7: Wrap collapsed variant in ShadCN `Tooltip` showing name, role, and status text
  - [ ] 1.8: Use `useSidebar()` hook to detect collapsed/expanded state

- [ ] Task 2: Create the AgentSidebar component (AC: #1, #3, #6, #8)
  - [ ] 2.1: Create `dashboard/components/AgentSidebar.tsx` with `"use client"` directive
  - [ ] 2.2: Use `useQuery(api.agents.list)` to subscribe to all agents (real-time updates)
  - [ ] 2.3: Render a ShadCN `SidebarGroup` with `SidebarGroupLabel` "Agents"
  - [ ] 2.4: Render each agent as an `AgentSidebarItem` inside a `SidebarMenu` / `SidebarMenuItem` list
  - [ ] 2.5: Show empty state when no agents: muted text "No agents found. Add a YAML config to `~/.nanobot/agents/`"
  - [ ] 2.6: Handle loading state (agents === undefined): show nothing or subtle placeholder

- [ ] Task 3: Implement avatar color generation (AC: #1)
  - [ ] 3.1: Create a deterministic color function that generates a consistent background color from an agent name (hash-based)
  - [ ] 3.2: Use a palette of 8-10 distinct, pleasant colors that work with white text initials
  - [ ] 3.3: Extract 2-letter initials from `displayName` (first letter of first two words, or first two letters if single word)

- [ ] Task 4: Integrate AgentSidebar into DashboardLayout (AC: #1)
  - [ ] 4.1: Import and render `AgentSidebar` inside the existing ShadCN `Sidebar` component in `DashboardLayout.tsx`
  - [ ] 4.2: Place it in the `SidebarContent` area of the existing sidebar structure
  - [ ] 4.3: Ensure the sidebar toggle (collapse/expand) works with the new agent items

- [ ] Task 5: Write unit tests (AC: #7)
  - [ ] 5.1: Create `dashboard/components/AgentSidebarItem.test.tsx`
  - [ ] 5.2: Test that expanded variant renders avatar, name, role, and status dot
  - [ ] 5.3: Test status dot color mapping: active -> blue, idle -> gray, crashed -> red
  - [ ] 5.4: Test 2-letter initials extraction from display name
  - [ ] 5.5: Test empty state message renders when no agents exist

## Dev Notes

### Critical Architecture Requirements

- **Convex reactive queries**: The `useQuery(api.agents.list)` hook automatically re-renders the sidebar when any agent's status changes in Convex. This is how real-time status updates work -- no polling, no WebSocket setup needed.
- **ShadCN Sidebar components**: The dashboard already has the ShadCN `Sidebar` primitive installed (see `dashboard/components/ui/sidebar.tsx`). Use the existing sidebar infrastructure: `SidebarProvider`, `Sidebar`, `SidebarContent`, `SidebarGroup`, `SidebarGroupLabel`, `SidebarMenu`, `SidebarMenuItem`, `SidebarMenuButton`. The sidebar already supports `collapsible="icon"` mode.
- **`useSidebar()` hook**: This hook from the ShadCN sidebar component provides `state` ("expanded" | "collapsed") which you can use to conditionally render the expanded or collapsed variant of `AgentSidebarItem`.
- **No separate sidebar state management**: The collapse/expand state is already managed by `SidebarProvider`. Just use `useSidebar()` to read the current state.

### Status Dot Styling

```tsx
const STATUS_DOT_STYLES: Record<AgentStatus, string> = {
  active: "bg-blue-500 shadow-[0_0_6px_rgba(59,130,246,0.5)]",
  idle: "bg-slate-400",
  crashed: "bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.5)]",
};
```

The `shadow-[...]` creates a subtle glow effect around the active and crashed dots, making them more noticeable without being aggressive. This aligns with the UX spec's "calm signals, not alarms" principle.

### Avatar Color Generation

```typescript
const AVATAR_COLORS = [
  "bg-blue-500", "bg-emerald-500", "bg-violet-500", "bg-amber-500",
  "bg-rose-500", "bg-cyan-500", "bg-indigo-500", "bg-teal-500",
];

function getAvatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function getInitials(displayName: string): string {
  const words = displayName.trim().split(/\s+/);
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  return displayName.slice(0, 2).toUpperCase();
}
```

### AgentSidebarItem Expanded Layout

```
+-----------------------------------------------+
|  [AV]  Agent Name              [*] status dot  |
|        Role description                        |
+-----------------------------------------------+
```

- Avatar: 32px circle, colored bg, white 2-letter initials
- Name: `text-sm font-medium text-slate-900`
- Role: `text-xs text-slate-500`
- Status dot: 8px circle, positioned at the right

### AgentSidebarItem Collapsed Layout

```
+------+
| [AV] |   <- 36px avatar with status dot overlaid at bottom-right
|   [*]|
+------+
```

- Avatar: 36px circle
- Status dot: 8px circle, absolute positioned at bottom-right
- Tooltip on hover: "Agent Name - Role - Status"

### ShadCN Sidebar Integration Pattern

The existing sidebar (from Story 2.1) should already have a structure like:

```tsx
<SidebarProvider>
  <Sidebar collapsible="icon">
    <SidebarHeader>...</SidebarHeader>
    <SidebarContent>
      <AgentSidebar />  {/* <-- Insert here */}
    </SidebarContent>
    <SidebarFooter>...</SidebarFooter>
  </Sidebar>
  <SidebarInset>
    {/* Main content (Kanban board) */}
  </SidebarInset>
</SidebarProvider>
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT create a custom sidebar collapse mechanism** -- The ShadCN `Sidebar` with `collapsible="icon"` already handles collapse/expand. Use `useSidebar()` to detect state. Do NOT add custom state management.
2. **DO NOT use `SidebarMenuButton` with `asChild` for non-interactive items** -- Agent items are display-only (no navigation). Use `SidebarMenuButton` for layout consistency but agents are not clickable for navigation in MVP.
3. **DO NOT poll for agent status updates** -- `useQuery(api.agents.list)` is reactive. It auto-updates. No `setInterval` or manual refetch.
4. **DO NOT hardcode agent data** -- Always use the Convex reactive query. Even for testing, mock the Convex hook.
5. **DO NOT forget the `"use client"` directive** -- Any component using `useQuery` or `useSidebar` must be a client component.
6. **DO NOT use random colors for avatars** -- Use a deterministic hash-based color function so the same agent always gets the same color.
7. **DO NOT import from `convex/agents.ts` directly in components** -- Use the `api` object: `useQuery(api.agents.list)`. The `api` is auto-generated by Convex from the function exports.
8. **DO NOT render the Tooltip in expanded mode** -- Tooltips are only for the collapsed sidebar state where the full name/role is hidden.

### What This Story Does NOT Include

- **No agent click actions** -- Clicking an agent in the sidebar doesn't navigate or open a detail panel. This is display-only for MVP.
- **No agent filtering or search** -- All registered agents are shown. No filter/search capability needed.
- **No drag-and-drop agent reordering** -- Agents are displayed in the order returned by Convex query.
- **No agent creation from sidebar** -- Agent creation is via CLI (Story 3.4) or YAML files.

### Files Created in This Story

| File | Purpose |
|------|---------|
| `dashboard/components/AgentSidebar.tsx` | Sidebar container with Convex reactive query for agents |
| `dashboard/components/AgentSidebarItem.tsx` | Individual agent entry with expanded/collapsed variants |
| `dashboard/components/AgentSidebarItem.test.tsx` | Unit tests for agent sidebar item |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/components/DashboardLayout.tsx` | Import and render `AgentSidebar` inside the existing `Sidebar` `SidebarContent` |

### Verification Steps

1. Ensure Story 3.2 agents exist in Convex `agents` table (or insert test data via Convex dashboard)
2. Open dashboard at localhost:3000 -> agents appear in sidebar with avatar, name, role, status dot
3. Change an agent's status in Convex dashboard (e.g., "idle" to "active") -> status dot updates in real-time (blue glow)
4. Set an agent to "crashed" -> red dot with glow appears
5. Toggle sidebar collapse -> avatars only with status dots, tooltips on hover
6. Clear all agents from Convex -> empty state message appears
7. Verify responsive behavior: at viewport 1024-1279px, sidebar should be collapsed by default
8. Run tests: `cd dashboard && npx vitest run`

### References

- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Component Strategy`] -- AgentSidebarItem spec (avatar, status dot, collapsed variant)
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Color System`] -- Status palette (blue active, gray idle, red crashed)
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Real-Time Update Patterns`] -- Status dot CSS transition 200ms
- [Source: `_bmad-output/planning-artifacts/architecture.md#Frontend Architecture`] -- Convex reactive queries for state management
- [Source: `dashboard/components/ui/sidebar.tsx`] -- ShadCN Sidebar component with all sub-components
- [Source: `dashboard/lib/constants.ts`] -- `AGENT_STATUS` constants
- [Source: `dashboard/convex/schema.ts`] -- `agents` table schema

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References
- TypeScript check: `npx tsc --noEmit` passed cleanly (zero errors)
- Tests: `npx vitest run components/AgentSidebarItem.test.tsx` — 15/15 passed

### Completion Notes List
- Created Convex `agents.list` query since Story 3.2 had not yet delivered it
- Updated existing `AgentSidebar.tsx` placeholder (from Story 2.1) with real-time Convex reactive query
- Created `AgentSidebarItem.tsx` with expanded/collapsed variants, deterministic avatar colors, status dot glow effects
- DashboardLayout.tsx already imported and rendered `AgentSidebar` from Story 2.1 — no changes needed
- All acceptance criteria satisfied: real-time updates via `useQuery`, collapsed mode with tooltips, empty state message, status dot CSS transitions

### File List
- `dashboard/convex/agents.ts` — NEW: Convex query for listing all agents
- `dashboard/components/AgentSidebar.tsx` — MODIFIED: Real agent list with Convex reactive query, empty state, loading state
- `dashboard/components/AgentSidebarItem.tsx` — NEW: Agent sidebar item with expanded/collapsed variants
- `dashboard/components/AgentSidebarItem.test.tsx` — NEW: 15 unit tests for initials, avatar color, status dots, collapsed mode
