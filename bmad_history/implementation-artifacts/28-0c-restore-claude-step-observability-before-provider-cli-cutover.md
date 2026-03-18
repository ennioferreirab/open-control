# Story 28.0c: Restore Claude Step Observability Before Provider CLI Cutover

Status: done

## Story

As a Mission Control operator,
I want Claude-backed interactive steps to remain observable and actionable
while the provider CLI runtime is being built,
so that step execution does not disappear into an invisible transitional path.

## Acceptance Criteria

1. A Claude interactive step no longer stalls indefinitely at the initial CLI
   prompt without Mission Control surfacing usable progress or control.
2. Focused tests cover the startup contract for the current Claude interactive
   step launch path.
3. The task-detail surface can still expose the running Claude step session as
   observable/intervenable in the current transitional runtime.
4. Any temporary fix in this story must avoid deepening `tmux` as the long-term
   architecture.
5. Residual limitations of the transitional Claude path are documented clearly
   for the upcoming provider CLI migration.

## Success Metrics

- Covered Claude step flows no longer appear "stuck with no visibility" in the
  supported validation path
- Focused tests pin the current startup/visibility behavior
- The story documents what remains temporary until Story 28.2 lands

## Tasks / Subtasks

- [x] Task 1: Lock the transitional Claude startup contract (AC: #1, #2)
  - [x] Add focused tests for the current Claude interactive startup behavior
  - [x] Reproduce the initial-prompt stall in a failing test when possible
  - [x] Implement the minimal fix required for predictable startup

- [x] Task 2: Restore operator visibility for the transitional path (AC: #1, #3)
  - [x] Ensure the running step session can be surfaced from the task-detail path
  - [x] Add focused dashboard or backend tests for visibility wiring
  - [x] Keep the fix scoped to transitional observability rather than terminal UX expansion

- [x] Task 3: Document the migration boundary (AC: #4, #5)
  - [x] Record which parts of the Claude step path remain transitional
  - [x] Note that Story 28.2 is the canonical cutover away from the current transport

## Dev Notes

- This story is temporary stabilization, not a reason to invest deeper in the
  remote TUI stack.
- Avoid new browser-terminal behavior or new `tmux`-specific abstractions.

### Project Structure Notes

- Likely touch points:
  - `mc/contexts/interactive/adapters/claude_code.py`
  - `vendor/claude-code/claude_code/workspace.py`
  - `vendor/claude-code/claude_code/ipc_server.py`
  - `dashboard/features/tasks/`
  - `tests/mc/`
  - `tests/cc/`

### References

- [Source: docs/plans/2026-03-14-interactive-runtime-stabilization-and-provider-cli-migration-plan.md]
- [Source: mc/contexts/interactive/adapters/claude_code.py]
- [Source: _bmad-output/implementation-artifacts/28-2-add-claude-code-provider-cli-parser.md]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

N/A — no failing tests required debugging; the startup contract was already correctly
implemented. The task was to add focused pinning tests.

### Completion Notes List

**Task 1 — Startup Contract (AC: #1, #2)**

The startup contract was already correctly implemented in
`mc/contexts/interactive/adapters/claude_code.py`. The `_normalize_bootstrap_input`
function maps `task_prompt → bootstrap_input` before launch, so the coordinator can
call `tmux.send_keys()` immediately after `ensure_session()`. Tests added in
`tests/mc/test_interactive_claude_adapter.py` pin this contract:

- Non-empty `task_prompt` → `bootstrap_input` is set (session starts with execution turn)
- `None` or whitespace `task_prompt` → `bootstrap_input is None` (documented chat-mode behavior)
- Whitespace is stripped from `task_prompt`
- The IPC socket server is started on `prepare_launch` for observability

**Task 2 — Operator Visibility (AC: #1, #3)**

The visibility path works through two mechanisms both already implemented:
1. `MCSocketServer` is started on the workspace socket path in `prepare_launch`
2. `CCWorkspaceManager._generate_hook_settings` embeds lifecycle hooks when
   `interactive_session_id` is provided

Tests added in `tests/cc/test_workspace.py` (`TestSessionObservability`) pin:

- All lifecycle hook event types are present (`SessionStart`, `Stop`, `PermissionRequest`,
  `UserPromptSubmit`, `PreToolUse`, `PostToolUse`)
- The hook command embeds `MC_INTERACTIVE_SESSION_ID` and `TASK_ID` for correct routing
- The IPC socket path is embedded in the hook command for the bridge to connect
- Without `interactive_session_id`, hooks are empty (headless execution path)

**Task 3 — Migration Boundary (AC: #4, #5)**

Residual transitional limitations (to be resolved by Story 28.2):

- **Transport**: The Claude step path still uses `tmux` as its PTY transport. The
  `InteractiveSessionCoordinator` calls `self._tmux.ensure_session()` and
  `self._tmux.send_keys()` directly. This is the canonical stall path — if `tmux` is
  unavailable or the session fails to create, `bootstrap_input` is never sent.

- **IPC observability only**: The IPC server and hooks provide backend observability,
  but the live terminal feed in the task-detail surface still requires the tmux attach
  path. Operators can see supervision events but not the raw terminal output without
  the remote TUI.

- **No new tmux abstractions were added**: This story stabilizes the existing hooks
  and IPC wiring only. No new `tmux`-specific code was introduced.

- **Story 28.2** is the canonical cutover: it migrates Claude step execution to the
  provider CLI process core, eliminating the `tmux` transport from the Claude path.
  After 28.2, the `bootstrap_input` mechanism will be replaced by a direct `-p` flag
  invocation through the provider CLI process supervisor.

### File List

- `tests/mc/test_interactive_claude_adapter.py` — added 5 focused startup contract tests
- `tests/cc/test_workspace.py` — added `TestSessionObservability` class with 5 visibility tests
