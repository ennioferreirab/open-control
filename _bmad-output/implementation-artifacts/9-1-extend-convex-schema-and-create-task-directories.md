# Story 9-1: Extend Convex Schema and Create Task Directories

**Epic:** 9 — Thread Files Context: Attach Files to Tasks
**Status:** ready-for-dev

## Story

As a **developer**,
I want the tasks table to support file metadata and the backend to create per-task directories on the filesystem,
So that files have a structured home and the dashboard knows what files exist on each task.

## Acceptance Criteria

**Given** the existing Convex `tasks` table schema
**When** the schema is extended
**Then** the `tasks` table gains a `files` field: optional array of objects with `{ name: string, type: string, size: number, subfolder: string, uploadedAt: string }`
**And** the Convex dev server starts without schema validation errors
**And** existing tasks without files continue to work (field is optional)

**Given** a new task is created in Convex (by dashboard or CLI)
**When** the Python bridge detects the new task via subscription
**Then** the bridge creates the directory `~/.nanobot/tasks/{task-id}/attachments/`
**And** the bridge creates the directory `~/.nanobot/tasks/{task-id}/output/`
**And** directory creation is atomic — if it fails, the failure is logged as an activity event with a clear error message (NFR10)
**And** the task-id used in the directory path is a filesystem-safe conversion of the Convex task ID

**Given** the task directory already exists (idempotent)
**When** directory creation is triggered again
**Then** no error occurs — the operation is safely idempotent

## Technical Notes

- Convex schema file: `dashboard/convex/schema.ts` — add `files` as optional field on the `tasks` table
- The `files` field type: `v.optional(v.array(v.object({ name: v.string(), type: v.string(), size: v.number(), subfolder: v.string(), uploadedAt: v.string() })))`
- Task directory creation: implement in `nanobot/mc/bridge.py` where new tasks are detected via Convex subscription
- Filesystem-safe task ID: Convex IDs may contain characters invalid for paths — use a safe conversion (e.g., replace `|` or other special chars, or use the ID as-is if already safe)
- Directory base: `~/.nanobot/tasks/{task-id}/` with `attachments/` and `output/` subdirs
- Use `os.makedirs(path, exist_ok=True)` for idempotent creation
- Activity event on failure: call the existing activity event mutation with type `"error"` and message describing the directory creation failure

## NFRs Covered

- NFR10: Task directory creation never fails silently — if directory creation fails, the task creation fails with a clear error
