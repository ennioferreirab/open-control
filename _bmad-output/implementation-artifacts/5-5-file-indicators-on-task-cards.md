# Story 5.5: File Indicators on Task Cards

Status: done

## Story

As a **user**,
I want to see at a glance which tasks have files on the Kanban board,
So that I can identify document-related tasks without clicking into each one.

## Acceptance Criteria

1. **TaskCard paperclip indicator** -- Given a task has one or more files in its `files` manifest, when the TaskCard renders on the Kanban board, then a paperclip icon (`Paperclip` from lucide-react, `h-3 w-3`) is displayed alongside the file count (e.g., "3") (FR-F26, FR-F27).

2. **TaskCard no-files state** -- Given a task has no files (undefined or empty array), when the TaskCard renders, then no paperclip icon or count is shown.

3. **StepCard paperclip indicator** -- Given a step's parent task has one or more files in its `files` manifest, when the StepCard renders on the Kanban board, then a paperclip icon and count are displayed on the StepCard, reflecting the parent task's file count.

4. **StepCard attachedFiles indicator** -- Given a step has its own `attachedFiles` array with one or more entries, when the StepCard renders, then a paperclip icon and count are displayed reflecting `step.attachedFiles.length`. If the parent task also has files, both indicators may coexist or the step-level count is shown (see Dev Notes for decision).

5. **StepCard no-files state** -- Given a step has no `attachedFiles` and the parent task has no files, when the StepCard renders, then no paperclip icon or count is shown.

6. **Real-time reactive updates** -- Given a file is added (by user upload or agent output), when the Convex reactive query updates the task's `files` array, then the paperclip icon and count appear or update in real-time on both TaskCard and StepCard without manual refresh (FR-F25).

7. **Tests pass** -- Vitest tests exist covering: TaskCard shows indicator when files present, TaskCard hides indicator when no files, StepCard shows indicator when attachedFiles present, StepCard hides indicator when no attachedFiles.

## Tasks / Subtasks

- [x] Task 1: Verify TaskCard already has file indicator (AC: #1, #2)
  - [x] 1.1: Read current `TaskCard.tsx` -- confirm the paperclip indicator already exists at lines 180-185
  - [x] 1.2: Verify it renders `Paperclip` icon (h-3 w-3) with `task.files.length` when `task.files && task.files.length > 0`
  - [x] 1.3: Verify it renders nothing when task has no files
  - [x] 1.4: If already correct, document as "pre-existing, verified" and move to Task 2. If missing or wrong, fix it.

- [x] Task 2: Add file indicator to StepCard (AC: #3, #4, #5)
  - [x] 2.1: Import `Paperclip` from `lucide-react` in `StepCard.tsx`
  - [x] 2.2: Add optional `fileCount` prop to `StepCardProps` interface: `fileCount?: number`
  - [x] 2.3: In the footer row (the `div` with `className="mt-2 flex items-center gap-2"`), after the status badge section and before the closing `</div>`, add the file indicator:
    ```tsx
    {(fileCount ?? 0) > 0 && (
      <span className="inline-flex items-center gap-0.5 text-xs text-muted-foreground">
        <Paperclip className="h-3 w-3" />
        {fileCount}
      </span>
    )}
    ```
  - [x] 2.4: The `fileCount` value will be computed by the caller and passed down (see Task 3)

- [x] Task 3: Pass file count data to StepCard from KanbanColumn (AC: #3, #6)
  - [x] 3.1: In `KanbanBoard.tsx`, build a `taskFileCountMap` from the tasks array: `const taskFileCountMap = new Map(tasks.map((t) => [t._id, t.files?.length ?? 0] as const));`
  - [x] 3.2: When building `stepsByTaskId`, also store the parent task's file count in each step group or pass the map to the column
  - [x] 3.3: In `KanbanColumn.tsx`, accept a `taskFileCountMap` prop (type: `Map<Id<"tasks">, number>`) or alternatively pass `fileCount` per step group
  - [x] 3.4: When rendering `<StepCard>`, compute and pass `fileCount`:
    - Use `step.attachedFiles?.length` if the step has its own attached files
    - Otherwise, fall back to the parent task's file count from the map
    - Simplest approach: `fileCount={(step.attachedFiles?.length ?? 0) || (taskFileCountMap?.get(step.taskId) ?? 0)}`
  - [x] 3.5: Alternative simpler approach -- only show step-level `attachedFiles` count on StepCard (no parent task files). This is cleaner because task-level files already show on the TaskGroupHeader area. **Choose this approach**: only render `step.attachedFiles?.length` on StepCard.

- [x] Task 4: Add file count to StepCard using step's own attachedFiles (AC: #4, #5) (SIMPLIFIED)
  - [x] 4.1: Instead of passing from parent, compute inside StepCard: check `step.attachedFiles?.length ?? 0`
  - [x] 4.2: No changes needed to KanbanBoard or KanbanColumn props
  - [x] 4.3: The `StepCardProps` already receives a `Doc<"steps">` which includes `attachedFiles?: string[]` from the schema
  - [x] 4.4: In StepCard footer, add:
    ```tsx
    {step.attachedFiles && step.attachedFiles.length > 0 && (
      <span className="inline-flex items-center gap-0.5 text-xs text-muted-foreground">
        <Paperclip className="h-3 w-3" />
        {step.attachedFiles.length}
      </span>
    )}
    ```

- [x] Task 5: Write Vitest tests for TaskCard file indicator (AC: #7)
  - [x] 5.1: In `TaskCard.test.tsx`, add test: "shows paperclip icon and file count when files present"
    - Render TaskCard with `files: [{ name: "a.pdf", type: "application/pdf", size: 100, subfolder: "attachments", uploadedAt: "2026-01-01T00:00:00Z" }]`
    - Assert `screen.getByText("1")` is in the document (the count)
  - [x] 5.2: Add test: "does not show file count when no files"
    - Render TaskCard with no `files` field
    - Assert no paperclip count is rendered
  - [x] 5.3: Add test: "shows correct count for multiple files"
    - Render TaskCard with 3 files
    - Assert `screen.getByText("3")` is in the document

- [x] Task 6: Write Vitest tests for StepCard file indicator (AC: #7)
  - [x] 6.1: In `StepCard.test.tsx`, add test: "shows paperclip icon and file count when attachedFiles present"
    - Render StepCard with `step: { ...baseStep, attachedFiles: ["report.pdf", "data.csv"] }`
    - Assert `screen.getByText("2")` is in the document
  - [x] 6.2: Add test: "does not show file indicator when no attachedFiles"
    - Render StepCard with `step: baseStep` (no attachedFiles)
    - Assert no paperclip count is rendered
  - [x] 6.3: Add test: "does not show file indicator when attachedFiles is empty array"
    - Render StepCard with `step: { ...baseStep, attachedFiles: [] }`
    - Assert no paperclip count is rendered

## Dev Notes

### Critical: TaskCard File Indicator Already Exists

**The TaskCard already has a working file indicator** at lines 180-185 of `dashboard/components/TaskCard.tsx`:

```tsx
{task.files && task.files.length > 0 && (
  <span className="inline-flex items-center gap-0.5">
    <Paperclip className="h-3 w-3" />
    {task.files.length}
  </span>
)}
```

The `Paperclip` icon is already imported in TaskCard. This was implemented as part of the brownfield codebase. **Do NOT re-implement or duplicate this.** Verify it works and add tests if missing.

The primary new work is on **StepCard**, which currently has NO file indicator.

### StepCard File Data Source

The `steps` table in Convex has an `attachedFiles: v.optional(v.array(v.string()))` field. This stores file **names** (strings), not full file metadata objects. The step's `attachedFiles` comes from the pre-kickoff modal (Story 4.4) where users can attach documents per step.

The StepCard receives `step: Doc<"steps">` which includes `attachedFiles` if present. Use `step.attachedFiles?.length` for the count. No prop drilling or parent data needed.

### Design Decision: Step-Level vs Task-Level Files on StepCard

Show **only step-level `attachedFiles`** on StepCard, not the parent task's file count. Rationale:
- Task-level files are visible on the TaskCard itself (which renders separately for tasks without steps)
- For tasks with steps, the TaskGroupHeader groups steps -- task files are accessible via clicking into the task detail
- Showing parent task files on every step card would be noisy and redundant
- Step-level `attachedFiles` is the more actionable indicator (tells you THIS step has documents attached)

### Placement in StepCard Layout

Add the file indicator in the **footer metadata row** (`mt-2 flex items-center gap-2`), after the status badge and crashed/blocked badges. This is consistent with where TaskCard places its file indicator (in the metadata area alongside trust level and other indicators).

### Styling Consistency

Match the exact styling pattern used in TaskCard:
- Container: `inline-flex items-center gap-0.5 text-xs text-muted-foreground`
- Icon: `Paperclip` from lucide-react, `h-3 w-3`
- Count: plain text (the number)

### Reactive Updates (FR-F25)

No special work needed for reactivity. Convex queries are reactive by default:
- `useQuery(api.tasks.list)` in KanbanBoard already streams task updates including `files` changes
- `useQuery(api.steps.listAll)` streams step updates including `attachedFiles` changes
- When a file is uploaded (via `addTaskFiles` mutation) or agent output synced (via `syncOutputFiles` mutation), the reactive query fires and TaskCard/StepCard re-render automatically

### Existing Imports in StepCard

StepCard currently imports from lucide-react: `AlertTriangle`, `Lock`. Add `Paperclip` to this import.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT re-implement the TaskCard file indicator** -- it already exists and works. Just verify and add tests.
2. **DO NOT import file data from the parent task into StepCard** -- use `step.attachedFiles` directly from the step's own document.
3. **DO NOT add a new Convex query for file counts** -- the data is already available on the task and step documents.
4. **DO NOT change KanbanBoard or KanbanColumn for this story** -- the step's `attachedFiles` is already available on the `Doc<"steps">` type.
5. **DO NOT use a tooltip for the file indicator** -- keep it simple: icon + count, same as TaskCard.
6. **DO NOT conditionally render based on file type or subfolder** -- show total count regardless.

### What This Story Does NOT Include

- **File upload UI on steps** -- That is Story 4.4 (Attach Documents to Steps in Pre-Kickoff)
- **File viewing** -- Stories 5.7-5.10 (Viewer Modal)
- **File serving API** -- Story 5.6
- **Agent file context** -- Stories in Epic 5 related to agent file awareness

### Project Structure Notes

- All components are in `dashboard/components/`
- Tests are co-located: `StepCard.test.tsx` next to `StepCard.tsx`
- UI library: ShadCN + Tailwind CSS
- Icons: `lucide-react` (already a project dependency)
- Test runner: Vitest with `@testing-library/react`
- No new files created -- only modifications to existing files

### Previous Story Intelligence

From Story 5.1 (done): trust level and reviewer configuration followed the same pattern of adding small visual indicators to card components. The `RefreshCw` icon for review and `HITL` badge were added in the footer metadata area of TaskCard. The StepCard file indicator follows the same placement pattern.

From Story 9-5 (previous numbering, ready-for-dev): A simpler version of this story existed targeting only TaskCard. The current story extends scope to include StepCard.

### Git Intelligence

Recent commits show patterns:
- Stories modify component files and their co-located test files
- Tests use `vi.mock` for motion and Convex dependencies
- `baseStep` and `baseTask` fixtures are already defined in test files
- The `Doc<"steps">` type from Convex includes `attachedFiles` automatically

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 5.5`] -- Original story definition with BDD acceptance criteria
- [Source: `_bmad-output/planning-artifacts/prd-thread-files-context.md#FR26`] -- Paperclip icon on task cards
- [Source: `_bmad-output/planning-artifacts/prd-thread-files-context.md#FR27`] -- File count next to paperclip
- [Source: `_bmad-output/planning-artifacts/prd-thread-files-context.md#FR25`] -- Reactive manifest display
- [Source: `_bmad-output/planning-artifacts/architecture.md#Step Rendering on Kanban`] -- Step cards show file indicator
- [Source: `dashboard/components/TaskCard.tsx:180-185`] -- Existing TaskCard file indicator implementation
- [Source: `dashboard/components/StepCard.tsx`] -- StepCard component to extend
- [Source: `dashboard/convex/schema.ts:88`] -- Steps table `attachedFiles` field
- [Source: `dashboard/convex/schema.ts:55-61`] -- Tasks table `files` field
- [Source: `dashboard/components/StepCard.test.tsx`] -- Existing StepCard tests to extend

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/components/StepCard.tsx` | Add `Paperclip` import, add file indicator in footer row |
| `dashboard/components/StepCard.test.tsx` | Add 3 tests for file indicator presence/absence |
| `dashboard/components/TaskCard.test.tsx` | Add 3 tests for existing file indicator |

### Files Created in This Story

| File | Purpose |
|------|---------|
| (none) | |

### Verification Steps

1. Open dashboard Kanban board
2. Create a task with file attachments -- verify TaskCard shows paperclip icon with correct count
3. Create a task without files -- verify no paperclip shown
4. Upload a file to an existing task -- verify count updates in real-time
5. Create a supervised task with steps where steps have `attachedFiles` -- verify StepCard shows paperclip icon with count
6. Verify StepCard with no attachedFiles shows no paperclip
7. Run `cd dashboard && npx vitest run` -- all tests pass

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

No debug issues encountered.

### Completion Notes List

- Task 1 (pre-existing, verified): TaskCard.tsx already had the Paperclip file indicator at lines 189-194. The `Paperclip` icon from lucide-react was already imported. The indicator renders `task.files.length` when `task.files && task.files.length > 0`. No code changes needed.
- Task 2/4 (simplified path): Added `Paperclip` to the lucide-react import in StepCard.tsx. Added the file indicator in the footer `mt-2 flex items-center gap-2` div, after the Blocked badge. Uses `step.attachedFiles` directly from the Doc<"steps"> — no prop drilling, no KanbanBoard/KanbanColumn changes needed.
- Task 5: Added 3 Vitest tests to TaskCard.test.tsx: shows count when 1 file present, hides indicator when no files, shows correct count (3) for multiple files.
- Task 6: Added 3 Vitest tests to StepCard.test.tsx: shows count when 2 attachedFiles present, hides indicator when no attachedFiles, hides indicator when attachedFiles is empty array.
- All 466 tests pass (no regressions). The 6 new tests all pass.

### File List

| File | Change |
|------|--------|
| `dashboard/components/StepCard.tsx` | Added `Paperclip` to lucide-react import; added file indicator span in footer row |
| `dashboard/components/StepCard.test.tsx` | Added 3 new tests for file indicator (AC #7) |
| `dashboard/components/TaskCard.test.tsx` | Added 3 new tests for pre-existing file indicator (AC #7) |

### Change Log

- 2026-02-25: Implemented Story 5.5 — verified TaskCard file indicator (pre-existing), added StepCard file indicator using step.attachedFiles, added 6 Vitest tests covering presence/absence of indicators on both card types.
