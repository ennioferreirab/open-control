# Story 27.8: Integrate Codex App-Server Supervision

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control operator,
I want Codex interactive sessions to be supervised from structured app-server events,
so that Codex can participate in the same TUI execution model without Claude-specific assumptions.

## Acceptance Criteria

1. The Codex interactive adapter gains a structured supervision path based on
   Codex app-server notifications and requests, not raw terminal scraping.
2. Codex supervision covers at least:
   - turn started
   - turn completed
   - item started
   - item completed
   - approval requested
   - request-user-input / elicitation
3. Codex app-server events are normalized into the same internal supervision
   contract used by Claude hooks.
4. The terminal `Live` attach flow remains independent from the supervision
   event stream, so attaching does not create or own the work session.
5. If structured Codex supervision cannot start, Mission Control fails cleanly
   with a provider-specific error rather than silently degrading to screen scraping
   or headless execution.
6. Focused tests cover event mapping and failure handling for the Codex path.

## Success Metrics

- 100% of supported Codex event fixtures map into the shared supervision contract
- Codex supervision startup failures surface a provider-specific error in all covered tests
- No new TUI parsing heuristics are introduced for Codex lifecycle tracking

## Tasks / Subtasks

- [ ] Task 1: Add a Codex supervision relay (AC: #1, #2, #3)
  - [ ] Launch or connect to the Codex app-server protocol for supervised sessions
  - [ ] Map turn, item, approval, and user-input events into normalized MC events
  - [ ] Add focused tests for event mapping and unsupported-event handling

- [ ] Task 2: Keep supervision decoupled from terminal attach (AC: #4)
  - [ ] Ensure the backend session can run with no attached browser
  - [ ] Keep `Live` attach as an optional viewer/controller over the running session
  - [ ] Add regression coverage proving attach does not create the Codex work session

- [ ] Task 3: Add clean failure paths (AC: #5, #6)
  - [ ] Surface startup/configuration failures explicitly in provider errors
  - [ ] Avoid terminal-screen fallback for lifecycle
  - [ ] Run focused backend tests plus architecture guardrails

## Dev Notes

- Codex supervision should use the structured app-server path, even if the TUI
  remains the interactive terminal surface.
- Keep provider-specific protocol handling inside the Codex adapter; do not leak
  app-server protocol details into runtime or dashboard modules.
- This story is not about UI changes.

### Project Structure Notes

- Likely touch points:
  - `mc/contexts/interactive/adapters/codex.py`
  - new provider-specific support under `mc/contexts/interactive/adapters/`
  - `tests/mc/`

### References

- [Source: docs/plans/2026-03-13-tui-execution-supervision-plan.md]
- [Source: docs/plans/2026-03-12-interactive-agent-tui-design.md]
- [Source: docs/ARCHITECTURE.md]
- [Source: mc/contexts/interactive/adapters/codex.py]
- [Source: `codex app-server generate-json-schema` output validated locally during planning]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
