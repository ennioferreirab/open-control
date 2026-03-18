# Story MEM.4: CCBackend Memory Parity

Status: ready-for-dev

## Story

As a **platform maintainer**,
I want the CCBackend to obey the same memory contract as the nanobot backend,
so that CC agents consolidate, search, and consume memory with the same guarantees as other agents.

## Acceptance Criteria

### AC1: CC agents persist memory under the same contract

**Given** a `cc/...` agent completes a meaningful execution
**When** post-execution consolidation runs
**Then** the agent writes `MEMORY.md` and `HISTORY.md` under the same memory contract used by the nanobot backend
**And** the effective workspace respects board-aware memory scope.

### AC2: CC prompt context includes the same memory context

**Given** a `cc/...` agent is prepared for execution
**When** its working context is generated
**Then** the prompt consumes the same long-term memory context expected by the nanobot backend
**And** this works for both shared and board-isolated scopes.

### AC3: `search_memory` finds CC-consolidated content

**Given** a CC agent has consolidated new facts
**When** `search_memory` is invoked
**Then** the consolidated content is retrievable from the same workspace the agent writes to.

### AC4: SQLite sync and invalid-memory handling match nanobot behavior

**Given** a CC agent consolidates or encounters invalid files in `memory/`
**When** post-processing completes
**Then** the SQLite index is synchronized
**And** invalid files are treated the same way the nanobot backend treats them.

### AC5: CC uses the same consolidation policy

**Given** the unified session policy is in effect
**When** a CC-backed execution crosses `threshold` or reaches `session boundary`
**Then** the CC path obeys the same trigger model as the nanobot backend.

### AC6: Real CC agents show observable evidence

**Given** representative agents such as `offer-strategist` or `sales-revops`
**When** the real execution path runs a scenario that should consolidate
**Then** `HISTORY.md` is observably non-empty
**And** tests cover the same behavior in automation.

## Tasks / Subtasks

- [ ] Task 1: Freeze current parity gaps in tests (AC: 1, 2, 3, 4, 5, 6)
  - [ ] 1.1 Extend [`tests/cc/test_memory_consolidator.py`](/Users/ennio/Documents/nanobot-ennio/tests/cc/test_memory_consolidator.py) to cover consolidation writes and index sync.
  - [ ] 1.2 Extend [`tests/mc/test_executor_cc.py`](/Users/ennio/Documents/nanobot-ennio/tests/mc/test_executor_cc.py) for end-to-end parity with nanobot execution.
  - [ ] 1.3 Extend [`tests/cc/test_mcp_bridge.py`](/Users/ennio/Documents/nanobot-ennio/tests/cc/test_mcp_bridge.py) for workspace/search parity.

- [ ] Task 2: Align CC workspace, prompt, and memory services (AC: 1, 2, 3)
  - [ ] 2.1 Update [`vendor/claude-code/claude_code/workspace.py`](/Users/ennio/Documents/nanobot-ennio/vendor/claude-code/claude_code/workspace.py) so memory context and workspace resolution mirror nanobot semantics.
  - [ ] 2.2 Update [`vendor/claude-code/claude_code/memory_consolidator.py`](/Users/ennio/Documents/nanobot-ennio/vendor/claude-code/claude_code/memory_consolidator.py) and [`mc/memory/service.py`](/Users/ennio/Documents/nanobot-ennio/mc/memory/service.py) to use the same contract and sync behavior.

- [ ] Task 3: Align CC runtime parity behavior (AC: 4, 5)
  - [ ] 3.1 Ensure the CC execution path uses the same post-execution consolidation semantics as the nanobot backend.
  - [ ] 3.2 Ensure invalid files in `memory/` are handled through the same enforcement path rather than a CC-only workaround.

- [ ] Task 4: Verify against real representative agents (AC: 6)
  - [ ] 4.1 Run focused tests and one representative real execution path.
  - [ ] 4.2 Confirm the resulting files and search behavior match expectations.

## Dev Notes

- This story is not only “make `HISTORY.md` non-empty.” It is parity for write path, read path, prompt context, search path, and index sync.
- Reuse the same board/memory semantics already established for nanobot instead of adding a CC-only memory model.

### Project Structure Notes

- Keep CC vendor changes minimal and route shared behavior through canonical MC memory services where possible.
- Do not introduce a separate index format or a separate prompt-memory contract for CC.

### References

- [Source: docs/plans/2026-03-11-memory-consolidation-backlog.md#Story-P1.1]
- [Source: docs/plans/2026-03-11-memory-consolidation-remediation-plan.md#AC5-CCBackend-Memory-Parity]
- [Source: /Users/ennio/Documents/nanobot-ennio/vendor/claude-code/claude_code/memory_consolidator.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/vendor/claude-code/claude_code/workspace.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/mc/memory/service.py]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
