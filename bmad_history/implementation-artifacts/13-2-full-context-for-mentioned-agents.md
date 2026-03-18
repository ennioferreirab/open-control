# Story 13.2: Full Context for Mentioned Agents

Status: review

## Story

As a **mentioned agent**,
I want to receive the complete task context (metadata, execution plan, thread history, files) when mentioned via @,
so that I can provide informed, contextual responses equal to what assigned agents receive.

## Acceptance Criteria

### AC1: Task Metadata Injection

**Given** an agent is mentioned via `@agentname` in a task thread
**When** the mention handler builds the prompt for the mentioned agent
**Then** the prompt includes task metadata: title, description, current status, assigned agent, tags, and board name
**And** the metadata is clearly labeled in a `[Task Context]` section

### AC2: Thread Context via ThreadContextBuilder

**Given** an agent is mentioned in a task with thread history
**When** the mention handler builds thread context
**Then** it uses `ThreadContextBuilder.build()` with `max_messages=20` (same as assigned agents)
**And** predecessor step completions with artifacts are included when applicable
**And** the `[Thread History]` and `[Latest Follow-up]` sections match the format assigned agents receive
**And** the old `_build_mention_context()` function is no longer used

### AC3: Execution Plan Summary

**Given** an agent is mentioned in a task that has an execution plan
**When** the mention handler builds the prompt
**Then** the prompt includes a `[Execution Plan]` section with step titles and their current statuses
**And** the plan summary is concise (step title + status, one line per step)
**And** if no execution plan exists, the section is omitted

### AC4: Task File References

**Given** an agent is mentioned in a task that has attached files
**When** the mention handler builds the prompt
**Then** the prompt includes a `[Task Files]` section listing file names and descriptions
**And** if no files are attached, the section is omitted

### AC5: Backward-Compatible Response Format

**Given** an agent processes a mention with the enriched context
**When** the agent responds
**Then** the response is posted to the thread exactly as before (via `bridge.send_message`)
**And** the response format and author attribution are unchanged
**And** the additional context only affects the quality of the response, not the thread structure

## Tasks / Subtasks

- [x] Task 1: Replace `_build_mention_context` with `ThreadContextBuilder` (AC: 2)
  - [x] 1.1: In `mc/mention_handler.py`, import `ThreadContextBuilder` from `mc.thread_context`.
  - [x] 1.2: In `handle_mention()`, replace the call to `_build_mention_context(thread_messages, max_messages=10)` with `ThreadContextBuilder().build(thread_messages, max_messages=20)`.
  - [x] 1.3: Remove the `_build_mention_context()` function entirely — it is only used in `handle_mention()` and becomes dead code.

- [x] Task 2: Fetch and inject task metadata (AC: 1)
  - [x] 2.1: In `handle_mention()`, after fetching `thread_messages`, also fetch the full task data: `task_data = await asyncio.to_thread(bridge.get_task, task_id)`. Added `get_task()` method to bridge since it didn't exist.
  - [x] 2.2: Build a `[Task Context]` section from the task data via `_build_task_context()` helper. Omits fields that are empty/None.
  - [x] 2.3: Insert the `[Task Context]` section in the structured `full_message`, after `[Mention]` and before thread context.

- [x] Task 3: Include execution plan summary (AC: 3)
  - [x] 3.1: From the task data, check if `execution_plan` or `executionPlan` exists and has steps.
  - [x] 3.2: If steps exist, build a `[Execution Plan]` section via `_build_execution_plan_summary()` helper.
  - [x] 3.3: If no execution plan exists or steps list is empty, omit the section entirely.

- [x] Task 4: Include task file references (AC: 4)
  - [x] 4.1: Check if the task data has a `files`, `file_manifest`, or `fileManifest` field.
  - [x] 4.2: If files exist, build a `[Task Files]` section via `_build_task_files_section()` helper.
  - [x] 4.3: If no files exist, omit the section entirely.

- [x] Task 5: Restructure the full_message prompt (AC: 1, 2, 3, 4, 5)
  - [x] 5.1: Reorganize `full_message` in `handle_mention()` using structured sections list joined by double newlines.
  - [x] 5.2: Ensure the `[System instructions]` block is only included if `agent_prompt` is not None.

- [x] Task 6: Tests (AC: all)
  - [x] 6.1: Added unit tests in `tests/mc/test_mention_handler_context.py` verifying `handle_mention()` injects task metadata.
  - [x] 6.2: Added unit test verifying `ThreadContextBuilder` is called with `max_messages=20`.
  - [x] 6.3: Added unit tests verifying execution plan summary is included when available and omitted when not.
  - [x] 6.4: Added tests verifying `_build_mention_context` is fully removed (no references remain in module).

## Dev Notes

### Architecture & Design Decisions

**Why use `ThreadContextBuilder` instead of fixing `_build_mention_context`?** The `ThreadContextBuilder` in `mc/thread_context.py` is the canonical context builder used by the executor for assigned agents. It handles predecessor step completions, artifact formatting, omission notes, and the `[Thread History]` / `[Latest Follow-up]` structure. Duplicating this logic in a mention-specific function would diverge over time. Using the same builder ensures mentioned agents get the same quality context.

**Context window: 20 messages (not 10).** The current mention handler uses only the last 10 messages. Assigned agents get 20 (the `MAX_THREAD_MESSAGES` constant in `thread_context.py`). Mentioned agents should have the same window to provide informed responses, especially in long-running tasks with extensive discussions.

**Task metadata placement.** The `[Task Context]` section goes at the beginning of the prompt (after system instructions) so the agent has orientation before reading thread history. This matches how humans read context: overview first, then details.

### Existing Code to Reuse

**`mc/thread_context.py`** (lines 1-221):
- `ThreadContextBuilder` — the canonical context builder
- `MAX_THREAD_MESSAGES = 20` — the standard window size
- `_format_message()` — handles step completions with artifacts
- `_format_artifacts()` — formats file diffs and descriptions

**`mc/mentions/handler.py`** (lines 109-341):
- `handle_mention()` — the function to modify
- `_build_mention_context()` (lines 400-433) — to be removed
- Lines 212-238 — current `full_message` construction to restructure

**`mc/bridge.py`**:
- `get_task(task_id)` — fetches full task data including executionPlan
- `get_task_messages(task_id)` — already used in handler

### Common Mistakes to Avoid

1. **Do NOT keep `_build_mention_context` as a fallback** — remove it entirely. There should be one context builder.
2. **Do NOT fetch task data in a separate call if bridge.get_task already returns everything** — avoid redundant API calls.
3. **Do NOT include the full execution plan JSON** — only include a summary (step title + status). The full plan would be too verbose.
4. **Do NOT change the response posting logic** — only the INPUT context to the agent changes, not the OUTPUT handling.
5. **Do NOT change the 120-second timeout** — enriched context doesn't justify a longer timeout.

### Project Structure Notes

- **MODIFIED**: `mc/mentions/handler.py` — replace `_build_mention_context`, add task metadata injection
- **NEW**: `tests/mc/mentions/test_handler_context.py` — tests for enriched context
- No Convex/dashboard changes in this story
- No new dependencies

### References

- [Source: mc/thread_context.py — ThreadContextBuilder, lines 19-221]
- [Source: mc/mentions/handler.py#handle_mention — lines 109-341, current mention handling]
- [Source: mc/mentions/handler.py#_build_mention_context — lines 400-433, function to remove]
- [Source: mc/bridge.py#get_task — task data fetcher]
- [Source: mc/executor.py — reference for how assigned agents receive context]

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
None required.

### Completion Notes List
- Replaced `_build_mention_context()` with `ThreadContextBuilder().build()` using `max_messages=20`
- Added `get_task()` convenience method to `ConvexBridge` (wraps `tasks:getById` query)
- Added `_build_task_context()` helper to format task metadata as `[Task Context]` section
- Added `_build_execution_plan_summary()` helper to format concise plan summary as `[Execution Plan]` section
- Added `_build_task_files_section()` helper to format file references as `[Task Files]` section
- Restructured `full_message` prompt with ordered sections: System instructions, Mention, Task Context, Execution Plan, Task Files, Thread context
- Removed `_build_mention_context()` function entirely
- Updated existing `test_mention_handler.py` to test new helper functions instead of removed function
- Created new `test_mention_handler_context.py` with 10 integration tests covering all ACs
- All 42 mention handler tests pass; no regressions in broader test suite
- Response posting logic and 120-second timeout unchanged (AC5)
- Removed unused `LEAD_AGENT_NAME` import (lint fix)

### File List
- `mc/mention_handler.py` — modified (replaced context building, added helpers, removed `_build_mention_context`)
- `mc/bridge.py` — modified (added `get_task()` method)
- `tests/mc/test_mention_handler.py` — modified (updated tests for new helper functions)
- `tests/mc/test_mention_handler_context.py` — new (10 integration tests for enriched context)
- `_bmad-output/implementation-artifacts/13-2-full-context-for-mentioned-agents.md` — updated (completion status)

### Change Log
- 2026-03-05: Implemented Story 13.2 — Full Context for Mentioned Agents. Replaced _build_mention_context with ThreadContextBuilder, added task metadata/execution plan/file injection, restructured prompt with ordered sections. 41 tests passing.
