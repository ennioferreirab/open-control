# Story 27.9: Make Interactive TUI the Primary Step Execution Strategy

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control execution owner,
I want interactive-capable providers to run steps through the backend-owned TUI runtime by default,
so that work can continue off-screen and the dashboard can attach live only when needed.

## Acceptance Criteria

1. A dedicated interactive step execution strategy exists and can be selected
   for interactive-capable providers without reusing the headless provider contract.
2. Running a TUI-backed step creates a backend-owned interactive session mapped
   to the active `task_id` and `step_id`.
3. Step completion, failure, and crash handling are driven by the supervision
   layer rather than terminal websocket state.
4. No browser attach is required for a TUI-backed step to execute end-to-end.
5. Interactive-capable providers use the interactive TUI runtime as the default
   execution path, and Mission Control does not silently fall back to headless
   when interactive startup fails.
6. Focused tests cover strategy selection, task/step-to-session mapping, and
   supervisor-driven completion/crash behavior.

## Success Metrics

- Interactive-capable providers resolve to the interactive strategy in 100% of covered selection tests
- A running interactive step remains alive after closing the UI in all covered tests
- No strategy test depends on a browser websocket for step completion

## Tasks / Subtasks

- [ ] Task 1: Add a new interactive step execution strategy (AC: #1, #2)
  - [ ] Create a strategy under `mc/application/execution/strategies/`
  - [ ] Map running task/step records to interactive session ids
  - [ ] Update dispatcher selection logic without breaking unsupported providers

- [ ] Task 2: Drive lifecycle from supervision (AC: #3, #4)
  - [ ] Start provider supervision before any UI attach
  - [ ] Resolve completion and failure from supervision events
  - [ ] Keep websocket close/detach separate from work completion

- [ ] Task 3: Enforce interactive-first execution semantics (AC: #5, #6)
  - [ ] Add an explicit mode resolution path for interactive-capable providers
  - [ ] Surface startup/configuration failures instead of silently switching to headless
  - [ ] Add focused tests and guardrails

## Dev Notes

- This story changes execution ownership. Be careful not to let `ChatPanel`,
  `InteractiveTerminalPanel`, or websocket lifecycle become the authority for
  step state.
- Reuse the interactive session registry; do not create a second per-step
  session store if the existing metadata can be extended.
- Headless stays in the codebase as a separate mode, but it must not become a
  hidden recovery path for interactive-capable providers after this story.

### Project Structure Notes

- Likely touch points:
  - `mc/application/execution/strategies/`
  - `mc/contexts/execution/`
  - `mc/contexts/interactive/`
  - `tests/mc/`

### References

- [Source: docs/plans/2026-03-13-tui-execution-supervision-plan.md]
- [Source: docs/ARCHITECTURE.md]
- [Source: mc/contexts/execution/step_dispatcher.py]
- [Source: mc/contexts/execution/cc_step_runner.py]
- [Source: mc/application/execution/strategies/claude_code.py]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
