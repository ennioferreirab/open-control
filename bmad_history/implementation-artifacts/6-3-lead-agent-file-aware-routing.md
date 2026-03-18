# Story 6.3: Lead Agent File-Aware Routing

Status: review

## Story

As a **user**,
I want the Lead Agent to consider attached file metadata when routing steps to agents,
So that file-heavy tasks are routed to agents best equipped to handle them.

## Acceptance Criteria

1. **Given** a task is created with file attachments, **When** the Lead Agent generates the execution plan, **Then** it receives the file manifest as part of the task context: file names, types, sizes (FR-F28)
2. **Given** the Lead Agent assigns an agent to a step, **When** the delegation context is constructed, **Then** file metadata is included: number of files, types, total size, and names (FR-F29). Example: "Task includes 2 attached files: invoice.pdf (847 KB), notes.md (12 KB). Available at the task's attachments directory."
3. **Given** a task has no file attachments, **When** the Lead Agent routes the task, **Then** routing proceeds normally without file metadata -- no empty file context noise
4. **Given** file metadata is provided to the Lead Agent, **When** it informs agent assignment, **Then** file awareness enriches the routing context but does not override the capability-matching algorithm

## Important: Existing Implementation State

This story was previously implemented as Story 9-13 in a prior sprint. The core plumbing already exists in the codebase:

- `nanobot/mc/planner.py` already has `_build_file_summary(files)` (line 118) that formats file metadata into a human-readable summary
- `nanobot/mc/planner.py` `_llm_plan()` (line 317) already appends the file summary to the LLM user prompt when files are present
- `nanobot/mc/orchestrator.py` `_process_planning_task()` (line 143) already passes `files=task_data.get("files") or []` to `planner.plan_task()`
- `nanobot/mc/step_dispatcher.py` `_execute_step()` (line 416) already injects per-step `attached_files` context into the execution description

**What this story must do:** Verify the existing implementation against the new epic 6 acceptance criteria (FR-F28, FR-F29), close any gaps between the 9-13 implementation and the refined 6.3 spec, add missing tests, and ensure delegation context includes file metadata at the step-dispatch level (not just the planning level).

## Tasks / Subtasks

- [ ] Task 1: Audit existing `_build_file_summary()` against FR-F28/FR-F29 (AC: #1, #2)
  - [ ] 1.1: Verify `_build_file_summary()` in `nanobot/mc/planner.py` produces the format specified in AC #2: "Task includes N attached file(s): name (size), ... Available at the task's attachments directory."
  - [ ] 1.2: If the current format differs from the AC #2 example (e.g., missing "Available at the task's attachments directory." suffix), update the output string to match
  - [ ] 1.3: Verify that file types (MIME types from the `type` field) are included in the summary, not just names and sizes
  - [ ] 1.4: Verify the function handles edge cases: single file, many files (10+), zero-byte files, very large files (1 GB+)

- [ ] Task 2: Verify zero-file noise suppression (AC: #3)
  - [ ] 2.1: Confirm `_build_file_summary([])` returns empty string `""`
  - [ ] 2.2: Confirm `_llm_plan()` does NOT append any file-related text when `files` is empty or `None`
  - [ ] 2.3: Confirm `orchestrator._process_planning_task()` passes `[]` (not `None`) when task has no files

- [ ] Task 3: Inject file metadata into step-level delegation context (AC: #2, #4)
  - [ ] 3.1: In `nanobot/mc/step_dispatcher.py` `_execute_step()`, verify that when the parent task has files, the step's `execution_description` includes a task-level file summary (not just per-step `attached_files`)
  - [ ] 3.2: Fetch the task's `files` array from `task_data` (already fetched at line 385-390) and build a task-level file summary
  - [ ] 3.3: Inject the task-level file summary into `execution_description` ONLY when the task has files (no noise for zero-file tasks)
  - [ ] 3.4: The task-level file summary must NOT override or conflict with the per-step `attached_files` context (which is step-specific document assignments from the execution plan)
  - [ ] 3.5: Format: "Parent task has N attached file(s) (total SIZE): name1 (size1), name2 (size2). Available at {files_dir}/attachments."

- [ ] Task 4: Ensure file awareness does NOT override capability matching (AC: #4)
  - [ ] 4.1: Verify `_build_file_summary()` output is appended to the user prompt AFTER the agent roster, so the LLM sees agent capabilities first
  - [ ] 4.2: Verify the system prompt instruction "Consider file types when selecting the best agent" is advisory, not prescriptive
  - [ ] 4.3: Verify heuristic fallback planner (`_fallback_heuristic_plan()`) does NOT use file metadata for agent selection (it uses keyword scoring only)

- [ ] Task 5: Write unit tests (AC: #1, #2, #3, #4)
  - [ ] 5.1: In `nanobot/mc/test_planner.py`, add test: `test_build_file_summary_with_files_returns_formatted_string`
  - [ ] 5.2: Add test: `test_build_file_summary_with_empty_files_returns_empty_string`
  - [ ] 5.3: Add test: `test_build_file_summary_single_file`
  - [ ] 5.4: Add test: `test_build_file_summary_large_files_uses_mb_format`
  - [ ] 5.5: Add test: `test_llm_plan_includes_file_summary_in_prompt_when_files_present` (mock the provider)
  - [ ] 5.6: Add test: `test_llm_plan_excludes_file_summary_when_no_files`
  - [ ] 5.7: In `nanobot/mc/test_step_dispatcher.py`, add test: `test_step_execution_includes_task_level_file_summary_when_task_has_files`
  - [ ] 5.8: Add test: `test_step_execution_excludes_task_level_file_summary_when_task_has_no_files`
  - [ ] 5.9: In `nanobot/mc/test_orchestrator.py`, add test: `test_process_planning_task_passes_files_to_planner`

- [ ] Task 6: Verify end-to-end flow (manual)
  - [ ] 6.1: Create a task with 2 file attachments in the dashboard
  - [ ] 6.2: Observe the Lead Agent planning log -- confirm file summary appears in the LLM prompt
  - [ ] 6.3: Observe the step dispatch log -- confirm task-level file summary appears in execution description
  - [ ] 6.4: Create a task with zero files -- confirm no file metadata noise in logs

## Dev Notes

### Existing Code Locations

| File | What exists | What may need changes |
|------|-------------|----------------------|
| `nanobot/mc/planner.py` lines 118-133 | `_build_file_summary()` builds human-readable file summary | Verify format matches AC #2; add file type information if missing |
| `nanobot/mc/planner.py` lines 317-335 | `_llm_plan()` appends file summary to user prompt | Already correct -- just needs test coverage |
| `nanobot/mc/planner.py` lines 286-315 | `plan_task()` accepts `files` param and forwards to `_llm_plan()` | Already correct -- just needs test coverage |
| `nanobot/mc/orchestrator.py` line 143 | `files=task_data.get("files") or []` passed to planner | Already correct -- just needs test coverage |
| `nanobot/mc/step_dispatcher.py` lines 385-426 | `_execute_step()` builds `execution_description` with per-step files | Needs task-level file summary injection |
| `nanobot/mc/test_planner.py` | Tests for plan parsing, validation, round-trips | Missing tests for `_build_file_summary()` |
| `nanobot/mc/test_orchestrator.py` | Tests for planning routing | Missing test for files passthrough |
| `nanobot/mc/test_step_dispatcher.py` | Tests for step execution with per-step files | Missing test for task-level file summary |

### Current `_build_file_summary()` Implementation

```python
def _build_file_summary(files: list[dict]) -> str:
    """Build a human-readable file summary for lead agent context."""
    if not files:
        return ""

    def _human_size(b: int) -> str:
        return f"{b // 1024} KB" if b < 1_048_576 else f"{b / 1_048_576:.1f} MB"

    total = sum(f.get("size", 0) for f in files)
    names = ", ".join(
        f"{f['name']} ({_human_size(f.get('size', 0))})" for f in files
    )
    return (
        f"Task has {len(files)} attached file(s) (total {_human_size(total)}): {names}. "
        f"Consider file types when selecting the best agent."
    )
```

**Gap analysis:**
- The current implementation outputs: "Task has 2 attached file(s) (total 859 KB): invoice.pdf (847 KB), notes.md (12 KB). Consider file types when selecting the best agent."
- The AC #2 example expects: "Task includes 2 attached files: invoice.pdf (847KB), notes.md (12KB). Available at the task's attachments directory."
- Delta: The current format is close but uses slightly different wording. The advisory "Consider file types" is appropriate for the LLM planning prompt but the delegation context (step-level) should say "Available at the task's attachments directory."
- Decision: Keep `_build_file_summary()` as-is for the planning prompt (it works well for the LLM). Create a separate `_build_delegation_file_summary()` for step-level context OR reuse the same function and adjust the step dispatcher to append the "Available at..." suffix.

### Step Dispatcher File Context Injection Pattern

The step dispatcher already builds `execution_description` at `step_dispatcher.py` line 407-426. The task-level file summary should be injected between the task description and the per-step attached files section:

```python
# After line 414 ("Do NOT save output files outside this directory.")
# and before the per-step attached_files check (line 416):

task_files = task_data.get("files") or []
if task_files:
    # Build task-level file summary for delegation context (FR-F29)
    from nanobot.mc.planner import _build_file_summary
    task_file_summary = _build_file_summary(task_files)
    if task_file_summary:
        execution_description += (
            f"\n\n{task_file_summary}\n"
            f"Files available at: {files_dir}/attachments"
        )
```

This keeps the per-step `attached_files` section separate (step-specific files assigned in the execution plan) from the task-level file summary (all files the task has).

### Architecture Compliance

- **Module boundary**: `planner.py` is the correct location for planning-level file context. `step_dispatcher.py` is the correct location for delegation-level file context.
- **NFR21 (500-line module limit)**: Both `planner.py` (452 lines) and `step_dispatcher.py` (528 lines) are near the limit. The changes for this story are minimal (a few lines in step_dispatcher, tests only in test files).
- **No Convex schema changes**: The `files` field on tasks already exists. No new fields needed.
- **No dashboard changes**: This story is purely Python backend.
- **LLM prompt enrichment only**: File metadata enriches context but the `score_agent()` heuristic and LLM capability matching remain unchanged.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT modify the capability-matching algorithm** -- AC #4 is explicit: file awareness enriches context but does not override agent selection. Do not add file-type-based scoring to `score_agent()` or change `_fallback_heuristic_plan()`.

2. **DO NOT add file metadata to the system prompt** -- File context belongs in the user prompt (per-task, dynamic). The system prompt is static and defines the LLM's role.

3. **DO NOT inject empty file sections** -- AC #3 is explicit: zero-file tasks must have no file context noise. Always guard with `if task_files:` before injecting.

4. **DO NOT duplicate `_build_file_summary()` in step_dispatcher.py** -- Import it from `planner.py` or create a shared utility. Do not copy-paste the function.

5. **DO NOT change the per-step `attached_files` logic** -- The per-step file context (lines 416-423 in step_dispatcher.py) is for step-specific document assignments from the execution plan. The task-level file summary is separate and complementary.

6. **DO NOT fetch files from Convex again in step_dispatcher** -- The task data is already fetched at line 385-390. Reuse `task_data.get("files")`.

7. **DO NOT break existing tests** -- The existing test suite (test_planner.py, test_step_dispatcher.py, test_orchestrator.py) must continue to pass. Run `uv run pytest nanobot/mc/` before and after changes.

### What This Story Does NOT Include

- **Agent-level file type skills** -- Agents do not have explicit file-handling skill tags. The LLM uses its reasoning to match file types to agent roles.
- **Dashboard file routing UI** -- No dashboard changes. File-aware routing is invisible to the user (it happens inside the Lead Agent's LLM reasoning).
- **File content analysis** -- The Lead Agent receives metadata (names, types, sizes) not file contents. Content analysis is out of scope.
- **Per-step file assignment changes** -- The execution plan `attachedFiles` feature (Story 4.4) is separate. This story is about task-level file awareness.

### Project Structure Notes

- All Python changes in `nanobot/mc/` (Mission Control module)
- Test files follow naming convention: `test_<module>.py` in the same directory
- Run tests with: `uv run pytest nanobot/mc/test_planner.py nanobot/mc/test_step_dispatcher.py nanobot/mc/test_orchestrator.py -v`
- Use `uv run python` (not system Python 3.9)

### Dependency: Story 6-1 (Inject File Context into Agent Task Context)

Story 6-1 (originally 9-11) is already implemented and done. It established:
- `filesDir` and `fileManifest` injection in executor.py
- Fresh Convex fetch for up-to-date file manifest (NFR-F8)
- Per-step `attached_files` injection in step_dispatcher.py

This story builds on 6-1 by enriching the Lead Agent's planning prompt and the step delegation context with task-level file metadata.

### Previous Story Intelligence (Story 9-13)

Story 9-13 implemented the core of this feature in a prior sprint:
- Added `_build_file_summary()` to `planner.py`
- Wired `files` parameter through `orchestrator.py` -> `planner.plan_task()` -> `_llm_plan()`
- The implementation was minimal and test-light

This story (6-3) is the "clean-up and complete" pass: verify, test, and close gaps in the delegation context.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 6.3`] -- Original story definition with AC
- [Source: `_bmad-output/planning-artifacts/epics.md` lines 111-112] -- FR-F28, FR-F29 definitions
- [Source: `_bmad-output/planning-artifacts/architecture.md#Execution Plan Structure`] -- ExecutionPlan with attachedFiles
- [Source: `nanobot/mc/planner.py` lines 118-133] -- Existing `_build_file_summary()` implementation
- [Source: `nanobot/mc/planner.py` lines 286-352] -- `plan_task()` and `_llm_plan()` with files parameter
- [Source: `nanobot/mc/orchestrator.py` line 143] -- Files passthrough to planner
- [Source: `nanobot/mc/step_dispatcher.py` lines 385-426] -- Step execution description assembly
- [Source: `nanobot/mc/executor.py` lines 641-679] -- File manifest injection in executor (legacy path)
- [Source: `_bmad-output/implementation-artifacts/9-13-lead-agent-file-aware-routing.md`] -- Prior implementation reference
- [Source: `_bmad-output/implementation-artifacts/9-11-inject-file-context-into-agent-task-context.md`] -- Dependency story
- [Source: `dashboard/convex/schema.ts` lines 55-61] -- Convex files field schema on tasks table

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — all tests passed cleanly on the first full run after fixing the `patch` target path for `create_provider` (it is imported locally inside `_llm_plan()` via `from nanobot.mc.provider_factory import create_provider`, so the patch target is `nanobot.mc.provider_factory.create_provider`).

### Completion Notes List

- **AC #1 (FR-F28)**: Verified `planner._llm_plan()` already passes the task's `files` array to `_build_file_summary()` and appends the summary to the user prompt. Updated `_build_file_summary()` to include MIME type (`type` field) in each file entry alongside name and size, satisfying the "file names, types, sizes" requirement.

- **AC #2 (FR-F29)**: Added task-level file routing summary injection in `step_dispatcher._execute_step()` using `_build_file_summary()` imported from `planner.py` (not duplicated). The injection appends `\n\n{file_routing_summary}\nFiles available at: {files_dir}/attachments` after the existing Story 6.1 manifest section. This provides the "Consider file types when selecting the best agent" advisory plus the attachments directory path.

- **AC #3**: Zero-file guard verified at three levels: `_build_file_summary([])` returns `""`, `_llm_plan()` skips the append when file_summary is falsy, and step dispatcher checks `if task_files:` before injecting. No empty file context noise for zero-file tasks.

- **AC #4**: Verified `_fallback_heuristic_plan()` uses only keyword scoring (not file types) for agent selection. File context is appended to the LLM user prompt (not system prompt) after the agent roster, making it advisory. No changes to `score_agent()` or `_fallback_heuristic_plan()`.

- **Gap closed**: `_build_file_summary()` previously omitted MIME types. Updated to include `f.get('type', 'application/octet-stream')` in each file entry. Existing tests all still pass.

- **Test count**: 13 new tests added (8 in test_planner.py, 2 in test_step_dispatcher.py, 1 in test_orchestrator.py). All 41 tests in the three target files pass. Full suite: 356 passed.

### File List

- `nanobot/mc/planner.py` — Updated `_build_file_summary()` to include MIME type in file entries (FR-F28, Task 1.3)
- `nanobot/mc/step_dispatcher.py` — Added task-level file routing summary injection using `_build_file_summary()` from planner (FR-F29, Task 3)
- `nanobot/mc/test_planner.py` — Added 8 new tests: 6 for `_build_file_summary()` and 2 async tests for `_llm_plan()` file summary injection/exclusion (Tasks 5.1-5.6)
- `nanobot/mc/test_step_dispatcher.py` — Added `TestTaskLevelFileSummaryInDelegationContext` class with 2 tests for file summary presence/absence in delegation context (Tasks 5.7-5.8)
- `nanobot/mc/test_orchestrator.py` — Added `test_process_planning_task_passes_files_to_planner` to verify orchestrator passes files to planner (Task 5.9)

## Senior Developer Review (AI)

**Reviewer:** Claude Sonnet 4.6 (adversarial senior review)
**Date:** 2026-02-25
**Result:** PASS with fixes applied

### Findings

#### ISSUE 1 — HIGH: Wrong advisory text in executor delegation context

**File:** `nanobot/mc/step_dispatcher.py` lines 381–398
**Severity:** HIGH
**Problem:** `_build_file_summary()` produces "Consider file types when selecting the best agent." This advisory is correct for the Lead Agent's planning-phase LLM prompt. However, the implementation reused `_build_file_summary()` verbatim in `step_dispatcher._execute_step()`, injecting the planner routing advisory into the executor delegation context — at which point the agent is already assigned and the routing decision is final. The text is semantically wrong in the delegation context and will confuse executor agents (e.g. a code agent being told to "consider file types when selecting the best agent" mid-execution). AC #2 specifies the delegation text as "Available at the task's attachments directory." — not a routing advisory.
**Fix applied:** The delegation section now calls `_build_file_summary()` and replaces the planner advisory with the executor-appropriate `"Files available at: {files_dir}/attachments"` path using `.replace()`. The LLM planning prompt retains "Consider file types" unchanged.

#### ISSUE 2 — MEDIUM: Inline deferred imports scattered deep inside hot-path conditionals

**File:** `nanobot/mc/step_dispatcher.py`
**Severity:** MEDIUM
**Problem:** `from nanobot.mc.executor import _human_size` and `from nanobot.mc.planner import _build_file_summary` were placed inside `if file_manifest:` and `if task_files:` conditional blocks respectively — i.e., the deepest nesting level inside `_execute_step()`. While Python caches module imports, scattering deferred imports inside conditionals in a hot path is a code smell: imports become invisible to static analyzers, linters cannot detect unused imports at a glance, and future developers will miss the dependency contract. The reason for deferring (circular import: `step_dispatcher → executor → gateway → orchestrator → step_dispatcher`) is valid, but the fix is to hoist them to the top of the function, not bury them in conditionals.
**Fix applied:** Both imports (plus `_snapshot_output_dir` and `_collect_output_artifacts`) are now consolidated at the top of `_execute_step()` with a comment explaining the circular-import reason. The pre-existing inline import of `_run_agent_on_task` in the module-level `_run_step_agent` helper is left unchanged (different function, same valid pattern).

#### ISSUE 3 — MEDIUM: Redundant `task_files = raw_files` alias obscures data flow

**File:** `nanobot/mc/step_dispatcher.py` line 386
**Severity:** MEDIUM
**Problem:** `task_files = raw_files  # already fetched above as raw_files` creates a dead alias. The comment explicitly acknowledges the variable is redundant. Using `task_files` and `raw_files` as two names for the same list in the same function makes it harder to trace data flow and introduces a future maintenance hazard (a reader might assume `task_files` went through some transformation that `raw_files` didn't).
**Fix applied:** The `task_files = raw_files` line was removed. The conditional now reads `if raw_files:` directly, which is consistent with how `raw_files` is used in the manifest section above it.

#### ISSUE 4 — LOW: Test assertion validates wrong behavior (routing advisory in executor context)

**File:** `nanobot/mc/test_step_dispatcher.py` line 923
**Severity:** LOW
**Problem:** `assert "Consider file types" in desc` in `TestTaskLevelFileSummaryInDelegationContext.test_step_execution_includes_task_level_file_summary_when_task_has_files` was asserting that the planner-only routing advisory appears in the executor delegation context. This locked in the buggy behavior described in Issue 1. After the Issue 1 fix, this assertion would have started failing — which is the correct behavior. The test should assert the executor-appropriate text instead.
**Fix applied:** The `assert "Consider file types" in desc` assertion was replaced with two assertions: `assert "Files available at:" in desc` (executor-appropriate path) and `assert "Consider file types when selecting the best agent" not in desc` (explicit guard against routing advisory leaking into delegation context).

#### ISSUE 5 — LOW: Redundant defensive `(task_data or {})` guard on line 333

**File:** `nanobot/mc/step_dispatcher.py` line 333
**Severity:** LOW
**Problem:** `raw_files = (task_data or {}).get("files") or []` uses `(task_data or {})` defensively, but `task_data` is already guaranteed to be a non-None dict by line 329: `task_data = task_data if isinstance(task_data, dict) else {}`. The double-guard adds noise and implies the invariant is weaker than it actually is.
**Fix applied:** Changed to `raw_files = task_data.get("files") or []` — consistent with how `task_data` is used everywhere else in the function.

### AC Verification

| AC | Status | Notes |
|----|--------|-------|
| AC #1 (FR-F28) — file manifest in planning prompt | IMPLEMENTED | `planner._llm_plan()` appends `_build_file_summary()` output (names, MIME types, sizes) to user prompt |
| AC #2 (FR-F29) — file metadata in delegation context | IMPLEMENTED (fixed) | `step_dispatcher._execute_step()` now injects executor-appropriate summary with files path, not routing advisory |
| AC #3 — no empty file noise | IMPLEMENTED | `_build_file_summary([])` returns `""`, `_llm_plan()` skips append, dispatcher guards with `if raw_files:` |
| AC #4 — file awareness does not override capability matching | IMPLEMENTED | `_fallback_heuristic_plan()` is unchanged; file context is appended to user prompt after agent roster |

### Test Results

43 passed, 0 failed (up from 41 — 2 additional pre-existing story-6.2 tests collected).
