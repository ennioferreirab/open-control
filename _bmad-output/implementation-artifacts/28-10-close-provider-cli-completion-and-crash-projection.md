# Story 28.10: Close Provider CLI Completion And Crash Projection

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want provider-cli sessions to project completion, final result, and crash state correctly,
so that the new backend runtime is operationally trustworthy.

## Acceptance Criteria

1. Canonical `final_result` is recorded on successful completion.
2. Crash projection updates step/task state correctly.
3. Cleanup and session close behavior are covered by backend tests.
4. No dashboard/frontend work is required in this story.

## Tasks / Subtasks

- [ ] Close final-result projection on the provider-cli path
- [ ] Close crash projection on the provider-cli path
- [ ] Add backend tests for cleanup and state transitions

## Dev Notes

- This story should leave no ambiguity about how a provider-cli step ends.

## References

- [Source: docs/plans/2026-03-15-provider-cli-backend-cutover-recovery-plan.md]
- [Source: docs/plans/2026-03-15-provider-cli-backend-cutover-recovery-wave-plan.md]
