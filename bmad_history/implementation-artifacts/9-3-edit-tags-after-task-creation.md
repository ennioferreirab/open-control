# Story 9.3: Edit Tags After Task Creation

Status: ready-for-dev

## Story

As a **user**,
I want to add and remove tags from tasks after they've been created,
so that I can organize tasks as priorities evolve.

## Acceptance Criteria

### AC1: updateTags Mutation
**Given** a task exists
**When** `tasks.updateTags` is called with `{ taskId, tags: ["bug", "urgent"] }`
**Then** the task's `tags` field is patched to `["bug", "urgent"]`
**And** the task's `updatedAt` is set to the current timestamp
**And** if `tags` is an empty array, the `tags` field is set to `undefined` (removed from document)

### AC2: Removable Tag Chips in TaskDetailSheet
**Given** the user opens a TaskDetailSheet for a task that has tags
**When** the Config tab renders the Tags section
**Then** each tag is shown as a chip/badge with an X button
**And** clicking the X button removes that tag from the array and calls `updateTags` with the remaining tags
**And** the tag disappears immediately via Convex reactivity

### AC3: Add Tag Button with Popover
**Given** the user is viewing the Tags section in the TaskDetailSheet Config tab
**When** they click the "+" button next to the existing tags
**Then** a popover opens showing all available tags from the `taskTags` catalog (via `useQuery(api.taskTags.list)`)
**And** tags already assigned to the task are shown as disabled/checked
**And** clicking an unassigned tag adds it to the task's tags array (calls `updateTags`)
**And** the popover stays open so the user can add multiple tags

### AC4: Tags Section When No Tags Exist
**Given** a task has no tags (tags is undefined or empty)
**When** the Config tab renders
**Then** the Tags section still appears with a "+" button
**And** clicking "+" opens the popover with all available tags
**And** if no tags are defined in the catalog, the popover shows "No tags defined. Open the Tags panel to create some."

### AC5: Tag Colors in Chips
**Given** tags are rendered as removable chips in the Config tab
**When** a tag has a matching entry in the `taskTags` catalog
**Then** the chip uses the tag's registered color (from `TAG_COLORS`)
**And** if the tag has no catalog entry (legacy free-form), it uses the default muted style

## Tasks / Subtasks

- [ ] Task 1: Create `updateTags` mutation in `dashboard/convex/tasks.ts` (AC: #1)
  - [ ] 1.1: Add the mutation after `updateExecutionPlan` (around line 346):
    ```ts
    export const updateTags = mutation({
      args: {
        taskId: v.id("tasks"),
        tags: v.array(v.string()),
      },
      handler: async (ctx, args) => {
        const task = await ctx.db.get(args.taskId);
        if (!task) throw new ConvexError("Task not found");
        await ctx.db.patch(args.taskId, {
          tags: args.tags.length > 0 ? args.tags : undefined,
          updatedAt: new Date().toISOString(),
        });
      },
    });
    ```
  - [ ] 1.2: Note: `tags: undefined` removes the field from the document (Convex convention for optional fields). This keeps task documents clean when all tags are removed.
  - [ ] 1.3: No status validation needed -- tags can be edited in any status including deleted (informational metadata, not workflow-affecting).

- [ ] Task 2: Update Tags section in `TaskDetailSheet.tsx` Config tab (AC: #2, #3, #4, #5)
  - [ ] 2.1: Add imports at the top of `TaskDetailSheet.tsx`:
    ```ts
    import { X, Plus } from "lucide-react";
    import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
    import { TAG_COLORS } from "@/lib/constants";
    ```
  - [ ] 2.2: Add query and mutation hooks inside the component:
    ```ts
    const tagsList = useQuery(api.taskTags.list);
    const updateTagsMutation = useMutation(api.tasks.updateTags);
    ```
  - [ ] 2.3: Build a `tagColorMap` for rendering colored chips (same pattern as KanbanBoard.tsx line 64-66):
    ```ts
    const tagColorMap: Record<string, string> = Object.fromEntries(
      tagsList?.map((t) => [t.name, t.color]) ?? []
    );
    ```
  - [ ] 2.4: Create helper functions for tag manipulation:
    ```ts
    const handleRemoveTag = (tagToRemove: string) => {
      if (!task || !isTaskLoaded) return;
      const currentTags = task.tags ?? [];
      const newTags = currentTags.filter((t) => t !== tagToRemove);
      updateTagsMutation({ taskId: task._id, tags: newTags });
    };

    const handleAddTag = (tagToAdd: string) => {
      if (!task || !isTaskLoaded) return;
      const currentTags = task.tags ?? [];
      if (currentTags.includes(tagToAdd)) return;
      updateTagsMutation({ taskId: task._id, tags: [...currentTags, tagToAdd] });
    };
    ```
  - [ ] 2.5: Replace the existing read-only tags rendering in the Config tab (lines 557-570) with an interactive version:
    ```tsx
    <div>
      <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        Tags
      </h4>
      <div className="flex flex-wrap items-center gap-1 mt-1">
        {(task.tags ?? []).map((tag) => {
          const colorKey = tagColorMap[tag];
          const color = colorKey ? TAG_COLORS[colorKey] : null;
          return (
            <span
              key={tag}
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${
                color
                  ? `${color.bg} ${color.text}`
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {color && (
                <span className={`w-1.5 h-1.5 rounded-full ${color.dot} flex-shrink-0`} />
              )}
              {tag}
              <button
                onClick={() => handleRemoveTag(tag)}
                className="ml-0.5 rounded-full hover:bg-black/10 p-0.5 transition-colors"
                aria-label={`Remove tag ${tag}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          );
        })}
        <Popover>
          <PopoverTrigger asChild>
            <button
              className="inline-flex items-center justify-center h-6 w-6 rounded-full border border-dashed border-muted-foreground/40 text-muted-foreground hover:border-foreground hover:text-foreground transition-colors"
              aria-label="Add tag"
            >
              <Plus className="h-3 w-3" />
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-48 p-2" align="start">
            {tagsList === undefined ? (
              <p className="text-xs text-muted-foreground p-2">Loading...</p>
            ) : tagsList.length === 0 ? (
              <p className="text-xs text-muted-foreground p-2">
                No tags defined. Open the Tags panel to create some.
              </p>
            ) : (
              <div className="flex flex-col gap-0.5">
                {tagsList.map((catalogTag) => {
                  const isAssigned = (task.tags ?? []).includes(catalogTag.name);
                  const color = TAG_COLORS[catalogTag.color];
                  return (
                    <button
                      key={catalogTag._id}
                      className={`flex items-center gap-2 rounded px-2 py-1.5 text-xs text-left transition-colors ${
                        isAssigned
                          ? "opacity-50 cursor-default"
                          : "hover:bg-muted cursor-pointer"
                      }`}
                      onClick={() => !isAssigned && handleAddTag(catalogTag.name)}
                      disabled={isAssigned}
                    >
                      {color && (
                        <span className={`w-2 h-2 rounded-full ${color.dot} flex-shrink-0`} />
                      )}
                      <span className="flex-1">{catalogTag.name}</span>
                      {isAssigned && (
                        <span className="text-muted-foreground text-[10px]">Added</span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </PopoverContent>
        </Popover>
      </div>
    </div>
    ```
  - [ ] 2.6: Remove the conditional wrapper `{task.tags && task.tags.length > 0 && (...)}` that currently guards the Tags section (line 557). The Tags section should ALWAYS render (even with no tags), so the "+" button is always accessible. This is the key UX change from read-only to editable.

- [ ] Task 3: Verify Popover component exists (AC: #3)
  - [ ] 3.1: Check if `dashboard/components/ui/popover.tsx` exists. If not, generate it via `npx shadcn@latest add popover` (from the `dashboard/` directory). The project already uses shadcn/ui components (`Sheet`, `Badge`, `Button`, etc.), so the Popover should be available or easily added.
  - [ ] 3.2: The Popover component is built on `@radix-ui/react-popover` which is already in the project's dependency tree (shadcn/ui pulls in Radix primitives).

- [ ] Task 4: Add tests (AC: #1, #2)
  - [ ] 4.1: Test `updateTags` mutation:
    - Verify tags are patched correctly
    - Verify empty array results in `undefined` (field removed)
    - Verify `updatedAt` is set
    - Verify task not found throws `ConvexError`
  - [ ] 4.2: Test tag chip rendering and interaction in `TaskDetailSheet` (if vitest component tests are used):
    - Verify X button calls `updateTags` with the tag removed
    - Verify "+" button opens the popover
    - Verify already-assigned tags are disabled in popover

## Dev Notes

### Architecture Patterns

- **No schema change needed**: The `tasks.tags` field is already `v.optional(v.array(v.string()))` (schema.ts line 41). The `updateTags` mutation simply patches this existing field. No migration or schema evolution required.
- **Empty array to undefined**: Convex convention for optional fields is to set them to `undefined` to remove from the document. The mutation does `tags: args.tags.length > 0 ? args.tags : undefined` to keep documents clean.
- **Tag catalog is a suggestion list**: The `taskTags` catalog (from `useQuery(api.taskTags.list)`) provides the available tags. Tags on tasks are denormalized strings. Deleting a catalog tag does NOT affect tasks that already have it. This matches the architecture from Story 8.7.
- **Popover stays open**: Using shadcn/ui `<Popover>` which stays open until the user clicks outside or presses Escape. This allows adding multiple tags without re-opening. The Radix Popover handles focus management and accessibility automatically.
- **Color rendering reuses existing pattern**: The tag chip color rendering exactly matches `TaskCard.tsx` (lines 100-124) and uses the same `TAG_COLORS` constant and `tagColorMap` pattern from `KanbanBoard.tsx` (lines 64-66).

### Common Mistakes to Avoid

- Do NOT create a new schema field or table. Use the existing `tasks.tags` field.
- Do NOT use optimistic updates -- Convex reactivity handles the UI update. The `useQuery(api.tasks.getById)` in `TaskDetailSheet` will automatically re-render when the task is patched.
- Do NOT add the Popover inside a `ScrollArea` -- it should portal to the document body (default Radix behavior) to avoid clipping issues.
- When removing a tag, filter the CURRENT `task.tags` array and pass the result to `updateTags`. Do not try to pass a "diff" -- the mutation expects the full new array.
- The Tags section must render even when `task.tags` is undefined or empty. Remove the `{task.tags && task.tags.length > 0 && (...)}` guard.

### Project Structure Notes

- Modified files: `dashboard/convex/tasks.ts`, `dashboard/components/TaskDetailSheet.tsx`
- Possibly new file: `dashboard/components/ui/popover.tsx` (if not already generated by shadcn)
- No Python backend changes
- No new component files needed (the tag editing UI is inline in `TaskDetailSheet`)

### References

- [Source: dashboard/convex/schema.ts:41] -- `tags: v.optional(v.array(v.string()))` existing field
- [Source: dashboard/convex/tasks.ts:331-346] -- `updateExecutionPlan` mutation pattern (model for `updateTags`)
- [Source: dashboard/convex/taskTags.ts:8-17] -- `list` query (used for tag catalog popover)
- [Source: dashboard/components/TaskDetailSheet.tsx:557-570] -- current read-only tags rendering (to replace)
- [Source: dashboard/components/TaskCard.tsx:100-124] -- tag color rendering pattern (reuse in chips)
- [Source: dashboard/components/KanbanBoard.tsx:63-66] -- `tagColorMap` build pattern
- [Source: dashboard/lib/constants.ts:220-232] -- `TAG_COLORS` constant

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
