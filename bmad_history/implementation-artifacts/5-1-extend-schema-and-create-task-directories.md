# Story 5.1: Extend Schema and Create Task Directories

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want the tasks table to support file metadata and the backend to create per-task directories,
so that files have a structured home and the dashboard knows what files exist on each task.

## Acceptance Criteria

1. **`files` field exists on the tasks table** -- Given the existing Convex `tasks` table schema, when the schema is inspected, then the `tasks` table has a `files` field: `v.optional(v.array(v.object({ name: v.string(), type: v.string(), size: v.number(), subfolder: v.string(), uploadedAt: v.string() })))` (FR-F22). Existing tasks without files continue to work (field is optional). The Convex dev server starts without schema validation errors.

2. **Per-task directories are created on new task** -- Given a new task is created in Convex, when the Python bridge detects the new task via subscription, then the bridge creates `~/.nanobot/tasks/{safe-task-id}/attachments/` and `~/.nanobot/tasks/{safe-task-id}/output/` (FR-F5). Directory creation failure is logged as an activity event with a clear error (NFR-F10). The task-id used in the directory path is a filesystem-safe conversion of the Convex task ID.

3. **Idempotent directory creation** -- Given the task directory already exists, when directory creation is triggered again, then no error occurs.

4. **Bridge `create_task_directory` has unit tests** -- Given the `create_task_directory` method in `bridge.py`, when the test suite runs, then at least 4 tests cover: happy path (directories created), idempotent re-creation, OSError handling with activity event logging, and filesystem-safe ID conversion.

5. **Convex `tasks.ts` supports file manifest mutations** -- Given a task record in Convex, when file metadata needs to be updated, then mutations exist to: append uploaded files (`addTaskFiles`), replace output files (`updateTaskOutputFiles`), and remove a single file entry (`removeTaskFile` accepting `{ taskId, subfolder, filename }`).

## Tasks / Subtasks

- [x] **Task 1: Verify Convex schema `files` field** (AC: 1)
  - [x] 1.1 Open `dashboard/convex/schema.ts` and confirm the `tasks` table has the `files` field at line 55 with the exact type: `v.optional(v.array(v.object({ name: v.string(), type: v.string(), size: v.number(), subfolder: v.string(), uploadedAt: v.string() })))`. **This field already exists** -- verify it matches the FR-F22 spec exactly. No code change expected.
  - [x] 1.2 Start the Convex dev server (`cd dashboard && npx convex dev`) and confirm no schema validation errors. Verify existing tasks without `files` field are still queryable.
  - [x] 1.3 Open `dashboard/convex/tasks.ts` and confirm the `create` mutation at line ~100 includes the `files` field in its argument validator (it already does at line 102: `files: v.optional(v.array(v.object({...})))`). Verify it matches the schema definition.

- [x] **Task 2: Verify `tasks.ts` file manifest mutations** (AC: 5)
  - [x] 2.1 Open `dashboard/convex/tasks.ts` and confirm the `updateTaskOutputFiles` mutation exists (line ~813). It should accept `{ taskId: v.id("tasks"), outputFiles: v.array(v.object({ name, type, size, subfolder, uploadedAt })) }` and replace only the output section of the files array while preserving attachment entries.
  - [x] 2.2 Confirm the `addTaskFiles` mutation exists (line ~889). It accepts `{ taskId: v.id("tasks"), files: v.array(v.object({ name, type, size, subfolder, uploadedAt })) }` and appends the provided files to the existing files array.
  - [x] 2.3 Confirm the `removeTaskFile` mutation exists (line ~914). It accepts `{ taskId, subfolder, filename }` and filters out the matching file entry from the files array.
  - [x] 2.4 If any of these mutations are missing or have incorrect signatures, add or fix them. All three mutations are needed by downstream stories (5.2, 5.4, 6.2).

- [x] **Task 3: Verify `bridge.py` `create_task_directory` method** (AC: 2, 3)
  - [x] 3.1 Open `nanobot/mc/bridge.py` and confirm `create_task_directory` exists at line ~236. Verify it:
    - Converts the Convex task ID to a filesystem-safe string using `re.sub(r"[^\w\-]", "_", task_id)`.
    - Creates `~/.nanobot/tasks/{safe_id}/attachments/` and `~/.nanobot/tasks/{safe_id}/output/` using `os.makedirs(path, exist_ok=True)`.
    - Catches `OSError` and logs it as a `system_error` activity event via `self.create_activity`.
    - The method does not raise on failure (graceful degradation).
  - [x] 3.2 Open `nanobot/mc/orchestrator.py` and confirm `create_task_directory` is called at line ~86 via `await asyncio.to_thread(self._bridge.create_task_directory, task_id)` during `_process_planning_task`. This is the trigger point -- every new task that enters the planning state gets its directories created.
  - [x] 3.3 Verify idempotency: `exist_ok=True` in `os.makedirs` ensures no error on re-creation.

- [x] **Task 4: Write unit tests for `create_task_directory`** (AC: 4)
  - [x] 4.1 Open `nanobot/mc/test_bridge.py` and check if tests for `create_task_directory` already exist. If not, add a new test class `TestCreateTaskDirectory`.
  - [x] 4.2 Add test: `test_creates_attachments_and_output_dirs` -- Mock `os.makedirs`, call `create_task_directory("jd7abc123xyz")`, assert `os.makedirs` was called twice with the correct paths: `~/.nanobot/tasks/jd7abc123xyz/attachments/` and `~/.nanobot/tasks/jd7abc123xyz/output/`, both with `exist_ok=True`.
  - [x] 4.3 Add test: `test_filesystem_safe_id_conversion` -- Call `create_task_directory("abc|def/ghi")`, assert the sanitized path uses `abc_def_ghi` (special characters replaced with underscore).
  - [x] 4.4 Add test: `test_idempotent_no_error_on_existing_dir` -- Mock `os.makedirs` to succeed (no error), call twice, assert no exception.
  - [x] 4.5 Add test: `test_oserror_logs_activity_event` -- Mock `os.makedirs` to raise `OSError("Permission denied")`, assert `create_activity` was called with `"system_error"` event type and the error message includes `"Permission denied"`. Assert the method does NOT raise.
  - [x] 4.6 Add test: `test_oserror_activity_failure_does_not_raise` -- Mock `os.makedirs` to raise `OSError`, and mock `create_activity` to also raise `Exception`. Assert `create_task_directory` does NOT raise (double-fault tolerance).
  - [x] 4.7 Run `uv run pytest nanobot/mc/test_bridge.py -v` and confirm all new tests pass alongside existing tests.

- [x] **Task 5: Run full test suite and verify no regressions** (AC: 1, 2, 3, 4, 5)
  - [x] 5.1 Run `uv run pytest nanobot/mc/ -v` and confirm all Python tests pass.
  - [x] 5.2 Run `cd dashboard && npx vitest run` and confirm all TypeScript tests pass.
  - [x] 5.3 Report total test count and pass rate.

## Dev Notes

### Brownfield Context -- Implementation Already Exists

This story is a **verification + test coverage story**. The core implementation was completed as part of the old epic 9 story (9-1). The following already exists in the codebase:

1. **Schema (`dashboard/convex/schema.ts` lines 55-61):** The `files` field is already on the `tasks` table with the exact type specified in FR-F22.
2. **Bridge (`nanobot/mc/bridge.py` lines 236-269):** `create_task_directory` is fully implemented with filesystem-safe ID conversion, `os.makedirs(exist_ok=True)`, and error logging via activity events.
3. **Orchestrator (`nanobot/mc/orchestrator.py` line 86):** `create_task_directory` is called during `_process_planning_task` for every new task.
4. **Convex mutations (`dashboard/convex/tasks.ts`):** `updateTaskOutputFiles`, `addTaskFiles`, and `removeTaskFile` mutations already exist.
5. **Existing test coverage:** `test_orchestrator.py` verifies `create_task_directory` is called during planning. However, `test_bridge.py` does NOT have dedicated unit tests for `create_task_directory` itself -- **this is the primary gap**.

The main deliverable for this story is **Task 4: unit tests for `create_task_directory`** in `nanobot/mc/test_bridge.py`.

### Filesystem-Safe ID Conversion

The bridge uses `re.sub(r"[^\w\-]", "_", task_id)` to sanitize Convex task IDs. Convex IDs are typically alphanumeric strings like `jd7abc123xyz` (no special characters), so the regex is a defensive measure. The sanitized ID becomes the directory name under `~/.nanobot/tasks/`.

### Directory Structure

```
~/.nanobot/tasks/{safe-task-id}/
  attachments/   # User-uploaded files (Stories 5.2, 5.4)
  output/        # Agent-produced files (Story 6.2)
```

### Error Handling Pattern

`create_task_directory` follows a **graceful degradation** pattern:
1. If `os.makedirs` raises `OSError`, log the error and attempt to create a `system_error` activity event.
2. If the activity event creation also fails, log that secondary failure but do NOT raise.
3. The method never raises -- task processing continues even if directory creation fails.

This pattern matches NFR-F10: "Task directory creation never fails silently -- if directory creation fails, the failure is logged."

### Testing Pattern

Follow the existing test structure in `nanobot/mc/test_bridge.py`:
- Use `@patch("nanobot.mc.bridge.ConvexClient")` to mock the Convex client.
- Use `@patch("nanobot.mc.bridge.os.makedirs")` to mock filesystem operations.
- Use `@patch.object(ConvexBridge, "create_activity")` or mock the client's mutation to verify activity event logging on error.
- Test class name: `TestCreateTaskDirectory`.
- Place the new test class after the existing `TestConvenienceMethods` class.

### Project Structure Notes

- **Files to modify:**
  - `nanobot/mc/test_bridge.py` -- add `TestCreateTaskDirectory` test class with 5-6 tests
- **Files to verify (read-only, no modification expected):**
  - `dashboard/convex/schema.ts` -- verify `files` field on `tasks` table (lines 55-61)
  - `dashboard/convex/tasks.ts` -- verify `updateTaskOutputFiles`, `addTaskFiles`, `removeTaskFile` mutations
  - `nanobot/mc/bridge.py` -- verify `create_task_directory` method (lines 236-269)
  - `nanobot/mc/orchestrator.py` -- verify `create_task_directory` call (line 86)
- **No changes to:**
  - Any Convex schema (already correct)
  - Any bridge logic (already implemented)
  - Any orchestrator logic (already wired)

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.1] -- Acceptance criteria (lines 1092-1115)
- [Source: _bmad-output/planning-artifacts/architecture.md#Task/Step Hierarchy] -- Task `files` field definition (line 190)
- [Source: _bmad-output/planning-artifacts/architecture.md#Technical Constraints] -- Task directory convention `~/.nanobot/tasks/{task-id}/attachments/` and `output/` (line 86)
- [Source: _bmad-output/planning-artifacts/architecture.md#File I/O Boundary] -- File metadata in Convex, filesystem accessed by Python backend and Next.js API routes (lines 843-845)
- [Source: _bmad-output/planning-artifacts/prd-thread-files-context.md#FR5] -- System creates a dedicated task directory with attachments/ and output/ subdirectories (line 219)
- [Source: _bmad-output/planning-artifacts/prd-thread-files-context.md#NFR10] -- Task directory creation never fails silently (from architecture)
- [Source: dashboard/convex/schema.ts#tasks] -- `files` field on tasks table (lines 55-61)
- [Source: nanobot/mc/bridge.py#create_task_directory] -- Full implementation with safe ID, makedirs, error logging (lines 236-269)
- [Source: nanobot/mc/orchestrator.py#_process_planning_task] -- create_task_directory call during task routing (line 86)
- [Source: nanobot/mc/test_bridge.py] -- Existing test structure and patterns for bridge unit tests
- [Source: nanobot/mc/test_orchestrator.py] -- Existing test verifying create_task_directory is called (line 120)
- [Source: _bmad-output/implementation-artifacts/9-1-extend-convex-schema-and-create-task-directories.md] -- Prior story covering same scope (old epic 9)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None -- all implementations were pre-existing; only test authorship required.

### Completion Notes List

- **Task 1 (Verify schema):** Confirmed `dashboard/convex/schema.ts` lines 55-61 have the exact `files` field matching FR-F22 spec. Field is `v.optional(...)` so existing tasks without files continue to work.
- **Task 2 (Verify mutations):** Confirmed `updateTaskOutputFiles` at line 865 of `tasks.ts`. The append and remove mutations exist as `addTaskFiles` (line 889) and `removeTaskFile` (line 914) -- functionally identical to the story's `appendFiles`/`removeFile` labels. All downstream stories (5-3, etc.) reference them by the actual names (`addTaskFiles`, `removeTaskFile`).
- **Task 3 (Verify bridge):** Confirmed `create_task_directory` at lines 236-269 of `bridge.py`. Uses `re.sub(r"[^\w\-]", "_", task_id)` for safe IDs, `os.makedirs(path, exist_ok=True)` for idempotency, `OSError` caught and logged as `system_error` activity with double-fault tolerance. Confirmed orchestrator calls it at line 86 via `asyncio.to_thread`.
- **Task 4 (Write tests):** Added `TestCreateTaskDirectory` class with 6 tests to `nanobot/mc/test_bridge.py`. Added `from pathlib import Path` import. Tests cover: happy path (dirs created), filesystem-safe ID conversion, idempotency (call twice, no error), OSError logs activity event, double-fault tolerance (makedirs + create_activity both fail), and alphanumeric/hyphen ID preservation. All 6 pass.
- **Task 5 (Full test suite):** `uv run pytest nanobot/mc/test_bridge.py` -- 97 passed (91 pre-existing + 6 new). `npx vitest run` -- 418 passed, 32 test files. Pre-existing failures in `test_gateway.py` and `test_process_manager.py` (12 tests) are unrelated to this story and were failing before this work.

### File List

- `nanobot/mc/test_bridge.py` -- added `from pathlib import Path` import and `TestCreateTaskDirectory` class with 6 unit tests

## Change Log

- 2026-02-25: Story 5.1 completed -- added `TestCreateTaskDirectory` unit test class (6 tests) to `nanobot/mc/test_bridge.py`, verified all pre-existing implementations match spec.
- 2026-02-25: review: fix findings for story 5-1 and mark done

## Senior Developer Review (AI)

**Reviewer:** Ennio (claude-opus-4-6) on 2026-02-25

### Findings (7 total: 1 HIGH, 4 MEDIUM, 2 LOW)

**HIGH:**
1. **[FIXED] `test_oserror_activity_failure_does_not_raise` missing `time.sleep` mock** -- The test exercised the retry path (4 retries x 2 subdirectories = 14 seconds of real sleeping). Added `@patch("nanobot.mc.bridge.time.sleep")` decorator. Test went from 14s to <5ms.

**MEDIUM:**
2. **[FIXED] `test_oserror_logs_activity_event` weak assertion `>= 1`** -- When `makedirs` raises `OSError` for both `attachments/` and `output/`, exactly 2 activity calls are expected. Changed assertion to `== 2` and now validates both calls.
3. **[FIXED] `test_oserror_logs_activity_event` missing `taskId` assertion** -- The `create_activity` call passes `task_id=task_id` but the test only checked `eventType` and `description`. Added assertion that `taskId` is present and equals `"jd7abc123xyz"`.
4. **[FIXED] Story AC 5 references wrong mutation names** -- Story said `appendFiles` and `removeFile` but actual Convex mutations are `addTaskFiles` and `removeTaskFile`. Updated AC 5, Tasks 2.2/2.3, and Dev Notes to use correct names.
5. **[FIXED] Story AC 5 wrong parameter name for `removeTaskFile`** -- Story said `{ taskId, name, subfolder }` but actual mutation accepts `{ taskId, subfolder, filename }`. Updated Task 2.3.

**LOW (accepted, not fixed):**
6. `test_oserror_activity_failure_does_not_raise` does not assert mutation call count -- With retry exhaustion for 2 subdirectories, exactly 10 mutation calls should occur. Not blocking since the primary purpose (no raise) is validated.
7. No test for empty string task ID -- An empty task ID creates a degenerate directory path. Convex IDs are never empty in practice, so this is a defensive edge case not worth a test.
