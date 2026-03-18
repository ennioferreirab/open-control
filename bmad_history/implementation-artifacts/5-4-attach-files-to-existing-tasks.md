# Story 5.4: Attach Files to Existing Tasks

Status: ready-for-dev

## Story

As a **user**,
I want to add files to a task that already exists,
So that I can provide additional context to agents working on in-progress tasks.

## Acceptance Criteria

1. **Given** the Files tab is open in TaskDetailSheet, **When** the user clicks "Attach File", **Then** a native file picker dialog opens allowing multi-file selection (FR-F2).

2. **Given** the user selects one or more files via the picker, **When** the upload completes, **Then** files are uploaded to `~/.nanobot/tasks/{task-id}/attachments/` via `POST /api/tasks/[taskId]/files` (same API route as Story 5.2).

3. **Given** the upload completes successfully, **When** the Convex mutation runs, **Then** the task's `files` array is updated with metadata objects `{ name, type, size, subfolder: "attachments", uploadedAt }` via the `addTaskFiles` mutation (FR-F23).

4. **Given** the file manifest is updated in Convex, **When** the reactive query fires, **Then** the Files tab updates in real-time without manual refresh (FR-F25).

5. **Given** the upload succeeds, **When** the post-upload logic runs, **Then** an activity event is created with `eventType: "file_attached"` and description `"User attached {count} file(s) to task"` via the `activities.create` mutation.

6. **Given** a file up to 10 MB in size, **When** uploaded, **Then** upload completes within 3 seconds (NFR-F1).

7. **Given** the upload fails mid-transfer, **When** the error is caught, **Then** no partial file is left on disk (NFR-F12) and an error message is shown to the user.

8. **Given** the upload button state, **When** a file upload is in progress, **Then** the button is disabled and shows "Uploading..." to prevent double-submission.

9. **Given** a file is successfully attached, **When** it appears in the Attachments section, **Then** the user can click its name to open it in the DocumentViewerModal, and can delete it via the trash icon.

## Tasks / Subtasks

- [ ] Task 1: Add "Attach File" button to the Files tab in TaskDetailSheet (AC: 1, 8)
  - [ ] 1.1 Add a hidden `<input type="file" multiple>` element with a ref
  - [ ] 1.2 Add an "Attach File" button with Paperclip icon that triggers the file input click
  - [ ] 1.3 Add `isUploading` state to disable button and show "Uploading..." text during upload
  - [ ] 1.4 Add `uploadError` state to display error message below the button

- [ ] Task 2: Implement `handleAttachFiles` handler in TaskDetailSheet (AC: 2, 3, 5, 6, 7)
  - [ ] 2.1 On file input change, build a `FormData` with all selected files
  - [ ] 2.2 POST to `/api/tasks/${task._id}/files` with the FormData body
  - [ ] 2.3 On success, call `addTaskFiles` mutation with the returned file metadata array
  - [ ] 2.4 On success, call `createActivity` mutation with `eventType: "file_attached"` and appropriate description
  - [ ] 2.5 On failure, set `uploadError` to "Upload failed. Please try again."
  - [ ] 2.6 Reset the file input value after selection (so same file can be re-selected)
  - [ ] 2.7 Wrap in try/catch with finally block to reset `isUploading`

- [ ] Task 3: Implement file deletion from Files tab (AC: 9)
  - [ ] 3.1 Add delete button (Trash2 icon) to each attachment row, hidden by default and visible on hover
  - [ ] 3.2 On click, call `DELETE /api/tasks/${task._id}/files` with `{ subfolder, filename }` body
  - [ ] 3.3 On success, call `removeTaskFile` mutation to update Convex
  - [ ] 3.4 Add `deletingFiles` set state to track which files are being deleted and show spinner
  - [ ] 3.5 Handle ENOENT as success (idempotent delete)

- [ ] Task 4: Verify reactive file list updates (AC: 4)
  - [ ] 4.1 Confirm the `useQuery(api.tasks.getById)` subscription in TaskDetailSheet automatically re-renders when `files` array changes
  - [ ] 4.2 Confirm new attachments appear in the Attachments section and new outputs appear in the Outputs section

- [ ] Task 5: Write unit tests for TaskDetailSheet file attachment behavior (AC: 1-9)
  - [ ] 5.1 Test: "Attach File" button renders in the Files tab
  - [ ] 5.2 Test: Button is disabled and shows "Uploading..." during upload
  - [ ] 5.3 Test: Error message displays when upload fails
  - [ ] 5.4 Test: File list renders with correct icon, name, and size for attachments
  - [ ] 5.5 Test: Delete button calls the mutation with correct args
  - [ ] 5.6 Test: Empty state shows "No attachments yet." placeholder

## Dev Notes

### CRITICAL: This story is ALREADY IMPLEMENTED

The current `TaskDetailSheet.tsx` (as of the `novo-plano` branch) **already contains the complete implementation** for this story. All the code for file attachment, deletion, upload state management, error handling, and activity event creation is present. The developer MUST verify the existing implementation against the acceptance criteria below and add any missing tests, rather than building from scratch.

**Existing implementation in TaskDetailSheet.tsx:**
- Lines 66-76: State variables (`addTaskFiles`, `removeTaskFile`, `createActivity`, `isUploading`, `uploadError`, `deletingFiles`, `deleteError`, `attachInputRef`)
- Lines 111-141: `handleAttachFiles` handler (FormData upload, addTaskFiles mutation, createActivity mutation)
- Lines 144-166: `handleDeleteFile` handler (DELETE API call, removeTaskFile mutation, idempotent ENOENT handling)
- Lines 380-484: Files tab JSX with Attach File button, Attachments section, Outputs section, file rows with viewer + delete

### What the developer MUST do

1. **Verify** the existing implementation matches all 9 acceptance criteria
2. **Add unit tests** to `TaskDetailSheet.test.tsx` covering the file attachment flow (Task 5)
3. **Fix any gaps** between the acceptance criteria and the existing implementation (there should be none or very few)

### Architecture & Patterns

**Data flow for file attachment:**
1. User clicks "Attach File" button -> native file picker opens
2. User selects files -> `handleAttachFiles` fires
3. `FormData` with files is POSTed to `POST /api/tasks/[taskId]/files` (Next.js API route)
4. API route writes files to `~/.nanobot/tasks/{taskId}/attachments/` using atomic write (write to `.tmp`, rename)
5. API returns file metadata array `[{ name, type, size, subfolder: "attachments", uploadedAt }]`
6. Client calls `addTaskFiles` Convex mutation to append metadata to `task.files` array
7. Client calls `activities.create` Convex mutation with `eventType: "file_attached"`
8. Convex reactive query re-fires -> Files tab updates automatically

**File deletion flow:**
1. User hovers over attachment row -> trash icon appears
2. User clicks trash -> `handleDeleteFile` fires
3. `DELETE /api/tasks/[taskId]/files` with `{ subfolder: "attachments", filename }` body
4. API route calls `unlink()` on the file path (ENOENT treated as success)
5. Client calls `removeTaskFile` Convex mutation to filter file from `task.files` array
6. Convex reactive query re-fires -> file disappears from list

**API route location:** `dashboard/app/api/tasks/[taskId]/files/route.ts`
- POST handler: validates taskId, creates attachments dir, writes files atomically (tmp + rename), returns metadata
- DELETE handler: validates taskId + subfolder + filename, unlinks file, treats ENOENT as success

**Convex mutations used:**
- `tasks.addTaskFiles({ taskId, files })` — appends to `task.files` array (dashboard/convex/tasks.ts, lines 837-856)
- `tasks.removeTaskFile({ taskId, subfolder, filename })` — filters out matching file entry, only allows `subfolder === "attachments"` (dashboard/convex/tasks.ts, lines 862-877)
- `activities.create({ taskId, eventType, description, timestamp })` — creates activity event (dashboard/convex/activities.ts)

**Convex schema (task.files field):**
```typescript
files: v.optional(v.array(v.object({
  name: v.string(),
  type: v.string(),
  size: v.number(),
  subfolder: v.string(),
  uploadedAt: v.string(),
})))
```

**Activity event type for file attachment:** `"file_attached"` (already in schema union)

### Dependencies

- **Story 5.1** (Extend Schema and Create Task Directories): MUST be complete. Provides the `files` field on tasks table, `addTaskFiles`/`removeTaskFile` mutations, and per-task directory creation.
- **Story 5.3** (Build Files Tab in Task Detail): MUST be complete. Provides the Files tab UI shell in TaskDetailSheet, including the Attachments/Outputs sections and file list rendering.
- **Story 5.2** (Upload Files at Task Creation): Uses the same `POST /api/tasks/[taskId]/files` API route established in 5.2.

### UI Components Used

- `Button` (shadcn/ui) — "Attach File" button with `variant="outline"` and `size="sm"`
- `Paperclip` (lucide-react) — icon for the attach button
- `Trash2` (lucide-react) — icon for the delete button on each attachment row
- `Loader2` (lucide-react) — spinning icon shown during file deletion
- `ScrollArea` (shadcn/ui) — wraps the file list for scrollable content
- `FileIcon` (local component) — renders file-type-specific icon based on extension

### File Icons Logic

The `FileIcon` component in TaskDetailSheet renders icons by extension:
- `.pdf` -> `FileText`
- `.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp` -> `Image`
- `.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.go`, `.rs`, `.java`, `.sh` -> `FileCode`
- Everything else -> `File`

### Testing Standards

- Test framework: **vitest** + **@testing-library/react**
- Test file: `dashboard/components/TaskDetailSheet.test.tsx`
- Mock pattern: mock `convex/react` (`useQuery`, `useMutation`) with `vi.mock()`
- The existing test file has 11 tests. File attachment tests should be ADDED to this file.
- The existing `mockMutationFn` mock (line 8) is shared across all `useMutation` calls. The test for `handleAttachFiles` needs to mock `fetch` globally (`vi.stubGlobal("fetch", ...)`) to simulate the API route call.
- Follow the existing pattern: `mockUseQuery` for data, `mockMutationFn` for mutations, `cleanup()` in afterEach.

### Existing Test Mock Pattern

```typescript
// Existing pattern in TaskDetailSheet.test.tsx
const mockUseQuery = vi.fn();
const mockMutationFn = vi.fn().mockResolvedValue(undefined);
vi.mock("convex/react", () => ({
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
  useMutation: () => mockMutationFn,
}));
```

To test file attachment, you need to:
1. Mock `useQuery` to return a task with `files` array
2. Mock `fetch` globally to simulate `POST /api/tasks/[taskId]/files`
3. Render component, navigate to Files tab, click Attach File
4. Fire change event on hidden file input with a mock FileList
5. Assert: `fetch` called with correct URL, `mockMutationFn` called for `addTaskFiles` and `createActivity`

### Project Structure Notes

- All dashboard components: `dashboard/components/`
- All Convex mutations/queries: `dashboard/convex/`
- API routes: `dashboard/app/api/`
- Tests co-located with components: `dashboard/components/*.test.tsx`
- Uses Next.js App Router conventions

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.4 - lines 1172-1191]
- [Source: _bmad-output/planning-artifacts/epics.md#FR-F2 - line 85]
- [Source: _bmad-output/planning-artifacts/epics.md#FR-F23 - line 106]
- [Source: _bmad-output/planning-artifacts/epics.md#FR-F25 - line 108]
- [Source: _bmad-output/planning-artifacts/epics.md#NFR-F1 - line 140]
- [Source: _bmad-output/planning-artifacts/epics.md#NFR-F12 - line 150]
- [Source: _bmad-output/planning-artifacts/architecture.md#Task directory convention - line 86]
- [Source: _bmad-output/planning-artifacts/architecture.md#File I/O via Next.js API Routes - lines 290-294]
- [Source: dashboard/components/TaskDetailSheet.tsx - full file]
- [Source: dashboard/app/api/tasks/[taskId]/files/route.ts - full file]
- [Source: dashboard/convex/tasks.ts#addTaskFiles - lines 837-856]
- [Source: dashboard/convex/tasks.ts#removeTaskFile - lines 862-877]
- [Source: dashboard/convex/activities.ts#create - lines 4-58]
- [Source: dashboard/convex/schema.ts#tasks.files - lines 55-61]
- [Source: dashboard/convex/schema.ts#activities.eventType.file_attached - line 187]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

---

## Senior Developer Review (AI)

**Reviewer:** Claude Sonnet 4.6 (adversarial review)
**Date:** 2026-02-25
**Result:** PASS (all issues fixed)

### AC Verification

| AC | Status | Notes |
|----|--------|-------|
| AC 1 – Attach File button opens file picker | IMPLEMENTED | Hidden `<input type="file" multiple ref={attachInputRef}>` + Button that triggers `.click()` |
| AC 2 – Files uploaded to attachments/ via POST | IMPLEMENTED | `handleAttachFiles` POSTs FormData to `/api/tasks/${task._id}/files` |
| AC 3 – `addTaskFiles` mutation called with metadata | IMPLEMENTED | Called with returned `uploadedFiles` array |
| AC 4 – Files tab updates reactively | IMPLEMENTED | Convex `useQuery(api.tasks.getById)` subscription handles this automatically |
| AC 5 – Activity event `file_attached` created | IMPLEMENTED | `createActivity` called with correct `eventType` and count-aware description |
| AC 6 – 10 MB upload performance | NOT TESTABLE IN UNIT TESTS | Atomic write (tmp + rename) pattern is appropriate; no artificial delays |
| AC 7 – Error shown on upload failure | IMPLEMENTED | `catch` block sets `uploadError`; `data-testid="upload-error"` added by review |
| AC 8 – Button disabled during upload | IMPLEMENTED | `isUploading` state drives `disabled` prop and button text |
| AC 9 – Click file name opens viewer; delete via trash icon | IMPLEMENTED | `onClick={() => setViewerFile(file)}` + `handleDeleteFile` with Trash2 button |

### Issues Found

#### HIGH

**H1 — Path Traversal Vulnerability in POST route (FIXED)**
- **File:** `dashboard/app/api/tasks/[taskId]/files/route.ts`, line 53
- **Problem:** `join(attachmentsDir, file.name)` used the raw `file.name` from the multipart `File` object without sanitization. A crafted request with a filename like `../../etc/passwd` would join outside the task directory.
- **Fix Applied:** Added `const safeName = basename(file.name)` before constructing `finalPath`. If `safeName` is empty (e.g. filename was `./`), the file is silently skipped. All subsequent path construction and metadata uses `safeName`.

#### MEDIUM

**M1 — Non-null assertions on `task` after async await (FIXED)**
- **File:** `dashboard/components/TaskDetailSheet.tsx`, lines 143, 148-151, 168, 173
- **Problem:** `task!._id` used non-null assertions in `handleAttachFiles` and `handleDeleteFile`. If the task is deleted between handler invocation and the async continuation (after `await fetch`), `task` could be null or undefined, causing an uncaught runtime TypeError.
- **Fix Applied:** Added `if (!task || !isTaskLoaded) return;` guard at the top of both handlers. Changed all `task!._id` to `task._id`.

**M2 — Missing `data-testid` on error/button elements (FIXED)**
- **File:** `dashboard/components/TaskDetailSheet.tsx`
- **Problem:** `uploadError` paragraph, `deleteError` paragraph, and the "Attach File" button lacked `data-testid` attributes, making tests rely on brittle role/text queries and making the error elements untestable via `getByTestId`.
- **Fix Applied:** Added `data-testid="attach-file-button"`, `data-testid="upload-error"`, and `data-testid="delete-error"` to respective elements.

**M3 — All Task 5 unit tests were entirely missing (FIXED)**
- **File:** `dashboard/components/TaskDetailSheet.test.tsx`
- **Problem:** The story requires 6 unit tests covering AC 1-9 (file attachment button, uploading state, error display, mutation calls, empty sections, delete). Zero such tests existed. The test file only covered Stories 5.3 and earlier.
- **Fix Applied:** Added 6 new tests to the `TaskDetailSheet` describe block:
  1. `renders Attach File button in the Files tab (AC: 1)`
  2. `disables button and shows Uploading... text during upload (AC: 8)`
  3. `shows upload error message when upload fails (AC: 7)`
  4. `calls addTaskFiles and createActivity mutations on successful upload (AC: 2, 3, 5)`
  5. `renders No attachments yet. placeholder when task has only output files (AC: 9 — empty attachments section)`
  6. `calls removeTaskFile mutation when delete button is clicked (AC: 9)`

#### LOW

**L1 — Missing `ResizeObserver` stub in vitest setup (FIXED)**
- **File:** `dashboard/vitest.setup.ts`
- **Problem:** `@radix-ui/react-scroll-area` uses `ResizeObserver` which does not exist in jsdom. Tests that interact with elements INSIDE a `ScrollArea` (e.g., clicking the delete button) threw `ReferenceError: ResizeObserver is not defined`.
- **Fix Applied:** Added a no-op `ResizeObserver` class to `globalThis` in `vitest.setup.ts`.

**L2 — `FileIcon` `ext` extraction silent failure for files without extension (LOW, FIXED by linter)**
- **File:** `dashboard/components/TaskDetailSheet.tsx`, line 38 (original)
- **Problem:** `name.slice(name.lastIndexOf(".")).toLowerCase()` returns the full filename (not empty) when there is no `.` in the name, because `lastIndexOf` returns -1 and `slice(-1)` returns the last character. For e.g. `Makefile`, `ext` would be `e` - matching nothing, rendering the fallback `<File>` icon correctly, but the logic is fragile.
- **Fix Applied:** Linter auto-fixed to `const dotIdx = name.lastIndexOf("."); const ext = dotIdx > 0 ? name.slice(dotIdx).toLowerCase() : "";` — correctly returns `""` for files without extension.

### Test Results After Fixes

```
Test Files  1 passed (1)
Tests       39 passed (39)
```

All pre-existing 33 tests continue to pass. 6 new Story 5.4 tests added and passing.
