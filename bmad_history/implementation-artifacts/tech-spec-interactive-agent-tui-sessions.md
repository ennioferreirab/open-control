# Tech Spec: Interactive Agent TUI Sessions

Status: ready-for-dev

## Story

As a Mission Control user,
I want to open a provider's native interactive TUI inside Mission Control,
so that I can keep the terminal-native experience while still using MC as the
coordination layer across agents, projects, and progress.

## Problem

Mission Control currently integrates Claude Code through a headless subprocess
contract. That path is strong for automation, but it cannot preserve the native
TUI experience: autocomplete, command palette, interactive follow-up prompts,
alternate-screen behavior, and live visibility into what the agent is doing.

The repository already has a remote terminal bridge, but that bridge is built
for monitoring and lightweight interaction through Convex-backed polling. It is
not a true PTY-backed browser terminal and should not be stretched into the new
interactive TUI runtime.

## Goals

1. Add a real interactive session runtime backed by PTY plus reconnectable
   `tmux` sessions.
2. Keep the new interactive mode fully separate from the existing headless
   execution path.
3. Ship the first visible POC as a `TUI` tab in the Chat panel.
4. Make the runtime provider-agnostic so Claude Code is first, not special.
5. Reuse the same infrastructure later for Codex and future CLI-based agents.

## Non-Goals

- No replacement of the current headless Claude Code backend
- No replacement of the remote terminal bridge
- No Convex-based terminal byte transport
- No board/task-detail UI requirement in the first POC
- No speculative abstraction unrelated to interactive terminal lifecycle

## Architecture

### Backend ownership

- `mc/contexts/interactive/`: session behavior and orchestration
- `mc/infrastructure/interactive/`: PTY/tmux/socket helpers
- `mc/runtime/`: startup wiring for the interactive runtime or sidecar

### Frontend ownership

- `dashboard/features/interactive/`: terminal hooks/components/session attach
- `dashboard/components/ChatPanel.tsx`: shell for `Chat` vs `TUI` tabs

### Data boundary

Convex should hold only interactive session metadata and discovery state. It
must not carry terminal bytes, screen polling, or keypress transport.

### Session identity

Interactive sessions must be stored separately from:

- `cc_session:*` settings used by headless Claude Code resume
- `terminalSessions` docs used by remote terminal agents

## Story Sequence

### Story 27.1: Build Interactive Session Runtime Foundation

Create the new metadata model, PTY/tmux lifecycle, socket transport, runtime
startup wiring, and architecture guardrails.

### Story 27.2: Add Claude Code Interactive Session Adapter

Launch Claude Code as a native TUI inside the new runtime while reusing CC
workspace/bootstrap logic where appropriate.

### Story 27.3: Embed Interactive TUI Tab in Chat Panel

Ship the first user-facing POC by attaching a real browser terminal to the
interactive runtime inside the Chat panel.

### Story 27.4: Generalize Interactive Adapter Contract and Add Codex Adapter

Lock the provider-agnostic contract and prove it by adding Codex support.

### Story 27.5: Harden Observability, Security, and Session Reuse

Add the operational guardrails and lifecycle visibility needed to scale the
feature beyond the POC.

#### Runtime hardening policy

- Reconnect authorization must use a runtime-issued `attachToken`, not a
  guessable `sessionId` alone.
- Runtime-only metadata can retain reconnect secrets; browser-safe queries must
  not expose them.
- Detached sessions older than 15 minutes should be treated as idle and cleaned
  up before launching a replacement process.
- Missing `tmux` sessions for otherwise live metadata should be treated as
  orphaned/crashed and folded into the lifecycle feed instead of silently
  relaunching.

## Success Metrics

### Fidelity

- Native Claude Code autocomplete works in the embedded browser TUI
- Native Claude Code interactive prompts/questions render and can be answered in
  the embedded TUI
- Terminal alternate-screen flows render without MC-specific hacks

### Performance

- Local keystroke-to-render latency p95 <= 150 ms
- Local attach or reattach latency <= 2 seconds
- New interactive session bootstrap to usable prompt <= 5 seconds

### Reliability

- Browser refresh reattaches to the same live session in >= 95% of local test
  runs
- Normal shutdown leaves no orphaned sessions in >= 90% of local test runs
- Headless Claude Code task/chat/step regressions remain at zero

### Reusability

- Codex support lands without changes to the web terminal renderer
- A future second interactive provider needs only a new adapter plus capability
  wiring, not a transport rewrite

## Key Risks and Guardrails

- Do not overload `terminalSessions` or the remote bridge with this feature.
- Do not add terminal byte streaming to Convex mutations/queries.
- Do not merge interactive and headless Claude Code session storage.
- Do not ship this feature validated only against `npm run dev`; use the full
  `nanobot mc start` stack.

## References

- [Source: docs/ARCHITECTURE.md]
- [Source: terminal_bridge.py]
- [Source: dashboard/components/TerminalPanel.tsx]
- [Source: dashboard/components/ChatPanel.tsx]
- [Source: vendor/claude-code/claude_code/provider.py]
- [Source: vendor/claude-code/claude_code/workspace.py]
- [Source: mc/contexts/execution/cc_executor.py]
- [Source: _bmad/bmm/workflows/4-implementation/create-story/checklist.md]
