# Story 28.9: Run Claude Steps Through Provider CLI Core

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want Claude steps to run through the provider-cli process core,
so that supported step execution no longer depends on tmux-backed interactive TUI sessions.

## Acceptance Criteria

1. Claude step startup runs through the provider-cli runtime path.
2. The bootstrap prompt starts execution without tmux-backed session injection.
3. Focused backend tests prove a Claude step can start on the provider-cli path.
4. No dashboard/frontend work is required in this story.

## Tasks / Subtasks

- [ ] Route Claude steps through provider-cli process/session lifecycle
- [ ] Preserve bootstrap, parsing, and provider event normalization
- [ ] Add focused backend tests for startup and execution

## Dev Notes

- This is the first real tmux-removal milestone.
- The story is not complete if Claude still needs tmux on the supported path.

## References

- [Source: docs/plans/2026-03-15-provider-cli-backend-cutover-recovery-plan.md]
- [Source: docs/plans/2026-03-15-provider-cli-backend-cutover-recovery-wave-plan.md]
