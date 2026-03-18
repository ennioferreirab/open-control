# Story 27.1: Build Interactive Session Runtime Foundation

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control platform maintainer,
I want a provider-agnostic interactive session runtime that owns PTY-backed
terminal sessions separately from headless execution,
so that native TUIs can run inside MC without changing the existing automated
execution path.

## Acceptance Criteria

1. A new interactive session metadata model exists and is kept separate from:
   - headless `cc_session:*` settings
   - existing `terminalSessions` docs used by the remote terminal bridge
2. The MC runtime can create, attach to, list, and terminate a reconnectable
   PTY-backed interactive session identified by provider, agent, and scope.
3. Interactive terminal bytes flow through a bidirectional runtime-owned socket
   channel, not through Convex polling or message documents.
4. `tmux` (or an equivalent reconnectable terminal session manager explicitly
   approved in code review) is used so browser reconnects can reattach to the
   same live process.
5. Existing headless Claude Code task, step, and chat flows behave exactly as
   before and keep their tests green.
6. Architecture or focused regression tests fail if a future change tries to:
   - route terminal bytes through Convex
   - reuse headless CC session storage for interactive mode
   - overload the remote `terminalSessions` bridge for the new runtime

## Success Metrics

- Local session bootstrap to attachable state <= 3 seconds
- Local reattach to existing live session <= 2 seconds
- Local keystroke-to-render latency p95 <= 150 ms on the runtime test harness
- Zero regression failures in existing headless CC task/chat/step suites

## Tasks / Subtasks

- [ ] Task 1: Define the interactive session domain and metadata contract (AC: #1, #2)
  - [ ] Add a new metadata owner for interactive sessions instead of extending `terminalSessions`
  - [ ] Add provider, agent, scope, capability, status, and last-activity fields
  - [ ] Add read/write helpers that keep interactive session ids separate from `cc_session:*`

- [ ] Task 2: Implement PTY plus tmux lifecycle infrastructure (AC: #2, #4)
  - [ ] Create infrastructure helpers for PTY spawn, tmux session creation, attach, and cleanup
  - [ ] Add reconnect semantics based on runtime session id and tmux session name
  - [ ] Add shutdown cleanup and orphan-handling tests

- [ ] Task 3: Implement the runtime transport channel (AC: #2, #3)
  - [ ] Add a runtime-owned bidirectional socket channel for terminal bytes
  - [ ] Add attach, detach, resize, input, and output events
  - [ ] Ensure Convex only stores metadata and discovery state

- [ ] Task 4: Wire the runtime into the supported MC startup path (AC: #2, #3, #5)
  - [ ] Start the interactive runtime or sidecar from `nanobot mc start`
  - [ ] Keep the unsupported frontend-only startup path out of validation
  - [ ] Verify the headless runtime remains untouched

- [ ] Task 5: Add guardrails and verification (AC: #5, #6)
  - [ ] Add focused tests that assert interactive and headless session isolation
  - [ ] Add architecture assertions that block Convex byte-streaming shortcuts
  - [ ] Run relevant Python and dashboard guardrails plus focused tests

## Dev Notes

- Reuse the remote terminal bridge only as a source of lifecycle lessons, not as
  the runtime contract for the new feature.
- Prefer the documented ownership model in `docs/ARCHITECTURE.md`:
  - runtime wiring in `mc/runtime/`
  - session behavior in `mc/contexts/interactive/`
  - terminal/tmux transport in `mc/infrastructure/interactive/`
- Prefer the existing `websockets` dependency already present through the
  Nanobot environment before introducing a second real-time transport stack.
- Do not touch `vendor/claude-code/claude_code/provider.py` in this story.

### Project Structure Notes

- Likely backend touch points:
  - `mc/runtime/`
  - `mc/contexts/interactive/`
  - `mc/infrastructure/interactive/`
  - `dashboard/convex/schema.ts`
  - `dashboard/convex/interactiveSessions.ts`
- Keep remote-terminal ownership intact:
  - `terminal_bridge.py`
  - `dashboard/convex/terminalSessions.ts`
  - `dashboard/components/TerminalPanel.tsx`

### References

- [Source: docs/ARCHITECTURE.md]
- [Source: terminal_bridge.py]
- [Source: dashboard/convex/terminalSessions.ts]
- [Source: vendor/nanobot/pyproject.toml]
- [Source: _bmad-output/implementation-artifacts/tech-spec-remote-terminal-bridge.md]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
