# Interactive Step Parity Validation

Date: 2026-03-13

## Scope

This validation pass closes Epic 27 by confirming that backend-owned interactive step execution is the default runtime model for supported providers without hidden fallback to headless execution.

Stories covered:

- 27.12 Bind `Live` sessions to the active step and correct agent
- 27.13 Capture canonical interactive results and post them to the thread
- 27.14 Add human takeover and manual step `Done` for Live execution
- 27.15 Complete interactive memory bootstrap and consolidation
- 27.16 Add Nanobot interactive `mc` Live support
- 27.17 Validate interactive step execution parity across providers

## Parity Checklist

| Provider | Step/Agent Ownership | Live Attach | Final Result to Thread | Ask User / Review | Memory Bootstrap + Consolidation | Hidden Fallback |
| --- | --- | --- | --- | --- | --- | --- |
| Claude Code | Validated | Validated | Validated | Validated via MCP `mcp__mc__ask_user` and review pause/resume | Validated | None in covered path |
| Codex | Validated | Validated | Validated | Not exercised as a structured `ask_user` flow in this pass | Validated | None in covered path |
| Nanobot (`mc`) | Validated | Validated | Validated | Manual takeover and manual `Done` validated | Validated | None in covered path |

## Evidence

### Automated Coverage

- Focused Python validation:
  - `tests/mc/application/execution/test_interactive_mode.py`
  - `tests/mc/application/execution/test_interactive_strategy.py`
  - `tests/mc/application/execution/test_post_processing.py`
  - `tests/mc/test_interactive_claude_adapter.py`
  - `tests/mc/test_interactive_codex_adapter.py`
  - `tests/mc/test_codex_app_server_adapter.py`
  - `tests/mc/test_interactive_nanobot_adapter.py`
  - `tests/mc/test_nanobot_interactive_session.py`
  - `tests/mc/test_interactive_session_registry.py`
  - `tests/mc/test_interactive_supervisor.py`
  - `tests/mc/test_yaml_validator.py`
  - `tests/cc/test_mcp_bridge.py`
  - `tests/cc/test_ipc_client.py`
  - `tests/cc/test_workspace.py`
- Focused dashboard validation:
  - `dashboard/convex/interactiveSessions.test.ts`
  - `dashboard/features/interactive/hooks/useTaskInteractiveSession.test.ts`
  - `dashboard/features/interactive/components/InteractiveTerminalPanel.test.tsx`
  - `dashboard/components/TaskDetailSheet.test.tsx`

### Browser Evidence

- `output/playwright/story-27-12-live-step-binding.png`
- `output/playwright/story-27-13-canonical-result-thread.png`
- `output/playwright/story-27-14-human-takeover-done.png`
- `output/playwright/story-27-15-memory-smoke.png`
- `output/playwright/story-27-16-nanobot-live.png`
- `output/playwright/story-27-17-provider-parity.png`

## Provider Notes

### Claude Code

- Session supervision comes from official Claude Code hooks plus the MC-owned `ask_user` MCP tool.
- Review state transitions are explicit: a structured `ask_user` request moves the task and active step into `review`, and the answer resumes execution.
- The interactive path intentionally diverges from the old headless executor after shared workspace/bootstrap setup.

### Codex

- Session supervision comes from the Codex `app-server`, not terminal parsing alone.
- `Live` attaches to the step-owned interactive session and does not reuse the legacy headless path.
- This validation pass focused on ownership, visible session attach, final result propagation, and memory handling.

### Nanobot (`mc`)

- Nanobot uses a simpler interactive REPL/runtime wrapper than Claude Code or Codex, but it participates in the same step-owned session model.
- Manual takeover is supported through the shared interactive session controls, and manual `Done` completes only the active step.
- Nanobot `Live` remains distinct from the older remote terminal bridge.

## Residual Risks

- Codex does not yet have a provider-native structured equivalent to Claude Code's MCP `ask_user` path in the covered flow; the parity model treats that as not applicable rather than silently emulating it.
- Interactive memory consolidation still depends on a configured consolidation model being available through the bridge. When unavailable, the runtime records an explicit skipped consolidation event instead of falling back.
- Nanobot's visible TUI remains intentionally simpler than Claude Code and Codex. Parity is defined here at the runtime contract level, not identical terminal richness.

## Outcome

Epic 27 can be treated as complete for the current contract:

- backend-owned interactive execution is the default step runtime for interactive providers
- `Live` attaches to the actual running step session
- canonical final output reaches the thread
- human takeover and manual completion are explicit
- memory bootstrap and consolidation is wired to the interactive lifecycle
- no covered path silently falls back to headless execution
