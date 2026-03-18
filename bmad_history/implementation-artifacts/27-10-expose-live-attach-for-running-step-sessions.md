# Story 27.10: Expose Live Attach for Running Step Sessions

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control operator,
I want to click `Live` from the running step context and attach to the existing TUI session,
so that I can observe or intervene without becoming the owner of the execution.

## Acceptance Criteria

1. Running interactive steps expose reusable session metadata so the dashboard
   can attach to the existing live session instead of creating a new one.
2. `Live` attach works from the relevant task/thread surface and reconnects to
   the backend-owned session for the active step.
3. Closing the live panel or disconnecting the browser does not stop the
   underlying step execution.
4. The dashboard surfaces when a running step is:
   - live and attachable
   - detached but still running
   - paused in `review`
5. Full-stack verification uses `uv run nanobot mc start` and browser
   validation via `playwright-cli`.
6. Existing chat-only TUI behavior remains functional while step-owned attach is added.

## Success Metrics

- `Live` attaches to the existing session in 100% of covered UI tests
- Closing the TUI panel leaves the session running in all covered full-stack validations
- Operators can tell whether a step is paused in review without opening the terminal

## Tasks / Subtasks

- [ ] Task 1: Expose step-owned interactive session metadata (AC: #1, #2)
  - [ ] Extend interactive session read models for step ownership
  - [ ] Add a feature hook for resolving the active step session
  - [ ] Add focused tests for metadata lookup and session reuse

- [ ] Task 2: Wire `Live` attach to the running session (AC: #2, #3, #4)
  - [ ] Update task/thread surfaces to attach to an existing session id
  - [ ] Keep attach/detach UI separate from start/stop execution actions
  - [ ] Surface paused-review and detached-running states in the UI

- [ ] Task 3: Run full-stack browser validation (AC: #5, #6)
  - [ ] Validate through the full MC stack, not a frontend-only dev server
  - [ ] Capture Playwright screenshots for running, attached, paused-review, and resumed states
  - [ ] Run focused dashboard tests plus architecture guardrails

## Dev Notes

- This story is about session reuse and UI attach, not execution ownership.
- Do not create a second websocket channel just for steps if the interactive
  runtime can be reused.
- Prefer feature-owned dashboard hooks and components; avoid reaching directly
  into Convex from presentation components.

### Project Structure Notes

- Likely touch points:
  - `dashboard/features/interactive/`
  - `dashboard/features/tasks/`
  - `dashboard/components/ChatPanel.tsx`
  - `dashboard/convex/interactiveSessions.ts`

### References

- [Source: docs/plans/2026-03-13-tui-execution-supervision-plan.md]
- [Source: docs/ARCHITECTURE.md]
- [Source: dashboard/features/interactive/components/InteractiveTerminalPanel.tsx]
- [Source: dashboard/features/tasks/components/TaskDetailSheet.tsx]
- [Source: mc/contexts/interactive/registry.py]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
