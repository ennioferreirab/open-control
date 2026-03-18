# Story 27.11: Add Interactive Execution Migration Controls and Metrics

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control platform owner,
I want rollout controls and metrics for interactive execution,
so that we can make TUI-backed execution the default safely while preserving headless fallback where needed.

## Acceptance Criteria

1. An explicit execution mode resolver exists so interactive execution can be:
   - the default for interactive-capable providers
   - disabled only by deliberate configuration or provider choice
   - observed clearly by operators
2. Interactive execution emits operator-visible activity for:
   - session created
   - supervision ready
   - paused for review
   - resumed after reply
   - completed
   - crashed
3. Metrics or counters exist for:
   - interactive startup success/failure
   - session crash rate
   - live reattach success
   - ask-user pause/resume count
4. Unsupported, disabled, or failed interactive startup cases surface clearly
   to operators instead of silently falling back to headless.
5. Full-stack validation covers the migration path with the supported startup command and browser validation.
6. Existing headless and remote-terminal flows remain unaffected.

## Success Metrics

- Interactive execution mode resolution is deterministic in 100% of covered tests
- All major rollout events create visible activity records in focused tests
- Fallback to headless succeeds for unsupported/disabled cases in all covered tests

## Tasks / Subtasks

- [ ] Task 1: Add explicit interactive-first execution mode resolution (AC: #1, #4)
  - [ ] Add explicit settings or config for interactive execution rollout
  - [ ] Surface unsupported or failed interactive startup clearly to operators
  - [ ] Add focused tests for resolution and failure behavior

- [ ] Task 2: Add observability and metrics (AC: #2, #3)
  - [ ] Emit activity events for the interactive rollout lifecycle
  - [ ] Add counters or measurement points for startup, crash, reattach, and ask-user pause/resume
  - [ ] Add focused backend tests for observability output

- [ ] Task 3: Run migration validation (AC: #5, #6)
  - [ ] Validate through the full MC stack
  - [ ] Run browser validation via `playwright-cli`
  - [ ] Run Python and dashboard guardrails and record residual risk

## Dev Notes

- This story controls rollout. It should not re-architect the execution engine again.
- Reuse existing activity/event infrastructure where possible; do not create a
  second observability channel without clear need.
- Keep remote-agent terminal bridge ownership unchanged.

### Project Structure Notes

- Likely touch points:
  - `mc/runtime/`
  - `mc/contexts/execution/`
  - `mc/contexts/interactive/`
  - `tests/mc/`
  - possibly dashboard read models if new activity summaries are surfaced

### References

- [Source: docs/plans/2026-03-13-tui-execution-supervision-plan.md]
- [Source: docs/plans/2026-03-12-interactive-agent-tui-design.md]
- [Source: docs/ARCHITECTURE.md]
- [Source: mc/runtime/gateway.py]
- [Source: mc/contexts/execution/executor.py]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
