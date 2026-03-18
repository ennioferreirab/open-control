# Story 9-2: Upload Files at Task Creation

**Epic:** 9 — Thread Files Context: Attach Files to Tasks
**Status:** ready-for-dev

## Story

As a **user**,
I want to attach files when creating a task by selecting them from a file picker,
So that agents receive relevant documents alongside my task description.

## Acceptance Criteria

**Given** the TaskInput component exists on the dashboard
**When** the user clicks the attachment button (paperclip icon) next to the task input
**Then** a native file picker dialog opens allowing selection of one or more files

**Given** the user selects files from the file picker
**When** the files are selected
**Then** each selected file appears as a chip below the task input showing: file name and size
**And** the user can remove any pending attachment by clicking the X on the chip (FR4)

**Given** the user submits a task with pending file attachments
**When** the form is submitted
**Then** the task is created in Convex first (optimistic UI — card appears in Inbox)
**And** files are uploaded to `~/.nanobot/tasks/{task-id}/attachments/` via a Next.js API route (`POST /api/tasks/[taskId]/files`) accepting multipart form data
**And** the API route writes each file to the `attachments/` subdirectory
**And** on successful upload, the Convex task record's `files` array is updated with metadata for each file: `{ name, type, size, subfolder: "attachments", uploadedAt }` (FR23)
**And** file upload completes within 3 seconds for files up to 10MB (NFR1)
**And** the file manifest reflects the upload within 2 seconds of completion (NFR6)

**Given** a file upload fails mid-transfer
**When** the error is detected
**Then** no partial file is left in the task directory (NFR12)
**And** an error message is shown to the user
**And** successfully uploaded files from the same batch are not affected

**Given** the user submits a task with no attachments
**When** the form is submitted
**Then** the task is created normally without files — the `files` field remains empty or undefined

## Technical Notes

### Next.js API Route
- Create `dashboard/app/api/tasks/[taskId]/files/route.ts`
- `POST` handler accepts multipart form data using `request.formData()`
- For each file: write to `Path.home()/.nanobot/tasks/{taskId}/attachments/{filename}` using Node.js `fs`
- To avoid partial files: write to a temp path first, then rename atomically (or write to final path but delete on error)
- Return JSON array of file metadata: `{ name, type, size, subfolder: "attachments", uploadedAt }`
- On success: call a Convex mutation to append the file entries to `task.files`
- Use the Convex HTTP client from the existing dashboard patterns (check other API routes for how Convex mutations are called server-side, or use the `ConvexHttpClient` from `convex/browser`)
- Path safety: validate that `taskId` doesn't contain path traversal characters

### Convex Mutation
- Add a mutation `addTaskFiles` in `dashboard/convex/tasks.ts`
- Args: `{ taskId: v.id("tasks"), files: v.array(v.object({ name, type, size, subfolder, uploadedAt })) }`
- Appends new file entries to the existing `task.files` array (or sets it if undefined)

### TaskInput Component
- Add a hidden `<input type="file" multiple ref={fileInputRef} />`
- Add a paperclip icon button (use `Paperclip` from `lucide-react`) next to the submit area that triggers `fileInputRef.current?.click()`
- State: `pendingFiles: File[]`
- On file selection: append to `pendingFiles`
- Render chips below the input for each pending file: filename + human-readable size + X button to remove
- On form submit:
  1. Create task in Convex (existing flow)
  2. If `pendingFiles.length > 0`: POST to `/api/tasks/{newTaskId}/files` with FormData
  3. Clear `pendingFiles` after upload
- Follow existing chip pattern in the codebase (check for tag chips or similar)
- Use `text-xs` size for file chips, consistent with existing metadata style

## NFRs Covered

- NFR1: File upload completes within 3 seconds for files up to 10MB
- NFR6: File manifest reflects upload within 2 seconds of completion
- NFR12: No partial files left on upload failure
