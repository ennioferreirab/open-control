# Story 4.4: Attach Documents to Steps

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to attach documents to specific steps in the plan,
so that individual agents receive targeted context for their work.

## Acceptance Criteria

1. **Attach button on plan step cards** -- Given a step card in the PlanEditor (within the PreKickoffModal), when the user clicks an "Attach" button on that step card, then a native file picker opens allowing selection of one or more files (FR15).

2. **Step card shows attached file names** -- Given the user selects files for a specific step, when the files are attached, then the step card shows the attached file names below the step description, and the step's `attachedFiles` array in the local execution plan state is updated with the file metadata.

3. **File upload to task attachments directory** -- Given the user selects files via the file picker for a step, when the files are submitted, then each file is uploaded to `~/.nanobot/tasks/{taskId}/attachments/` via the existing `POST /api/tasks/[taskId]/files` route, the task-level `files` array in Convex is updated with the metadata, and the step's `attachedFiles` array in the local plan state stores the file names referencing those uploads.

4. **Each step shows only its own files** -- Given the user attaches files to multiple steps, when reviewing the plan, then each step shows only its own attached file names, not files attached to other steps.

5. **Attached files persist across plan edits** -- Given the user attaches files to steps and then performs other plan edits (reorder, reassign agents, change dependencies), when reviewing the plan, then all step-level file attachments are preserved.

6. **Remove file from step** -- Given a step has attached files displayed on its card, when the user clicks a remove/X button on an attached file, then the file is removed from that step's `attachedFiles` array (the file remains on disk and in the task-level `files` manifest since other steps might reference it).

7. **Attached files included in materialized step context** -- Given the plan is kicked off with step-level file attachments, when the step records are materialized and later dispatched, then each step's file attachments are included in the agent's context (added to the `execution_description` in the step dispatcher) so the agent knows which specific files to read for its step.

8. **Empty state** -- Given a step has no attached files, when the step card renders in the PlanEditor, then no file attachment section is shown (only the Attach button in the step card actions area).

## Tasks / Subtasks

- [x] **Task 1: Add `attachedFiles` to the execution plan data model** (AC: 2, 4, 5)
  - [x] 1.1 Add `attachedFiles` field to the `ExecutionPlanStep` dataclass in `nanobot/mc/types.py`: `attached_files: list[str] = field(default_factory=list)`. This is a list of file names (strings) attached to this specific step. Include it in `to_dict()` serialization as `"attachedFiles"` and in `from_dict()` deserialization (handling both `attached_files` and `attachedFiles` keys).
  - [x] 1.2 Add `attachedFiles` to the `ExecutionPlanStep` interface in `dashboard/components/ExecutionPlanTab.tsx`: `attachedFiles?: string[]`. This makes the field available for rendering in the plan visualization.
  - [x] 1.3 Add `attachedFiles` to the `steps` table schema in `dashboard/convex/schema.ts`: `attachedFiles: v.optional(v.array(v.string()))`. This stores the file names on the materialized step record for dispatch-time access.
  - [x] 1.4 Update the `steps:create` mutation args in `dashboard/convex/steps.ts` to accept `attachedFiles: v.optional(v.array(v.string()))` and persist it on insert.
  - [x] 1.5 Update the `steps:batchCreate` mutation in `dashboard/convex/steps.ts`: add `attachedFiles: v.optional(v.array(v.string()))` to the step input schema within the `steps` array argument, and persist it during Phase 1 insert.
  - [x] 1.6 Update the `PlanMaterializer._build_steps_payload()` in `nanobot/mc/plan_materializer.py` to include `attached_files` in each step's payload dict. Read it from `step.attached_files` on the `ExecutionPlanStep` object and include it as `"attached_files": step.attached_files or []` (only if non-empty, to keep payloads clean).

- [x] **Task 2: Build step-level file attachment UI in the PlanEditor** (AC: 1, 2, 4, 6, 8)
  - [x] 2.1 The PlanEditor component does not yet exist (it will be created in Story 4.1 as part of the PreKickoffModal). This task defines the file attachment interface that the PlanEditor step cards must support. If the PlanEditor already exists when this story is implemented, add the attachment UI directly. If not, create a reusable `StepFileAttachment` component that the PlanEditor will integrate.
  - [x] 2.2 Create `dashboard/components/StepFileAttachment.tsx` with the following interface:
    ```tsx
    interface StepFileAttachmentProps {
      stepTempId: string;
      attachedFiles: string[];   // File names currently attached to this step
      taskId: string;            // Task ID for upload route
      onFilesAttached: (stepTempId: string, fileNames: string[]) => void;
      onFileRemoved: (stepTempId: string, fileName: string) => void;
    }
    ```
  - [x] 2.3 Render an "Attach" button using the `Paperclip` icon from `lucide-react` and a hidden `<input type="file" multiple>`. When the button is clicked, trigger the file input's `click()`. Style the button as `Button variant="ghost" size="sm"` with `Paperclip` icon + "Attach" text, matching the existing attach button pattern in `TaskDetailSheet.tsx`.
  - [x] 2.4 On file selection (`onChange`), upload each file to `POST /api/tasks/{taskId}/files` using `FormData` (same pattern as `handleAttachFiles` in `TaskDetailSheet.tsx`). After successful upload, call `onFilesAttached(stepTempId, newFileNames)` to update the parent's plan state.
  - [x] 2.5 Display attached files as a compact list below the step description. Each file shows: `FileIcon` (reuse the icon mapping pattern from `TaskDetailSheet.tsx` -- `FileText` for PDFs, `Image` for images, `FileCode` for code files, `File` as fallback), file name as truncated text, and a small `X` button (`lucide-react X` icon, `h-3 w-3`) to remove.
  - [x] 2.6 On remove click, call `onFileRemoved(stepTempId, fileName)`. This removes the file name from the step's `attachedFiles` but does NOT delete the file from disk or the task-level `files` array (other steps may reference the same file).
  - [x] 2.7 Show a loading spinner (`Loader2` with `animate-spin`) on the Attach button during upload. Show error text `"Upload failed"` in `text-xs text-red-500` if the upload fails.
  - [x] 2.8 When `attachedFiles` is empty, render only the Attach button. When non-empty, render the file list + Attach button.

- [x] **Task 3: Integrate step file attachments into the execution plan local state** (AC: 2, 3, 4, 5)
  - [x] 3.1 The PreKickoffModal (Story 4.1) manages a local copy of the execution plan in React state (`useState` or `useReducer`). When this story is implemented, add handler functions to update the `attachedFiles` array on a specific step in the plan state:
    - `handleStepFilesAttached(stepTempId: string, newFileNames: string[])`: appends new file names to the step's `attachedFiles` array (deduplicating by name).
    - `handleStepFileRemoved(stepTempId: string, fileName: string)`: filters the file name out of the step's `attachedFiles` array.
  - [x] 3.2 Pass these handlers as props to each step card's `StepFileAttachment` component.
  - [x] 3.3 When the user clicks "Kick-off", the current plan state (including all `attachedFiles` arrays) is saved to the task's `executionPlan` field via `tasks:updateExecutionPlan` mutation before materialization begins. The `attachedFiles` persist because `executionPlan` is stored as `v.any()`.

- [x] **Task 4: Inject step-level file context into agent dispatch** (AC: 7)
  - [x] 4.1 Update `StepDispatcher._execute_step()` in `nanobot/mc/step_dispatcher.py` to read the step's `attached_files` field from the step dict (fetched via `self._bridge.get_steps_by_task`). The bridge returns snake_case keys, so look for `step.get("attached_files")` which will be a list of file name strings (or `None`).
  - [x] 4.2 If the step has attached files, append a file context section to the `execution_description` string:
    ```python
    attached = step.get("attached_files") or []
    if attached:
        files_list = ", ".join(attached)
        execution_description += (
            f"\n\nThis step has {len(attached)} attached file(s) "
            f"at {files_dir}/attachments: {files_list}\n"
            f"Read these files for context specific to this step."
        )
    ```
  - [x] 4.3 The `files_dir` variable already exists in `_execute_step()` (line 394 in current code). Reuse it for the attachment path. The files are already physically present in `~/.nanobot/tasks/{taskId}/attachments/` because they were uploaded via the file API in Task 2.

- [x] **Task 5: Update bridge to include `attachedFiles` in step data** (AC: 7)
  - [x] 5.1 Verify that the bridge's `_to_snake_case()` converter correctly transforms `"attachedFiles"` to `"attached_files"`. The existing `_to_snake_case()` function in `nanobot/mc/bridge.py` handles this pattern (camelCase to snake_case). Verify by checking the conversion: `_to_snake_case("attachedFiles")` should return `"attached_files"`.
  - [x] 5.2 No explicit bridge changes should be needed -- the bridge's generic key conversion handles this. But verify by tracing the data flow: `steps:getByTask` query returns step docs with `attachedFiles` field -> bridge converts keys to snake_case -> `step.get("attached_files")` works in the dispatcher.

- [x] **Task 6: Write tests** (AC: 1, 2, 4, 6, 7)
  - [x] 6.1 Create `dashboard/components/StepFileAttachment.test.tsx` with the following tests:
    - Renders Attach button when no files are attached
    - Renders file list when files are attached
    - Shows file icon appropriate to file type (PDF, image, code, other)
    - Calls `onFileRemoved` when X button is clicked on an attached file
    - Does not show file list when `attachedFiles` is empty
  - [x] 6.2 Add tests to `dashboard/convex/steps.test.ts` (extend existing file):
    - `batchCreate` persists `attachedFiles` when provided
    - `batchCreate` creates steps without `attachedFiles` when not provided (backward compatibility)
  - [x] 6.3 Update `nanobot/mc/test_step_dispatcher.py` with a test:
    - Step with `attached_files: ["report.pdf", "data.csv"]` produces an `execution_description` that includes the file context section mentioning both files
    - Step without `attached_files` does NOT include the file context section
  - [x] 6.4 Add a test to the `ExecutionPlan` / `ExecutionPlanStep` dataclass tests (in `nanobot/mc` test files):
    - `ExecutionPlanStep` round-trip: `to_dict()` includes `attachedFiles`, `from_dict()` parses it back
    - `from_dict()` handles missing `attachedFiles` gracefully (defaults to empty list)

## Dev Notes

### Architecture: File Storage Strategy

This story uses the **existing file storage pattern** already established in Epics 8-9 (Thread Files). Files are stored on the local filesystem at `~/.nanobot/tasks/{taskId}/attachments/` and metadata is tracked in the Convex `tasks.files` array. Step-level attachment is a **logical layer on top** -- the step's `attachedFiles` array contains file names that reference files already present in the task's attachments directory.

This means:
- **One upload, multiple steps**: A file uploaded for Step 2 can also be referenced by Step 5 without re-uploading. The `attachedFiles` array is just a list of names.
- **No new storage location**: All files go to the same `attachments/` subdirectory. The step merely declares which files are relevant to its work.
- **No new API route**: The existing `POST /api/tasks/[taskId]/files` route handles uploads. No step-specific route is needed.

### Data Model: `attachedFiles` on Both Plan and Step Record

The `attachedFiles` field exists at two levels:

1. **On the execution plan step** (pre-kickoff, `task.executionPlan.steps[].attachedFiles`): Used by the PlanEditor UI. This is the editable version. Stored as part of the `v.any()` executionPlan JSON blob on the task record.

2. **On the materialized step record** (post-kickoff, `steps.attachedFiles`): Used by the step dispatcher at runtime. This is the frozen version written during plan materialization. Stored as `v.optional(v.array(v.string()))` on the steps table.

The `PlanMaterializer._build_steps_payload()` copies `attached_files` from the plan step to the materialized step during kick-off.

### Existing File Upload Pattern (Reference)

The `TaskDetailSheet.tsx` component (lines 110-141) demonstrates the upload pattern:

```tsx
const handleAttachFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
  const files = Array.from(e.target.files ?? []);
  if (files.length === 0) return;
  e.target.value = "";
  setIsUploading(true);
  try {
    const formData = new FormData();
    for (const file of files) formData.append("files", file, file.name);
    const res = await fetch(`/api/tasks/${task!._id}/files`, {
      method: "POST", body: formData,
    });
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    const { files: uploadedFiles } = await res.json();
    await addTaskFiles({ taskId: task!._id, files: uploadedFiles });
  } catch { setUploadError("Upload failed."); }
  finally { setIsUploading(false); }
};
```

The `StepFileAttachment` component should follow this same pattern for uploads. The key difference: after uploading, it updates both the task-level `files` array (via `addTaskFiles` mutation) AND the step's `attachedFiles` in the local plan state (via the callback prop).

### Step Dispatcher Context Injection (Reference)

The `StepDispatcher._execute_step()` in `nanobot/mc/step_dispatcher.py` (lines 407-416) already builds the step's execution description:

```python
execution_description = (
    f'You are executing step: "{step_title}"\n'
    f"Step description: {step_description}\n\n"
    f'This step is part of task: "{task_title}"\n'
    f"Task workspace: {files_dir}\n"
    f"Save ALL output files to: {output_dir}\n"
    "Do NOT save output files outside this directory."
)
if thread_context:
    execution_description += f"\n{thread_context}"
```

The step-level file attachment section should be inserted between the workspace info and the thread context, providing the agent with specific file references before the broader thread context.

### Dependency on Story 4.1 (PreKickoffModal)

Story 4.1 creates the PreKickoffModal shell and PlanEditor component. Story 4.4 adds file attachment capabilities to step cards within the PlanEditor. If Story 4.1 is not yet implemented when this story begins:
- The `StepFileAttachment` component (Task 2) can be built and tested independently.
- The plan state integration (Task 3) requires the PreKickoffModal's state management to exist.
- The data model changes (Task 1) and backend dispatch changes (Task 4) are fully independent of the UI.

**Recommended approach**: Implement Tasks 1, 4, 5, 6 first (data model + backend), then Task 2 (UI component), then Task 3 (integration with PlanEditor) once Story 4.1 is complete.

### Convex Schema Addition

Current `steps` table in `dashboard/convex/schema.ts` (lines 67-89):
```typescript
steps: defineTable({
  taskId: v.id("tasks"),
  title: v.string(),
  description: v.string(),
  assignedAgent: v.string(),
  status: v.union(/* ... */),
  blockedBy: v.optional(v.array(v.id("steps"))),
  parallelGroup: v.number(),
  order: v.number(),
  createdAt: v.string(),
  startedAt: v.optional(v.string()),
  completedAt: v.optional(v.string()),
  errorMessage: v.optional(v.string()),
})
```

Add after `errorMessage`:
```typescript
  attachedFiles: v.optional(v.array(v.string())),
```

This is backward-compatible -- existing steps without the field will have `undefined` for `attachedFiles`, which the code treats as "no attached files."

### ExecutionPlanStep Dataclass Update (Python)

Current `ExecutionPlanStep` in `nanobot/mc/types.py` (lines 145-153):
```python
@dataclass
class ExecutionPlanStep:
    temp_id: str
    title: str
    description: str
    assigned_agent: str = GENERAL_AGENT_NAME
    blocked_by: list[str] = field(default_factory=list)
    parallel_group: int = 1
    order: int = 1
```

Add:
```python
    attached_files: list[str] = field(default_factory=list)
```

Update `to_dict()` in `ExecutionPlan` (line 186) to include:
```python
"attachedFiles": s.attached_files,
```

Update `from_dict()` (around line 224) to parse:
```python
attached_files = raw_step.get("attached_files") or raw_step.get("attachedFiles") or []
```

### Icon Pattern for File List

Reuse the `FileIcon` component pattern from `TaskDetailSheet.tsx` (lines 34-43):
```tsx
const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]);
const CODE_EXTS = new Set([".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".sh"]);

function FileIcon({ name }: { name: string }) {
  const ext = name.slice(name.lastIndexOf(".")).toLowerCase();
  if (ext === ".pdf") return <FileText className="h-3 w-3 text-muted-foreground" />;
  if (IMAGE_EXTS.has(ext)) return <Image className="h-3 w-3 text-muted-foreground" />;
  if (CODE_EXTS.has(ext)) return <FileCode className="h-3 w-3 text-muted-foreground" />;
  return <File className="h-3 w-3 text-muted-foreground" />;
}
```

Use `h-3 w-3` sizing to fit the compact step card layout (smaller than the `h-4 w-4` used in the full Files tab).

### Testing Standards

- **Component tests**: Use Vitest + `@testing-library/react` following the pattern in `StepCard.test.tsx`. Mock `convex/react` and `motion/*` as needed.
- **Python tests**: Use pytest. Follow the pattern in `test_step_dispatcher.py` for dispatcher tests and the existing types tests for dataclass round-trip verification.
- **Convex mutation tests**: Follow the pattern in `steps.test.ts` for extending the `batchCreate` test coverage.

### Project Structure Notes

- **Files to create:**
  - `dashboard/components/StepFileAttachment.tsx` -- new component for step-level file attachment UI
  - `dashboard/components/StepFileAttachment.test.tsx` -- tests for the above component
- **Files to modify:**
  - `dashboard/convex/schema.ts` -- add `attachedFiles` to `steps` table
  - `dashboard/convex/steps.ts` -- add `attachedFiles` to `create` and `batchCreate` mutation args
  - `dashboard/convex/steps.test.ts` -- add tests for `attachedFiles` in `batchCreate`
  - `dashboard/components/ExecutionPlanTab.tsx` -- add `attachedFiles?: string[]` to `ExecutionPlanStep` interface
  - `nanobot/mc/types.py` -- add `attached_files` to `ExecutionPlanStep` dataclass, update `to_dict()`/`from_dict()`
  - `nanobot/mc/plan_materializer.py` -- include `attached_files` in `_build_steps_payload()`
  - `nanobot/mc/step_dispatcher.py` -- inject step-level file context into `execution_description`
  - `nanobot/mc/test_step_dispatcher.py` -- add tests for step file context injection
- **Files to verify (no changes expected):**
  - `nanobot/mc/bridge.py` -- verify `_to_snake_case("attachedFiles")` returns `"attached_files"`
  - `dashboard/app/api/tasks/[taskId]/files/route.ts` -- no changes needed, same upload route

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.4] -- Acceptance criteria (lines 1008-1032)
- [Source: _bmad-output/planning-artifacts/prd.md#FR15] -- "User can attach documents to specific steps in the pre-kickoff modal" (line 334)
- [Source: _bmad-output/planning-artifacts/architecture.md#ExecutionPlan Structure] -- `attachedFiles?: string[]` on plan steps (lines 214-227)
- [Source: _bmad-output/planning-artifacts/architecture.md#Pre-Kickoff Modal] -- "file attachment per step" (line 335)
- [Source: _bmad-output/planning-artifacts/architecture.md#Task Directory Convention] -- `~/.nanobot/tasks/{task-id}/attachments/` (line 86)
- [Source: dashboard/convex/schema.ts#steps] -- Current steps table schema (lines 67-89)
- [Source: nanobot/mc/types.py#ExecutionPlanStep] -- Current dataclass (lines 145-153)
- [Source: nanobot/mc/plan_materializer.py#_build_steps_payload] -- Materialization payload builder (lines 83-104)
- [Source: nanobot/mc/step_dispatcher.py#_execute_step] -- Step dispatch with execution_description (lines 337-466)
- [Source: dashboard/components/TaskDetailSheet.tsx#handleAttachFiles] -- Existing file upload pattern (lines 110-141)
- [Source: dashboard/app/api/tasks/[taskId]/files/route.ts] -- File upload API route (lines 1-79)
- [Source: dashboard/components/ExecutionPlanTab.tsx#ExecutionPlanStep] -- Current plan step interface (lines 17-29)
- [Source: dashboard/convex/steps.ts#batchCreate] -- Batch step creation mutation (lines 277-347)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — implementation completed without blocking issues.

### Completion Notes List

- Task 1: Added `attached_files: list[str]` to `ExecutionPlanStep` dataclass with `to_dict()` serialization as `"attachedFiles"` and `from_dict()` parsing handling both snake_case and camelCase keys. Added `attachedFiles?: string[]` to `ExecutionPlanStep` TypeScript interface, `attachedFiles` to steps Convex schema, `create` and `batchCreate` mutations. Updated `PlanMaterializer._build_steps_payload()` to include `attached_files` in step payload (only if non-empty).
- Task 2: Created `StepFileAttachment` component with Attach button (Paperclip icon, ghost variant), hidden file input, upload via `POST /api/tasks/{taskId}/files`, loading spinner during upload, error text on failure, file list with `FileIcon` (PDF/image/code/generic), X button per file for removal, deduplication on attach.
- Task 3: Added `handleStepFilesAttached` and `handleStepFileRemoved` handlers to `PlanEditor.tsx`. Integrated `StepFileAttachment` into `PlanStepCard.tsx`. Updated `PlanEditor` and `PlanStepCard` props to accept `taskId`, `onFilesAttached`, `onFileRemoved`. Updated `PreKickoffModal.tsx` to pass `taskId` to `PlanEditor`.
- Task 4: Updated `StepDispatcher._execute_step()` to read `step.get("attached_files")` and append file context section to `execution_description` when files present, including count, path (files_dir/attachments), and file names.
- Task 5: Verified `_to_snake_case("attachedFiles") == "attached_files"` — no bridge changes needed.
- Task 6: All tests written and passing — 13 tests in `StepFileAttachment.test.tsx`, 2 new `batchCreate` tests in `steps.test.ts`, 3 tests in `TestStepFileContextInjection` class in `test_step_dispatcher.py`, 6 dataclass round-trip tests in `test_planner.py`.
- Updated `PlanStepCard.test.tsx` to mock `StepFileAttachment` and add new required props (`taskId`, `onFilesAttached`, `onFileRemoved`). Added 1 new test verifying `StepFileAttachment` renders.
- Bridge task: `_to_snake_case("attachedFiles")` confirmed to return `"attached_files"` — no changes needed.

### File List

- `nanobot/mc/types.py` — Added `attached_files` field to `ExecutionPlanStep`, updated `to_dict()` and `from_dict()`
- `nanobot/mc/plan_materializer.py` — Updated `_build_steps_payload()` to include `attached_files`
- `nanobot/mc/step_dispatcher.py` — Injected step-level file context into `execution_description`
- `nanobot/mc/test_step_dispatcher.py` — Added `TestStepFileContextInjection` class with 3 tests
- `nanobot/mc/test_planner.py` — Added 6 `ExecutionPlanStep.attachedFiles` round-trip tests
- `dashboard/convex/schema.ts` — Added `attachedFiles: v.optional(v.array(v.string()))` to steps table
- `dashboard/convex/steps.ts` — Added `attachedFiles` to `create` and `batchCreate` mutations
- `dashboard/convex/steps.test.ts` — Added 2 tests for `batchCreate` with `attachedFiles`
- `dashboard/components/ExecutionPlanTab.tsx` — Added `attachedFiles?: string[]` to `ExecutionPlanStep` interface
- `dashboard/components/StepFileAttachment.tsx` — NEW: step-level file attachment UI component
- `dashboard/components/StepFileAttachment.test.tsx` — NEW: 13 tests for `StepFileAttachment`
- `dashboard/components/PlanStepCard.tsx` — Added `taskId`, `onFilesAttached`, `onFileRemoved` props, integrated `StepFileAttachment`
- `dashboard/components/PlanStepCard.test.tsx` — Updated tests with new required props, added mock for `StepFileAttachment`, added 1 new test
- `dashboard/components/PlanEditor.tsx` — Added `taskId` prop, `handleStepFilesAttached`, `handleStepFileRemoved` handlers
- `dashboard/components/PreKickoffModal.tsx` — Passes `taskId` to `PlanEditor`

## Senior Developer Review (AI)

**Reviewer:** Ennio (via claude-opus-4-6)
**Date:** 2026-02-25
**Verdict:** Approved with fixes applied

### Findings Summary

| # | Severity | Description | Status |
|---|----------|-------------|--------|
| 1 | MEDIUM | `to_dict()` unconditionally serializes `attachedFiles: []` for every step, bloating execution plan JSON. Inconsistent with `_build_steps_payload()` which conditionally includes it. | FIXED |
| 2 | MEDIUM | Icon tests in `StepFileAttachment.test.tsx` only check file name presence, not the actual icon type. Test names are misleading. | FIXED |
| 3 | MEDIUM | `act()` warning in loading spinner test from unresolved React state updates outside act boundary. | FIXED |
| 4 | LOW | `FileIcon` produces incorrect extension for extensionless files (e.g., `Makefile`). `lastIndexOf(".")` returns -1, causing `slice(-1)` to return last char. | FIXED |
| 5 | MEDIUM | Loading spinner test does not properly await promise resolution, causing leaked state updates. | FIXED (merged with #3) |
| 6 | LOW | `PlanEditor` `useState(plan)` captures initial prop but never re-syncs with parent prop changes (latent bug for story 4.5 integration). | NOTED (pre-existing design, out of scope for this story) |

### Fixes Applied

1. **`nanobot/mc/types.py`**: `to_dict()` now conditionally includes `"attachedFiles"` only when `s.attached_files` is non-empty, matching the pattern in `_build_steps_payload()`.
2. **`nanobot/mc/test_planner.py`**: Updated test `test_execution_plan_step_empty_attached_files_omitted_from_to_dict` to verify `attachedFiles` key is absent (not present as `[]`) when no files attached.
3. **`dashboard/components/StepFileAttachment.tsx`**: Extracted `getFileIconType()` helper that properly handles extensionless files (`lastIndexOf` returns -1). Added `data-testid` to each icon variant (`icon-pdf`, `icon-image`, `icon-code`, `icon-generic`).
4. **`dashboard/components/StepFileAttachment.test.tsx`**: Icon tests now assert `getByTestId("icon-pdf")` etc. Loading spinner test resolves fetch inside `act()` to prevent leaked state updates. Imported `act` from testing library.

### AC Validation

| AC | Description | Status |
|----|-------------|--------|
| 1 | Attach button on step cards | IMPLEMENTED |
| 2 | Step card shows attached file names | IMPLEMENTED |
| 3 | File upload to task attachments directory | IMPLEMENTED |
| 4 | Each step shows only its own files | IMPLEMENTED |
| 5 | Attached files persist across plan edits | IMPLEMENTED |
| 6 | Remove file from step | IMPLEMENTED |
| 7 | Attached files in materialized step context | IMPLEMENTED |
| 8 | Empty state | IMPLEMENTED |

### Test Results

- Python: 28/28 passed (`test_step_dispatcher.py`, `test_planner.py`)
- TypeScript: 80/80 passed (`StepFileAttachment.test.tsx`, `steps.test.ts`, `PlanStepCard.test.tsx`)
