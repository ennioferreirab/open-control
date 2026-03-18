# Story 9-5: File Indicators on Task Cards

**Epic:** 9 — Thread Files Context: Attach Files to Tasks
**Status:** ready-for-dev

## Story

As a **user**,
I want to see at a glance which tasks have files on the Kanban board,
So that I can identify document-related tasks without clicking into each one.

## Acceptance Criteria

**Given** a task has one or more files in its `files` manifest
**When** the TaskCard renders on the Kanban board
**Then** a paperclip icon is displayed on the card (FR26)
**And** the file count is shown next to the paperclip icon (e.g. "3") (FR27)

**Given** a task has no files
**When** the TaskCard renders
**Then** no paperclip icon or file count is shown

**Given** a file is added to a task (by user upload or agent output)
**When** the Convex reactive query updates
**Then** the paperclip icon and count appear (or update) on the card in real-time

## Technical Notes

- Modify `components/TaskCard.tsx`
- The task prop already has the `files` field from the Convex schema
- Add a paperclip indicator in the card's metadata row (same row as tags, assignee, or other metadata)
- Use `Paperclip` icon from `lucide-react`, size `w-3 h-3`
- Style: `text-xs text-muted-foreground flex items-center gap-0.5` — consistent with other card metadata
- Only render when `task.files && task.files.length > 0`
- Count: `task.files.length`
- Place it in the existing metadata/footer row of the card — check the current TaskCard layout to find the right location
