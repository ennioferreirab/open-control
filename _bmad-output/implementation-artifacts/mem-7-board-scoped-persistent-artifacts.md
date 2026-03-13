# Story MEM.7: Board-Scoped Persistent Artifacts

Status: ready-for-dev

## Story

As a **board user and platform maintainer**,
I want agents to store reusable artifacts in a board-scoped location that is visible in board settings,
so that durable files can be shared and reused without polluting memory or task output.

## Acceptance Criteria

### AC1: `artifacts/` exists as a board-scoped persistent directory

**Given** a board is active
**When** an agent needs to save a reusable durable file
**Then** the file is stored under a board-scoped `artifacts/` directory
**And** that directory is separate from `memory/` and from `tasks/<id>/output/`.

### AC2: Agent guidance differentiates `memory/`, `artifacts/`, and `output/`

**Given** nanobot and CC-backed agents receive workspace guidance
**When** they decide where to save information
**Then** prompts and filesystem guidance clearly distinguish:
- `memory/` for facts and consolidated history,
- `artifacts/` for durable board-scoped reusable files,
- `tasks/<id>/output/` for task deliverables.

### AC3: Board settings expose persistent artifacts

**Given** a board has persistent artifacts
**When** the user opens board settings
**Then** they can list, open, and download those artifacts from the board settings UI.

### AC4: Viewer logic is reused, not reinvented

**Given** a user opens a board artifact from board settings
**When** the preview opens
**Then** it reuses the existing document viewer flow already used by task files
**And** the implementation does not introduce a second parallel preview system.

### AC5: Reuse works across future executions on the same board

**Given** an agent wrote a persistent artifact in a prior execution
**When** a future execution on the same board starts
**Then** the artifact is available for reuse
**And** official channels without `board_id` bind to the default board when they need board-scoped artifacts.

### AC6: Persistent artifacts are not indexed as memory

**Given** files exist under board-scoped `artifacts/`
**When** memory indexing or memory-context loading runs
**Then** those files are not treated as memory by default.

### AC7: Tests cover backend contract and board UI

**Given** the board-scoped artifact contract is implemented
**When** the relevant backend and dashboard tests run
**Then** there is automated coverage for:
- allowed artifact writes,
- future reuse,
- separation from `memory/`,
- board-settings list/open/download behavior,
- viewer reuse.

## Tasks / Subtasks

- [ ] Task 1: Freeze the contract in backend and UI tests (AC: 1, 2, 3, 4, 5, 6, 7)
  - [ ] 1.1 Add backend tests for allowed artifact writes and future reuse.
  - [ ] 1.2 Add dashboard tests for board settings listing and viewer opening.

- [ ] Task 2: Add the backend artifact contract (AC: 1, 2, 5, 6)
  - [ ] 2.1 Create artifact policy/service code under a new `mc/artifacts/` package.
  - [ ] 2.2 Update [`vendor/nanobot/nanobot/agent/context.py`](/Users/ennio/Documents/nanobot-ennio/vendor/nanobot/nanobot/agent/context.py), [`vendor/claude-code/claude_code/workspace.py`](/Users/ennio/Documents/nanobot-ennio/vendor/claude-code/claude_code/workspace.py), and [`mc/application/execution/file_enricher.py`](/Users/ennio/Documents/nanobot-ennio/mc/application/execution/file_enricher.py) with the new contract.
  - [ ] 2.3 Ensure official channels without `board_id` bind to the default board for board-scoped artifacts.

- [ ] Task 3: Expose artifacts in board settings (AC: 3, 4, 7)
  - [ ] 3.1 Extend [`dashboard/features/boards/hooks/useBoardSettingsSheet.ts`](/Users/ennio/Documents/nanobot-ennio/dashboard/features/boards/hooks/useBoardSettingsSheet.ts) and [`dashboard/features/boards/components/BoardSettingsSheet.tsx`](/Users/ennio/Documents/nanobot-ennio/dashboard/features/boards/components/BoardSettingsSheet.tsx) to surface board artifacts.
  - [ ] 3.2 Reuse [`dashboard/components/DocumentViewerModal.tsx`](/Users/ennio/Documents/nanobot-ennio/dashboard/components/DocumentViewerModal.tsx) and its viewer subcomponents instead of creating a new modal system.
  - [ ] 3.3 Generalize fetch logic only as much as necessary so board artifacts can use the same viewing pipeline.

- [ ] Task 4: Verify end-to-end separation and reuse (AC: 5, 6, 7)
  - [ ] 4.1 Run focused Python tests for artifact policy.
  - [ ] 4.2 Run focused dashboard tests for board settings and viewer behavior.

## Dev Notes

- This story is intentionally board-scoped, not global-per-agent.
- The path may allow agent subfolders inside board `artifacts/` if needed to avoid collisions, but the contract remains board-owned.
- Reuse existing viewer components and patterns from task files. Do not clone `Files` tab code into a second independent system.

### Project Structure Notes

- Backend artifact rules belong under `mc/`.
- Board settings UI belongs under `dashboard/features/boards/`.
- File preview stays in shared dashboard viewer components.

### References

- [Source: docs/plans/2026-03-11-memory-consolidation-backlog.md#Story-P1.4]
- [Source: docs/plans/2026-03-11-memory-consolidation-remediation-plan.md#AC7-Persistent-Artifact-Contract]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/features/boards/components/BoardSettingsSheet.tsx]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/features/boards/hooks/useBoardSettingsSheet.ts]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/components/DocumentViewerModal.tsx]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/features/tasks/components/TaskDetailFilesTab.tsx]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
