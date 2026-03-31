# Story 5.6: Command Palette Projected Search

Status: ready-for-dev

## Story

As a dashboard user,
I want the command palette to stop subscribing to large task lists when it is closed,
so that opening and closing the palette does not pull unnecessary Convex bandwidth.

## Acceptance Criteria

1. `CommandPalette` passes an enabled flag to the search hook.
2. `useCommandPaletteSearch` does no Convex work when disabled.
3. Agent search uses the shared AppDataProvider instead of its own query.
4. Task search uses a projected query that returns only minimal fields.
5. Existing command palette behavior still works.

## Tasks / Subtasks

- [ ] Task 1: Gate the hook
  - [ ] 1.1 Update `dashboard/components/CommandPalette.tsx`
  - [ ] 1.2 Update `dashboard/hooks/useCommandPaletteSearch.ts`

- [ ] Task 2: Add projected search query
  - [ ] 2.1 Add a minimal task query in `dashboard/convex/tasks.ts`

- [ ] Task 3: Update tests
  - [ ] 3.1 Update `dashboard/hooks/__tests__/useCommandPaletteSearch.test.ts`

## Expected Files

| File | Change |
|------|--------|
| `dashboard/components/CommandPalette.tsx` | Pass enabled flag |
| `dashboard/hooks/useCommandPaletteSearch.ts` | Skip queries when closed |
| `dashboard/convex/tasks.ts` | Add projected search query |
| `dashboard/hooks/__tests__/useCommandPaletteSearch.test.ts` | Update tests |
