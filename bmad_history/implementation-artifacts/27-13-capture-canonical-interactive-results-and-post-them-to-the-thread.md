# Story 27.13: Capture Canonical Interactive Results and Post Them to the Thread

Status: done

## Story

As a Mission Control operator,
I want interactive step execution to capture the agent's real final result and post it into the task thread,
so that interactive execution preserves the same completion visibility expected from headless runs.

## Acceptance Criteria

1. Interactive execution stores a canonical session journal or equivalent runtime-owned record for step sessions.
2. The step-completion message posted to the task thread uses the final agent result captured from the interactive runtime, not only a supervision summary placeholder.
3. Claude Code and Codex both provide a deterministic final result path for step completion.
4. If the interactive session ends without a usable final result, the step fails clearly instead of posting a misleading success message.
5. Step completion artifacts and thread-post semantics remain consistent with existing step completion UX.
6. Existing headless completion posting remains untouched in code and behavior.

## Success Metrics

- Focused tests prove canonical final-result capture for Claude and Codex
- 100% of interactive step completions in covered tests post a non-placeholder thread result
- No covered success path marks a step completed when the final result is missing

## Tasks / Subtasks

- [x] Task 1: Introduce canonical interactive result capture (AC: #1, #2, #3, #4)
  - [x] Add runtime-owned journal/final-result storage for interactive step sessions
  - [x] Define provider contracts for writing a final result into that storage
  - [x] Add focused backend tests for success, missing-result, and error cases

- [x] Task 2: Integrate interactive final results into step completion posting (AC: #2, #4, #5, #6)
  - [x] Update step-dispatch/post-processing flow to read canonical interactive results
  - [x] Preserve existing artifact collection and step completion message semantics
  - [x] Add regression tests for the task-thread completion message

- [x] Task 3: Validate in the real UI (AC: #2, #3)
  - [x] Run end-to-end validation for a Claude interactive step
  - [x] Run end-to-end validation for a Codex interactive step
  - [x] Capture Playwright evidence showing the final result posted into the task thread

## Dev Notes

- Do not parse the rendered terminal screen as the canonical completion record if a stronger provider/runtime signal exists.
- This story is about step execution, not chat-scoped conversational TUI turns.
- Avoid weakening the existing `post_step_completion` thread contract.

### Project Structure Notes

- Likely touch points:
  - `mc/application/execution/`
  - `mc/contexts/interactive/`
  - `mc/runtime/`
  - `tests/mc/`
  - dashboard thread/task detail tests if the visible completion presentation changes

### References

- [Source: mc/contexts/execution/step_dispatcher.py]
- [Source: mc/application/execution/strategies/interactive.py]
- [Source: mc/contexts/interactive/supervision.py]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
