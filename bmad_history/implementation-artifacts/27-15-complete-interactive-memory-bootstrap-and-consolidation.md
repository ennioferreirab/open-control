# Story 27.15: Complete Interactive Memory Bootstrap and Consolidation

Status: done

## Story

As a Mission Control platform owner,
I want interactive step execution to inject memory correctly at startup and consolidate memory at completion,
so that TUI-backed execution preserves the same memory quality expected from the structured execution flows.

## Acceptance Criteria

1. Interactive step execution passes the correct memory workspace and prompt context into provider startup for Claude Code, Codex, and any supported interactive provider.
2. The initial interactive execution context includes the task prompt/instruction in a deterministic provider-supported way, not only background workspace files when a direct turn is required.
3. Interactive step execution triggers memory consolidation on successful or failed session boundary completion using the canonical interactive result.
4. If memory consolidation cannot run, the skip/failure is logged clearly and does not silently disappear.
5. Covered tests verify that the interactive path uses the intended memory workspace and prompt bootstrap.
6. Existing board-memory semantics (`clean` vs `with_history`) remain intact.

## Success Metrics

- Focused tests prove memory workspace propagation for all covered interactive providers
- Focused tests prove consolidation is invoked from interactive step completion
- No covered interactive success path finishes without either consolidating or logging a clear skip reason

## Tasks / Subtasks

- [x] Task 1: Fix interactive startup context injection (AC: #1, #2, #5, #6)
  - [x] Audit and wire memory workspace, board mode, and initial task prompt through interactive startup
  - [x] Add focused tests for Claude and Codex startup context propagation
  - [x] Keep provider-specific bootstrap mechanisms explicit and testable

- [x] Task 2: Wire interactive completion into memory consolidation (AC: #3, #4, #5)
  - [x] Feed canonical interactive final results into the existing memory consolidation pipeline
  - [x] Add clear structured logging for consolidate/skip/fail paths
  - [x] Add focused tests for consolidation trigger and skip behavior

- [x] Task 3: Validate memory behavior end-to-end (AC: #1, #2, #3)
  - [x] Validate startup context in a real interactive session
  - [x] Validate consolidation trigger after step completion
  - [x] Capture Playwright evidence where visible and note non-visual backend verification

## Dev Notes

- Reuse the canonical memory service; do not invent an interactive-only memory store.
- The provider startup path must be explicit about whether the initial instruction is passed via CLI, IPC, workspace file, or first terminal input.
- This story must not rely on the old headless executor as a fallback path.

### Project Structure Notes

- Likely touch points:
  - `mc/application/execution/`
  - `mc/contexts/interactive/`
  - `vendor/claude-code/claude_code/`
  - `tests/mc/`
  - `tests/cc/`

### References

- [Source: mc/application/execution/post_processing.py]
- [Source: vendor/claude-code/claude_code/workspace.py]
- [Source: mc/contexts/interactive/adapters/codex.py]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
