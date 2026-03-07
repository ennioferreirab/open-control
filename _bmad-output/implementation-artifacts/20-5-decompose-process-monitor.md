# Story 20.5: Decompose process_monitor

Status: review

## Story

As a **maintainer**,
I want process_monitor.py decomposed into focused modules,
so that it stops being the last utility god file at 778 lines.

## Acceptance Criteria

### AC1: Config/Defaults Extracted

**Given** process_monitor.py contains env/config resolution logic (default model, timestamp parsing, etc.)
**When** the extraction is complete
**Then** config resolution logic lives in `mc/infrastructure/config.py` or a dedicated module
**And** process_monitor.py no longer owns config defaults

### AC2: Sync Utilities Extracted

**Given** process_monitor.py contains sync utilities (model tier sync, embedding model sync, skill distribution)
**When** the extraction is complete
**Then** sync utilities live in `mc/infrastructure/` or `mc/services/` as appropriate
**And** process_monitor.py delegates to these modules

### AC3: Cleanup Logic Extracted

**Given** process_monitor.py contains cleanup logic (deleted agent cleanup, archived file restoration)
**When** the extraction is complete
**Then** cleanup logic lives in a dedicated module
**And** process_monitor.py delegates to it

### AC4: process_monitor.py Reduced

**Given** the extractions are complete
**When** measuring process_monitor.py
**Then** it is under 300 lines
**And** it only contains orchestration/coordination logic, not implementation details

### AC5: No Behavior Change

**Given** this is a pure refactoring
**When** the decomposition is complete
**Then** all existing tests pass
**And** gateway startup behavior is identical
**And** agent sync, model tier sync, skill distribution all work the same

## Tasks / Subtasks

- [x] **Task 1: Analyze process_monitor.py** (AC: #1, #2, #3)
  - [x] 1.1 Read `mc/process_monitor.py` completely (778 lines)
  - [x] 1.2 Categorize each function by responsibility:
    - Config/defaults (lines ~28-72)
    - Timestamp parsing (line ~112)
    - File I/O helpers (line ~138)
    - Session data reading (line ~149)
    - Archived file restoration (line ~175)
    - Agent cleanup (line ~202)
    - Bot identity fetching (line ~257)
    - Model tier sync (line ~321)
    - Embedding model sync (line ~392)
    - Skill distribution (line ~421)
  - [x] 1.3 Map dependencies between functions

- [x] **Task 2: Extract config/defaults** (AC: #1)
  - [x] 2.1 Move config resolution to `mc/infrastructure/config.py`
  - [x] 2.2 Move timestamp parsing to infrastructure
  - [x] 2.3 Update imports in process_monitor.py

- [x] **Task 3: Extract sync utilities** (AC: #2)
  - [x] 3.1 Move model tier sync, embedding model sync, skill distribution to appropriate module
  - [x] 3.2 Consider `mc/infrastructure/startup_sync.py` or similar
  - [x] 3.3 Update imports

- [x] **Task 4: Extract cleanup logic** (AC: #3)
  - [x] 4.1 Move deleted agent cleanup, archived file restoration
  - [x] 4.2 Update imports

- [x] **Task 5: Verify agent_sync.py overlap** (AC: #4)
  - [x] 5.1 Read `mc/agent_sync.py` (627 lines)
  - [x] 5.2 Identify duplication with process_monitor.py and agent_bootstrap.py
  - [x] 5.3 Consolidate if appropriate

- [x] **Task 6: Verify and test** (AC: #5)
  - [x] 6.1 Run `uv run pytest tests/`
  - [x] 6.2 Verify process_monitor.py is under 300 lines
  - [x] 6.3 Verify gateway startup still works

## Dev Notes

### Architecture Patterns

**process_monitor.py is a utility collection, not a domain owner.** It accumulated startup/sync logic over time. The goal is to distribute its contents to appropriate infrastructure/service modules.

**Existing infrastructure modules:**
- `mc/infrastructure/config.py` -- already exists, good home for config defaults
- `mc/infrastructure/agent_bootstrap.py` -- 867 lines, handles agent bootstrap
- `mc/agent_sync.py` -- 627 lines, may overlap with process_monitor

**Check for duplication:** agent_sync.py and agent_bootstrap.py may already contain similar logic. Consolidate rather than create new modules.

**Key Files to Read First:**
- `mc/process_monitor.py` -- the target (778 lines)
- `mc/agent_sync.py` -- potential overlap (627 lines)
- `mc/infrastructure/agent_bootstrap.py` -- potential overlap (867 lines)
- `mc/infrastructure/config.py` -- target for config extraction
- `mc/gateway.py` -- how process_monitor is used at startup

### Project Structure Notes

**Files to MODIFY:**
- `mc/process_monitor.py` -- reduce to coordinator
- `mc/infrastructure/config.py` -- receive config functions
- `mc/gateway.py` -- update imports if needed

**Files to CREATE:**
- `mc/infrastructure/startup_sync.py` (or similar) for sync utilities
- Potentially consolidate agent_sync.py content

### References

- [Source: mc/process_monitor.py] -- the god file to decompose
- [Source: mc/infrastructure/] -- target layer for extracted code
- [Source: docs/ARCHITECTURE.md] -- infrastructure layer description

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
N/A

### Completion Notes List
- Analysis revealed that process_monitor.py (778 lines) and agent_sync.py (627 lines) were fully dead code -- every function had already been extracted to canonical modules by previous stories (17.2, 19.1):
  - Config/defaults/timestamp/file-I/O: `mc/infrastructure/config.py`
  - Sync utilities/cleanup/bot identity/agent registry: `mc/infrastructure/agent_bootstrap.py`
  - AgentGateway crash handler: `mc/crash_handler.py`
  - AgentSyncService: `mc/services/agent_sync.py`
  - Plan negotiation manager: `mc/services/plan_negotiation.py`
- Gateway re-exports all symbols for backward compatibility
- Neither file was imported by any module or test in the codebase
- Both dead files deleted; KNOWN_ISSUES.md updated to reference correct file
- 28 new decomposition verification tests added
- 1917 mc tests pass (1 pre-existing failure in vendor code, unrelated)
- 0 lines remaining in process_monitor.py (file deleted entirely)

### File List
- `mc/process_monitor.py` -- DELETED (778 lines of dead code removed)
- `mc/agent_sync.py` -- DELETED (627 lines of dead code removed)
- `KNOWN_ISSUES.md` -- Updated file reference from `mc/process_monitor.py` to `mc/infrastructure/agent_bootstrap.py`
- `tests/mc/test_process_monitor_decomposition.py` -- NEW (28 tests verifying decomposition completeness)

## Change Log
- 2026-03-07: Analyzed process_monitor.py and agent_sync.py; found all 1405 lines are dead code already extracted to canonical modules
- 2026-03-07: Deleted mc/process_monitor.py (778 lines) and mc/agent_sync.py (627 lines)
- 2026-03-07: Added 28 decomposition verification tests
- 2026-03-07: Updated KNOWN_ISSUES.md reference
- 2026-03-07: All mc tests pass (1917 passed, 1 pre-existing failure)
