# Story 27.7: Add Claude Code Hook Supervision and Ask-User Review Pauses

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control operator,
I want Claude Code interactive sessions to emit structured lifecycle events and pause correctly for `ask_user`,
so that Claude-backed TUI execution can be supervised without scraping the terminal.

## Acceptance Criteria

1. Interactive Claude Code workspaces inject and register hook handlers for the
   official Claude lifecycle events used by MC supervision.
2. Claude hook callbacks are relayed into the interactive supervision contract
   and cover at least:
   - `SessionStart`
   - `UserPromptSubmit`
   - `PreToolUse`
   - `PermissionRequest`
   - `PostToolUse`
   - `PostToolUseFailure`
   - `Stop`
3. When Claude uses `mcp__mc__ask_user`, Mission Control moves:
   - the owning task to `review`
   - the active step to `review`
4. When the user replies to a pending `ask_user`, Mission Control resumes:
   - the owning task to `in_progress`
   - the active step to `in_progress`
5. Review workers continue to skip tasks paused by pending `ask_user`, so the
   pause is not mistaken for completion.
6. Focused tests cover hook mapping, hook registration, and task/step review
   transitions for `ask_user`.

## Success Metrics

- 100% of covered Claude lifecycle events map to normalized supervision events
- A pending `ask_user` always pauses both task and active step in focused tests
- No Claude interactive lifecycle coverage depends on TUI output parsing

## Tasks / Subtasks

- [ ] Task 1: Inject Claude hook registration into the interactive workspace (AC: #1, #2)
  - [ ] Reuse the existing workspace manager and keep headless and interactive configs separate
  - [ ] Add a Claude hook relay that forwards hook payloads into the supervision sink
  - [ ] Add tests for generated workspace config and hook payload mapping

- [ ] Task 2: Pause and resume task/step state for `ask_user` (AC: #3, #4, #5)
  - [ ] Record the active `step_id` alongside pending ask-user requests
  - [ ] Move task and step to `review` when `mcp__mc__ask_user` is invoked
  - [ ] Resume task and step to `in_progress` when the user reply is delivered
  - [ ] Keep review routing skipped while ask-user is pending

- [ ] Task 3: Run focused regression and guardrails (AC: #6)
  - [ ] Run backend tests for hooks and ask-user transitions
  - [ ] Run architecture guardrails
  - [ ] Record residual risks for Claude-only behavior that still needs provider abstraction

## Dev Notes

- Use Claude hooks as the primary lifecycle source; do not add terminal parsing
  fallback for these covered events in this story.
- The `ask_user` pause behavior is cross-provider in intent, but this story
  establishes it first through the Claude path because `mcp__mc__ask_user` is
  already live there.
- Reuse the current ask-user registry rather than creating a second pause store.

### Project Structure Notes

- Likely touch points:
  - `vendor/claude-code/claude_code/workspace.py`
  - `mc/contexts/interactive/adapters/claude_code.py`
  - `mc/contexts/conversation/ask_user/`
  - `mc/runtime/workers/review.py`
  - `tests/cc/`
  - `tests/mc/`

### References

- [Source: docs/plans/2026-03-13-tui-execution-supervision-plan.md]
- [Source: docs/ARCHITECTURE.md]
- [Source: vendor/claude-code/claude_code/workspace.py]
- [Source: mc/contexts/conversation/ask_user/handler.py]
- [Source: mc/contexts/review/handler.py]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
