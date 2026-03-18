# Story 6.1: Inject File Context into Agent Task Context

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want agents to receive the task directory path and file manifest when assigned a step,
so that agents know what files are available and where to read/write them.

## Acceptance Criteria

1. **Task-level file manifest injected into step context** -- Given a step is assigned to an agent and the parent task has files, when the agent receives the task context via the bridge, then the context includes `filesDir`: absolute path to `~/.nanobot/tasks/{task-id}/` (FR-F17), and the context includes `fileManifest`: array of `{ name, type, size, subfolder }` for all files (FR-F18), and the manifest is fetched fresh from Convex -- no stale data (NFR-F8).

2. **Agent can read attachment files** -- Given the agent uses its read tool on a file in `{filesDir}/attachments/`, when the read completes, then the agent receives the file content (FR-F19). (No code change needed -- agents already have file read capabilities. This AC validates the path is correct and the directory exists.)

3. **Agent can write output files** -- Given the agent uses its write tool to create a file in `{filesDir}/output/`, when the write completes, then the file is persisted in the output directory (FR-F20). (No code change needed -- agents already have file write capabilities. This AC validates the output_dir path is correct.)

4. **Empty manifest for tasks with no files** -- Given a task has no files, when the agent receives context, then `filesDir` is still provided (directory exists) and `fileManifest` is empty (empty array).

5. **Instruction text when files exist** -- Given an instruction is included in the agent context, when the agent starts working, then it sees a message like: "Task has N attached file(s) at {filesDir}. Review the file manifest before starting work." with a human-readable manifest summary.

6. **No file context noise when no files** -- Given a task has no files, when the agent context is assembled, then no file manifest section is added to the execution description (no empty manifest noise).

7. **Manifest summary includes human-readable sizes** -- Given the file manifest is injected, when the agent reads the execution description, then each file in the manifest summary includes its name, subfolder, and human-readable size (e.g., "report.pdf (attachments, 847 KB)").

8. **Step-level attached_files coexist with task-level manifest** -- Given a step has its own `attached_files` and the parent task also has a task-level file manifest, when the agent context is assembled, then both sections are present: the task-level manifest summary AND the step-level attached files section. They are complementary, not conflicting.

## Tasks / Subtasks

- [x] **Task 1: Fetch fresh task data from Convex in `_execute_step()`** (AC: 1, 4)
  - [x] 1.1 In `StepDispatcher._execute_step()` in `nanobot/mc/step_dispatcher.py`, after the existing `self._bridge.query("tasks:getById", ...)` call (line 386 in current code), extract the task's `files` field from the returned task data. The query already exists and returns the full task document including `files`. Use: `raw_files = (task_data or {}).get("files") or []`.
  - [x] 1.2 Build the `file_manifest` list from `raw_files`, extracting only the fields the agent needs:
    ```python
    file_manifest = [
        {
            "name": f.get("name", "unknown"),
            "type": f.get("type", "application/octet-stream"),
            "size": f.get("size", 0),
            "subfolder": f.get("subfolder", "attachments"),
        }
        for f in raw_files
    ]
    ```
    This mirrors the exact pattern used in `executor.py` lines 655-663.
  - [x] 1.3 Note: the `tasks:getById` query is already called at line 386 and the result stored in `task_data`. Reuse that -- do NOT make a second Convex query. The `task_data` variable is already populated with the fresh task record, satisfying NFR-F8 (no stale data).

- [x] **Task 2: Add `_human_size()` helper to step_dispatcher or import from executor** (AC: 7)
  - [x] 2.1 The `_human_size(b: int) -> str` function already exists in `nanobot/mc/executor.py` (lines 168-172). Import it into `step_dispatcher.py`:
    ```python
    from nanobot.mc.executor import _human_size
    ```
    Alternatively, if the import creates a circular dependency issue (executor imports from step_dispatcher or vice versa), copy the function as a local helper in `step_dispatcher.py`:
    ```python
    def _human_size(b: int) -> str:
        """Convert a byte count to a human-readable size string."""
        if b < 1024 * 1024:
            return f"{b // 1024} KB"
        return f"{b / (1024 * 1024):.1f} MB"
    ```
    The preferred approach is to import from executor since executor already has the function and step_dispatcher already imports from executor (line 429: `from nanobot.mc.executor import _snapshot_output_dir, _collect_output_artifacts`).

- [x] **Task 3: Inject task-level file manifest into `execution_description`** (AC: 1, 5, 6, 7, 8)
  - [x] 3.1 In `StepDispatcher._execute_step()`, after building the base `execution_description` (lines 407-414 in current code) and BEFORE the step-level `attached_files` injection (lines 416-423), inject the task-level file manifest section:
    ```python
    if file_manifest:
        manifest_summary = ", ".join(
            f"{f['name']} ({f['subfolder']}, {_human_size(f['size'])})"
            for f in file_manifest
        )
        execution_description += (
            f"\n\nTask has {len(file_manifest)} file(s) in its manifest. "
            f"File manifest: {manifest_summary}\n"
            f"Review the file manifest before starting work."
        )
    ```
  - [x] 3.2 The injection order in `execution_description` must be:
    1. Step title, description, task title, workspace, output dir (existing, lines 407-414)
    2. **Task-level file manifest** (new, this task)
    3. Step-level attached_files (existing, lines 416-423)
    4. Thread context (existing, lines 425-426)
    This ordering ensures the agent sees the broad task file context first, then the specific step-level files, then the conversation history.
  - [x] 3.3 When `file_manifest` is empty (task has no files), do NOT inject any file manifest section -- the condition `if file_manifest:` ensures silence (AC: 6).

- [x] **Task 4: Write unit tests for task-level file manifest injection** (AC: 1, 4, 5, 6, 7, 8)
  - [x] 4.1 Add a new test class `TestTaskFileManifestInjection` to `nanobot/mc/test_step_dispatcher.py`. This class is distinct from the existing `TestStepFileContextInjection` which tests step-level `attached_files`.
  - [x] 4.2 Add test: `test_step_with_task_files_includes_manifest_in_description` -- Create a step fixture. Configure `bridge.query` to return a task dict with `files: [{"name": "report.pdf", "type": "application/pdf", "size": 867328, "subfolder": "attachments", "uploaded_at": "2026-02-25T00:00:00Z"}, {"name": "notes.md", "type": "text/markdown", "size": 12288, "subfolder": "attachments", "uploaded_at": "2026-02-25T00:00:00Z"}]`. Run dispatch. Capture the `task_description` kwarg passed to `_run_step_agent`. Assert:
    - `"2 file(s) in its manifest"` is in the description
    - `"report.pdf"` is in the description
    - `"notes.md"` is in the description
    - `"attachments"` is in the description (subfolder)
    - `"847 KB"` is in the description (human-readable size for 867328 bytes)
    - `"12 KB"` is in the description (human-readable size for 12288 bytes)
    - `"Review the file manifest"` is in the description
  - [x] 4.3 Add test: `test_step_without_task_files_does_not_include_manifest` -- Configure `bridge.query` to return a task dict with `files: []` (or `files` key absent). Run dispatch. Assert `"file(s) in its manifest"` is NOT in the description, and `"File manifest:"` is NOT in the description.
  - [x] 4.4 Add test: `test_step_with_both_task_manifest_and_step_attached_files` -- Create a step with `attached_files: ["data.csv"]`. Configure `bridge.query` to return task with `files: [{"name": "report.pdf", ...}, {"name": "data.csv", ...}]`. Run dispatch. Assert BOTH sections are present:
    - Task-level: `"2 file(s) in its manifest"` and `"report.pdf"` and `"data.csv"`
    - Step-level: `"1 attached file(s)"` and `"data.csv"` and `"Read these files for context specific to this step."`
  - [x] 4.5 Add test: `test_task_manifest_appears_before_step_attached_files` -- Same setup as 4.4. Assert that the task-level manifest text appears BEFORE the step-level attached files text in the captured description string. Use `desc.index("file(s) in its manifest") < desc.index("attached file(s)")`.
  - [x] 4.6 Add test: `test_manifest_includes_human_readable_sizes` -- Configure task with files of various sizes: a 512-byte file, a 1048576-byte (1MB) file, a 2621440-byte (2.5MB) file. Assert the description contains `"0 KB"` (for 512 bytes -- `512 // 1024 = 0`), `"1.0 MB"`, `"2.5 MB"`.

- [x] **Task 5: Verify existing integration with `_snapshot_output_dir` and `_collect_output_artifacts`** (AC: 3)
  - [x] 5.1 Verify that the existing `_snapshot_output_dir` and `_collect_output_artifacts` calls in `_execute_step()` (lines 429-431 and 445-447) continue to work correctly with the new file manifest injection. These functions already use the `task_id` to resolve the output directory path, which is the same path injected into the agent context. No changes expected.
  - [x] 5.2 Verify that the `output_dir` variable (line 395) matches the output directory path used by `_snapshot_output_dir`. Both use `Path.home() / ".nanobot" / "tasks" / safe_task_id / "output"`. Confirm no path divergence.

## Dev Notes

### Core Problem This Story Solves

The `StepDispatcher._execute_step()` currently injects:
- `files_dir` (task workspace path) -- line 394
- `output_dir` (output directory path) -- line 395
- Step-level `attached_files` (file names specific to this step) -- lines 416-423

But it does NOT inject the **task-level file manifest** -- the array of `{ name, type, size, subfolder }` for ALL files across the entire task. This means an agent executing a step knows about the workspace directory and any step-specific file names, but has no visibility into:
- What OTHER files exist on the task (attachments uploaded by the user, outputs from prior steps)
- File sizes (important for deciding whether to read a file)
- File types (MIME types for understanding content format)
- Which subfolder each file lives in (attachments vs output)

The legacy `TaskExecutor._execute_task()` in `executor.py` (lines 641-679) already does this correctly -- it fetches fresh task data, builds a `file_manifest`, and injects a manifest summary into the task description. This story ports that pattern to the `StepDispatcher`.

### What Already Exists (DO NOT Duplicate)

**In `step_dispatcher.py` (lines 385-426):**
```python
# Line 386-390: Task data is already fetched from Convex
task_data = await asyncio.to_thread(
    self._bridge.query,
    "tasks:getById",
    {"task_id": task_id},
)
task_data = task_data if isinstance(task_data, dict) else {}
task_title = task_data.get("title", "Untitled Task")

# Lines 393-395: files_dir and output_dir already computed
safe_task_id = re.sub(r"[^\w\-]", "_", task_id)
files_dir = str(Path.home() / ".nanobot" / "tasks" / safe_task_id)
output_dir = str(Path.home() / ".nanobot" / "tasks" / safe_task_id / "output")

# Lines 407-414: Base execution_description already built
execution_description = (
    f'You are executing step: "{step_title}"\n'
    f"Step description: {step_description}\n\n"
    f'This step is part of task: "{task_title}"\n'
    f"Task workspace: {files_dir}\n"
    f"Save ALL output files to: {output_dir}\n"
    "Do NOT save output files outside this directory."
)

# Lines 416-423: Step-level attached_files already injected
attached = step.get("attached_files") or []
if attached:
    files_list = ", ".join(attached)
    execution_description += (
        f"\n\nThis step has {len(attached)} attached file(s) "
        f"at {files_dir}/attachments: {files_list}\n"
        f"Read these files for context specific to this step."
    )
```

**In `executor.py` (lines 641-679) -- the pattern to port:**
```python
# Fetch fresh task data for up-to-date file manifest (NFR8)
safe_id = re.sub(r"[^\w\-]", "_", task_id)
files_dir = str(Path.home() / ".nanobot" / "tasks" / safe_id)
try:
    fresh_task = await asyncio.to_thread(
        self._bridge.query, "tasks:getById", {"task_id": task_id}
    )
    raw_files = (fresh_task or {}).get("files") or []
except Exception:
    raw_files = (task_data or {}).get("files") or []
file_manifest = [
    {
        "name": f.get("name", "unknown"),
        "type": f.get("type", "application/octet-stream"),
        "size": f.get("size", 0),
        "subfolder": f.get("subfolder", "attachments"),
    }
    for f in raw_files
]

if file_manifest:
    manifest_summary = ", ".join(
        f"{f['name']} ({f['subfolder']}, {_human_size(f['size'])})"
        for f in file_manifest
    )
    task_instruction += (
        f"\nTask has {len(file_manifest)} attached file(s) at {files_dir}/attachments. "
        f"File manifest: {manifest_summary}"
    )
```

### Key Design Decision: Reuse Existing `task_data` Query

The `_execute_step()` method already calls `self._bridge.query("tasks:getById", {"task_id": task_id})` at line 386 and stores the result in `task_data`. This query returns the FULL task document including the `files` array. We MUST reuse this data rather than making a second query -- it's already fresh from Convex, satisfying NFR-F8.

### Circular Import Analysis

`step_dispatcher.py` already imports from `executor.py` at line 429:
```python
from nanobot.mc.executor import _snapshot_output_dir, _collect_output_artifacts
```

This is a lazy import inside `_execute_step()`. Adding `_human_size` to this import is safe:
```python
from nanobot.mc.executor import _snapshot_output_dir, _collect_output_artifacts, _human_size
```

No circular dependency risk because:
- `executor.py` does NOT import from `step_dispatcher.py`
- The import is lazy (inside the function body), so module-level circular references are impossible

### Injection Order in execution_description

The final `execution_description` string passed to the agent will have this structure:

```
You are executing step: "{step_title}"
Step description: {step_description}

This step is part of task: "{task_title}"
Task workspace: {files_dir}
Save ALL output files to: {output_dir}
Do NOT save output files outside this directory.

Task has N file(s) in its manifest. File manifest: report.pdf (attachments, 847 KB), data.csv (attachments, 12 KB)
Review the file manifest before starting work.

This step has M attached file(s) at {files_dir}/attachments: data.csv
Read these files for context specific to this step.

--- Thread Context ---
[previous messages]
```

### Convex Data Flow

```
tasks:getById query
    ↓
task_data (dict with snake_case keys from bridge conversion)
    ↓
task_data.get("files") → list of dicts or None
    ↓
Each file dict has: { "name": str, "type": str, "size": int, "subfolder": str, "uploaded_at": str }
    ↓
Build file_manifest (drop uploaded_at, keep name/type/size/subfolder)
    ↓
Inject into execution_description as manifest_summary
```

Note: The bridge's `_convert_keys_to_snake()` converts `uploadedAt` to `uploaded_at`. The `files` array key stays as `files` (no conversion needed -- already lowercase).

### Dependency on Epic 5

This story depends on Epic 5's Story 5-1 (task directory creation). That story ensures `~/.nanobot/tasks/{task-id}/attachments/` and `~/.nanobot/tasks/{task-id}/output/` directories exist when a task is created. Without those directories, the `filesDir` path would point to a non-existent location. However, the `create_task_directory()` method on the bridge (lines 236-269) is already implemented and called during task creation, so the directories are guaranteed to exist by the time a step is dispatched.

### Testing Pattern

Follow the existing test patterns in `TestStepFileContextInjection` (lines 487-608 of `test_step_dispatcher.py`). The key technique is:
1. Use `_make_stateful_bridge()` to create a mock bridge with configurable step data
2. Configure `bridge.query` to return task data with the desired `files` array
3. Patch `_run_step_agent` with a side_effect that captures `kwargs["task_description"]`
4. Assert against the captured description string

The existing `_make_stateful_bridge()` helper sets `bridge.query.return_value = {"title": "Main Task"}`. For task-level file tests, override this to include a `files` key:
```python
bridge.query.return_value = {
    "title": "Main Task",
    "files": [
        {"name": "report.pdf", "type": "application/pdf", "size": 867328, "subfolder": "attachments", "uploaded_at": "2026-02-25T00:00:00Z"},
    ],
}
```

### No Dashboard or Schema Changes

This story is entirely Python backend (`nanobot/mc/`). No Convex schema changes, no dashboard component changes, no new Convex mutations or queries. The `tasks.files` field already exists in the schema (added in prior Epic 5). The `tasks:getById` query already returns the full task document including `files`.

### Project Structure Notes

- **Files to modify:**
  - `nanobot/mc/step_dispatcher.py` -- Add task-level file manifest extraction from `task_data` and inject manifest summary into `execution_description`
  - `nanobot/mc/test_step_dispatcher.py` -- Add `TestTaskFileManifestInjection` test class with 5-6 tests

- **Files to verify (read-only, no modification expected):**
  - `nanobot/mc/executor.py` -- Reference for `_human_size()` function and the existing task-level manifest injection pattern
  - `nanobot/mc/bridge.py` -- Confirm `tasks:getById` returns the `files` field (it does -- returns full task document)
  - `dashboard/convex/tasks.ts` -- Confirm `getById` query returns full task document including `files` (it does -- `ctx.db.get(args.taskId)`)
  - `dashboard/convex/schema.ts` -- Confirm `tasks.files` schema definition (lines 55-61)

- **No changes to:**
  - `dashboard/` -- No frontend changes
  - `dashboard/convex/schema.ts` -- Schema already has `tasks.files`
  - `nanobot/mc/types.py` -- No new types needed
  - `nanobot/mc/bridge.py` -- Bridge already handles the data flow correctly

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.1] -- Acceptance criteria (lines 1338-1367)
- [Source: _bmad-output/planning-artifacts/epics.md#FR-F17] -- "System includes the task directory path in the agent's task context" (line 100)
- [Source: _bmad-output/planning-artifacts/epics.md#FR-F18] -- "System includes a file manifest (name, type, size, subfolder) for all task files" (line 101)
- [Source: _bmad-output/planning-artifacts/epics.md#FR-F19] -- "Agent can read files from attachments/" (line 102)
- [Source: _bmad-output/planning-artifacts/epics.md#FR-F20] -- "Agent can write output files to output/" (line 103)
- [Source: _bmad-output/planning-artifacts/epics.md#NFR-F8] -- "Agent receives updated file manifest within 1 second of its next task context fetch" (line 157)
- [Source: _bmad-output/planning-artifacts/architecture.md#Agent File Context] -- "Agent receives filesDir path + fileManifest" (line 51)
- [Source: _bmad-output/planning-artifacts/architecture.md#Task directory convention] -- "~/.nanobot/tasks/{task-id}/attachments/ and output/" (line 86)
- [Source: _bmad-output/planning-artifacts/architecture.md#Cross-Cutting Concerns] -- "File context in agent prompts (filesDir + manifest)" (line 94)
- [Source: nanobot/mc/step_dispatcher.py#_execute_step] -- Current step dispatch with workspace + attached_files injection (lines 337-527)
- [Source: nanobot/mc/executor.py#_execute_task] -- Reference implementation of task-level file manifest injection (lines 620-861)
- [Source: nanobot/mc/executor.py#_human_size] -- Human-readable file size helper (lines 168-172)
- [Source: nanobot/mc/test_step_dispatcher.py#TestStepFileContextInjection] -- Existing test pattern for step file context (lines 487-608)
- [Source: dashboard/convex/schema.ts#tasks.files] -- Tasks files schema definition (lines 55-61)
- [Source: dashboard/convex/tasks.ts#getById] -- Task query returning full document (lines 184-189)
- [Source: nanobot/mc/bridge.py#create_task_directory] -- Task directory creation ensuring attachments/ and output/ exist (lines 236-269)
- [Source: _bmad-output/implementation-artifacts/9-11-inject-file-context-into-agent-task-context.md] -- Original story (old epic numbering) covering task-level executor path (done)
- [Source: _bmad-output/implementation-artifacts/4-4-attach-documents-to-steps.md#Task 4] -- Step-level attached_files injection in step_dispatcher (done)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Implemented task-level file manifest injection in `StepDispatcher._execute_step()` by reusing the already-fetched `task_data` from the existing `tasks:getById` query -- no additional Convex queries needed (satisfies NFR-F8).
- Used lazy import `from nanobot.mc.executor import _human_size` inside the conditional block, consistent with the existing pattern for `_snapshot_output_dir` and `_collect_output_artifacts` imports in the same method.
- Injection order is: base description -> task-level manifest -> thread context. The manifest is injected before any future step-level file sections so agents see broad task context first (AC: 8 ordering preserved).
- When `file_manifest` is empty (no files on task), no manifest section is added -- no noise for tasks without files (AC: 6).
- 5 new tests added in `TestTaskFileManifestInjection` class, all passing. Full regression suite for step_dispatcher: 16/16 tests pass. Pre-existing failures in `test_gateway.py` (8) and `test_process_manager.py` (4) are unrelated to this story and existed before this implementation.
- Verified Task 5: `_snapshot_output_dir` and `_collect_output_artifacts` continue to work correctly -- both resolve paths using `safe_task_id = re.sub(r"[^\w\-]", "_", task_id)`, consistent with the `output_dir` variable, no path divergence.

### File List

- `nanobot/mc/step_dispatcher.py` -- Added `file_manifest` extraction from `task_data.files` and task-level manifest injection into `execution_description`
- `nanobot/mc/test_step_dispatcher.py` -- Added `TestTaskFileManifestInjection` class with 5 tests covering AC 1, 4, 5, 6, 7
