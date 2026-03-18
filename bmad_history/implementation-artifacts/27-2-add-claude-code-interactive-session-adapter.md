# Story 27.2: Add Claude Code Interactive Session Adapter

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control user,
I want Claude Code to launch through the new interactive runtime as a native
terminal session,
so that I can use Claude Code's real TUI inside MC without losing autocomplete,
commands, or interactive prompts.

## Acceptance Criteria

1. A dedicated Claude Code interactive adapter launches `claude` inside the new
   interactive runtime and reconnectable terminal session manager.
2. The interactive Claude Code path is fully separate from the headless
   `ClaudeCodeProvider` path:
   - no `claude -p`
   - no `--output-format stream-json`
   - no reuse of the headless parser contract
3. The adapter reuses the existing CC workspace/bootstrap assets where
   appropriate, including:
   - workspace preparation
   - `CLAUDE.md`
   - MCP config/bootstrap
4. Interactive Claude sessions can reconnect after browser refresh without
   starting a new Claude process if the session is still alive.
5. Existing headless Claude Code task, step, and chat behavior remains
   unchanged and covered by regression tests.
6. Failure cases are explicit:
   - Claude binary missing
   - workspace bootstrap failure
   - tmux/PTY startup failure
   - interactive attach failure

## Success Metrics

- Interactive Claude session reaches a usable prompt in local dev <= 5 seconds
- Browser refresh reattaches to the same live Claude session in >= 95% of local
  validation runs
- Zero changes are required in the existing headless `ClaudeCodeProvider`
  command contract

## Tasks / Subtasks

- [ ] Task 1: Define the Claude Code interactive adapter contract (AC: #1, #2)
  - [ ] Add a provider adapter surface for launch command, env, capabilities, and health checks
  - [ ] Register a Claude Code adapter against the new interactive runtime
  - [ ] Keep the headless provider path untouched

- [ ] Task 2: Reuse CC workspace/bootstrap preparation without reusing the headless process path (AC: #2, #3)
  - [ ] Reuse CC workspace manager output where it fits the interactive mode
  - [ ] Pass MCP and bootstrap assets into the interactive Claude launch
  - [ ] Add tests proving interactive and headless paths diverge after workspace setup

- [ ] Task 3: Implement Claude interactive launch and reconnect lifecycle (AC: #1, #4, #6)
  - [ ] Launch `claude` inside the interactive session runtime
  - [ ] Persist enough runtime metadata to reattach after refresh
  - [ ] Handle missing binary and startup failures with actionable errors

- [ ] Task 4: Add regression and lifecycle tests (AC: #4, #5, #6)
  - [ ] Add focused tests for launch, reconnect, and failure cases
  - [ ] Re-run headless Claude Code task/chat/step regression coverage
  - [ ] Record verification evidence for path separation

## Dev Notes

- The story must learn from the existing CC backend without inheriting its
  headless process contract.
- Reuse bootstrap context, not the execution mode.
- The interactive adapter should remain a provider plugin over the runtime from
  Story 27.1, not a special hard-coded branch inside Chat UI.

### Project Structure Notes

- Likely touch points:
  - `vendor/claude-code/claude_code/workspace.py`
  - `mc/contexts/interactive/`
  - `mc/infrastructure/interactive/`
  - `mc/types.py` or interactive-specific types
- Avoid changing:
  - `vendor/claude-code/claude_code/provider.py`
  - `mc/contexts/execution/cc_executor.py`
  - `mc/application/execution/strategies/claude_code.py`
  except for explicit, minimal integration points proven necessary by tests.

### References

- [Source: vendor/claude-code/claude_code/workspace.py]
- [Source: vendor/claude-code/claude_code/provider.py]
- [Source: mc/contexts/execution/cc_executor.py]
- [Source: mc/application/execution/strategies/claude_code.py]
- [Source: _bmad-output/implementation-artifacts/cc-3-workspace-manager.md]
- [Source: _bmad-output/implementation-artifacts/cc-4-claude-code-provider.md]
- [Source: _bmad-output/implementation-artifacts/cc-6-session-management.md]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
