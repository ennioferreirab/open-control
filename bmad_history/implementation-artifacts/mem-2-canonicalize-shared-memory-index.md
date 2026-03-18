# Story MEM.2: Canonicalize Shared Memory SQLite Index

Status: ready-for-dev

## Story

As a **platform maintainer**,
I want shared-memory files to be indexed under a single canonical path,
so that `search_memory` does not return duplicate chunks for the same underlying file.

## Acceptance Criteria

### AC1: Shared files produce one logical chunk set

**Given** the same shared file is reachable through a global path and a board path
**When** the SQLite memory index syncs that file
**Then** only one logical set of chunks is stored
**And** both paths are treated as the same canonical file.

### AC2: `chunks.file_path` is canonical and stable

**Given** a shared-memory file is indexed repeatedly
**When** `sync()` or `sync_file()` runs multiple times
**Then** `chunks.file_path` is stored in one stable canonical form
**And** re-sync does not create a second logical file identity.

### AC3: Legacy duplicate entries are pruned correctly

**Given** a database already contains duplicate entries for equivalent shared paths
**When** the canonicalized sync logic runs
**Then** stale duplicate entries are removed
**And** legitimate `clean` board entries are preserved.

### AC4: Search results contain no symlink-driven duplicates

**Given** `search_memory` is run against content that was previously duplicated by symlinked paths
**When** the canonicalized index is queried
**Then** duplicate hits do not appear for the same underlying file content.

### AC5: Tests cover shared and isolated modes

**Given** the fix is implemented
**When** the focused memory-index test suite runs
**Then** there is automated coverage for:
- indexing the same file via two equivalent paths,
- re-sync after canonicalization,
- duplicate-pruning behavior,
- isolation preservation for `clean` boards.

## Tasks / Subtasks

- [ ] Task 1: Freeze current duplication in tests (AC: 1, 2, 3, 4, 5)
  - [ ] 1.1 Extend [`tests/mc/memory/test_index.py`](/Users/ennio/Documents/nanobot-ennio/tests/mc/memory/test_index.py) with a symlink-equivalent indexing regression.
  - [ ] 1.2 Extend [`tests/mc/test_board_utils.py`](/Users/ennio/Documents/nanobot-ennio/tests/mc/test_board_utils.py) to confirm `clean` boards remain isolated.

- [ ] Task 2: Canonicalize indexed file paths (AC: 1, 2)
  - [ ] 2.1 Update [`mc/memory/index.py`](/Users/ennio/Documents/nanobot-ennio/mc/memory/index.py) so file identity is resolved through a canonical path before persistence.
  - [ ] 2.2 Ensure `sync()` and `sync_file()` use that same identity consistently.

- [ ] Task 3: Prune stale duplicates safely (AC: 3, 4)
  - [ ] 3.1 Add pruning logic for prior duplicate records created from equivalent shared paths.
  - [ ] 3.2 Verify the pruning path does not collapse legitimate board-isolated files.

- [ ] Task 4: Verify focused search behavior (AC: 4, 5)
  - [ ] 4.1 Run the focused memory index tests.
  - [ ] 4.2 Confirm search results are identical regardless of which logical path reaches the same file.

## Dev Notes

- The root bug is not chunking or ranking. It is file identity.
- Do not replace SQLite or change retrieval strategy in this story.
- Canonicalization must work with the current `with_history` symlink model and must not break `clean` isolation.

### Project Structure Notes

- Keep canonicalization logic inside memory indexing code, not spread across every caller.
- Board helpers may assist with path normalization, but the source of truth for index persistence belongs in [`mc/memory/index.py`](/Users/ennio/Documents/nanobot-ennio/mc/memory/index.py).

### References

- [Source: docs/plans/2026-03-11-memory-consolidation-backlog.md#Story-P0.2]
- [Source: docs/plans/2026-03-11-memory-consolidation-remediation-plan.md#AC4-No-Duplicate-Chunks]
- [Source: /Users/ennio/Documents/nanobot-ennio/mc/memory/index.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/tests/mc/memory/test_index.py]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
