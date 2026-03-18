# Story 29.2: Enrich Supervisor with Activity Log Writes

Status: ready-for-dev

## Story

As a Mission Control platform maintainer,
I want the existing InteractiveExecutionSupervisor to write structured events
to the sessionActivityLog table,
so that every supervision event becomes a persistent, queryable record.

## Acceptance Criteria

1. `InteractiveExecutionSupervisor.handle_event()` calls
   `sessionActivityLog:append` after the existing `record_supervision` call
2. The mutation payload extracts `tool_name` and `input` from `event.metadata`
   with graceful fallback when missing
3. `tool_input` is stringified and truncated to 2000 chars
4. `file_path` is extracted from `input.file_path` or `input.path` when present
5. `requires_action` is true for `approval_requested`, `user_input_requested`,
   `ask_user_requested`
6. Focused tests verify the mutation is called with correct fields for each
   canonical event kind, including cases where metadata is empty

## Tasks / Subtasks

- [ ] Task 1: Add `_stringify_input()` and `_extract_file_path()` helpers
- [ ] Task 2: Add the `sessionActivityLog:append` call in `handle_event()`
- [ ] Task 3: Add focused tests covering all event kinds and missing metadata

## Dev Notes

- This is ~25 lines added to `mc/contexts/interactive/supervisor.py`.
- No new Python modules. Keep the helpers private in the supervisor module.
- Test with mock bridge — verify mutation name and payload fields.
- The existing `record_supervision` call must not change.

### References

- [Source: docs/plans/2026-03-14-agent-activity-feed-design.md]
- [Source: mc/contexts/interactive/supervisor.py]
- [Source: mc/contexts/interactive/supervision_types.py]
