# Story 28.7: Retire Remote TUI UI and Runtime

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control maintainer,
I want the obsolete remote TUI UI and runtime paths removed or explicitly gated,
so that the new provider CLI live-share model is the only supported path and
the project is not polluted by dead terminal code.

## Acceptance Criteria

1. Chat and step live share no longer depend on the remote TUI terminal panel
   as the primary or fallback UX.
2. TUI-only UI affordances are removed or clearly gated for a short migration
   window, including:
   - `Chat | TUI` tabs
   - remote terminal attach affordances
   - TUI-only status badges or tokens
3. Backend PTY/websocket transport paths that exist only for the remote TUI are
   removed or clearly marked as transitional and disabled by default.
4. The old interactive TUI design doc is marked superseded and the current
   design and wave plan point to the provider CLI live-share path.
5. Focused tests and guardrails cover the absence of the old TUI-first wiring.
6. Supported interactive step execution no longer instantiates
   `TmuxSessionManager` on the production path.

## Success Metrics

- No user-facing default path still enters the remote TUI stack.
- The repo no longer contains silent parallel ownership for live-share between
  remote TUI and provider CLI live chat.
- Docs clearly state the TUI design is superseded.

## Tasks / Subtasks

- [ ] Task 1: Remove or gate the old TUI user path (AC: #1, #2)
  - [ ] Remove TUI-first tabs and terminal-panel routing from the main chat and
        step live-share surfaces
  - [ ] Delete dead UI references when safe
  - [ ] Add focused dashboard tests

- [ ] Task 2: Remove or gate obsolete backend transport paths (AC: #3)
  - [ ] Delete dead PTY/websocket runtime code when safe
  - [ ] If temporary gating is needed, disable it by default and document the
        migration boundary
  - [ ] Ensure supported interactive step execution no longer constructs the
        tmux-backed runtime in gateway/engine wiring
  - [ ] Add focused backend tests for the supported path

- [ ] Task 3: Align docs and run final guardrails (AC: #4, #5)
  - [ ] Mark the old TUI design doc as superseded
  - [ ] Keep the new design, plan, and wave plan aligned
  - [ ] Run dashboard and Python guardrails for touched files

## Dev Notes

- Prefer deletion over indefinite compatibility layers.
- If a temporary migration flag is required, it must be explicit, short-lived,
  and tracked for removal.
- Do not keep dormant xterm or websocket attach code “just in case”.
- The story is not complete while the production path still selects
  `RunnerType.INTERACTIVE_TUI` for supported providers.

### Project Structure Notes

- Likely touch points:
  - `dashboard/features/interactive/components/InteractiveChatTabs.tsx`
  - `dashboard/features/interactive/components/InteractiveTerminalPanel.tsx`
  - `dashboard/features/interactive/hooks/`
  - `dashboard/convex/interactiveSessions.ts`
  - `mc/runtime/interactive.py`
  - `mc/runtime/interactive_transport.py`
  - `tests/mc/`
  - `dashboard/features/interactive/components/`

### References

- [Source: docs/plans/2026-03-14-provider-cli-parser-design.md]
- [Source: docs/plans/2026-03-14-provider-cli-parser-plan.md]
- [Source: docs/plans/2026-03-12-interactive-agent-tui-design.md]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
