---
title: 'Agent Delete/Restore — YAML Lifecycle + Deleted Group UI'
slug: 'agent-delete-restore-yaml-lifecycle'
created: '2026-02-23'
status: 'completed'
stepsCompleted: [1, 2, 3, 4, 5, 6]
tech_stack: ['Next.js', 'Convex', 'Python', 'TypeScript', 'vitest', 'pytest']
files_to_modify:
  - 'dashboard/convex/schema.ts'
  - 'dashboard/convex/agents.ts'
  - 'dashboard/components/AgentSidebar.tsx'
  - 'dashboard/components/AgentSidebarItem.tsx'
  - 'nanobot/mc/gateway.py'
  - 'nanobot/mc/bridge.py'
  - 'tests/mc/test_gateway.py'
code_patterns:
  - 'Convex soft-delete pattern: set deletedAt timestamp, filter !deletedAt in list queries'
  - 'Agent grouping: regularAgents / systemAgents via useMemo filter on isSystem + SYSTEM_AGENT_NAMES'
  - 'Collapsible group UI: Collapsible > CollapsibleTrigger > SidebarGroupLabel + CollapsibleContent'
  - 'Sync lifecycle: _write_back_convex_agents (Convex→local) → validate YAML → resolve model → sync_agent → deactivate_agents_except'
  - 'Bridge snake_case ↔ Convex camelCase: bridge.py handles conversion'
  - 'Activity events: all mutations write to activities table as architectural invariant'
test_patterns:
  - 'Python: pytest with tmp_path, MagicMock for bridge — tests/mc/test_gateway.py'
  - 'TypeScript: vitest — dashboard/components/AgentSidebarItem.test.tsx'
  - 'Gateway tests mock bridge methods and validate call args'
---

# Tech-Spec: Agent Delete/Restore — YAML Lifecycle + Deleted Group UI

**Created:** 2026-02-23

## Overview

### Problem Statement

Soft-deleting an agent sets `deletedAt` in Convex but leaves the YAML file on disk. The next `sync_agent_registry()` scan finds the YAML and calls `upsertByName`, which has `deletedAt: undefined` hardcoded (agents.ts:40) — bringing the agent back every sync cycle. Additionally, there is no way to restore a deleted agent, and no visibility into what was deleted. Critical agent data (MEMORY.md, HISTORY.md, session JSONL) lives only on the local filesystem and is not backed up to Convex — meaning any local folder deletion would cause unrecoverable data loss.

### Solution

1. **Archive before delete**: When sync detects a `deletedAt` agent with a local YAML folder, upload memory/history/session files to Convex, then delete the local folder.
2. **Restore from Convex**: New `restoreAgent` mutation clears `deletedAt`. The existing write-back mechanism recreates the YAML, and the archived memory/history/sessions are restored to local files.
3. **Deleted group UI**: New collapsible "Deleted" group in AgentSidebar (below System) with per-agent restore button.

### Scope

**In Scope:**
- Convex schema: new fields on agents table for archived memory/history/session data
- `convex/agents.ts`: `listDeleted` query, `archiveAgentData` mutation, `restoreAgent` mutation, `getArchive` query
- `gateway.py`: archive + cleanup step in sync for `deletedAt` agents; restore archived data in write-back
- `bridge.py`: new methods to call archive/restore mutations and queries
- `AgentSidebar.tsx`: "Deleted" collapsible group + restore button per agent
- Defense-in-depth: remove `deletedAt: undefined` from `upsertByName`

**Out of Scope:**
- Hard delete / purge from Convex permanently
- Bulk delete/restore operations
- Board-scoped memory archival (`~/.nanobot/boards/{board}/agents/{name}/` — separate path, not affected)
- Custom per-agent skills archival

## Context for Development

### Codebase Patterns

**Convex soft-delete pattern:**
- `softDeleteAgent` sets `deletedAt: timestamp` (agents.ts:207)
- `list` query filters `!a.deletedAt` (agents.ts:8)
- `upsertByName` clears `deletedAt: undefined` on re-registration (agents.ts:40) — this is the bug

**Agent grouping in sidebar:**
- `regularAgents` = `!a.isSystem && !SYSTEM_AGENT_NAMES.has(a.name)` (AgentSidebar.tsx:51)
- `systemAgents` = `a.isSystem || SYSTEM_AGENT_NAMES.has(a.name)` (AgentSidebar.tsx:52)
- `SYSTEM_AGENT_NAMES` = `{"lead-agent", "mc-agent"}` (constants.ts:75)
- System group uses `Collapsible` + `CollapsibleTrigger` + `CollapsibleContent` (AgentSidebar.tsx:114-137)

**Sync lifecycle (gateway.py:169-223):**
1. `_write_back_convex_agents()` — Convex→local (uses `agents:list`, already skips deleted)
2. Validate YAML files in `~/.nanobot/agents/` subdirectories
3. Resolve model with provider prefix
4. `bridge.sync_agent()` → `agents:upsertByName`
5. `bridge.deactivate_agents_except()` → sets `status: "idle"` (does NOT touch `deletedAt`)

**Bridge data flow:**
- `sync_agent()` sends: `name`, `display_name`, `role`, `skills`, `model`, optional `prompt`/`soul`
- `write_agent_config()` writes YAML + creates `memory/` + `skills/` dirs
- `list_agents()` → `agents:list` (filters `!deletedAt`)

**Activity events:** All mutations write to `activities` table as architectural invariant.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `dashboard/convex/schema.ts:81-101` | Agents table schema — add archive fields here |
| `dashboard/convex/agents.ts:4-10` | `list` query — filters `!deletedAt` |
| `dashboard/convex/agents.ts:12-71` | `upsertByName` — clears `deletedAt` on line 40 (the bug) |
| `dashboard/convex/agents.ts:188-216` | `softDeleteAgent` — sets `deletedAt` timestamp |
| `dashboard/convex/agents.ts:218-235` | `deactivateExcept` — only touches `status`, safe |
| `dashboard/components/AgentSidebar.tsx:48-54` | Agent grouping logic (regularAgents/systemAgents) |
| `dashboard/components/AgentSidebar.tsx:114-137` | System group collapsible pattern (replicate for Deleted) |
| `dashboard/components/AgentSidebar.tsx:151-183` | Delete confirmation dialog |
| `dashboard/components/AgentSidebarItem.tsx` | Agent item renderer with delete button |
| `nanobot/mc/gateway.py:119-167` | `_write_back_convex_agents()` — Convex→local write-back |
| `nanobot/mc/gateway.py:169-223` | `sync_agent_registry()` — full sync lifecycle |
| `nanobot/mc/bridge.py:318-338` | `sync_agent()` — calls `upsertByName` |
| `nanobot/mc/bridge.py:340-363` | `list_agents()` + `deactivate_agents_except()` |
| `nanobot/mc/bridge.py:441-492` | `write_agent_config()` — YAML reconstruction from Convex |
| `nanobot/agent/memory.py` | `MemoryStore` — MEMORY.md + HISTORY.md read/write |
| `nanobot/session/manager.py` | `SessionManager` — session JSONL persistence |
| `tests/mc/test_gateway.py` | Gateway sync tests with mock bridge |

### Technical Decisions

1. **Archive as string fields on agents record** — simple, no new tables. Session JSONL ~30KB, well within Convex 1MB doc limit.
2. **Delete flow**: `softDeleteAgent` (frontend) → sync detects `deletedAt` (Python) → archive to Convex → delete local folder.
3. **Restore flow**: `restoreAgent` clears `deletedAt` (frontend) → write-back recreates YAML + restores archived data (Python).
4. **Separate archive query**: `getArchive` query returns archived data only when needed (avoids bloating `list` response).
5. **Defense-in-depth**: Remove `deletedAt: undefined` from `upsertByName` — guards against manual YAML recreation.
6. **`_write_back_convex_agents` needs no changes** — already uses `agents:list` which skips deleted.
7. **`deactivateExcept` is safe** — only modifies `status`, never `deletedAt`.

## Implementation Plan

### Tasks

- [x] **Task 1: Add archive fields to Convex schema**
  - File: `dashboard/convex/schema.ts`
  - Action: Add three optional string fields to agents table:
    - `memoryContent: v.optional(v.string())` — archived MEMORY.md content
    - `historyContent: v.optional(v.string())` — archived HISTORY.md content
    - `sessionData: v.optional(v.string())` — archived session JSONL content
  - Notes: Fields only populated during soft-delete archive step; cleared after successful restore write-back (optional)

- [x] **Task 2: Add Convex queries and mutations**
  - File: `dashboard/convex/agents.ts`
  - Action — `listDeleted` query:
    - Returns agents WHERE `deletedAt` is truthy
    - Same structure as `list` query but inverse filter
  - Action — `archiveAgentData` mutation:
    - Args: `agentName: string`, `memoryContent?: string`, `historyContent?: string`, `sessionData?: string`
    - Finds agent by name, patches with archive fields
    - No activity event needed (archive is internal bookkeeping)
  - Action — `restoreAgent` mutation:
    - Args: `agentName: string`
    - Finds agent by name, clears `deletedAt` (set to `undefined`)
    - Writes `"agent_restored"` activity event (add to `eventType` union in schema)
    - Throws if agent not found or not deleted
  - Action — `getArchive` query:
    - Args: `agentName: string`
    - Returns `{ memoryContent, historyContent, sessionData }` for the agent
    - Used by Python write-back to restore archived files
  - Action — Defense-in-depth in `upsertByName`:
    - Remove line 40: `deletedAt: undefined`
    - Instead: if existing agent has `deletedAt`, **skip the upsert entirely** (log warning if needed — the YAML should have been cleaned up)

- [x] **Task 3: Add activity event type for restore**
  - File: `dashboard/convex/schema.ts`
  - Action: Add `v.literal("agent_restored")` to activities `eventType` union (after `"agent_deleted"`)

- [x] **Task 4: Add Python bridge methods**
  - File: `nanobot/mc/bridge.py`
  - Action — `list_deleted_agents()`:
    - Calls `self.query("agents:listDeleted")`
    - Returns `list[dict[str, Any]]` (snake_case keys)
  - Action — `archive_agent_data(name, memory_content, history_content, session_data)`:
    - Calls `self.mutation("agents:archiveAgentData", {...})`
    - Sends only non-None fields
  - Action — `get_agent_archive(name)`:
    - Calls `self.query("agents:getArchive", {"agent_name": name})`
    - Returns dict with `memory_content`, `history_content`, `session_data` (or None)

- [x] **Task 5: Add cleanup step in sync — archive + delete local folders**
  - File: `nanobot/mc/gateway.py`
  - Action — New function `_cleanup_deleted_agents(bridge, agents_dir)`:
    ```python
    def _cleanup_deleted_agents(bridge: ConvexBridge, agents_dir: Path) -> None:
        """Archive local data for soft-deleted agents, then remove their folders."""
        try:
            deleted_agents = bridge.list_deleted_agents()
        except Exception:
            logger.exception("Failed to list deleted agents for cleanup")
            return

        for agent_data in deleted_agents:
            name = agent_data.get("name")
            if not name:
                continue
            agent_dir = agents_dir / name
            if not agent_dir.is_dir():
                continue  # Already cleaned up

            # Read local files
            memory = _read_file_or_none(agent_dir / "memory" / "MEMORY.md")
            history = _read_file_or_none(agent_dir / "memory" / "HISTORY.md")
            session = _read_session_data(agent_dir / "sessions")

            # Archive to Convex
            try:
                bridge.archive_agent_data(name, memory, history, session)
                logger.info("Archived agent data for '%s'", name)
            except Exception:
                logger.exception("Failed to archive agent '%s' — skipping cleanup", name)
                continue  # Don't delete if archive failed

            # Delete local folder
            import shutil
            shutil.rmtree(agent_dir)
            logger.info("Removed local folder for deleted agent '%s'", name)
    ```
  - Action — Helper functions:
    - `_read_file_or_none(path: Path) -> str | None` — returns file content or None if not exists
    - `_read_session_data(sessions_dir: Path) -> str | None` — reads all `.jsonl` files in sessions dir, concatenates (or reads primary `mc_task_*.jsonl`)
  - Action — Integrate into `sync_agent_registry()`:
    - Call `_cleanup_deleted_agents(bridge, agents_dir)` as **Step 0a** (before `_write_back_convex_agents`)
  - Notes: Archive MUST succeed before local deletion (fail-safe). If archive fails, skip cleanup for that agent.

- [x] **Task 6: Restore archived data in write-back**
  - File: `nanobot/mc/gateway.py`
  - Action: In `_write_back_convex_agents()`, when creating a new agent (the `else` branch at line 161):
    - After `bridge.write_agent_config(agent_data, agents_dir)`, call `bridge.get_agent_archive(name)`
    - If archive exists: write `MEMORY.md`, `HISTORY.md`, session JSONL to the appropriate subdirectories
    ```python
    # After write_agent_config in the "else" branch (new agent creation):
    try:
        archive = bridge.get_agent_archive(name)
        if archive:
            _restore_archived_files(agents_dir / name, archive)
            logger.info("Restored archived data for agent '%s'", name)
    except Exception:
        logger.exception("Failed to restore archive for agent '%s'", name)
    ```
  - Action — Helper function `_restore_archived_files(agent_dir, archive)`:
    - Writes `memory/MEMORY.md` if `memory_content` present
    - Writes `memory/HISTORY.md` if `history_content` present
    - Writes `sessions/mc_task_{name}.jsonl` if `session_data` present
  - Notes: Only runs when YAML didn't exist locally (i.e., agent was restored from Convex). Normal write-back updates skip this.

- [x] **Task 7: Frontend UI — Deleted group in AgentSidebar**
  - File: `dashboard/components/AgentSidebar.tsx`
  - Action — Data fetching:
    - Add `const deletedAgents = useQuery(api.agents.listDeleted);`
    - Add `const restoreAgent = useMutation(api.agents.restoreAgent);`
  - Action — Agent grouping (update useMemo at line 48):
    - No change needed — `deletedAgents` comes from separate query, not filtered from `agents`
  - Action — Deleted group (add after System group, before closing `SidebarContent`):
    - Follow System group's Collapsible pattern (AgentSidebar.tsx:114-137)
    - Use `Trash2` icon + "Deleted" label
    - Default collapsed (`useState(false)`)
    - Only render if `deletedAgents?.length > 0`
  - Action — Restore button per deleted agent:
    - Each `AgentSidebarItem` in deleted group gets `onRestore` callback
    - Restore confirmation dialog (similar to delete dialog at line 151-183)
    - On confirm: `await restoreAgent({ agentName: agent.name })`
  - Action — Update `AgentSidebarItem.tsx`:
    - Add optional `onRestore?: () => void` prop
    - When `onRestore` is provided: show `RotateCcw` (undo) icon button instead of status dot
    - Style deleted agents with reduced opacity or strikethrough to indicate deleted state

### Acceptance Criteria

- [x] **AC 1**: Given an agent is soft-deleted in the UI, when `sync_agent_registry` runs, then the agent's MEMORY.md, HISTORY.md, and session JSONL are archived to Convex AND the local `~/.nanobot/agents/{name}/` folder is deleted.
- [x] **AC 2**: Given a deleted agent's local YAML folder was cleaned up, when `sync_agent_registry` runs again, then the agent does NOT get re-registered in Convex (stays deleted — `deletedAt` preserved).
- [x] **AC 3**: Given deleted agents exist in Convex, when viewing the agent sidebar, then deleted agents appear in a "Deleted" collapsible group below the System group.
- [x] **AC 4**: Given a deleted agent in the "Deleted" group, when the user clicks "Restore" and confirms, then `deletedAt` is cleared in Convex AND the agent moves to the regular agents list.
- [x] **AC 5**: Given a restored agent, when `sync_agent_registry` runs, then the local YAML + memory/history/session files are recreated from Convex archived data.
- [x] **AC 6**: Given a restored agent with archived memory, when the agent executes a task, then it has access to its previous MEMORY.md and HISTORY.md contents.
- [x] **AC 7**: Given a system agent (lead-agent, mc-agent), when delete mode is active, then system agents cannot be deleted (existing behavior preserved).
- [x] **AC 8**: Given `upsertByName` is called for an agent that has `deletedAt` set, then the upsert is skipped (agent stays deleted) — defense-in-depth.
- [x] **AC 9**: Given a deleted agent whose local folder was already cleaned up, when sync runs again, then no error occurs (cleanup is idempotent).
- [x] **AC 10**: Given a deleted agent with no archived data (empty memory/history), when restored, then the agent is recreated with empty memory + history directories (as if newly created).
- [x] **AC 11**: Given archiving to Convex fails for a deleted agent, when cleanup runs, then the local folder is NOT deleted (fail-safe — archive must succeed before deletion).

## Additional Context

### Dependencies

- No external libraries needed — all functionality uses existing Convex SDK, Python stdlib (`shutil`, `pathlib`)
- `write_agent_config()` (bridge.py:441-492) already reconstructs YAML from Convex data — verified complete
- `deactivateExcept` does not interfere with `deletedAt` — verified safe
- `lastActiveAt` survives soft-delete — verified (softDeleteAgent only patches deletedAt)

### Testing Strategy

**Python unit tests** (`tests/mc/test_gateway.py`):
- `test_cleanup_deleted_agents_archives_and_removes` — mock bridge with deleted agents, verify archive called with correct file contents, verify `shutil.rmtree` called
- `test_cleanup_deleted_agents_skips_if_no_local_folder` — deleted agent but no local folder → no error, no archive call
- `test_cleanup_deleted_agents_preserves_folder_on_archive_failure` — archive raises → folder NOT deleted
- `test_restore_archived_files_writes_memory_and_sessions` — verify files written to correct paths
- `test_write_back_restores_archive_for_new_agent` — write-back creates YAML + restores archived data
- `test_upsert_skips_deleted_agent` — sync_agent with deleted agent → upsert skipped

**TypeScript component tests** (extend existing patterns):
- Deleted group renders when deleted agents exist
- Deleted group hidden when no deleted agents
- Restore button triggers `restoreAgent` mutation
- System agents do not appear in deleted group

**Manual testing**:
1. Delete an agent → verify it disappears from regular list → appears in Deleted group
2. Restart MC (triggers sync) → verify agent's local folder is cleaned up
3. Click Restore on deleted agent → verify it moves back to regular list
4. Restart MC again → verify YAML + memory/history are recreated locally
5. Run a task with restored agent → verify memory is accessible

### Notes

- Board-scoped memories (`~/.nanobot/boards/{board}/agents/`) are NOT affected by deleting `~/.nanobot/agents/{name}/` — separate filesystem path
- Session files can reach ~30KB for active agents — well within Convex 1MB document size limit
- `variables` field exists in schema, is not sent via `upsertByName`, and survives soft-delete independently
- Lead Agent visibility is NOT a separate bug — it's a timing consequence of the re-registration cycle; once YAML cleanup is in place, deleted agents stay deleted

## Review Notes

- Adversarial review completed
- Findings: 12 total, 8 fixed, 4 skipped (3 invalid/noise, 1 pre-existing)
- Resolution approach: auto-fix
- Key fixes applied: `shutil.rmtree` exception handling (F3), `archiveAgentData` guard for live agents (F5), `clearAgentArchive` mutation + bridge method to free archive fields post-restore (F7), `getArchive` falsy-string fix (F8), all-None archive call guard (F2), `upsertByName` skip log (F1), cursor affordance for deleted items (F10), session data doc comment (F4)
