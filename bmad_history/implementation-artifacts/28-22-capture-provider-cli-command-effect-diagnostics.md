# Story 28.22: Capture Provider CLI Command Effect Diagnostics

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want every provider-cli control command to leave a durable backend diagnostic trail,
so that I can prove whether `interrupt`, `stop`, or `resume` was requested, applied, or failed without relying on gateway logs.

## Acceptance Criteria

1. Every `interrupt`, `stop`, and `resume` request persists command diagnostics in backend state.
2. Backend state distinguishes at least `requested`, `applied`, and `failed` outcomes.
3. Command diagnostics are queryable from `interactiveSessions` and/or `sessionActivityLog`.
4. Failures carry actionable error text instead of generic status-only transitions.

## Tasks / Subtasks

- [ ] Add failing tests for command-effect diagnostics
- [ ] Persist command lifecycle metadata in session state
- [ ] Append command lifecycle events to backend activity log

## Dev Notes

- Backend-first story.
- This is the operator audit trail for real process control.
- Do not depend on dashboard controls or rendering for proof.

## References

- [Source: docs/plans/2026-03-15-provider-cli-live-observability-and-intervention-plan.md]
- [Source: docs/plans/2026-03-15-provider-cli-live-observability-and-intervention-wave-plan.md]
