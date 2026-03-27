# Story PERF-1: Deduplicate Dashboard Convex Subscriptions

Status: ready-for-dev

## Story

As the platform operator,
I want redundant Convex subscriptions eliminated from the dashboard,
so that idle page load doesn't create ~26 WebSocket subscriptions when ~18 suffice.

## Acceptance Criteria

1. A single `AppDataProvider` React Context subscribes once to `agents.list`, `boards.list`, `taskTags.list`, and `tagAttributes.list`. All hooks that previously subscribed independently now consume from this context.
2. `TrashBinSheet` and `DoneTasksSheet` only mount (and subscribe) when their respective sheets are open — not on initial KanbanBoard mount.
3. `ActivityFeedPanel`'s `useActivityFeed` accepts an `enabled` parameter and uses the `"skip"` pattern when disabled (panel collapsed).
4. `useAgentSidebarData` derives `deletedAgents` from the shared `agents.list` data via `useMemo` instead of subscribing to `agents.listDeleted` separately.
5. All existing dashboard tests pass without regression.
6. No visual or behavioral regression in the dashboard UI.

## Tasks / Subtasks

- [ ] Task 1: Create `AppDataProvider` (AC: #1)
  - [ ] 1.1 Create `dashboard/components/AppDataProvider.tsx` with React Context providing `agents`, `boards`, `taskTags`, `tagAttributes` via single `useQuery` calls each
  - [ ] 1.2 Create `useAppData()` hook for consuming the context
  - [ ] 1.3 Wrap the dashboard root (in `DashboardLayout` or `app/page.tsx`) with `<AppDataProvider>`
  - [ ] 1.4 Update `dashboard/features/boards/hooks/useBoardProviderData.ts` — consume `boards` from `useAppData()` instead of `useQuery(api.boards.list)`
  - [ ] 1.5 Update `dashboard/features/boards/hooks/useBoardSelectorData.ts` — consume `boards` and `agents` from `useAppData()`
  - [ ] 1.6 Update `dashboard/features/agents/hooks/useAgentSidebarData.ts` — consume `agents` from `useAppData()`
  - [ ] 1.7 Update `dashboard/features/search/hooks/useSearchBarFilters.ts` — consume `taskTags` and `tagAttributes` from `useAppData()`
  - [ ] 1.8 Update `dashboard/features/tasks/hooks/useTaskInputData.ts` — consume `taskTags` and `tagAttributes` from `useAppData()`

- [ ] Task 2: Lazy-mount TrashBinSheet and DoneTasksSheet (AC: #2)
  - [ ] 2.1 In `dashboard/features/boards/components/KanbanBoard.tsx`, conditionally render sheets: `{trashOpen && <TrashBinSheet open ... />}` and `{doneSheetOpen && <DoneTasksSheet open ... />}`

- [ ] Task 3: Lazy ActivityFeedPanel subscription (AC: #3)
  - [ ] 3.1 Add `enabled` parameter to `useActivityFeed()` in `dashboard/features/activity/hooks/useActivityFeed.ts`; use `"skip"` pattern when `enabled=false`
  - [ ] 3.2 Pass `enabled={!activityPanelCollapsed}` from the parent component that renders `ActivityFeedPanel`

- [ ] Task 4: Derive deletedAgents from shared agents list (AC: #4)
  - [ ] 4.1 In `dashboard/features/agents/hooks/useAgentSidebarData.ts`, remove `useQuery(api.agents.listDeleted)` and derive `deletedAgents` from the `agents` list using `useMemo(() => allAgents?.filter(a => !!a.deletedAt), [allAgents])`

- [ ] Task 5: Verify no regressions (AC: #5, #6)
  - [ ] 5.1 Run `cd dashboard && npm run test` — all tests pass
  - [ ] 5.2 Run `cd dashboard && npx tsc --noEmit` — no type errors

## Dev Notes

### Why this story exists

The dashboard creates ~26 Convex WebSocket subscriptions on page load, many duplicated across components. Each subscription re-evaluates when its tables are mutated, causing unnecessary server compute and bandwidth. This story consolidates duplicates and defers unused subscriptions.

### Expected Files

| File | Change |
|------|--------|
| `dashboard/components/AppDataProvider.tsx` | **NEW** — React Context providing shared Convex subscriptions |
| `dashboard/components/DashboardLayout.tsx` | Wrap with `<AppDataProvider>` |
| `dashboard/features/boards/hooks/useBoardProviderData.ts` | Use `useAppData()` for boards |
| `dashboard/features/boards/hooks/useBoardSelectorData.ts` | Use `useAppData()` for boards + agents |
| `dashboard/features/agents/hooks/useAgentSidebarData.ts` | Use `useAppData()` for agents; derive deletedAgents |
| `dashboard/features/search/hooks/useSearchBarFilters.ts` | Use `useAppData()` for taskTags + tagAttributes |
| `dashboard/features/tasks/hooks/useTaskInputData.ts` | Use `useAppData()` for taskTags + tagAttributes |
| `dashboard/features/boards/components/KanbanBoard.tsx` | Conditional rendering of TrashBin/DoneSheets |
| `dashboard/features/activity/hooks/useActivityFeed.ts` | Add `enabled` param with skip pattern |
| Parent of `ActivityFeedPanel` | Pass `enabled={!collapsed}` |

### Technical Constraints

- `AppDataProvider` must be placed INSIDE the Convex provider (it uses `useQuery`).
- The `useAppData()` hook must throw if used outside the provider (standard React Context pattern).
- `agents.list` returns non-deleted agents. `deletedAgents` must be derived from a separate source OR the `AppDataProvider` must also subscribe to a combined query. The simplest approach: include `agents.listDeleted` in the provider too (still 1 subscription vs previous 2).
- Actually, looking at agents.list code: it does `ctx.db.query("agents").collect()` then filters `!deletedAt`. So both `list` and `listDeleted` do full scans of the same table. Best approach: subscribe to a new `agents.listAll` (or just use `agents.list` which already fetches all and filters) — the AppDataProvider can expose both filtered and deleted views from a single subscription. BUT this requires a Convex change. Simpler: keep `agents.listDeleted` in the provider as a second subscription, just centralized.
- CORRECTION: The simplest approach that avoids Convex changes: the `AppDataProvider` subscribes to `agents.listDeleted` alongside `agents.list` and exposes both. This still centralizes from 2+1 scattered subscriptions to 2 centralized ones. The `useAgentSidebarData` no longer needs its own `useQuery(api.agents.listDeleted)`.

### Testing Guidance

- Follow `agent_docs/running_tests.md`.
- The primary risk is breaking components that currently call `useQuery` directly — they must now use `useAppData()`.
- Mock `useAppData()` in tests that mock Convex queries, or ensure `AppDataProvider` wraps test renderers.
- Run full test suite to catch any component that still uses the old direct `useQuery` pattern.

### References

- [Plan: /Users/ennio/.claude/plans/piped-gliding-emerson.md — Fixes A1, A2, A3, A6]
- [Source: dashboard/components/DashboardLayout.tsx]
- [Source: dashboard/features/boards/hooks/useBoardProviderData.ts]
- [Source: dashboard/features/boards/hooks/useBoardSelectorData.ts]
- [Source: dashboard/features/agents/hooks/useAgentSidebarData.ts]
- [Source: dashboard/features/search/hooks/useSearchBarFilters.ts]
- [Source: dashboard/features/tasks/hooks/useTaskInputData.ts]
- [Source: dashboard/features/boards/components/KanbanBoard.tsx]
- [Source: dashboard/features/activity/hooks/useActivityFeed.ts]

## Dev Agent Record

### Status: completed

### Files Changed

| File | Change |
|------|--------|
| `dashboard/components/AppDataProvider.tsx` | **NEW** — React Context providing centralized Convex subscriptions for agents, deletedAgents, boards, taskTags, tagAttributes |
| `dashboard/components/DashboardLayout.tsx` | Wrapped with `<AppDataProvider>` outside `<BoardProvider>` |
| `dashboard/components/DashboardLayout.test.tsx` | Added mock for `@/components/AppDataProvider` |
| `dashboard/features/boards/hooks/useBoardProviderData.ts` | Consumes `boards` from `useAppData()` instead of direct `useQuery(api.boards.list)` |
| `dashboard/features/boards/hooks/useBoardSelectorData.ts` | Consumes `boards` and `agents` from `useAppData()`; replaced `ReturnType<typeof useQuery<...>>` types with concrete `Doc<>` types |
| `dashboard/features/agents/hooks/useAgentSidebarData.ts` | Consumes `agents` and `deletedAgents` from `useAppData()` instead of direct queries |
| `dashboard/features/search/hooks/useSearchBarFilters.ts` | Consumes `taskTags` and `tagAttributes` from `useAppData()` |
| `dashboard/features/tasks/hooks/useTaskInputData.ts` | Consumes `taskTags` and `tagAttributes` from `useAppData()` |
| `dashboard/features/boards/components/KanbanBoard.tsx` | Conditional rendering: `{trashOpen && <TrashBinSheet>}` and `{doneSheetOpen && <DoneTasksSheet>}` |
| `dashboard/features/activity/hooks/useActivityFeed.ts` | Added `enabled` option with `"skip"` pattern for `useQuery` |
| `dashboard/features/activity/components/ActivityFeed.tsx` | Accepts `enabled` prop, passes to `useActivityFeed({ enabled })` |
| `dashboard/features/activity/components/ActivityFeedPanel.tsx` | Passes `enabled={!collapsed}` to `<ActivityFeed>` |
| `dashboard/hooks/__tests__/useSearchBarFilters.test.ts` | Updated mock from `convex/react` useQuery to `useAppData` mock |
| `dashboard/hooks/__tests__/useTaskInputData.test.ts` | Added `useAppData` mock, removed unused taskTags/tagAttributes from convex/react mock |

### Change Log

1. **Task 1 (AppDataProvider)**: Created `AppDataProvider` context with centralized subscriptions to `agents.list`, `agents.listDeleted`, `boards.list`, `taskTags.list`, and `tagAttributes.list`. Added eslint-disable comment since it's infrastructure, not a UI component. Wrapped `DashboardLayout` with `<AppDataProvider>` outside `<BoardProvider>`. Updated all 5 consumer hooks to use `useAppData()`.
2. **Task 2 (Lazy sheets)**: Changed `TrashBinSheet` and `DoneTasksSheet` in KanbanBoard to only mount when their respective state booleans are true.
3. **Task 3 (ActivityFeed skip)**: Added `enabled` option to `useActivityFeed` with `"skip"` pattern. Threaded `enabled` prop through `ActivityFeedPanel` -> `ActivityFeed` -> `useActivityFeed`.
4. **Task 4 (deletedAgents)**: `useAgentSidebarData` now consumes `deletedAgents` from `useAppData()` (centralized subscription) instead of its own `useQuery(api.agents.listDeleted)`.
5. **Task 5 (Verification)**: TypeScript type check passes (no new errors). All 104 test files pass; 1 pre-existing failure in `AgentSidebarItem.test.tsx` unrelated to this change.
