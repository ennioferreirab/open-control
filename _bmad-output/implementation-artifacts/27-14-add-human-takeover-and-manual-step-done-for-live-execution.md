# Story 27.14: Add Human Takeover and Manual Step Done for Live Execution

Status: done

## Story

As a Mission Control operator,
I want to intervene in a running `Live` step session and manually mark that step done,
so that I can take control, finish the work myself, and conclude only the active step.

## Acceptance Criteria

1. A running step-backed `Live` session can be explicitly put into human-takeover mode from the task-detail UI.
2. Human takeover pauses automated step supervision clearly and prevents the agent from silently continuing as if it still owned the step.
3. After manual intervention, the operator can mark only the active step as `done` from the UI.
4. Manual step completion posts an explicit thread/activity record that the human intervened and completed the step manually.
5. Manual `Done` does not auto-complete the whole task unless existing downstream workflow rules would normally do so from step completion.
6. If the operator exits takeover without marking done, the step remains in a safe review/running state defined by the workflow contract.

## Success Metrics

- Focused tests cover takeover, manual done, and non-terminal exit paths
- Browser validation demonstrates takeover and manual step completion from `Live`
- No covered path allows manual `Done` to complete the entire task directly

## Tasks / Subtasks

- [x] Task 1: Add backend workflow/state support for human takeover (AC: #1, #2, #6)
  - [x] Define how a step/session enters takeover and leaves automated supervision
  - [x] Reuse existing review/pause workflow semantics where possible instead of inventing a parallel state machine
  - [x] Add focused backend tests for takeover state transitions

- [x] Task 2: Add manual step completion for takeover sessions (AC: #3, #4, #5)
  - [x] Implement a backend action that marks only the active step complete
  - [x] Post explicit thread/activity records for human completion
  - [x] Add focused tests for manual completion and downstream workflow behavior

- [x] Task 3: Add `Live` UX for takeover and manual done (AC: #1, #3, #6)
  - [x] Add clear controls for takeover and manual done in the task-detail `Live` UI
  - [x] Prevent accidental usage against non-active or mismatched sessions
  - [x] Capture Playwright evidence of the intervention flow

## Dev Notes

- `Done` here means “the active step is done,” not “the task is done.”
- Keep the UI honest about who currently owns the execution: agent or human.
- Avoid hidden state transitions; intervention should be visible in thread/activity.

### Project Structure Notes

- Likely touch points:
  - `mc/contexts/interactive/`
  - `mc/contexts/execution/`
  - `dashboard/features/interactive/`
  - `dashboard/features/tasks/`
  - `dashboard/convex/`
  - `tests/mc/`

### References

- [Source: mc/contexts/interactive/supervisor.py]
- [Source: mc/contexts/execution/step_dispatcher.py]
- [Source: shared/workflow/workflow_spec.json]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
