# Story MEM.6: Enforce Memory Directory Contract

Status: ready-for-dev

## Story

As a **platform maintainer**,
I want `memory/` to accept only official memory files,
so that the index, prompt context, and consolidation logic are not contaminated by arbitrary artifacts.

## Acceptance Criteria

### AC1: Only the official memory contract is accepted

**Given** an agent workspace contains a `memory/` directory
**When** the memory policy evaluates its contents
**Then** the only accepted files in the critical path are:
- `MEMORY.md`,
- `HISTORY.md`,
- `HISTORY_ARCHIVE.md`,
- SQLite sidecars and lock files required by the store.

### AC2: Task-generated invalid files are relocated out of `memory/`

**Given** an agent writes an invalid `.md`, `.json`, or other ad hoc file into `memory/` during execution
**When** post-processing enforces the memory contract
**Then** the invalid file is relocated using the existing relocation semantics
**And** it no longer participates in memory indexing or memory context.

### AC3: Legacy invalid files do not contaminate indexing

**Given** a workspace already contains invalid legacy files inside `memory/`
**When** the store or policy synchronizes memory
**Then** those files do not enter the main memory index
**And** the behavior is deterministic and covered by tests.

### AC4: The `youtube-summarizer` case is reproducible and covered

**Given** the known `youtube-summarizer` style of arbitrary `.md` and `.json` files in `memory/`
**When** the memory contract is enforced
**Then** the case is reproduced in tests
**And** the invalid files are excluded from the memory path.

### AC5: Agent guidance no longer points durable artifacts to `memory/`

**Given** prompts and filesystem guard messages guide agents on where to save files
**When** the contract is enforced
**Then** no guidance tells agents to save reusable artifacts inside `memory/`.

## Tasks / Subtasks

- [ ] Task 1: Freeze current invalid-memory behavior in tests (AC: 1, 2, 3, 4, 5)
  - [ ] 1.1 Extend [`tests/mc/memory/test_policy.py`](/Users/ennio/Documents/nanobot-ennio/tests/mc/memory/test_policy.py) with invalid-file coverage.
  - [ ] 1.2 Extend [`tests/mc/test_filesystem_memory_guard.py`](/Users/ennio/Documents/nanobot-ennio/tests/mc/test_filesystem_memory_guard.py) so prompt/guard guidance stays aligned.
  - [ ] 1.3 Add a reproducible `youtube-summarizer`-style fixture.

- [ ] Task 2: Enforce the contract in the backend path (AC: 1, 2, 3, 4)
  - [ ] 2.1 Update [`mc/memory/policy.py`](/Users/ennio/Documents/nanobot-ennio/mc/memory/policy.py) with the official allowlist.
  - [ ] 2.2 Update [`mc/application/execution/post_processing.py`](/Users/ennio/Documents/nanobot-ennio/mc/application/execution/post_processing.py) so task-generated invalid files are relocated consistently.
  - [ ] 2.3 Update [`mc/memory/service.py`](/Users/ennio/Documents/nanobot-ennio/mc/memory/service.py) so invalid files cannot enter the main index path.

- [ ] Task 3: Align agent guidance (AC: 5)
  - [ ] 3.1 Update [`vendor/nanobot/nanobot/agent/tools/filesystem.py`](/Users/ennio/Documents/nanobot-ennio/vendor/nanobot/nanobot/agent/tools/filesystem.py) or adjacent guidance so reusable artifacts are directed away from `memory/`.

- [ ] Task 4: Verify the cleaned memory path (AC: 1, 2, 3, 4, 5)
  - [ ] 4.1 Run focused memory-policy and filesystem-guard tests.
  - [ ] 4.2 Confirm the index no longer chunks invalid ad hoc files.

## Dev Notes

- Do not expand `memory/` into a general-purpose document store.
- Preserve the current relocation behavior for task-generated invalid files instead of inventing a second cleanup path.
- This story protects the memory path. Persistent reusable files belong in the board-scoped `artifacts/` contract from MEM.7.

### Project Structure Notes

- Memory policy belongs in `mc/memory/`.
- Runtime relocation belongs in post-processing, not in frontend code or ad hoc vendor patches.

### References

- [Source: docs/plans/2026-03-11-memory-consolidation-backlog.md#Story-P1.3]
- [Source: docs/plans/2026-03-11-memory-consolidation-remediation-plan.md#Task-5-Saneamento-e-guarda-do-contrato-de-arquivos-em-memory]
- [Source: /Users/ennio/Documents/nanobot-ennio/mc/memory/policy.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/mc/application/execution/post_processing.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/vendor/nanobot/nanobot/agent/tools/filesystem.py]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
