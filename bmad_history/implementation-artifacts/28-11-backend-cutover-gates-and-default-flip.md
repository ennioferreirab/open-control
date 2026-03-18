# Story 28.11: Backend Cutover Gates And Default Flip

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want the default interactive execution mode flipped only after backend cutover gates are met,
so that provider-cli becomes the supported path without repeating the earlier rollback.

## Acceptance Criteria

1. `provider-cli` becomes the default only after backend tests prove the supported path is complete.
2. Any legacy escape hatch is explicit and temporary.
3. Focused backend tests prove the supported path no longer requires tmux.
4. No dashboard/frontend work is required in this story.

## Tasks / Subtasks

- [ ] Flip the default in `interactive_mode`
- [ ] Keep temporary escape hatch only if necessary
- [ ] Add backend gating tests for no-tmux supported execution

## Dev Notes

- This story is a control-plane gate, not a parser story.
- **BLOCKED** until Stories 28-13, 28-14, and 28-15 are green (remediation wave).

## References

- [Source: docs/plans/2026-03-15-provider-cli-backend-cutover-recovery-plan.md]
- [Source: docs/plans/2026-03-15-provider-cli-backend-cutover-recovery-wave-plan.md]
- [Prerequisite: 28-13-populate-canonical-provider-cli-prompt.md]
- [Prerequisite: 28-14-route-gateway-provider-cli-services-through-runtime.md]
- [Prerequisite: 28-15-prove-provider-cli-step-execution-backend-only.md]
