# Story 27.6: Build Interactive Supervision Contract and Runtime Sink

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control runtime owner,
I want a provider-agnostic supervision contract above the interactive TUI runtime,
so that task and step lifecycle can be driven by structured events instead of raw terminal output.

## Acceptance Criteria

1. A canonical interactive supervision event contract exists under `mc.contexts.interactive`
   and supports at least:
   - `session_started`
   - `session_ready`
   - `turn_started`
   - `turn_completed`
   - `item_started`
   - `item_completed`
   - `approval_requested`
   - `user_input_requested`
   - `paused_for_review`
   - `session_failed`
   - `session_stopped`
2. A runtime-owned supervisor consumes those normalized events and updates
   interactive session metadata, task status, and step status through the bridge.
3. The supervisor marks the active step `in_progress` from structured lifecycle
   events instead of inferring progress from terminal bytes.
4. The new supervision layer does not change existing headless execution flows
   or the websocket PTY transport contract.
5. Focused backend tests cover event normalization and supervisor-driven
   task/step state changes.

## Success Metrics

- 100% of targeted supervision tests pass without relying on terminal parsing
- A `turn_started` event moves the owning step to `in_progress` in all covered tests
- No existing interactive transport tests require updates because of protocol breakage

## Tasks / Subtasks

- [ ] Task 1: Define the normalized supervision types (AC: #1)
  - [ ] Add provider-agnostic supervision event types and payload fields
  - [ ] Extend interactive type exports without reintroducing root facades
  - [ ] Add focused tests for event normalization and validation

- [ ] Task 2: Add the runtime-owned supervision sink (AC: #2, #3, #4)
  - [ ] Create a supervisor that receives normalized events and updates bridge-owned state
  - [ ] Record active `task_id` and `step_id` ownership per interactive session
  - [ ] Ensure the websocket PTY transport remains byte-oriented and supervision-free

- [ ] Task 3: Verify architecture boundaries (AC: #4, #5)
  - [ ] Keep runtime wiring in `mc/runtime/`
  - [ ] Keep behavior ownership in `mc/contexts/interactive/`
  - [ ] Run focused backend tests plus architecture guardrails

## Dev Notes

- This story is the foundation for provider-specific supervision. Do not add
  Claude- or Codex-specific logic here.
- Reuse the current interactive runtime and session registry rather than adding
  a second session store.
- Do not parse the TUI screen for lifecycle while structured provider signals
  are available in later stories.

### Project Structure Notes

- Likely touch points:
  - `mc/contexts/interactive/`
  - `mc/runtime/`
  - `tests/mc/`
- Keep Convex-facing state changes behind the bridge boundary.

### References

- [Source: docs/plans/2026-03-13-tui-execution-supervision-plan.md]
- [Source: docs/plans/2026-03-12-interactive-agent-tui-design.md]
- [Source: docs/ARCHITECTURE.md]
- [Source: mc/contexts/interactive/coordinator.py]
- [Source: mc/runtime/interactive.py]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
