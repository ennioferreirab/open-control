# Story 28.15: Prove Provider CLI Step Execution Backend-Only

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want a backend-only proof that a supported step runs through `provider-cli` without `tmux`,
so that the cutover is backed by the real execution path instead of only synthetic unit seams.

## Acceptance Criteria

1. A backend-only test covers the real provider-cli step path from request construction to completion or crash.
2. The supported path proves absence of `tmux` dependency.
3. The test verifies prompt presence and correct runner selection.
4. No dashboard/frontend work is required in this story.

## Tasks / Subtasks

- [ ] Add an integration-style backend test for provider-cli step execution
- [ ] Verify no supported path dependency on `interactive_session_coordinator` or `tmux`
- [ ] Verify completion/crash behavior on the supported path

## Dev Notes

- If `LiveStreamProjector` is part of the runtime claim, prove its usage here; otherwise explicitly keep it out of scope.
- This story is the backend proof gate before reopening default flip and retirement.

## References

- [Source: docs/plans/2026-03-15-provider-cli-cutover-remediation-plan.md]
- [Source: docs/plans/2026-03-15-provider-cli-cutover-remediation-wave-plan.md]
