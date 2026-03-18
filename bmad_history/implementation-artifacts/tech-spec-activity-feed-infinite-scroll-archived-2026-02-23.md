---
title: 'Activity Feed Infinite Scroll'
slug: 'activity-feed-infinite-scroll'
created: '2026-02-23'
status: 'review'
stepsCompleted: [1, 2, 3, 4, 5]
tech_stack: ['Next.js', 'Convex', 'TypeScript', 'Tailwind CSS', 'Radix ScrollArea']
files_to_modify:
  - 'convex/activities.ts'
  - 'components/ActivityFeed.tsx'
  - 'components/ActivityFeed.test.tsx'
code_patterns:
  - 'paginatedQuery / usePaginatedQuery (Convex SDK)'
  - 'IntersectionObserver for bottom sentinel'
  - 'useCallback ref for ScrollArea viewport (existing pattern)'
test_patterns:
  - 'vi.mock("convex/react") with usePaginatedQuery stub'
  - 'vi.mock motion/react, scroll-area (existing pattern)'
---

# Tech-Spec: Activity Feed Infinite Scroll

**Created:** 2026-02-23

## Overview

### Problem Statement

`ActivityFeed` loads all activities in a single query (`.take(100)`), mounts all DOM nodes at once, and will degrade UI performance as the feed grows. The `listRecent` query is also a hard-capped batch — it cannot load history beyond 100 items and has no pagination.

### Solution

Replace `listRecent` with a Convex `paginatedQuery` (`listPaginated`) ordered newest-first. On the frontend, use the Convex `usePaginatedQuery` hook (initial 20 items) and an `IntersectionObserver` sentinel at the bottom of the list to trigger `loadMore(20)` when the user scrolls to older items. New live items arrive at the top reactively. Auto-scroll to top on new activity when user is already at the top; show a "New activity" badge otherwise.

### Scope

**In Scope:**
- Add `listPaginated` paginatedQuery to `convex/activities.ts`
- Rewrite `ActivityFeed.tsx` to use `usePaginatedQuery`, reverse-chronological order, bottom-sentinel loadMore, and top-scroll for live items
- Update `ActivityFeed.test.tsx` to mock `usePaginatedQuery`
- Keep all existing UI states: loading, reconnecting, empty, "New activity" badge

**Out of Scope:**
- Virtual DOM windowing (overkill for 20-item pages)
- Removing or deprecating `listRecent` (other callers may exist)
- Changes to `ActivityFeedPanel.tsx` (already fixed in prior session)
- Changes to `FeedItem.tsx`

---

## Context for Development

### Codebase Patterns

- **Convex queries**: `convex/activities.ts` uses `query` / `mutation` from `"./_generated/server"`. paginatedQuery uses the same import.
- **Convex `paginatedQuery`**: Backend handler receives `paginationOpts` (validated with `paginationOptsValidator` from `"convex/server"`). Returns `ctx.db.query(...).order("desc").paginate(paginationOpts)`. No `.take()` or `.collect()`.
- **`usePaginatedQuery` hook**: `import { usePaginatedQuery } from "convex/react"`. Returns `{ results, status, loadMore }`. `results` is the accumulated array of all loaded items across pages. `status` is `"LoadingFirstPage" | "CanLoadMore" | "Exhausted"`.
- **Scroll viewport**: The `ScrollArea` (Radix) viewport is obtained via a `useCallback` ref querying `[data-radix-scroll-area-viewport]`. This pattern must be preserved.
- **Auto-scroll**: Currently auto-scrolls to bottom on new items. New design: auto-scroll to **top** (`scrollTop = 0`) when user is at top and new items arrive.
- **"New activity" badge**: Shown when new items arrive and user is not at top. Clicking scrolls to top.
- **Existing test mocks**: `convex/react`, `motion/react`, `@/components/ui/scroll-area` are all mocked in the test file. Test must add `usePaginatedQuery` to the `convex/react` mock.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `convex/activities.ts` | Add `listPaginated` paginatedQuery |
| `components/ActivityFeed.tsx` | Rewrite to use `usePaginatedQuery` + sentinel |
| `components/ActivityFeed.test.tsx` | Update mocks and tests |
| `convex/schema.ts` | Reference: `activities` table has `by_timestamp` index |

### Technical Decisions

- **Order**: `order("desc")` in the backend — newest items come first. The frontend renders items as-is (no `.reverse()`). Newest = top of list. Older = bottom.
- **Sentinel element**: A `<div ref={sentinelRef}>` placed after the last item. `IntersectionObserver` watches it; when it enters the viewport, call `loadMore(20)` if `status === "CanLoadMore"`.
- **Live updates**: Convex `usePaginatedQuery` reactively re-runs the first page query. New items appearing at the top are handled automatically.
- **Scroll detection for "at top"**: `scrollTop < 30` (mirroring the existing `< 30` threshold used for bottom detection).
- **`prevCountRef`**: Track `results.length` to detect new items (same pattern as today).

---

## Implementation Plan

### Tasks

- [x] **Task 1 — Backend: add `listPaginated` to `convex/activities.ts`**
  - File: `convex/activities.ts`
  - Add import: `import { paginationOptsValidator } from "convex/server";`
  - Add export:
    ```ts
    export const listPaginated = query({
      args: { paginationOpts: paginationOptsValidator },
      handler: async (ctx, args) => {
        return await ctx.db
          .query("activities")
          .withIndex("by_timestamp")
          .order("desc")
          .paginate(args.paginationOpts);
      },
    });
    ```
  - Do NOT remove `listRecent` or `list`.

- [x] **Task 2 — Frontend: rewrite `ActivityFeed.tsx`**
  - File: `components/ActivityFeed.tsx`
  - Replace `useQuery` import with `usePaginatedQuery` from `"convex/react"`.
  - Replace `useQuery(api.activities.listRecent)` with:
    ```ts
    const { results: activities, status, loadMore } = usePaginatedQuery(
      api.activities.listPaginated,
      {},
      { initialNumItems: 20 }
    );
    ```
  - Add `sentinelRef = useRef<HTMLDivElement>(null)` for the IntersectionObserver.
  - **Scroll direction inversion**: Change `isAtBottom` → `isAtTop` (true by default). Detection: `el.scrollTop < 30`.
  - **Auto-scroll**: On new items (`results.length > prevCountRef.current`) and `isAtTop`, scroll to `top: 0` (not `scrollHeight`). Otherwise set `hasNewActivity = true`.
  - **"New activity" button**: Scrolls to `top: 0`.
  - **`scrollToTop` function**: `viewportRef.current?.scrollTo({ top: 0, behavior: "smooth" })`.
  - **IntersectionObserver**: In a `useEffect` watching `sentinelRef.current` and `status`:
    ```ts
    useEffect(() => {
      const sentinel = sentinelRef.current;
      if (!sentinel) return;
      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting && status === "CanLoadMore") {
            loadMore(20);
          }
        },
        { threshold: 0.1 }
      );
      observer.observe(sentinel);
      return () => observer.disconnect();
    }, [status, loadMore]);
    ```
  - **Loading more indicator**: Below items (above sentinel), when `status === "CanLoadMore"` or `status === "Exhausted"`, render a small status row:
    - `"CanLoadMore"`: render nothing extra (observer handles it silently)
    - `"Exhausted"`: render `<p className="text-xs text-center text-muted-foreground py-2">No more activity</p>`
    - `"LoadingFirstPage"`: handled by the existing `activities === undefined` / `status === "LoadingFirstPage"` check — return null.
  - **Reconnecting state**: Check `status === "LoadingFirstPage" && hadDataRef.current` → show "Reconnecting...". Since `usePaginatedQuery` doesn't return `undefined`, use `status === "LoadingFirstPage"` as the loading indicator. Adjust `hadDataRef` to track `activities.length > 0`.
  - **Empty state**: `activities.length === 0 && status !== "LoadingFirstPage"`.
  - **Sentinel div**: Add `<div ref={sentinelRef} className="h-1" />` as the last child inside the items `<div>`, after the last `<motion.div>` item and the "No more activity" text.
  - Keep `motion.div` animation wrapper per item (unchanged).
  - Keep `hasNewActivity` button at absolute bottom-2 (unchanged position, now scrolls to top).

- [x] **Task 3 — Tests: update `ActivityFeed.test.tsx`**
  - File: `components/ActivityFeed.test.tsx`
  - Add `mockUsePaginatedQuery` alongside `mockUseQuery` in the `convex/react` mock:
    ```ts
    const mockUsePaginatedQuery = vi.fn();
    vi.mock("convex/react", () => ({
      useQuery: (...args: unknown[]) => mockUseQuery(...args),
      usePaginatedQuery: (...args: unknown[]) => mockUsePaginatedQuery(...args),
    }));
    ```
  - Update all `ActivityFeed` tests to call `mockUsePaginatedQuery.mockReturnValue(...)` instead of `mockUseQuery`. The mock returns `{ results: [...], status: "Exhausted", loadMore: vi.fn() }`.
  - **Update "empty state" test**: `mockUsePaginatedQuery.mockReturnValue({ results: [], status: "Exhausted", loadMore: vi.fn() })` → expect "Waiting for activity...".
  - **Update "loading state" test**: `mockUsePaginatedQuery.mockReturnValue({ results: [], status: "LoadingFirstPage", loadMore: vi.fn() })` → expect empty container.
  - **Update "renders activities" test**: `mockUsePaginatedQuery.mockReturnValue({ results: [...], status: "Exhausted", loadMore: vi.fn() })`.
  - **Update "chronological order" test**: Items now rendered newest-first (desc). Reverse the expected order assertion (was First→Second→Third, now Third→Second→First).
  - **Add "shows No more activity when Exhausted" test**: When `status === "Exhausted"` and results exist, expect "No more activity" text.
  - `mockUsePaginatedQuery.mockReset()` in `afterEach` alongside `mockUseQuery.mockReset()`.
  - `FeedItem` tests are unaffected — no changes needed.
  - Add `IntersectionObserver` stub in `beforeEach` (jsdom doesn't implement it):
    ```ts
    beforeEach(() => {
      Element.prototype.scrollTo = vi.fn();
      global.IntersectionObserver = vi.fn().mockImplementation(() => ({
        observe: vi.fn(),
        disconnect: vi.fn(),
      }));
    });
    ```

### Acceptance Criteria

**AC1 — Paginated backend query:**
- Given the Convex schema has an `activities` table with `by_timestamp` index,
- When `listPaginated` is called with `paginationOpts`,
- Then it returns activities ordered newest-first (desc), paginated by the provided cursor.

**AC2 — Initial load:**
- Given the activity feed mounts,
- When the first 20 activities load,
- Then the 20 newest items are displayed with the newest at the top.

**AC3 — Load more on scroll:**
- Given 20+ items exist and the initial page is loaded,
- When the user scrolls to the bottom of the feed,
- Then `loadMore(20)` is called and older items appear below the current items.

**AC4 — Live new items at top:**
- Given the user has not scrolled (is at top),
- When a new activity event is received,
- Then it appears at the top of the feed and the panel auto-scrolls to show it.

**AC5 — "New activity" badge:**
- Given the user has scrolled down (is not at top),
- When a new activity event is received,
- Then a "New activity" button appears; clicking it scrolls back to the top.

**AC6 — "No more activity" indicator:**
- Given all historical items have been loaded (status is Exhausted),
- When looking at the bottom of the feed,
- Then "No more activity" text is shown.

**AC7 — Loading state:**
- Given the feed is first mounting (status is LoadingFirstPage),
- Then nothing is rendered (same as current behavior).

**AC8 — Empty state:**
- Given the database has no activities,
- When status is Exhausted and results is empty,
- Then "Waiting for activity..." is shown.

**AC9 — All tests pass.**

---

## Additional Context

### Dependencies

- `paginationOptsValidator` from `"convex/server"` — already a transitive dependency of Convex.
- `usePaginatedQuery` from `"convex/react"` — already installed.
- No new npm packages required.

### Testing Strategy

- Unit tests in `ActivityFeed.test.tsx` using vitest + testing-library.
- Mock `usePaginatedQuery` in the `convex/react` mock block.
- Mock `IntersectionObserver` in `beforeEach` (jsdom lacks it).
- Run with `npx vitest run components/ActivityFeed.test.tsx`.

### Notes

- `listRecent` is preserved; not removed.
- The `by_timestamp` index already exists in `schema.ts` — no schema migration needed.
- Convex `paginatedQuery` does not require any schema changes.
- `hadDataRef` reconnecting detection: with `usePaginatedQuery`, there is no `undefined` return — use `status === "LoadingFirstPage"` as the proxy for "loading/reconnecting". Track `hadDataRef` as `results.length > 0` to detect reconnection (same intent as before).

---

## Dev Agent Record

### Completion Notes (2026-02-23)

All 3 tasks implemented and verified:

1. **Task 1 — `convex/activities.ts`**: Added `paginationOptsValidator` import from `"convex/server"` and exported `listPaginated` paginatedQuery using `order("desc").paginate(paginationOpts)`. `listRecent` and `list` preserved unchanged.

2. **Task 2 — `components/ActivityFeed.tsx`**: Full rewrite — replaced `useQuery(listRecent)` with `usePaginatedQuery(listPaginated, {}, { initialNumItems: 20 })`. Changed scroll direction from bottom-tracking to top-tracking (`scrollTop < 30`). Added `IntersectionObserver` sentinel for load-more at bottom. Auto-scrolls to `top: 0` on new items when at top; shows "New activity" badge otherwise. Renders "No more activity" when `status === "Exhausted"`.

3. **Task 3 — `components/ActivityFeed.test.tsx`**: Added `mockUsePaginatedQuery` to `convex/react` mock; added `IntersectionObserver` constructor stub (using regular `function`, not arrow); updated all `ActivityFeed` tests to use `mockUsePaginatedQuery`; updated chronological order test to expect newest-first; added "No more activity" exhausted test; reset both mocks in `afterEach`.

### Test Results

- `ActivityFeed.test.tsx`: **9/9 passed**
- Full suite: 165 passed, 1 pre-existing failure in `TaskCard.test.tsx` (unrelated to this spec)

### Files Modified

- `dashboard/convex/activities.ts`
- `dashboard/components/ActivityFeed.tsx`
- `dashboard/components/ActivityFeed.test.tsx`
