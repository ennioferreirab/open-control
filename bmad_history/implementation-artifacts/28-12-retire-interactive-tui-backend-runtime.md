# Story 28.12: Retire Interactive TUI Backend Runtime

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want the obsolete backend interactive TUI runtime removed after provider-cli cutover,
so that the backend no longer carries tmux/PTY ownership for supported step execution.

## Acceptance Criteria

1. Supported backend step execution no longer imports or instantiates the legacy interactive runtime.
2. `TmuxSessionManager` is not part of the supported execution path.
3. Legacy PTY/tmux modules are removed or hard-disabled and covered by backend tests.
4. No dashboard/frontend work is required in this story.

## Tasks / Subtasks

- [ ] Remove or hard-disable backend legacy runtime modules
- [ ] Remove supported-path uses of tmux/PTY transport
- [ ] Add backend retirement tests and architecture checks

## Dev Notes

- Prefer deletion over long-lived compatibility layers.
- Do not land this story before 28.8 through 28.11 are green.
- **BLOCKED** until the backend-only no-tmux proof (Story 28-15) is green.

## References

- [Source: docs/plans/2026-03-15-provider-cli-backend-cutover-recovery-plan.md]
- [Source: docs/plans/2026-03-15-provider-cli-backend-cutover-recovery-wave-plan.md]
- [Prerequisite: 28-15-prove-provider-cli-step-execution-backend-only.md]
