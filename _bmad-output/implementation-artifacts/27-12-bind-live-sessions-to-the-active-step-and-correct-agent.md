# Story 27.12: Bind Live Sessions to the Active Step and Correct Agent

Status: done

## Story

As a Mission Control operator,
I want the `Live` tab to always attach to the exact running step session for the correct provider and agent,
so that I never observe or control the wrong execution.

## Acceptance Criteria

1. Task-detail `Live` discovery selects the interactive session by the active `stepId`, `taskId`, `agentName`, and `provider`, not only by task-level recency.
2. If multiple interactive sessions exist for the same task, the UI only offers `Live` for the currently active step session.
3. `Live` attach works for both Claude Code and Codex step executions when their sessions are running in the backend.
4. If the active step belongs to a different agent/provider than the visible task shell suggests, the `Live` surface shows the real executing agent/provider identity clearly.
5. If no valid active-step interactive session exists, the task detail must not attach to a stale or unrelated session.
6. Existing chat-scoped TUI sessions remain unaffected.

## Success Metrics

- 100% of focused tests for task-detail live-session selection reject stale or mismatched sessions
- Browser validation confirms `Live` opens the correct agent/provider session for Claude Code and Codex
- No task-detail `Live` attach path relies on recency-only session selection after this story

## Tasks / Subtasks

- [x] Task 1: Tighten runtime/session identity for task-step execution (AC: #1, #2, #5)
  - [x] Ensure step-owned interactive sessions persist enough metadata to uniquely identify the active step execution
  - [x] Reuse existing interactive session metadata rather than inventing a second task-live registry
  - [x] Add focused backend tests for active-step session lookup and stale-session rejection

- [x] Task 2: Fix task-detail `Live` discovery and labeling (AC: #1, #2, #4, #5)
  - [x] Update dashboard live-session selection to match the active step and real provider/agent
  - [x] Surface the executing provider/agent identity in the task-detail header or `Live` tab
  - [x] Add focused dashboard tests for mismatched-session rejection and correct labeling

- [x] Task 3: Validate Claude and Codex `Live` flows (AC: #3, #6)
  - [x] Validate Claude step execution opens the correct `Live` session
  - [x] Validate Codex step execution opens the correct `Live` session
  - [x] Capture Playwright screenshots for the working task-detail `Live` flows

## Dev Notes

- Do not use “latest session wins” heuristics for step execution.
- Keep chat-scoped TUI behavior separate from step-scoped `Live`.
- Avoid exposing attach tokens in browser queries; continue using runtime-owned attach authorization.

### Project Structure Notes

- Likely touch points:
  - `mc/contexts/interactive/`
  - `mc/application/execution/`
  - `dashboard/features/interactive/`
  - `dashboard/features/tasks/`
  - `tests/mc/`
  - `dashboard/components/` and `dashboard/features/.../*.test.tsx`

### References

- [Source: docs/plans/2026-03-13-tui-execution-supervision-plan.md]
- [Source: docs/plans/2026-03-12-interactive-agent-tui-design.md]
- [Source: mc/contexts/interactive/registry.py]
- [Source: dashboard/features/interactive/hooks/useTaskInteractiveSession.ts]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
