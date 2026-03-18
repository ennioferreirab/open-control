# Story 27.3: Embed Interactive TUI Tab in Chat Panel

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control user,
I want a `TUI` tab inside the Chat panel for interactive-capable agents,
so that I can switch between chat history and the live terminal session in the
same agent context.

## Acceptance Criteria

1. The Chat panel adds a `TUI` tab for interactive-capable agents while keeping
   the existing chat experience unchanged for non-interactive agents.
2. The `TUI` tab uses a real browser terminal emulator, not a `<pre>`-style
   text dump.
3. Opening the `TUI` tab creates or reattaches to an interactive session
   through the new runtime from Stories 27.1 and 27.2.
4. Browser refresh or transient disconnect reattaches to the same live session
   when it still exists.
5. The POC scope for this story is Chat only:
   - no Task Detail TUI
   - no Board-area TUI
   - no replacement of the remote terminal panel
6. Manual validation in the full MC stack demonstrates that native Claude Code
   terminal behaviors work inside the browser:
   - autocomplete
   - interactive prompts/questions
   - command or menu navigation

## Success Metrics

- Local keystroke-to-render latency p95 <= 150 ms
- Opening the `TUI` tab to first usable prompt <= 5 seconds
- Reattach after browser refresh succeeds in >= 95% of local validation runs
- Existing Chat panel behavior for non-interactive agents has zero regressions

## Tasks / Subtasks

- [ ] Task 1: Add a dedicated interactive terminal feature owner in the dashboard (AC: #1, #2)
  - [ ] Create feature-owned hooks/components for terminal session attach and rendering
  - [ ] Keep `ChatPanel` as a shell, not the owner of transport details
  - [ ] Avoid direct Convex byte-stream coupling in shared/root components

- [ ] Task 2: Add the Chat panel TUI surface (AC: #1, #3, #5)
  - [ ] Add `Chat` and `TUI` tabs to the selected-agent chat view
  - [ ] Show the `TUI` tab only when the selected agent advertises interactive capability
  - [ ] Preserve the existing message history and composer behavior

- [ ] Task 3: Attach the browser terminal to the interactive runtime (AC: #2, #3, #4)
  - [ ] Use a real terminal emulator component in the browser
  - [ ] Implement connect, reconnect, resize, and detach behavior
  - [ ] Surface clear runtime errors to the user

- [ ] Task 4: Add validation and regression coverage (AC: #4, #6)
  - [ ] Add focused dashboard tests for tab visibility and attach state
  - [ ] Validate the full MC stack using the supported `nanobot mc start` path
  - [ ] Use `playwright-cli` for browser validation and record evidence

## Dev Notes

- The existing `TerminalPanel` is useful precedent for shell chrome and status
  display, but it is not the correct renderer for this story because it is not
  a VT-compatible browser terminal.
- Keep interactive terminal ownership in a feature module, not in
  `dashboard/components/` or root hooks.
- Do not let this story reintroduce direct `convex/react` coupling into shared
  shells that Epic 22/23 intentionally removed.

### Project Structure Notes

- Likely touch points:
  - `dashboard/components/ChatPanel.tsx`
  - `dashboard/components/ChatMessages.tsx`
  - `dashboard/features/interactive/`
  - `dashboard/tests/architecture.test.ts`
- Useful existing reference surfaces:
  - `dashboard/components/TerminalPanel.tsx`
  - `dashboard/features/terminal/components/TerminalBoard.tsx`
  - `dashboard/features/tasks/components/TaskDetailSheet.tsx`

### References

- [Source: dashboard/components/ChatPanel.tsx]
- [Source: dashboard/components/ChatMessages.tsx]
- [Source: dashboard/components/TerminalPanel.tsx]
- [Source: dashboard/features/terminal/components/TerminalBoard.tsx]
- [Source: dashboard/features/tasks/components/TaskDetailSheet.tsx]
- [Source: _bmad-output/implementation-artifacts/23-1-extract-task-detail-tabs-and-shrink-task-detail-sheet.md]
- [Source: _bmad-output/implementation-artifacts/23-2-finish-dashboard-shell-feature-ownership-for-agents-activity-and-terminal.md]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
