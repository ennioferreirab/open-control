# Story 9-4: Attach Files to Existing Tasks

**Epic:** 9 — Thread Files Context: Attach Files to Tasks
**Status:** ready-for-dev

## Story

As a **user**,
I want to add files to a task that already exists,
So that I can provide additional context to agents working on in-progress tasks.

## Acceptance Criteria

**Given** the TaskDetailSheet is open on the Files tab (Story 9-3)
**When** the user clicks the "Attach File" button at the top of the Files tab
**Then** a native file picker dialog opens allowing selection of one or more files

**Given** the user selects files
**When** the upload is initiated
**Then** files are uploaded to `~/.nanobot/tasks/{task-id}/attachments/` via the same API route as Story 9-2 (`POST /api/tasks/[taskId]/files`)
**And** the Convex task record's `files` array is updated with the new file metadata (FR2, FR23)
**And** the Files tab updates reactively to show the newly attached files (FR25)
**And** an activity event is created: "User attached {count} file(s) to task"

**Given** the upload completes
**When** the user views the Files tab
**Then** both previously existing files and newly uploaded files are visible
**And** upload completes within 3 seconds for files up to 10MB (NFR1)

## Technical Notes

- Modify the Files tab in `components/TaskDetailSheet.tsx` (built in Story 9-3)
- Add an "Attach File" button at the top of the Files tab content area (above the file list)
  - Use `Paperclip` icon + "Attach File" label, `variant="outline"` `size="sm"`
  - Hidden `<input type="file" multiple ref={attachInputRef}>` triggered on button click
- On file selection: POST to `/api/tasks/${task._id}/files` with FormData (same pattern as TaskInput.tsx)
- On success: call `addTaskFiles` Convex mutation with the returned file metadata
- Activity event: call a Convex mutation to create an activity event
  - Look at existing activity creation patterns in the dashboard (how other actions create activity events)
  - Message: `User attached ${count} file(s) to task`
  - Use activity type `"user_action"` or the nearest equivalent used elsewhere
- Show a loading state on the button while uploading (disable + spinner or text change)
- On error: show inline error message below the button
- Upload state is local to the sheet — no global state needed

## NFRs Covered

- NFR1: Upload completes within 3 seconds for files up to 10MB
