# Story 28.0b: Stabilize Interactive Supervision and State Projection

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want interactive supervision events to project cleanly into Convex and
workflow state,
so that provider lifecycle events do not crash the pipeline or hide real
errors before the provider CLI migration.

## Acceptance Criteria

1. `sessionActivityLog:append` payloads omit optional string fields when they
   are absent instead of sending `null`.
2. Focused tests prove the session activity payload shape for covered
   supervision events.
3. Repeated interactive lifecycle events do not attempt invalid same-status
   transitions such as `in_progress -> in_progress` or `running -> running`.
4. Same-status lifecycle handling is explicit and idempotent, not hidden behind
   a generic broad exception swallow.
5. Unexpected task or step mutation failures still surface clearly in logs or
   tests and are not silently masked as successful supervision.
6. Focused tests cover the payload contract, idempotent transition behavior,
   and non-idempotent failure behavior.
7. The idempotent same-status matcher is proven against the real Convex error
   text format `Cannot transition from '<status>' to '<status>'`, not only a
   shorthand mock string.

## Success Metrics

- No covered supervision event crashes because Convex received `null` for an
  optional string
- No covered repeated lifecycle event causes invalid same-status transition
  errors
- Focused tests distinguish expected idempotency from real mutation failures

## Tasks / Subtasks

- [ ] Task 1: Lock session activity payload serialization (AC: #1, #2)
  - [ ] Add focused tests for optional field omission
  - [ ] Confirm required fields remain present and correctly named
  - [ ] Keep Convex-facing payload construction explicit

- [ ] Task 2: Make lifecycle projection idempotent (AC: #3, #4)
  - [ ] Add focused tests for repeated running/started events
  - [ ] Add a regression test using the real Convex message format for
        `in_progress -> in_progress`
  - [ ] Implement explicit same-status handling
  - [ ] Avoid generic `except Exception: pass` for expected idempotency

- [ ] Task 3: Preserve visibility of genuine failures (AC: #5, #6)
  - [ ] Add focused regression coverage for unexpected bridge failures
  - [ ] Ensure unexpected errors remain observable

## Dev Notes

- This story is a stabilization pass over the current runtime, not the final
  process-based design.
- Prefer precise suppression of same-status cases over blanket exception
  swallowing.
- This story is not done until the matcher works against the exact Convex error
  shape already observed in gateway logs.

### Project Structure Notes

- Likely touch points:
  - `mc/contexts/interactive/supervisor.py`
  - `mc/bridge/repositories/tasks.py`
  - `mc/bridge/repositories/steps.py`
  - `tests/mc/test_interactive_supervisor.py`
  - `tests/mc/bridge/`

### References

- [Source: docs/plans/2026-03-14-interactive-runtime-stabilization-and-provider-cli-migration-plan.md]
- [Source: mc/contexts/interactive/supervisor.py]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
