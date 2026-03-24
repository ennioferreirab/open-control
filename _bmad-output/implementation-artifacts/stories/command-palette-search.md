# Story: Command Palette Search

## Story
As a dashboard user, I want the Cmd+K command palette to search across tasks, agents, squads, and quick actions, so I can navigate to any entity without clicking through menus.

## Status: ready-for-dev

## Acceptance Criteria
- [ ] Cmd+K palette searches tasks by title
- [ ] Cmd+K palette searches agents by name/displayName
- [ ] Cmd+K palette searches squads by name/displayName
- [ ] Quick actions (Settings, Tags, Cron Jobs, Board Settings) appear when query is empty and are filterable
- [ ] Selecting a task opens TaskDetailSheet
- [ ] Selecting an agent opens AgentConfigSheet
- [ ] Selecting a squad opens SquadDetailSheet
- [ ] Selecting a quick action opens the corresponding panel/modal
- [ ] Keyboard navigation works: ↑↓ to move, Enter to select, Esc to close
- [ ] Footer filter buttons (All, Tasks, Agents, Squads) restrict visible categories
- [ ] Empty query shows quick actions as launcher mode
- [ ] `make lint && make typecheck` passes
- [ ] Existing tests still pass

## Tasks
- [ ] **Create `dashboard/hooks/useCommandPaletteSearch.ts`** — search hook
  - Subscribe to `api.agents.list`, `api.squadSpecs.list`, `api.tasks.list` via Convex `useQuery`
  - Define `CommandPaletteAction` discriminated union type (openTask, openAgent, openSquad, openSettings, openTags, openCronJobs, openBoardSettings)
  - Define `SearchResult` type: `{ id, category, title, subtitle?, icon, action }`
  - Define `SearchResultGroup` type: `{ category, label, results }`
  - Static `QUICK_ACTIONS` array (Settings, Tags, Cron Jobs, Board Settings)
  - Client-side case-insensitive substring matching (same pattern as AgentSidebar filterQuery)
  - `CategoryFilter` type: `"all" | "task" | "agent" | "squad" | "action"`
  - Hook signature: `useCommandPaletteSearch(query, categoryFilter, boardId)` → `{ groups, flatResults, isLoading }`
  - Empty query → return quick actions only
  - AC refs: all search ACs

- [ ] **Create `dashboard/components/CommandPaletteResultItem.tsx`** — result row component
  - Props: `result: SearchResult`, `isSelected: boolean`, `onClick: () => void`, `ref` for scroll
  - Category icons: `ListChecks` (tasks), `Bot` (agents), `Users` (squads), per-action icon from result
  - Title bold, subtitle muted-foreground
  - Selected state: `bg-accent` background
  - Task results show status as subtle badge
  - AC refs: keyboard navigation, result display

- [ ] **Lift agent/squad selection state — modify `dashboard/features/agents/components/AgentSidebar.tsx`**
  - Change component signature to accept props: `selectedAgent: string | null`, `onSelectAgent: (name: string | null) => void`, `selectedSquadId: Id<"squadSpecs"> | null`, `onSelectSquad: (id: Id<"squadSpecs"> | null) => void`
  - Remove internal `useState` for `selectedAgent` and `selectedSquadId` (lines 59, 63)
  - Replace `setSelectedAgent(...)` calls with `onSelectAgent(...)`
  - Replace `setSelectedSquadId(...)` calls with `onSelectSquad(...)`
  - Remove `AgentConfigSheet` rendering (line ~425-436)
  - Remove `SquadDetailSheet` rendering (line ~438-442)
  - Keep all other internal state (wizards, delete dialogs, filter, collapsibles)
  - AC refs: selecting agent/squad from palette opens correct sheet

- [ ] **Modify `dashboard/components/DashboardLayout.tsx`** — lift state + wire action handler
  - Add imports: `AgentConfigSheet`, `SquadDetailSheet`, `CommandPaletteAction` type
  - Add state: `selectedAgent: string | null`, `selectedSquadId: Id<"squadSpecs"> | null`
  - Create `handleCommandPaletteAction` callback that:
    - Closes palette (`setCommandPaletteOpen(false)`)
    - Switches on `action.type` to set appropriate state
  - Pass `selectedAgent`/`onSelectAgent`/`selectedSquadId`/`onSelectSquad` to `AgentSidebar`
  - Render `AgentConfigSheet` after existing `TaskDetailSheet` with `agentName={selectedAgent}`, `onClose={() => setSelectedAgent(null)}`, `onOpenSquad={(id) => setSelectedSquadId(id)}`
  - Render `SquadDetailSheet` with `squadId={selectedSquadId}`, `onClose={() => setSelectedSquadId(null)}`
  - Pass `onAction={handleCommandPaletteAction}` to `CommandPalette`
  - AC refs: all navigation ACs

- [ ] **Rewrite `dashboard/components/CommandPalette.tsx`** — full search UI
  - Add `onAction` prop to `CommandPaletteProps`
  - Add state: `categoryFilter` (default "all"), `selectedIndex` (default 0)
  - Wire `useCommandPaletteSearch(query, categoryFilter, activeBoardId)` (get boardId from `useBoard()`)
  - Reset `selectedIndex` to 0 when `query` or `categoryFilter` changes
  - Keyboard handler in existing useEffect:
    - ArrowDown: increment selectedIndex (clamp to flatResults.length - 1)
    - ArrowUp: decrement selectedIndex (clamp to 0)
    - Enter: call `onAction(flatResults[selectedIndex].action)` if results exist
  - Render results area: map over `groups`, each with category label header, then result items
  - Empty query: show quick actions
  - No results: show "No results for {query}"
  - Footer filter buttons: make clickable, highlight active filter
  - Add "Squads" filter button alongside existing All/Tasks/Agents
  - `scrollIntoView({ block: "nearest" })` via ref callback on selected item
  - AC refs: all ACs

- [ ] **Tests — `dashboard/hooks/__tests__/useCommandPaletteSearch.test.ts`**
  - Test filtering logic with mock data
  - Test empty query returns quick actions only
  - Test category filter restricts results
  - Test case-insensitive matching
  - Follow patterns from existing `dashboard/hooks/__tests__/useSearchBarFilters.test.ts`

## File List
- `dashboard/hooks/useCommandPaletteSearch.ts` (create)
- `dashboard/components/CommandPaletteResultItem.tsx` (create)
- `dashboard/components/CommandPalette.tsx` (rewrite)
- `dashboard/components/DashboardLayout.tsx` (modify)
- `dashboard/features/agents/components/AgentSidebar.tsx` (modify)
- `dashboard/hooks/__tests__/useCommandPaletteSearch.test.ts` (create)

## Dev Notes
- **No new Convex queries needed.** Reuse `api.agents.list`, `api.squadSpecs.list`, `api.tasks.list`. Convex client deduplicates subscriptions.
- **No new npm dependencies.** Substring matching is sufficient (same pattern as AgentSidebar filter on line ~82).
- **State lifting pattern** follows existing `selectedTaskId` in DashboardLayout — agents/squads are analogous.
- `AgentConfigSheet` accepts `agentName: string | null` (see `AgentConfigSheet.tsx:110-114`).
- `SquadDetailSheet` accepts `squadId: Id<"squadSpecs"> | null` (see `SquadDetailSheet.tsx:27-33`). Also accepts optional `boardId`, `focusWorkflowId`, `onMissionLaunched`.
- `AgentConfigSheet` has `onOpenSquad` callback for cross-navigation to squads.
- Use `useBoard()` hook to get `activeBoardId` for task queries.
- Icons: `ListChecks`, `Bot`, `Users`, `Settings`, `Tag`, `Clock`, `LayoutDashboard` from lucide-react.
- `SYSTEM_AGENT_NAMES` from `@/lib/constants` to identify system agents in results.
- Existing `STATUS_COLORS` or similar from constants for task status badges.
- Keep motion/react animations on the palette shell — only change the content area.
- `api.tasks.list` requires `{ boardId }` argument.

## Testing Standards
- Follow `agent_docs/running_tests.md` decision tree
- Vitest for unit tests, no mocking of Convex unless necessary
- Test the pure filtering/grouping logic by extracting it as a pure function from the hook

## Dev Agent Record
- Model: (to be filled by dev agent)
- Completion notes: (to be filled by dev agent)
- Files modified: (to be filled by dev agent)
