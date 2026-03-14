# Story 28.5: Build Live Chat Surface for Chat and Steps

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control user,
I want one live chat surface for both agent chat and step live share,
so that I can watch provider output in real time without opening a remote TUI.

## Acceptance Criteria

1. A unified live chat panel exists and renders normalized provider output in
   real time.
2. The same UI component powers:
   - interactive agent chat live share
   - step live share in task details
3. The UI shows session metadata and state without exposing terminal-only
   affordances such as terminal attach tokens or TUI tabs.
4. The live chat surface can show provider output from the new live stream
   projector without requiring xterm or browser terminal emulation.
5. Focused dashboard tests cover reuse in chat and step contexts plus core live
   rendering states.
6. `Live` binds to the canonical provider session for the active chat/step and
   not to terminal attach state, tmux session names, or PTY-only metadata.

## Success Metrics

- Chat and step live share visibly use the same component boundary.
- No user-facing live-share flow still depends on `InteractiveTerminalPanel`.
- Focused dashboard tests cover loading, streaming, and empty-state rendering.

## Tasks / Subtasks

- [ ] Task 1: Build the unified live chat panel (AC: #1, #4)
  - [ ] Create the shared panel component
  - [ ] Render streamed provider output and basic session status
  - [ ] Keep terminal emulation concerns out of scope
  - [ ] Add focused component tests

- [ ] Task 2: Integrate the panel into chat and task step surfaces (AC: #2, #3)
  - [ ] Route interactive chat to the unified live chat surface
  - [ ] Route step live share to the same component
  - [ ] Remove or hide TUI-first tabs from the primary user path
  - [ ] Bind the surface to the active provider session record for the correct
        step, agent, and provider
  - [ ] Add focused integration tests

- [ ] Task 3: Run focused guardrails (AC: #5)
  - [ ] Run dashboard-focused tests for the panel
  - [ ] Run dashboard lint/format checks
  - [ ] Record any remaining runtime dependencies explicitly

## Dev Notes

- This is a live-share UI story, not a terminal emulation story.
- Prefer explicit provider session status and streamed text over terminal
  metaphors.
- Keep feature ownership inside `dashboard/features/interactive/` and
  `dashboard/features/tasks/`.
- The browser surface must treat the MC-owned provider session as the source of
  truth; terminal transport artifacts are not valid selectors.

### Project Structure Notes

- Likely touch points:
  - `dashboard/features/interactive/components/`
  - `dashboard/components/ChatPanel.tsx`
  - `dashboard/features/tasks/components/TaskDetailSheet.tsx`
  - `dashboard/features/interactive/hooks/`
  - `dashboard/features/tasks/hooks/`

### References

- [Source: docs/plans/2026-03-14-provider-cli-parser-design.md]
- [Source: docs/plans/2026-03-14-provider-cli-parser-plan.md]
- [Source: docs/ARCHITECTURE.md]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
