# Story PERF-2: Optimize getBoardView and getDetailView Queries

Status: ready-for-dev

## Story

As the platform operator,
I want the heaviest Convex queries (`getBoardView` and `getDetailView`) to have narrower read-sets and smaller payloads,
so that step/task mutations don't cause unnecessarily expensive re-evaluations.

## Acceptance Criteria

1. `getBoardView` no longer returns `allSteps` (raw step documents). Instead, it returns pre-computed step groups with minimal projected fields needed by `useBoardColumns`.
2. `getBoardView` no longer scans `taskTags` table for `tagColorMap`. The `tagColorMap` is computed client-side from the `AppDataProvider`'s `taskTags` data (from Story PERF-1).
3. `getDetailView` no longer scans `taskTags` and `tagAttributes` tables. These are injected client-side from `AppDataProvider`.
4. `useBoardColumns` consumes the pre-computed step groups from `getBoardView` instead of processing raw `allSteps`.
5. All existing dashboard tests pass without regression.

## Tasks / Subtasks

- [ ] Task 1: Compute step groups server-side in getBoardView (AC: #1)
  - [ ] 1.1 In `dashboard/convex/boards.ts`, replace `allSteps: stepBatches.flat()` with server-computed step group data. For each task's steps, project only: `_id`, `taskId`, `title`, `status`, `order`, `assignedAgent`, `startedAt`, `createdAt`, `stateVersion`. Compute `stepStatusToColumnStatus` server-side to group steps by column.
  - [ ] 1.2 Export `stepStatusToColumnStatus` from `dashboard/hooks/useBoardColumns.ts` to a shared module (e.g., `dashboard/lib/stepColumns.ts`) so both server and client can use it. OR: duplicate the mapping logic in the Convex function (simpler, avoids import complexities between Convex and client code).
  - [ ] 1.3 Return `boardStepGroups` from `getBoardView`: an array of `{ taskId, taskTitle, steps: ProjectedStep[], columnStatus }` objects, pre-grouped by column.

- [ ] Task 2: Refactor useBoardColumns to consume pre-computed groups (AC: #4)
  - [ ] 2.1 Update `dashboard/hooks/useBoardColumns.ts` to accept `boardStepGroups` instead of `allSteps`
  - [ ] 2.2 Update `dashboard/features/boards/hooks/useBoardView.ts` to pass the new shape
  - [ ] 2.3 Update any components that depend on `allSteps` from `useBoardView`

- [ ] Task 3: Remove tagColorMap from getBoardView (AC: #2)
  - [ ] 3.1 Remove `const tagCatalog = await ctx.db.query("taskTags").collect()` and `tagColorMap` computation from `dashboard/convex/boards.ts`
  - [ ] 3.2 Remove `tagColorMap` from the return value of `getBoardView`
  - [ ] 3.3 Compute `tagColorMap` client-side in `dashboard/features/boards/hooks/useBoardView.ts` using `taskTags` from `useAppData()` (depends on PERF-1)

- [ ] Task 4: Remove tagCatalog and tagAttributes from getDetailView (AC: #3)
  - [ ] 4.1 In `dashboard/convex/lib/taskDetailView.ts`, remove `ctx.db.query("taskTags").collect()` and `ctx.db.query("tagAttributes").collect()` calls
  - [ ] 4.2 Remove `tagCatalog` and `tagAttributes` from the return value
  - [ ] 4.3 In `dashboard/features/tasks/hooks/useTaskDetailView.ts`, inject `tagCatalog` and `tagAttributes` from `useAppData()` into the returned data

- [ ] Task 5: Verify (AC: #5)
  - [ ] 5.1 Run `cd dashboard && npm run test`
  - [ ] 5.2 Run `cd dashboard && npx tsc --noEmit`

## Dev Notes

### Why this story exists

`getBoardView` reads 6 tables (boards, tasks, steps, taskTags, tagAttributes, tagAttributeValues) and returns the entire steps array for all board tasks. Any mutation to ANY of these tables triggers a full re-evaluation. By narrowing the read-set and reducing the payload, we cut re-evaluation cost dramatically.

### Expected Files

| File | Change |
|------|--------|
| `dashboard/convex/boards.ts` | Remove `allSteps` from return; compute step groups server-side; remove `taskTags` scan and `tagColorMap` |
| `dashboard/convex/lib/taskDetailView.ts` | Remove `taskTags` and `tagAttributes` scans |
| `dashboard/hooks/useBoardColumns.ts` | Consume pre-computed step groups instead of raw allSteps |
| `dashboard/features/boards/hooks/useBoardView.ts` | Adjust return type; compute tagColorMap client-side |
| `dashboard/features/tasks/hooks/useTaskDetailView.ts` | Inject tagCatalog/tagAttributes from AppDataProvider |

### Technical Constraints

- **Depends on PERF-1**: This story uses `useAppData()` from AppDataProvider. If implementing independently, the tag catalog queries can be moved client-side using direct `useQuery` calls as an intermediate step.
- `stepStatusToColumnStatus` logic currently lives in `dashboard/hooks/useBoardColumns.ts`. The Convex function cannot import from client code. Either duplicate the mapping in the Convex function, or extract to `dashboard/convex/lib/stepColumns.ts` (importable by both).
- The `isWorkflowOwnedTask` check used in `useBoardColumns` needs `task.workMode` — this is available server-side since `getBoardView` already has the full task documents.
- Be careful with the `useBoardColumns` return type: `ColumnData` includes `stepGroups` and `tagGroups`. The step groups must be compatible.

### Testing Guidance

- Follow `agent_docs/running_tests.md`.
- `dashboard/hooks/useBoardColumns.test.ts` and `dashboard/hooks/useBoardView.test.ts` will need updates for the new data shape.
- `dashboard/convex/lib/readModels.test.ts` may test `getBoardView` — verify and update.
- Key risk: breaking the kanban step group rendering. Verify visually that step cards still appear in the correct columns.

### References

- [Plan: /Users/ennio/.claude/plans/piped-gliding-emerson.md — Fixes A4, A5]
- [Source: dashboard/convex/boards.ts — getBoardView at line 189]
- [Source: dashboard/convex/lib/taskDetailView.ts — buildTaskDetailView]
- [Source: dashboard/hooks/useBoardColumns.ts]
- [Source: dashboard/features/boards/hooks/useBoardView.ts]

## Dev Agent Record
