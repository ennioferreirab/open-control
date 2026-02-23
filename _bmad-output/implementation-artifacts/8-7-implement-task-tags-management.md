# Story 8.7: Implement Task Tags Management

Status: done

## Story

As a **user**,
I want to define a reusable list of tags from a dedicated side panel and attach them to tasks at creation time,
so that I can visually categorize and filter tasks on the Kanban board.

## Acceptance Criteria

### AC1: Tags Management Panel (side panel access)
**Given** the user is on the dashboard
**When** they click the Tags icon button in the header (next to the Settings gear)
**Then** a Sheet panel slides in from the right
**And** it lists all existing predefined tags (name + colored dot)
**And** if no tags exist, an empty-state message is shown: "No tags yet. Add your first tag below."

### AC2: Create a New Predefined Tag
**Given** the Tags panel is open
**When** the user types a tag name (max 32 chars) and selects a color, then clicks "Add"
**Then** a new tag is saved to the `taskTags` Convex table
**And** the tag immediately appears in the list
**And** the input fields are cleared
**And** if the name already exists (case-insensitive), an error is shown: "Tag already exists"
**And** if the name is empty, the button stays disabled

### AC3: Delete a Predefined Tag
**Given** the Tags panel shows at least one tag
**When** the user clicks the delete (×) button next to a tag
**Then** the tag is removed from the `taskTags` table
**And** the tag disappears from the panel list immediately (optimistic update via Convex reactivity)
**And** existing tasks that had this tag still retain the name string in their `tags` array (no cascade delete — tag names are strings)

### AC4: Tag Selection During Task Creation
**Given** predefined tags exist in `taskTags`
**When** the user opens the collapsible options in `TaskInput`
**Then** a "Tags" section shows all predefined tags as checkboxes with colored dots
**And** the user can select multiple tags
**And** selected tags are highlighted (checkbox checked + colored badge preview)
**And** the `#tag` text-parsing from the title input is removed (replaced by this UI)

### AC5: Tags Visible on Task Cards (with color)
**Given** a task has tags
**When** it is rendered as a `TaskCard` on the Kanban board
**Then** each tag is displayed as a small colored badge (using the tag's registered color from `taskTags`)
**And** if a tag name exists in `taskTags`, it uses the registered color
**And** if a tag name is NOT found in `taskTags` (legacy free-form), it falls back to the existing `bg-muted text-muted-foreground` style

### AC6: Color Palette
**Given** the user is creating or the system is rendering a tag
**Then** exactly 8 colors are available: `blue`, `green`, `red`, `amber`, `violet`, `pink`, `orange`, `teal`
**And** each color maps to Tailwind classes (bg + text + dot) defined in `dashboard/lib/constants.ts`

## Tasks / Subtasks

- [x] Task 1: Update Convex schema — add `taskTags` table (AC: #1, #2, #3, #6)
  - [x] 1.1: Add `taskTags` table to `dashboard/convex/schema.ts`:
    ```ts
    taskTags: defineTable({
      name: v.string(),
      color: v.string(), // one of: blue|green|red|amber|violet|pink|orange|teal
    }).index("by_name", ["name"]),
    ```
  - [x] 1.2: Run `npx convex dev` to regenerate types (or confirm it runs on next start)

- [x] Task 2: Create `dashboard/convex/taskTags.ts` — Convex mutations/queries (AC: #1, #2, #3)
  - [x] 2.1: `list` query — returns all tags ordered by `name`
  - [x] 2.2: `create(name: string, color: string)` mutation — validate non-empty name (≤32 chars), check unique name (case-insensitive via index scan), insert; throw `ConvexError("Tag already exists")` on duplicate
  - [x] 2.3: `remove(id: Id<"taskTags">)` mutation — delete document by id

- [x] Task 3: Add `TAG_COLORS` constant to `dashboard/lib/constants.ts` (AC: #6)
  - [x] 3.1: Add:
    ```ts
    export const TAG_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
      blue:   { bg: "bg-blue-100",   text: "text-blue-700",   dot: "bg-blue-500" },
      green:  { bg: "bg-green-100",  text: "text-green-700",  dot: "bg-green-500" },
      red:    { bg: "bg-red-100",    text: "text-red-700",    dot: "bg-red-500" },
      amber:  { bg: "bg-amber-100",  text: "text-amber-700",  dot: "bg-amber-500" },
      violet: { bg: "bg-violet-100", text: "text-violet-700", dot: "bg-violet-500" },
      pink:   { bg: "bg-pink-100",   text: "text-pink-700",   dot: "bg-pink-500" },
      orange: { bg: "bg-orange-100", text: "text-orange-700", dot: "bg-orange-500" },
      teal:   { bg: "bg-teal-100",   text: "text-teal-700",   dot: "bg-teal-500" },
    };
    ```

- [x] Task 4: Create `dashboard/components/TagsPanel.tsx` — management UI (AC: #1, #2, #3, #6)
  - [x] 4.1: `useQuery(api.taskTags.list)` to load tags
  - [x] 4.2: Render list with: colored dot + tag name + × delete button per row
  - [x] 4.3: Empty state: "No tags yet. Add your first tag below."
  - [x] 4.4: Add-tag form at the bottom:
    - Name `<Input>` (max 32 chars, placeholder "Tag name…")
    - Color picker: 8 small circular swatches (one per TAG_COLORS key), selected swatch gets a ring
    - "Add" `<Button>` disabled when name is empty
    - Show inline error for duplicate name
  - [x] 4.5: `useMutation(api.taskTags.create)` on submit; `useMutation(api.taskTags.remove)` on delete

- [x] Task 5: Update `DashboardLayout.tsx` — add Tags panel trigger (AC: #1)
  - [x] 5.1: Import `Tag` icon from `lucide-react` and `TagsPanel` component
  - [x] 5.2: Add `tagsOpen: boolean` state (default `false`)
  - [x] 5.3: Add `<button aria-label="Open tags">` with `Tag` icon in the header, next to the Settings gear, using same className pattern
  - [x] 5.4: Add `<Sheet open={tagsOpen} onOpenChange={setTagsOpen}>` with `<SheetContent side="right" className="w-[400px] sm:w-[400px] p-0">` wrapping `<TagsPanel />` — same pattern as the Settings Sheet

- [x] Task 6: Update `TaskInput.tsx` — replace `#` text parsing with tag checkboxes (AC: #4)
  - [x] 6.1: Remove the `#` tag parsing block (lines 43-54) from `handleSubmit`; remove the `tags` variable from submit args; tags will now come from `selectedTags` state
  - [x] 6.2: Add `selectedTags: string[]` state (default `[]`)
  - [x] 6.3: `useQuery(api.taskTags.list)` for predefined tags
  - [x] 6.4: In the `CollapsibleContent`, add a "Tags" section below the reviewers section:
    - Section label "Tags:" (same style as "Agent:" label)
    - If no predefined tags: show "No tags defined. Open the Tags panel to add some." (small muted text)
    - If tags exist: render each as a row with `<Checkbox>` + colored dot + tag name
    - Checking toggles `selectedTags` (add/remove tag name)
  - [x] 6.5: Pass `tags: selectedTags.length > 0 ? selectedTags : undefined` in the `createTask` args
  - [x] 6.6: Reset `selectedTags` to `[]` after successful task creation (alongside other resets at line 89-94)
  - [x] 6.7: Update placeholder text: remove any mention of `#tag` syntax

- [x] Task 7: Thread `tagColorMap` through `KanbanBoard` → `KanbanColumn` → `TaskCard` (AC: #5)
  - [x] 7.1: In `KanbanBoard.tsx`: add `useQuery(api.taskTags.list)` to get all tags; build `tagColorMap: Record<string, string>` = `Object.fromEntries(tags?.map(t => [t.name, t.color]) ?? [])`
  - [x] 7.2: Pass `tagColorMap` prop to each `<KanbanColumn>` call
  - [x] 7.3: In `KanbanColumn.tsx`: add `tagColorMap?: Record<string, string>` to `KanbanColumnProps`; pass it through to each `<TaskCard>`
  - [x] 7.4: In `TaskCard.tsx`:
    - Add `tagColorMap?: Record<string, string>` to `TaskCardProps`
    - In the tags rendering block (currently lines 65-76), replace the hardcoded `bg-muted text-muted-foreground` with:
      ```tsx
      const color = tagColorMap?.[tag] ? TAG_COLORS[tagColorMap[tag]] : null;
      <span className={`text-xs px-1.5 py-0.5 rounded-full flex items-center gap-1 ${color ? `${color.bg} ${color.text}` : "bg-muted text-muted-foreground"}`}>
        {color && <span className={`w-1.5 h-1.5 rounded-full ${color.dot} flex-shrink-0`} />}
        {tag}
      </span>
      ```
    - Import `TAG_COLORS` from `@/lib/constants`

## Dev Notes

### Critical Architecture Requirements

- **No new dependencies**: All UI uses existing shadcn/ui components (`Sheet`, `Checkbox`, `Button`, `Input`, `Badge`) and `lucide-react` icons. No `@radix-ui` installs needed — already in the project.
- **Convex reactivity**: `useQuery(api.taskTags.list)` in `KanbanBoard` automatically re-renders when tags are added/deleted. No manual refresh needed.
- **Backward compatibility**: `tasks.tags` remains `v.optional(v.array(v.string()))` — task tags are stored as name strings. Deleting a predefined tag does NOT cascade to tasks (tags remain as strings on existing tasks). This is intentional: tags on tasks are denormalized strings, not foreign keys.
- **tagColorMap threading**: Thread through `KanbanBoard` → `KanbanColumn` → `TaskCard` as a prop (not context). This follows the existing prop-drilling pattern used for `onTaskClick`, `hitlCount`, etc. Do NOT use React Context — would be over-engineering for 3 levels.
- **Color as Tailwind strings**: Colors must be complete, non-dynamic Tailwind class strings (e.g., `"bg-blue-100"` not `"bg-"+color+"-100"`) so Tailwind's JIT compiler detects them. The `TAG_COLORS` map satisfies this.
- **Sheet pattern**: `TagsPanel` follows the exact same pattern as `SettingsPanel` — wrapped in a `Sheet` in `DashboardLayout`. Width `w-[400px]` is slightly narrower than Settings `w-[480px]` since the panel is simpler. Sheet has `p-0` and the panel component owns its padding.

### Key File References

| Component | File | What to change |
|-----------|------|----------------|
| Convex schema | `dashboard/convex/schema.ts:5` | Add `taskTags` table after `skills` table |
| New Convex module | `dashboard/convex/taskTags.ts` | Create new file: list query + create/remove mutations |
| Constants | `dashboard/lib/constants.ts:end` | Add `TAG_COLORS` export |
| Tags panel | `dashboard/components/TagsPanel.tsx` | Create new file |
| Layout | `dashboard/components/DashboardLayout.tsx:19,67-78,94-103` | Add Tag icon, `tagsOpen` state, Sheet |
| Task input | `dashboard/components/TaskInput.tsx:43-54,24-34,156-end` | Remove `#` parsing, add `selectedTags`, add tag checkboxes section |
| Kanban board | `dashboard/components/KanbanBoard.tsx:27,47-end` | Add `taskTags` query, build `tagColorMap`, pass to columns |
| Kanban column | `dashboard/components/KanbanColumn.tsx:14-24,26-36` | Add `tagColorMap` prop, pass to `TaskCard` |
| Task card | `dashboard/components/TaskCard.tsx:12,16-19,65-76` | Add `tagColorMap` prop, import `TAG_COLORS`, color-aware tag rendering |

### Existing Patterns to Follow

- **Icon usage**: All icons from `lucide-react`. Use `Tag` icon for the header button (same size/style as `Settings`: `h-5 w-5`). Use `X` icon for the delete button per tag row in `TagsPanel` (`h-3.5 w-3.5`).
- **Header button pattern**: The Settings gear in `DashboardLayout.tsx:71-77` uses `className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"` — use the same class for the Tags button.
- **Sheet pattern** (from `DashboardLayout.tsx:94-103`):
  ```tsx
  <Sheet open={tagsOpen} onOpenChange={setTagsOpen}>
    <SheetContent side="right" className="w-[400px] sm:w-[400px] p-0">
      <SheetHeader className="sr-only">
        <SheetTitle>Tags</SheetTitle>
        <SheetDescription>Manage predefined task tags</SheetDescription>
      </SheetHeader>
      <TagsPanel />
    </SheetContent>
  </Sheet>
  ```
- **Checkbox pattern** (from `TaskInput.tsx:20,166-188`): Project already uses `@/components/ui/checkbox`. Reviewers section shows the usage pattern — replicate it for tags.
- **Framer Motion on TaskCard**: The `motion.div layoutId` on the card root (line 35-38) will handle re-layout automatically when tag rendering changes. No extra motion setup needed.
- **AgentConfigSheet pattern**: `AgentSidebar` triggers `AgentConfigSheet` via `selectedAgent` state. The Tags panel is simpler — it's always fully open, no sub-sheet needed.
- **Convex error handling in mutations**: Pattern from `tasks.ts:ConvexError` — throw `new ConvexError("Tag already exists")` on duplicate. The client should catch this with `.catch()` in the submit handler and show an inline error.

### Removing the `#` Tag Parsing

Lines 43-54 in `TaskInput.tsx` parse `#tag1,tag2` from the title. This must be removed entirely:
- Remove the `hashIndex` parsing block
- Remove `tags` and `taskTitle` variables (revert to using `trimmed` directly as `title`)
- Remove `tags?: string[]` from the `args` type (it stays as part of `createTask` args via `selectedTags`)
- Update placeholder from "Create a new task..." to keep it as-is (no mention of `#` was in placeholder)

### Project Structure Notes

- All new components go in `dashboard/components/` (flat structure, no subdirs)
- New Convex module `dashboard/convex/taskTags.ts` follows the naming convention of `tasks.ts`, `agents.ts`
- `TAG_COLORS` added to existing `dashboard/lib/constants.ts` at the bottom (same file already exports `STATUS_COLORS` map)
- No Python backend changes needed — tags are purely a dashboard concern

### References

- [Source: dashboard/convex/schema.ts:5-34] — Tasks table (existing `tags` field at line 25)
- [Source: dashboard/convex/schema.ts:109-118] — `skills` table as model for `taskTags` table structure
- [Source: dashboard/components/DashboardLayout.tsx:19,67-103] — Settings Sheet pattern to replicate for Tags
- [Source: dashboard/components/AgentSidebar.tsx] — Sidebar panel structure reference (for TagsPanel content layout)
- [Source: dashboard/components/TaskInput.tsx:21,43-54,156-219] — Current `#` tag parsing (to remove) + collapsible section structure
- [Source: dashboard/components/TaskCard.tsx:65-76] — Current tag rendering (to enhance with colors)
- [Source: dashboard/components/KanbanBoard.tsx:26-37] — Query pattern + prop passing to columns
- [Source: dashboard/components/KanbanColumn.tsx:14-24] — KanbanColumnProps interface to extend
- [Source: dashboard/lib/constants.ts:79-124] — `STATUS_COLORS` map as model for `TAG_COLORS`
- [Source: _bmad-output/implementation-artifacts/8-6-human-manual-tasks-kanban.md#Existing Patterns to Follow] — Icon usage, framer motion, card design, button styling

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_None — implementation completed cleanly with zero TypeScript errors._

### Completion Notes List

- Implemented all 7 tasks covering: Convex schema (`taskTags` table), backend mutations/queries (`taskTags.ts`), color constants (`TAG_COLORS` in `constants.ts`), Tags management panel (`TagsPanel.tsx`), layout integration (`DashboardLayout.tsx`), task creation UI (`TaskInput.tsx`), and Kanban prop threading (`KanbanBoard` → `KanbanColumn` → `TaskCard`).
- The `#tag` parsing from `TaskInput.handleSubmit` was fully removed; tags now come from `selectedTags` state populated via checkboxes.
- Convex dev server automatically picked up the new `taskTags.ts` module and regenerated `api.d.ts` — no manual regeneration needed.
- TypeScript compilation: zero errors (`npx tsc --noEmit` clean pass). 23/23 tests pass (`npx vitest run tests/`).
- Color-aware tag rendering in `TaskCard` falls back gracefully to `bg-muted text-muted-foreground` for legacy free-form tag strings not found in `taskTags`.
- All Tailwind color classes use complete static strings (no dynamic interpolation) per Tailwind JIT requirements.
- **Code review fixes applied:** (1) `selectedTags` now reset when switching to manual mode (M1); (2) server-side color validation added to `taskTags.create` (M2); (3) ConvexError detection uses `.data` instead of `.includes()` string matching (M3); (4) 23 tests written for `TAG_COLORS`, `TagsPanel`, and `TaskInput` tag logic (H1); (5) added `globals: true` to vitest config to enable RTL cleanup.

### File List

- `dashboard/convex/schema.ts` — added `taskTags` table definition
- `dashboard/convex/taskTags.ts` — new file: `list` query, `create` mutation, `remove` mutation (with server-side color validation)
- `dashboard/lib/constants.ts` — added `TAG_COLORS` export (8-color palette)
- `dashboard/components/TagsPanel.tsx` — new file: tags management side panel UI (ConvexError.data detection)
- `dashboard/components/DashboardLayout.tsx` — added `Tag` icon button + `tagsOpen` state + Tags Sheet
- `dashboard/components/TaskInput.tsx` — removed `#` parsing, added `selectedTags` state + tag checkboxes section; reset `selectedTags` on manual mode toggle
- `dashboard/components/KanbanBoard.tsx` — added `taskTags` query + `tagColorMap` build + prop pass
- `dashboard/components/KanbanColumn.tsx` — added `tagColorMap` prop, threaded to `TaskCard`
- `dashboard/components/TaskCard.tsx` — added `tagColorMap` prop + color-aware tag badge rendering
- `dashboard/vitest.config.ts` — added `globals: true` for RTL cleanup support
- `dashboard/tests/lib/constants.test.ts` — new: 6 tests for `TAG_COLORS`
- `dashboard/tests/components/TagsPanel.test.tsx` — new: 11 tests for `TagsPanel` component
- `dashboard/tests/components/TaskInput.tags.test.tsx` — new: 6 tests for tag selection in `TaskInput`

## Change Log

- 2026-02-23: Story 8.7 implemented — added full task tags management system including `taskTags` Convex table, list/create/remove mutations, `TAG_COLORS` constant (8 colors), `TagsPanel` side panel, Tags Sheet trigger in header, tag checkbox selection in task creation, and color-aware tag badge rendering threaded through KanbanBoard → KanbanColumn → TaskCard. Removed legacy `#tag` text parsing from TaskInput.
- 2026-02-23: Code review fixes — fixed selectedTags leak to manual tasks, added server-side color validation, improved ConvexError detection, added 23 vitest tests, enabled RTL globals in vitest config.
