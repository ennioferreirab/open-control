# Story MEM.1: Canonical Shared Memory Workspace

Status: ready-for-dev

## Story

As a **platform maintainer**,
I want official nanobot channels and Mission Control to resolve the same canonical memory workspace for the same logical agent,
so that memory reads, writes, search, and shared learning behave the same regardless of entry channel.

## Acceptance Criteria

### AC1: Logical agent identity is explicit and stable

**Given** the system needs to decide whether two executions target the same logical agent
**When** memory resolution runs
**Then** identity is computed as `agent_name + effective memory scope`
**And** `with_history` resolves to the shared agent workspace
**And** `clean` resolves to a board-isolated workspace
**And** this rule is documented in code and covered by tests.

### AC2: Official channels and MC resolve the same canonical memory storage

**Given** the `nanobot` agent runs from an official channel and from MC in shared-memory mode
**When** each flow resolves the memory workspace
**Then** both flows point to the same canonical storage target
**And** `MEMORY.md`, `HISTORY.md`, and `memory-index.sqlite` resolve to the same physical or canonical target.

### AC3: `search_memory` uses the same workspace as execution

**Given** a shared-memory agent is queried through execution and through memory search
**When** the runtime builds memory context and the MCP bridge performs `search_memory`
**Then** both use the same canonical memory workspace
**And** search results do not depend on which logical path was used to reach that workspace.

### AC4: Board-scoped artifact binding is explicit for official channels

**Given** an official channel interaction needs access to board-scoped `artifacts`
**When** no `board_id` is present in the channel context
**Then** the runtime binds the request to the default board
**And** that binding is explicit in code, observable at runtime, and covered by tests.

### AC5: Automated coverage locks the contract

**Given** the canonical shared memory contract is implemented
**When** the relevant Python test suites run
**Then** there are automated tests for:
- official-channel workspace resolution,
- MC workspace resolution,
- `search_memory` workspace parity,
- canonical target equality for `MEMORY.md`, `HISTORY.md`, and `memory-index.sqlite`,
- default-board binding when `board_id` is absent.

## Tasks / Subtasks

- [ ] Task 1: Freeze the contract in tests (AC: 1, 2, 3, 4, 5)
  - [ ] 1.1 Extend [`tests/mc/test_board_utils.py`](/Users/ennio/Documents/nanobot-ennio/tests/mc/test_board_utils.py) with shared-workspace resolution cases for `clean` vs `with_history`.
  - [ ] 1.2 Extend [`tests/cc/test_mcp_bridge.py`](/Users/ennio/Documents/nanobot-ennio/tests/cc/test_mcp_bridge.py) so `search_memory` asserts the same workspace the execution path uses.
  - [ ] 1.3 Add a regression test for channel flows that do not carry `board_id`, asserting default-board binding for board-scoped resources.

- [ ] Task 2: Centralize canonical workspace resolution (AC: 1, 2, 3)
  - [ ] 2.1 Add or extend a single helper in [`mc/infrastructure/boards.py`](/Users/ennio/Documents/nanobot-ennio/mc/infrastructure/boards.py) that resolves effective memory scope and canonical paths.
  - [ ] 2.2 Update [`mc/application/execution/context_builder.py`](/Users/ennio/Documents/nanobot-ennio/mc/application/execution/context_builder.py) to use the same helper as the execution path.
  - [ ] 2.3 Update [`vendor/claude-code/claude_code/mcp_bridge.py`](/Users/ennio/Documents/nanobot-ennio/vendor/claude-code/claude_code/mcp_bridge.py) so `search_memory` consumes the same canonical target.

- [ ] Task 3: Make default-board binding explicit for board-scoped resources (AC: 4)
  - [ ] 3.1 Introduce a single runtime rule for “channel without `board_id`” that resolves to the default board for `artifacts`.
  - [ ] 3.2 Ensure the chosen board binding is surfaced in runtime metadata or logs.

- [ ] Task 4: Verify the contract end-to-end (AC: 5)
  - [ ] 4.1 Run focused Python tests for board resolution and MCP memory search.
  - [ ] 4.2 Confirm the same canonical targets are reached in shared-memory mode.

## Dev Notes

- This story is about workspace identity and routing, not chunk deduplication inside SQLite. Chunk canonicalization belongs in MEM.2.
- Keep the existing board semantics:
  - `clean` stays isolated per board.
  - `with_history` stays shared.
- Do not introduce channel-specific storage behavior. Channels differ only by trigger timing, not by where memory is stored.

### Project Structure Notes

- Runtime and board resolution logic belongs in `mc/infrastructure/` and `mc/application/execution/`.
- Do not create a second memory-resolution path in CC bridge code; reuse a canonical resolver.
- Avoid UI changes in this story. The only board-scoped artifact concern here is backend binding when `board_id` is absent.

### References

- [Source: docs/plans/2026-03-11-memory-consolidation-backlog.md#Story-P0.1]
- [Source: docs/plans/2026-03-11-memory-consolidation-remediation-plan.md#AC1-Canonical-Storage-Equality]
- [Source: /Users/ennio/Documents/nanobot-ennio/mc/infrastructure/boards.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/mc/application/execution/context_builder.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/vendor/claude-code/claude_code/mcp_bridge.py]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
