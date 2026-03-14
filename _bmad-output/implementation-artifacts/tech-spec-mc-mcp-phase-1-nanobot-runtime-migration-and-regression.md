# Story: MC MCP Phase 1 Nanobot Runtime Migration and Regression

Status: ready-for-dev

## Story

As a Mission Control backend maintainer,
I want nanobot task execution inside MC to consume the Phase 1 MC tools through
the canonical MCP surface and to fail cleanly when provider submission fails,
so that tool selection is unambiguous and schema/provider errors stop being
misreported as successful task completion.

## Acceptance Criteria

### AC1: MC Nanobot Runtime Uses MCP-First Phase 1 Tools

**Given** a nanobot task is running inside Mission Control
**When** the execution loop is prepared
**Then** the runtime injects the repo-owned MC MCP bridge through nanobot's existing `mcpServers` path
**And** the model sees the canonical Phase 1 tools from that MCP surface.

### AC2: Overlapping Native Tools Are Hidden in MC Runtime

**Given** vendor nanobot still registers overlapping native tools
**When** MC nanobot execution starts
**Then** overlapping native MC-owned tools are removed from the model-visible surface in that runtime
**And** the model sees `send_message` rather than the native `message` tool.

### AC3: Non-MC Nanobot Behavior Stays Unchanged

**Given** nanobot can also run outside Mission Control
**When** a non-MC runtime starts
**Then** local nanobot behavior remains unchanged
**And** the Phase 1 MCP-first migration affects MC task execution only.

### AC4: Provider/Schema Failures Propagate as Execution Errors

**Given** provider submission can fail before the first model turn
**When** a schema/provider error occurs in nanobot MC execution
**Then** the structured error state is preserved
**And** the task does not get marked successful or moved to review as if work completed.

### AC5: Focused Regression Passes

**Given** this migration touches runtime wiring and failure semantics
**When** the story completes
**Then** focused runtime tests pass
**And** there is a regression test proving the former Codex `ask_user` schema failure no longer masquerades as a successful task.

## Tasks / Subtasks

- [ ] **Task 1: Inject the repo-owned MC MCP bridge into nanobot MC execution** (AC: #1, #3)
  - [ ] 1.1 Build MC-only `mcpServers` config for the repo-owned bridge in the execution path
  - [ ] 1.2 Keep the non-MC nanobot path unchanged
  - [ ] 1.3 Document the runtime boundary clearly in code comments

- [ ] **Task 2: Hide overlapping native tools in MC runtime** (AC: #1, #2, #3)
  - [ ] 2.1 Remove overlapping native MC-owned tools from the model-visible surface after loop setup
  - [ ] 2.2 Ensure `send_message` is the only message tool shown to the model in MC runtime
  - [ ] 2.3 Keep local/non-MC tools such as filesystem, shell, web, and spawn untouched

- [ ] **Task 3: Preserve structured execution failure state** (AC: #4)
  - [ ] 3.1 Switch the runtime path from bare direct string handling to structured direct result handling
  - [ ] 3.2 Propagate `is_error` into `ExecutionResult(success=False, ...)`
  - [ ] 3.3 Add regression coverage for provider/schema failure routing

- [ ] **Task 4: Run focused verification and smoke validation** (AC: #5)
  - [ ] 4.1 Run focused nanobot execution tests
  - [ ] 4.2 Run backend architecture/boundary guardrails
  - [ ] 4.3 Run a real-stack smoke proving a Codex-backed nanobot task can start without the previous `ask_user` schema failure

## Dev Notes

### Architecture Notes

- This story is the runtime cutover for the already-defined Phase 1 surface.
- Keep vendor edits minimal; prefer MC-owned wiring in `mc/contexts/execution/*`.
- The migration goal is runtime clarity, not a total removal of all legacy code in one story.

### Likely Touch Points

- `mc/contexts/execution/agent_runner.py`
- `mc/application/execution/runtime.py`
- `mc/application/execution/strategies/nanobot.py`
- new focused tests under `tests/mc/contexts/execution/` and `tests/mc/application/execution/`

### References

- [Source: /Users/ennio/Documents/nanobot-ennio/mc/contexts/execution/agent_runner.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/mc/application/execution/runtime.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/mc/application/execution/strategies/nanobot.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/vendor/nanobot/nanobot/agent/loop.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/docs/plans/2026-03-14-mc-mcp-phase-1-tools-implementation-plan.md]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
