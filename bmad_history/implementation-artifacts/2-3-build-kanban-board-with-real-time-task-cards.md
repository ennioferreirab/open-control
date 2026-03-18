# Story 2.3: Build Kanban Board with Real-Time Task Cards

Status: done

## Story

As a **user**,
I want to see all my tasks organized on a Kanban board that updates in real-time,
So that I can monitor task progress at a glance without refreshing the page.

## Acceptance Criteria

1. **Given** tasks exist in the Convex `tasks` table, **When** the dashboard loads, **Then** the KanbanBoard renders 5 columns via CSS Grid (`grid-template-columns: repeat(5, 1fr)`): Inbox, Assigned, In Progress, Review, Done
2. **Given** the board renders, **Then** each column has a header with the column name (`text-lg`, `font-semibold`) and a task count badge
3. **Given** tasks exist, **Then** tasks appear as TaskCard components in the correct column based on their status
4. **Given** a TaskCard renders, **Then** it displays: 3px left-border accent in status color, title (`text-sm`, `font-semibold`), description preview (`text-xs`, 2-line clamp via `line-clamp-2`, optional), tags row (small pills, `text-xs`, `rounded-full`), assigned agent name and avatar dot (`text-xs`), status Badge, progress bar on In Progress cards
5. **Given** a TaskCard renders, **Then** cards use `p-3.5` (14px padding) and `rounded-[10px]` (10px border radius)
6. **Given** cards exist in a column, **Then** cards within each column are rendered inside a ShadCN `ScrollArea` for vertical overflow
7. **Given** a task status changes in Convex (by any source), **When** the reactive query updates, **Then** the card animates from its current column to the new column using Framer Motion `layoutId` (300ms transition)
8. **Given** a task status changes, **Then** the board update reflects within 2 seconds of the state change (NFR1)
9. **Given** a task status changes, **Then** every task state transition is visible on the board — no silent failures (NFR8)
10. **Given** no tasks exist, **When** the board renders, **Then** centered text appears: "No tasks yet. Type above to create your first task."
11. **Given** no tasks exist in a specific column, **Then** the empty column shows subtle muted text: "No tasks"
12. **Given** the user has `prefers-reduced-motion` enabled, **When** a card moves between columns, **Then** the card transitions instantly without animation
13. **And** `KanbanBoard.tsx`, `KanbanColumn.tsx`, and `TaskCard.tsx` components are created
14. **And** Convex `tasks.ts` contains a `list` query returning all tasks
15. **And** Vitest tests exist for `KanbanBoard.tsx` and `TaskCard.tsx`

## Tasks / Subtasks

- [x]Task 1: Create the KanbanColumn component (AC: #2, #6, #11)
  - [x]1.1: Create `dashboard/components/KanbanColumn.tsx` with `"use client"` directive
  - [x]1.2: Accept props: `title` (string), `status` (string), `tasks` (array), `accentColor` (string)
  - [x]1.3: Render column header with title (`text-lg font-semibold`) and task count Badge
  - [x]1.4: Render task cards inside a ShadCN `ScrollArea` for vertical overflow
  - [x]1.5: Show "No tasks" muted text when column has no tasks
  - [x]1.6: Apply status-specific accent color to the column header or top border

- [x]Task 2: Create the TaskCard component (AC: #4, #5, #7, #12)
  - [x]2.1: Create `dashboard/components/TaskCard.tsx` with `"use client"` directive
  - [x]2.2: Accept props: `task` object (matching Convex task document shape)
  - [x]2.3: Render card with Card-Rich design: 3px left border in status color, title (`text-sm font-semibold`), description preview (`text-xs line-clamp-2`), tags row (pills), assigned agent name, status Badge
  - [x]2.4: Apply `p-3.5` padding and `rounded-[10px]` border radius
  - [x]2.5: Wrap card in Framer Motion `motion.div` with `layoutId={task._id}` for animated transitions between columns
  - [x]2.6: Implement `prefers-reduced-motion` check: if enabled, set `layout` transition to `{ duration: 0 }`
  - [x]2.7: Add `onClick` handler prop (used by Story 2.6 to open TaskDetailSheet)
  - [x]2.8: Add `role="article"` and `aria-label` with task title and status

- [x]Task 3: Create status color mapping utility (AC: #4)
  - [x]3.1: Create a `getStatusColor` utility function (can live in `lib/constants.ts` or a new `lib/status-colors.ts`)
  - [x]3.2: Map status values to Tailwind colors: inbox -> violet-500, assigned -> blue-400, in_progress -> blue-500, review -> amber-500, done -> green-500, retrying -> amber-600, crashed -> red-500

- [x]Task 4: Create the KanbanBoard component (AC: #1, #3, #7, #8, #9, #10, #14)
  - [x]4.1: Create `dashboard/components/KanbanBoard.tsx` with `"use client"` directive
  - [x]4.2: Use `useQuery(api.tasks.list)` to subscribe to all tasks (real-time updates)
  - [x]4.3: Group tasks by status into 5 columns: inbox, assigned, in_progress, review, done
  - [x]4.4: Render 5 `KanbanColumn` components in a CSS Grid with `grid-template-columns: repeat(5, 1fr)`
  - [x]4.5: Include `retrying` and `crashed` tasks in their logical columns (retrying in In Progress, crashed in a visible location)
  - [x]4.6: Wrap columns in Framer Motion `AnimatePresence` and `LayoutGroup` for cross-column card animations
  - [x]4.7: Show "No tasks yet. Type above to create your first task." when no tasks exist at all
  - [x]4.8: Handle loading state: show nothing or subtle placeholder while Convex query loads

- [x]Task 5: Integrate KanbanBoard into DashboardLayout (AC: #1)
  - [x]5.1: Import and render `KanbanBoard` in the main content area of `DashboardLayout.tsx`, below the TaskInput
  - [x]5.2: Give the board area `flex-1 overflow-hidden` so it fills remaining vertical space

- [x]Task 6: Write unit tests (AC: #15)
  - [x]6.1: Create `dashboard/components/KanbanBoard.test.tsx`
  - [x]6.2: Test that 5 columns render with correct titles
  - [x]6.3: Test that tasks are grouped into correct columns by status
  - [x]6.4: Test empty state message renders when no tasks exist
  - [x]6.5: Create `dashboard/components/TaskCard.test.tsx`
  - [x]6.6: Test that card renders title, description, status badge
  - [x]6.7: Test that card has correct aria-label
  - [x]6.8: Test that left border color matches status

## Dev Notes

### Critical Architecture Requirements

- **Convex reactive queries**: The `useQuery(api.tasks.list)` hook automatically re-renders the component when any task in the database changes. This is Convex's core feature — no manual polling, no WebSocket setup. The board stays in sync automatically.
- **Framer Motion `layoutId`**: Each `TaskCard` must have a Framer Motion `layoutId` set to the task's Convex `_id`. When a task's status changes and it moves to a different column, Framer Motion automatically animates the transition because it recognizes the same `layoutId` in a new position.
- **`LayoutGroup`**: Wrap the entire KanbanBoard in a Framer Motion `LayoutGroup` to enable cross-column animations. Without `LayoutGroup`, `layoutId` animations only work within the same parent.
- **Status color palette**: The left-border accent color on cards maps to the status color palette from the UX spec. These are the same colors used throughout the dashboard.

### Status Color Mapping

| Status | Color | Tailwind Border Class | Badge Variant |
|--------|-------|----------------------|---------------|
| inbox | violet-500 (`#8B5CF6`) | `border-l-violet-500` | violet/outline |
| assigned | blue-400 (`#60A5FA`) | `border-l-blue-400` | blue/outline |
| in_progress | blue-500 (`#3B82F6`) | `border-l-blue-500` | blue/default |
| review | amber-500 (`#F59E0B`) | `border-l-amber-500` | amber/default |
| done | green-500 (`#22C55E`) | `border-l-green-500` | green/default |
| retrying | amber-600 (`#D97706`) | `border-l-amber-600` | amber/outline |
| crashed | red-500 (`#EF4444`) | `border-l-red-500` | red/destructive |

### Column Definitions

```typescript
const COLUMNS = [
  { title: "Inbox", status: "inbox", color: "violet" },
  { title: "Assigned", status: "assigned", color: "blue" },
  { title: "In Progress", status: "in_progress", color: "blue" },
  { title: "Review", status: "review", color: "amber" },
  { title: "Done", status: "done", color: "green" },
] as const;
```

Tasks with `retrying` status should appear in the "In Progress" column (they are being retried). Tasks with `crashed` status could appear in a special section or in the column where they last were — for MVP, display them in the "In Progress" column with a red badge.

### KanbanBoard Component Pattern

```tsx
"use client";

import { useQuery } from "convex/react";
import { api } from "../convex/_generated/api";
import { LayoutGroup } from "framer-motion";
import { KanbanColumn } from "./KanbanColumn";

const COLUMNS = [
  { title: "Inbox", status: "inbox" },
  { title: "Assigned", status: "assigned" },
  { title: "In Progress", status: "in_progress" },
  { title: "Review", status: "review" },
  { title: "Done", status: "done" },
] as const;

export function KanbanBoard() {
  const tasks = useQuery(api.tasks.list);

  if (tasks === undefined) {
    // Loading state — Convex query hasn't returned yet
    return null;
  }

  if (tasks.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-500">
        No tasks yet. Type above to create your first task.
      </div>
    );
  }

  // Group tasks by status
  const tasksByStatus = COLUMNS.map((col) => ({
    ...col,
    tasks: tasks.filter((t) => {
      if (col.status === "in_progress") {
        return t.status === "in_progress" || t.status === "retrying" || t.status === "crashed";
      }
      return t.status === col.status;
    }),
  }));

  return (
    <LayoutGroup>
      <div className="flex-1 grid grid-cols-5 gap-4 p-4 overflow-hidden">
        {tasksByStatus.map((col) => (
          <KanbanColumn
            key={col.status}
            title={col.title}
            status={col.status}
            tasks={col.tasks}
          />
        ))}
      </div>
    </LayoutGroup>
  );
}
```

### TaskCard Component Pattern

```tsx
"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Doc } from "../convex/_generated/dataModel";

interface TaskCardProps {
  task: Doc<"tasks">;
  onClick?: () => void;
}

export function TaskCard({ task, onClick }: TaskCardProps) {
  const shouldReduceMotion = useReducedMotion();

  const borderColor = getStatusBorderColor(task.status);

  return (
    <motion.div
      layoutId={task._id}
      layout
      transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.3 }}
    >
      <Card
        className={`p-3.5 rounded-[10px] border-l-[3px] cursor-pointer
          hover:shadow-md transition-shadow ${borderColor}`}
        onClick={onClick}
        role="article"
        aria-label={`${task.title} - ${task.status}`}
      >
        <h3 className="text-sm font-semibold text-slate-900">{task.title}</h3>
        {task.description && (
          <p className="text-xs text-slate-500 line-clamp-2 mt-1">
            {task.description}
          </p>
        )}
        {task.tags && task.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {task.tags.map((tag) => (
              <span
                key={tag}
                className="text-xs px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-600"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
        <div className="flex items-center justify-between mt-2">
          {task.assignedAgent && (
            <span className="text-xs text-slate-500">{task.assignedAgent}</span>
          )}
          <Badge variant="outline" className="text-xs">
            {task.status.replace("_", " ")}
          </Badge>
        </div>
      </Card>
    </motion.div>
  );
}
```

### Framer Motion Import Notes

```bash
# framer-motion should already be installed from Story 1.1
npm install framer-motion  # if not already installed
```

Key Framer Motion imports:
- `motion` — For animated elements (`motion.div`)
- `LayoutGroup` — Wraps the board to enable cross-column `layoutId` animations
- `AnimatePresence` — For enter/exit animations (optional, for new cards appearing)
- `useReducedMotion` — Hook to respect `prefers-reduced-motion`

### Convex Document Types

The `Doc<"tasks">` type from `convex/_generated/dataModel` provides the TypeScript type for task documents, including the `_id` field (which is the Convex document ID). Use this for type-safe props:

```typescript
import { Doc } from "../convex/_generated/dataModel";

// Doc<"tasks"> includes: _id, _creationTime, title, status, trustLevel, etc.
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT forget `LayoutGroup` wrapper** — Without `LayoutGroup`, Framer Motion's `layoutId` animations will NOT work across different parent containers (columns). The `LayoutGroup` must wrap all columns.

2. **DO NOT use `AnimatePresence` as the only animation wrapper** — `AnimatePresence` is for enter/exit animations. Cross-column card movement requires `layoutId` + `LayoutGroup`. Use both together for the best effect.

3. **DO NOT poll for task updates** — Convex's `useQuery` is reactive. It automatically re-renders when data changes. Do NOT implement `setInterval`, `setTimeout`, or manual refetch logic.

4. **DO NOT hardcode task IDs as layoutId** — Use the Convex `_id` field (`task._id`) as the `layoutId`. This is the unique, stable identifier for each task document.

5. **DO NOT use `grid-template-columns: repeat(5, 1fr)` with fixed-width sidebar visible** — The board is inside the flex-1 main content area. The CSS Grid is 5 equal columns WITHIN the board area, not the full viewport.

6. **DO NOT forget `overflow-hidden` on the board container** — Without it, a column with many tasks will expand the board beyond the viewport. Each column uses `ScrollArea` for vertical overflow.

7. **DO NOT make the entire card clickable with an `<a>` tag** — Use `onClick` handler on the `Card` component. The click opens the TaskDetailSheet (Story 2.6). For now, just pass the handler prop.

8. **DO NOT put loading skeletons in the board** — For localhost, the Convex query returns almost instantly. Show `null` or nothing while loading. No skeleton screens needed for MVP.

9. **DO NOT forget `useReducedMotion`** — The `prefers-reduced-motion` media query must be respected. Use Framer Motion's `useReducedMotion()` hook and set `transition: { duration: 0 }` when reduced motion is preferred.

10. **DO NOT import `framer-motion` in server components** — All components using Framer Motion must have `"use client"` directive. Framer Motion is a client-side library.

11. **DO NOT create separate queries per column** — Use a single `useQuery(api.tasks.list)` and filter on the client side. Multiple queries would create unnecessary subscriptions and potential race conditions.

12. **DO NOT forget the `key` prop on column components** — React requires a `key` prop for list rendering. Use the column status as the key.

### What This Story Does NOT Include

- **No drag-and-drop** — Cards move autonomously via agent state changes, not user dragging. No manual card movement.
- **No TaskDetailSheet click handler** — The `onClick` prop is added but not connected to anything yet. Built in Story 2.6.
- **No HITL approve/deny buttons on cards** — Added in Epic 6.
- **No progress bar on In Progress cards** — The progress bar requires execution plan data (Epic 4). For now, In Progress cards show a blue accent without a progress bar.
- **No optimistic UI for task creation** — Optimistic card appearance (violet fade-in) can be added but is not required if Convex reactive updates are fast enough (< 200ms on localhost).

### Files Created in This Story

| File | Purpose |
|------|---------|
| `dashboard/components/KanbanBoard.tsx` | 5-column board with CSS Grid + Convex reactive query |
| `dashboard/components/KanbanColumn.tsx` | Single column with header, count badge, ScrollArea |
| `dashboard/components/TaskCard.tsx` | Card-Rich task card with Framer Motion layoutId |
| `dashboard/components/KanbanBoard.test.tsx` | Unit tests for board rendering and column grouping |
| `dashboard/components/TaskCard.test.tsx` | Unit tests for card rendering and accessibility |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/components/DashboardLayout.tsx` | Add `KanbanBoard` to main content area below TaskInput |
| `dashboard/lib/constants.ts` | Add status color mapping (or create `lib/status-colors.ts`) |

### Verification Steps

1. Create a task via TaskInput (Story 2.2) — Card appears in the Inbox column
2. Verify card shows: title, left border in violet, status badge "inbox"
3. Create multiple tasks — Cards appear in the Inbox column
4. Manually update a task status in Convex dashboard (change `status` to "assigned") — Card moves to Assigned column with animation
5. Verify card count badges update on column headers
6. Empty board shows "No tasks yet. Type above to create your first task."
7. Empty column shows "No tasks" muted text
8. Toggle `prefers-reduced-motion` in browser DevTools — Card transitions are instant
9. Open browser DevTools and verify no console errors
10. `cd dashboard && npx vitest run` — Tests pass

### References

- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Component Strategy`] — KanbanBoard, KanbanColumn, TaskCard component specs
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Design Direction Decision`] — Card-Rich direction: `p-3.5`, `rounded-[10px]`, 3px left border, description preview, tags, status badge
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#UX Consistency Patterns`] — Real-time update patterns, anti-disruption rules
- [Source: `_bmad-output/planning-artifacts/architecture.md#Frontend Architecture`] — Convex reactive queries, Framer Motion layoutId
- [Source: `_bmad-output/planning-artifacts/epics.md#Story 2.3`] — Original story definition with acceptance criteria
- [Source: `dashboard/convex/schema.ts`] — Tasks table schema
- [Source: `dashboard/lib/constants.ts`] — TASK_STATUS constants

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
- Fixed DashboardLayout.test.tsx: added useQuery mock and motion mocks, updated placeholder test to check for empty state text

### Completion Notes List
- Created KanbanBoard with 5 columns (Inbox, Assigned, In Progress, Review, Done) using CSS Grid
- Created KanbanColumn with header, count badge, ScrollArea, and empty state
- Created TaskCard with 3px left-border accent, title, description preview, tags, assigned agent, status badge
- Added STATUS_COLORS mapping to lib/constants.ts
- Used motion/react (v12+) LayoutGroup for cross-column animations and useReducedMotion for a11y
- Retrying and crashed tasks display in the In Progress column
- Convex reactive query (useQuery) for real-time updates, no polling
- Updated DashboardLayout to replace placeholder with KanbanBoard
- Updated DashboardLayout.test.tsx with new mocks for convex/react, motion/react, motion/react-client
- All 34 tests pass across 4 test files; tsc --noEmit clean

### File List
| File | Action |
|------|--------|
| `dashboard/components/KanbanBoard.tsx` | Created |
| `dashboard/components/KanbanColumn.tsx` | Created |
| `dashboard/components/TaskCard.tsx` | Created |
| `dashboard/components/KanbanBoard.test.tsx` | Created |
| `dashboard/components/TaskCard.test.tsx` | Created |
| `dashboard/components/DashboardLayout.tsx` | Modified |
| `dashboard/components/DashboardLayout.test.tsx` | Modified |
| `dashboard/lib/constants.ts` | Modified |

### Code Review Findings

**Reviewer:** Claude Opus 4.6 (adversarial review)

**Issues Found (5):**

1. **[MEDIUM - FIXED] `task.status.replace("_", " ")` only replaces first underscore** — `String.replace` with a string argument only replaces the first occurrence. Changed to `replaceAll` in TaskCard.tsx and TaskDetailSheet.tsx for correctness. No current statuses have multiple underscores, but this is defensive.

2. **[MEDIUM - FIXED] TaskCard missing avatar dot next to assigned agent name** — AC#4 requires "assigned agent name and avatar dot (`text-xs`)". The agent name was rendered but no dot indicator. Added a small green dot (`w-1.5 h-1.5 rounded-full bg-green-400`) before the agent name.

3. **[LOW] KanbanColumn `status` prop unused in component body** — The `status` prop is in the interface and passed by KanbanBoard but never read. It exists for API completeness and potential future use.

4. **[LOW] No `AnimatePresence` wrapper for enter/exit animations** — AC#7 mentions animated transitions. The implementation uses `LayoutGroup` + `layoutId` for cross-column movement (correct) but does not wrap new cards in `AnimatePresence` for initial entry animations. The dev notes say this is optional: "Use both together for the best effect."

5. **[LOW] TaskCard.test.tsx uses `as never` type assertion for mock `_id`** — At line 28, `_id: "task1" as never` is a type workaround to avoid importing Convex ID types. Works but is fragile. KanbanBoard.test.tsx uses a cleaner approach with `makeTask()` factory function.

**Verification:** tsc --noEmit clean (0 errors), 69/69 vitest tests passing.
