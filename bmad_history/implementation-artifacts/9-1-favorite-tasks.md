# Story 9.1: Favorite Tasks

Status: ready-for-dev

## Story

As a **user**,
I want to star/favorite tasks for quick access in a fixed section at the top of the Kanban board,
so that I can track important tasks without searching.

## Acceptance Criteria

### AC1: Toggle Favorite on a Task
**Given** a task exists on the Kanban board
**When** the user clicks the star icon on the task card
**Then** the task's `isFavorite` field is toggled (true/false)
**And** the star icon fills with amber-400 when favorited, or shows as outline when not favorited
**And** the toggle is reflected in real-time via Convex reactivity

### AC2: Favorite Star Renders on TaskCard
**Given** a task card is rendered on the Kanban board
**When** the component mounts
**Then** a star icon is visible in the top-right corner of the card (next to existing icons)
**And** if `isFavorite === true`, the star is filled (`fill-amber-400 text-amber-400`)
**And** if `isFavorite` is false or undefined, the star is an outline (`text-muted-foreground`)
**And** clicking the star calls `toggleFavorite` without opening the task detail sheet

### AC3: Favorites Section on Kanban Board
**Given** at least one task has `isFavorite === true`
**When** the Kanban board renders
**Then** a horizontal "Favorites" section appears at the top of the board, above the columns
**And** the section header reads "Favorites" with a filled star icon
**And** favorited tasks are shown as compact cards in a horizontally scrollable row (`overflow-x-auto`)
**And** the section is not rendered when no favorites exist

### AC4: CompactFavoriteCard Display
**Given** a task is favorited
**When** it appears in the Favorites section
**Then** it renders as a compact card with: truncated title (1 line), status badge (colored), assigned agent initials, and a filled star icon
**And** clicking the card opens the TaskDetailSheet (same as clicking a regular TaskCard)
**And** clicking the star on the compact card un-favorites the task (removes it from the section)

### AC5: Favorites Query Excludes Deleted Tasks
**Given** a favorited task is soft-deleted
**When** the `listFavorites` query runs
**Then** the deleted task is NOT included in the favorites section
**And** a favorited task that is subsequently restored re-appears in favorites if still favorited

### AC6: Favorite Persists Across Board Switches
**Given** a task is favorited on one board
**When** the user switches to a different board and back
**Then** the favorite status is preserved (stored on the task document, not in local state)

## Tasks / Subtasks

- [ ] Task 1: Add `isFavorite` field to tasks schema (AC: #1, #6)
  - [ ] 1.1: In `dashboard/convex/schema.ts`, add `isFavorite: v.optional(v.boolean())` to the `tasks` table definition, after the `isManual` field (line 50):
    ```ts
    isFavorite: v.optional(v.boolean()),
    ```
  - [ ] 1.2: No index needed — favorites are filtered client-side from the existing task list query. The `v.optional` ensures backward compatibility with existing tasks.

- [ ] Task 2: Create `toggleFavorite` mutation in `dashboard/convex/tasks.ts` (AC: #1)
  - [ ] 2.1: Add a new `toggleFavorite` mutation after the `list` query (around line 206):
    ```ts
    export const toggleFavorite = mutation({
      args: { taskId: v.id("tasks") },
      handler: async (ctx, args) => {
        const task = await ctx.db.get(args.taskId);
        if (!task) throw new ConvexError("Task not found");
        await ctx.db.patch(args.taskId, {
          isFavorite: task.isFavorite ? undefined : true,
          updatedAt: new Date().toISOString(),
        });
      },
    });
    ```
  - [ ] 2.2: Note: setting `isFavorite: undefined` when un-favoriting removes the field from the document (Convex convention for optional booleans). This keeps unfavorited documents clean.

- [ ] Task 3: Create `listFavorites` query in `dashboard/convex/tasks.ts` (AC: #3, #5)
  - [ ] 3.1: Add a new `listFavorites` query after `toggleFavorite`:
    ```ts
    export const listFavorites = query({
      args: {},
      handler: async (ctx) => {
        const all = await ctx.db.query("tasks").collect();
        return all.filter((t) => t.isFavorite === true && t.status !== "deleted");
      },
    });
    ```
  - [ ] 3.2: Uses full-table scan + filter rather than an index. This matches the existing `list` query pattern (line 199-205) and is acceptable since task count is small (< 1000). Adding an index on `isFavorite` would only help if we had thousands of tasks.

- [ ] Task 4: Add star icon to `TaskCard.tsx` (AC: #2)
  - [ ] 4.1: Import `Star` from `lucide-react` (add to existing import on line 12-18)
  - [ ] 4.2: Import `useMutation` is already imported (line 6). Add `const toggleFavoriteMutation = useMutation(api.tasks.toggleFavorite);` in the component body.
  - [ ] 4.3: In the top-right icon section (lines 88-93, inside `<div className="mt-0.5 flex shrink-0 items-center gap-1">`), add the star icon BEFORE the existing icons:
    ```tsx
    <Star
      className={`h-3.5 w-3.5 cursor-pointer transition-colors ${
        task.isFavorite
          ? "fill-amber-400 text-amber-400"
          : "text-muted-foreground hover:text-amber-400"
      }`}
      onClick={(e) => {
        e.stopPropagation();
        toggleFavoriteMutation({ taskId: task._id });
      }}
    />
    ```
  - [ ] 4.4: The `e.stopPropagation()` prevents the card's `onClick` (which opens the detail sheet) from firing when the star is clicked.

- [ ] Task 5: Create `CompactFavoriteCard.tsx` component (AC: #4)
  - [ ] 5.1: Create new file `dashboard/components/CompactFavoriteCard.tsx`
  - [ ] 5.2: Component props: `{ task: Doc<"tasks">; onClick?: () => void }`
  - [ ] 5.3: Import `Star` from `lucide-react`, `useMutation` from `convex/react`, `api`, `Doc`, `Badge`, `STATUS_COLORS`, `TaskStatus`
  - [ ] 5.4: Component structure:
    ```tsx
    export function CompactFavoriteCard({ task, onClick }: CompactFavoriteCardProps) {
      const toggleFavorite = useMutation(api.tasks.toggleFavorite);
      const colors = STATUS_COLORS[task.status as TaskStatus] ?? STATUS_COLORS.inbox;
      const initials = task.assignedAgent
        ? task.assignedAgent.split(/[\s-_]+/).filter(Boolean).slice(0, 2)
            .map((w) => w[0]?.toUpperCase() ?? "").join("")
        : "?";

      return (
        <div
          className="flex items-center gap-2 rounded-lg border px-3 py-2 cursor-pointer
                     hover:shadow-sm transition-shadow min-w-[180px] max-w-[260px] shrink-0"
          onClick={onClick}
        >
          <span className="flex h-5 w-5 items-center justify-center rounded bg-muted text-[9px] font-semibold">
            {initials}
          </span>
          <span className="flex-1 min-w-0 text-sm font-medium truncate">
            {task.title}
          </span>
          <Badge
            variant="secondary"
            className={`h-5 rounded-full px-2 text-[10px] font-medium ${colors.bg} ${colors.text}`}
          >
            {task.status.replaceAll("_", " ")}
          </Badge>
          <Star
            className="h-3.5 w-3.5 fill-amber-400 text-amber-400 cursor-pointer shrink-0"
            onClick={(e) => {
              e.stopPropagation();
              toggleFavorite({ taskId: task._id });
            }}
          />
        </div>
      );
    }
    ```

- [ ] Task 6: Add Favorites section to `KanbanBoard.tsx` (AC: #3, #4, #5)
  - [ ] 6.1: Import `CompactFavoriteCard` from `./CompactFavoriteCard` and `Star` from `lucide-react`
  - [ ] 6.2: Add the favorites query: `const favorites = useQuery(api.tasks.listFavorites);`
  - [ ] 6.3: If `activeBoardId` is set, filter favorites to only show tasks belonging to the active board:
    ```ts
    const boardFavorites = activeBoardId
      ? (favorites ?? []).filter((t) => t.boardId === activeBoardId || (!t.boardId && isDefaultBoard))
      : (favorites ?? []);
    ```
  - [ ] 6.4: Insert the Favorites section inside the `<LayoutGroup>`, before the existing `<div className="flex-1 flex gap-4 overflow-hidden">` (line 160). Only render when `boardFavorites.length > 0`:
    ```tsx
    {boardFavorites.length > 0 && (
      <div className="px-1 pb-2">
        <div className="flex items-center gap-1.5 mb-1.5">
          <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Favorites
          </span>
        </div>
        <div className="flex gap-2 overflow-x-auto pb-1">
          {boardFavorites.map((task) => (
            <CompactFavoriteCard
              key={task._id}
              task={task}
              onClick={() => onTaskClick?.(task._id)}
            />
          ))}
        </div>
      </div>
    )}
    ```
  - [ ] 6.5: Wrap the existing column grid and the new favorites section in a flex-col container so favorites sit above the columns:
    - Change the outer `<div className="flex-1 flex gap-4 overflow-hidden">` to wrap both the favorites section and the columns layout.

## Dev Notes

### Architecture Patterns

- **Schema addition is backward-compatible**: `isFavorite: v.optional(v.boolean())` means existing tasks have `isFavorite === undefined`, which is treated as "not favorited" everywhere. No migration needed.
- **Toggle mutation uses `undefined` not `false`**: Convex convention for optional fields is to patch with `undefined` to remove the field from the document, keeping documents lean. The condition `task.isFavorite ? undefined : true` handles this correctly.
- **No separate index**: The `listFavorites` query does a full table scan (same as `list` on line 199-205). This is fine for the expected task volume. If performance becomes an issue, add `.index("by_isFavorite", ["isFavorite"])` later.
- **Board-scoped filtering**: Favorites are stored globally on the task document but filtered by board in the component. This matches the `listByBoard` pattern (line 207-229) where board scoping is a query-time concern.
- **stopPropagation pattern**: Critical on the star icon click handler to prevent the card's `onClick` from firing. This follows the existing pattern used for Trash2 (TaskCard line 236-239) and Approve/Deny buttons (lines 214-231).

### Common Mistakes to Avoid

- Do NOT add a separate `favorites` table. Favorites are a boolean on the task document, not a relation.
- Do NOT store favorites in React state or localStorage. They must persist in Convex for cross-device and cross-session access.
- Do NOT create an index on `isFavorite` unless profiling shows it's needed. The `list` query already does a full table scan.
- When rendering the star on `TaskCard`, check `task.isFavorite` (truthy check), not `task.isFavorite === true`, because the field is `v.optional(v.boolean())` and will be `undefined` for existing tasks.

### Project Structure Notes

- New file: `dashboard/components/CompactFavoriteCard.tsx`
- Modified files: `dashboard/convex/schema.ts`, `dashboard/convex/tasks.ts`, `dashboard/components/TaskCard.tsx`, `dashboard/components/KanbanBoard.tsx`

### References

- [Source: dashboard/convex/schema.ts:18-67] -- tasks table definition (add `isFavorite` field)
- [Source: dashboard/convex/tasks.ts:199-205] -- `list` query pattern (model for `listFavorites`)
- [Source: dashboard/components/TaskCard.tsx:84-93] -- top-right icon section (add star icon)
- [Source: dashboard/components/TaskCard.tsx:234-239] -- stopPropagation pattern on Trash2
- [Source: dashboard/components/KanbanBoard.tsx:45-196] -- board component (add favorites section)
- [Source: dashboard/components/KanbanBoard.tsx:63-66] -- `tagColorMap` build pattern (model for favorites query)
- [Source: dashboard/lib/constants.ts:121-180] -- STATUS_COLORS map (used in CompactFavoriteCard)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
