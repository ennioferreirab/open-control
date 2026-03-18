---
title: 'Convex Security Hardening'
slug: 'convex-security-hardening'
created: '2026-02-28'
status: 'ready-for-dev'
stepsCompleted: []
tech_stack: ['Convex', 'TypeScript', 'Python']
files_to_modify: ['dashboard/convex/terminalSessions.ts', 'dashboard/convex/steps.ts', 'dashboard/convex/agents.ts', 'dashboard/convex/tasks.ts', 'dashboard/convex/messages.ts', 'dashboard/convex/chats.ts', 'dashboard/convex/skills.ts', 'dashboard/convex/boards.ts', 'terminal_bridge.py', 'nanobot/mc/gateway.py', 'nanobot/mc/bridge.py']
code_patterns: ['Convex mutation/internalMutation distinction', 'ConvexBridge admin_key auth', 'Python argparse CLI patterns']
test_patterns: ['npx convex dev deploy', 'uv run pytest tests/mc/ -v', 'dashboard smoke test']
---

# Tech-Spec: Convex Security Hardening

**Created:** 2026-02-28

## Overview

### Problem Statement

All 100+ Convex mutations and queries are exported as public `mutation()`/`query()`, meaning any client with the Convex deployment URL can call them without authentication. The most critical risk is `terminalSessions:sendInput`, which allows arbitrary command injection into a live Claude Code tmux session — anyone with the deployment URL can execute shell commands on the host machine. Additionally, 23 backend-only mutations (steps, agents, tasks, messages, chats, skills, boards) are callable from any browser, allowing data manipulation that should only come from the Python bridge running with admin auth.

### Solution

Convert backend-only Convex functions from public `mutation()` to `internalMutation()`, which are only callable with an admin key. Harden the Python bridge and terminal_bridge to require `CONVEX_ADMIN_KEY` at startup, and remove the hardcoded Convex URL from `terminal_bridge.py`.

The work is split into 3 phases by risk priority:
1. **Phase 1 (Critical):** Lock down terminal session mutations — the command injection vector
2. **Phase 2 (High):** Convert 23 backend-only functions to `internalMutation`
3. **Phase 3 (Medium):** Harden Python startup to require admin key

### Scope

**In Scope:**
- Converting backend-only mutations to `internalMutation` in 8 Convex files
- Removing hardcoded `_DEFAULT_CONVEX_URL` from `terminal_bridge.py`
- Making `CONVEX_ADMIN_KEY` required in `terminal_bridge.py` and `gateway.py`
- Adding a warning log in `bridge.py` when no admin key is provided
- Updating Python bridge method calls to use `internalMutation`-compatible function names

**Out of Scope:**
- User authentication for dashboard (Convex Auth, Clerk, etc.) — separate story
- Rate limiting or IP allowlisting
- Encrypting terminal session data at rest
- Converting frontend-facing mutations (those called from `.tsx` components via `useMutation`)
- Converting queries to `internalQuery` (read-only, lower risk)

## Context for Development

### Codebase Patterns

- **Convex `mutation` vs `internalMutation`:** Convex exports both `mutation` and `internalMutation` from `"./_generated/server"`. Public `mutation()` functions are callable by any client. `internalMutation()` functions are only callable with admin auth (via admin key). The import line changes from `import { mutation, query } from "./_generated/server"` to `import { mutation, query, internalMutation } from "./_generated/server"`. The function definition changes from `export const foo = mutation({...})` to `export const foo = internalMutation({...})`.
- **Python ConvexBridge:** `nanobot/mc/bridge.py:64-78` — `ConvexBridge.__init__` accepts an optional `admin_key`. When present, it calls `self._client.set_admin_auth(admin_key)`, which enables calling `internalMutation` functions. All bridge methods use `self._client.mutation("module:function", args)` — the function name format stays the same for internal functions.
- **Terminal bridge architecture:** `terminal_bridge.py` is a standalone Python script that connects a local tmux session to Convex. It uses its own `ConvexBridge` instance (line 35-36). It has a hardcoded `_DEFAULT_CONVEX_URL` fallback (line 38) and optional `--admin-key` argument (line 78-81). It calls `terminalSessions:registerTerminal`, `terminalSessions:upsert`, and `terminalSessions:disconnectTerminal` — all backend-only.
- **Dashboard frontend callers:** The dashboard frontend (`components/*.tsx`) calls `terminalSessions:sendInput`, `terminalSessions:get`, and `terminalSessions:listSessions` via `useMutation`/`useQuery`. These 3 functions MUST remain public `mutation()`/`query()`. All other terminal session functions are only called from the Python bridge.
- **Gateway startup:** `nanobot/mc/gateway.py:1152-1165` — the `main()` function resolves the Convex URL and optionally reads `CONVEX_ADMIN_KEY` from the environment. Currently, if no admin key is set, the bridge works in unauthenticated mode (can't call internal functions).

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `dashboard/convex/_generated/server.js:49,59` | Exports `mutation` and `internalMutation` — both are available |
| `dashboard/convex/terminalSessions.ts:1-227` | Terminal session functions — `upsert`, `registerTerminal`, `disconnectTerminal` (backend-only) + `sendInput`, `get`, `listSessions` (frontend-facing) |
| `dashboard/convex/steps.ts:244,303,375,546` | `create`, `batchCreate`, `updateStatus`, `checkAndUnblockDependents` — all backend-only |
| `dashboard/convex/agents.ts:85,240,329,351` | `updateStatus`, `archiveAgentData`, `clearAgentArchive`, `deactivateExcept` — all backend-only |
| `dashboard/convex/tasks.ts:770,449,1065,973` | `updateStatus`, `kickOff`, `updateTaskOutputFiles`, `markStalled` — all backend-only |
| `dashboard/convex/messages.ts:37,81,155,120` | `create`, `postStepCompletion`, `postLeadAgentMessage`, `postSystemError` — all backend-only |
| `dashboard/convex/chats.ts:60` | `updateStatus` — backend-only |
| `dashboard/convex/skills.ts:11,53` | `upsertByName`, `deactivateExcept` — all backend-only |
| `dashboard/convex/boards.ts:176` | `ensureDefaultBoard` — backend-only |
| `terminal_bridge.py:38,73-81` | Hardcoded `_DEFAULT_CONVEX_URL` and optional `--admin-key` argument |
| `nanobot/mc/gateway.py:1152-1165` | Gateway `main()` — optional `CONVEX_ADMIN_KEY` |
| `nanobot/mc/bridge.py:64-78` | `ConvexBridge.__init__` — optional `admin_key` with `set_admin_auth()` |
| `dashboard/components/TerminalPanel.tsx:16-17` | Frontend caller of `sendInput` and `get` — these must stay public |
| `dashboard/components/AgentSidebarItem.tsx:72-73` | Frontend caller of `listSessions` — this must stay public |

### Technical Decisions

- **`internalMutation` over custom auth middleware:** Convex's built-in `internalMutation` provides zero-config server-side auth gating. No need to implement custom token validation or middleware — the admin key mechanism is already supported by the ConvexClient.
- **Keep `sendInput`, `get`, `listSessions` as public:** These are called from dashboard React components (`TerminalPanel.tsx`, `AgentSidebarItem.tsx`). Converting them to internal would break the frontend. Dashboard auth (Clerk/Convex Auth) is a separate concern.
- **Required vs optional admin key:** Currently `admin_key` is optional in both `terminal_bridge.py` and `gateway.py`. After converting mutations to `internalMutation`, calls without admin auth will fail at runtime. Making the key required at startup (with a clear error message) prevents confusing runtime errors.
- **Remove hardcoded Convex URL:** `terminal_bridge.py` has `_DEFAULT_CONVEX_URL = "https://affable-clownfish-908.convex.cloud"` hardcoded. This is a security smell — the deployment URL should come from environment or CLI args only, never from source code.
- **Warning log in `bridge.py`:** The `ConvexBridge` class is used by both `gateway.py` and `terminal_bridge.py`. Adding a warning when no admin key is provided helps operators diagnose "permission denied" errors without a hard crash (the gateway may still work for some operations).
- **Phased approach:** Phase 1 (terminal) addresses the critical command injection vector immediately. Phase 2 (23 functions) is the bulk of the work but lower urgency. Phase 3 (Python startup) is a hardening measure.

## Implementation Plan

### Tasks

- [ ] **Phase 1, Task 1: Convert terminal session backend-only mutations to `internalMutation`**
  - File: `dashboard/convex/terminalSessions.ts`
  - Action:
    1. Add `internalMutation` to the import: `import { mutation, query, internalMutation } from "./_generated/server";`
    2. Change `export const upsert = mutation({` → `export const upsert = internalMutation({` (line 5)
    3. Change `export const registerTerminal = mutation({` → `export const registerTerminal = internalMutation({` (line 113)
    4. Change `export const disconnectTerminal = mutation({` → `export const disconnectTerminal = internalMutation({` (line 188)
    5. Leave `sendInput` as `mutation` (line 56) — called from `TerminalPanel.tsx`
    6. Leave `get` as `query` (line 46) — called from `TerminalPanel.tsx`
    7. Leave `listSessions` as `query` (line 81) — called from `AgentSidebarItem.tsx`
  - Notes: After this change, `upsert`, `registerTerminal`, and `disconnectTerminal` can only be called with admin auth. The terminal bridge must provide `CONVEX_ADMIN_KEY` to call these.

- [ ] **Phase 1, Task 2: Remove hardcoded Convex URL from `terminal_bridge.py`**
  - File: `terminal_bridge.py`
  - Action:
    1. Remove the `_DEFAULT_CONVEX_URL = "https://affable-clownfish-908.convex.cloud"` constant (line 38)
    2. Update the `--convex-url` argument default to only use `CONVEX_URL` env var: `default=os.environ.get("CONVEX_URL")` (line 75)
    3. Add a startup check after `parse_args()`: if `args.convex_url` is `None`, print an error and exit: `"Error: Convex URL required. Set CONVEX_URL env var or pass --convex-url."`
  - Notes: The hardcoded URL is a deployment-specific value that should never be in source code.

- [ ] **Phase 1, Task 3: Make `CONVEX_ADMIN_KEY` required in `terminal_bridge.py`**
  - File: `terminal_bridge.py`
  - Action:
    1. Add a startup check after `parse_args()`: if `args.admin_key` is `None`, print an error and exit: `"Error: CONVEX_ADMIN_KEY required. Set CONVEX_ADMIN_KEY env var or pass --admin-key."`
    2. This check should come after the Convex URL check from Task 2
  - Notes: Since `upsert`, `registerTerminal`, and `disconnectTerminal` are now `internalMutation`, they require admin auth. Without the key, the bridge would fail at runtime with cryptic Convex errors.

- [ ] **Phase 2, Task 4: Convert `steps.ts` backend-only mutations to `internalMutation`**
  - File: `dashboard/convex/steps.ts`
  - Action:
    1. Add `internalMutation` to the import: `import { mutation, query, internalMutation } from "./_generated/server";` (line 4)
    2. Change `export const create = mutation({` → `export const create = internalMutation({` (line 244)
    3. Change `export const batchCreate = mutation({` → `export const batchCreate = internalMutation({` (line 303)
    4. Change `export const updateStatus = mutation({` → `export const updateStatus = internalMutation({` (line 375)
    5. Change `export const checkAndUnblockDependents = mutation({` → `export const checkAndUnblockDependents = internalMutation({` (line 546)
    6. Leave `acceptHumanStep` as `mutation` (line 431) — called from `ExecutionPlanTab.tsx`
    7. Leave `deleteStep` as `mutation` (line 516) — called from `StepCard.tsx`
    8. Leave queries (`getByTask`, `listAll`, `listByBoard`) as `query`
  - Notes: These 4 mutations are only called from `nanobot/mc/bridge.py` methods: `create_step()`, `batch_create_steps()`, `update_step_status()`, `check_and_unblock_dependents()`.

- [ ] **Phase 2, Task 5: Convert `agents.ts` backend-only mutations to `internalMutation`**
  - File: `dashboard/convex/agents.ts`
  - Action:
    1. Add `internalMutation` to the import (line 1)
    2. Change `export const updateStatus = mutation({` → `export const updateStatus = internalMutation({` (line 85)
    3. Change `export const deactivateExcept = mutation({` → `export const deactivateExcept = internalMutation({` (line 351)
    4. Change `export const archiveAgentData = mutation({` → `export const archiveAgentData = internalMutation({` (line 240)
    5. Change `export const clearAgentArchive = mutation({` → `export const clearAgentArchive = internalMutation({` (line 329)
    6. Leave `upsertByName` as `mutation` (line 12) — called from gateway sync but ALSO needs admin key context; however, since the gateway already uses admin key, converting this is safe. **Convert:** `export const upsertByName = internalMutation({`
    7. Leave `updateConfig`, `setEnabled`, `softDeleteAgent`, `restoreAgent` as `mutation` — called from frontend components
    8. Leave `list` as `query` — called from frontend
  - Notes: 5 mutations converted. The remaining mutations are called from dashboard React components.

- [ ] **Phase 2, Task 6: Convert `tasks.ts` backend-only mutations to `internalMutation`**
  - File: `dashboard/convex/tasks.ts`
  - Action:
    1. Add `internalMutation` to the import (line 1)
    2. Change `export const updateStatus = mutation({` → `export const updateStatus = internalMutation({` (line 770)
    3. Change `export const kickOff = mutation({` → `export const kickOff = internalMutation({` (line 449)
    4. Change `export const updateTaskOutputFiles = mutation({` → `export const updateTaskOutputFiles = internalMutation({` (line 1065)
    5. Change `export const markStalled = mutation({` → `export const markStalled = internalMutation({` (line 973)
    6. Leave all other mutations as `mutation` — `create`, `toggleFavorite`, `updateExecutionPlan`, `updateTags`, `pauseTask`, `resumeTask`, `approveAndKickOff`, `retry`, `approve`, `manualMove`, `deny`, `returnToLeadAgent`, `softDelete`, `clearAllDone`, `addTaskFiles`, `removeTaskFile`, `restore`, `updateTitle`, `updateDescription` are called from frontend components
    7. Leave queries as `query`
  - Notes: `updateExecutionPlan` (line 416) is also backend-only (called from `bridge.update_execution_plan()`). **Also convert** `export const updateExecutionPlan = internalMutation({`.

- [ ] **Phase 2, Task 7: Convert `messages.ts` backend-only mutations to `internalMutation`**
  - File: `dashboard/convex/messages.ts`
  - Action:
    1. Add `internalMutation` to the import (line 1)
    2. Change `export const create = mutation({` → `export const create = internalMutation({` (line 37)
    3. Change `export const postStepCompletion = mutation({` → `export const postStepCompletion = internalMutation({` (line 81)
    4. Change `export const postLeadAgentMessage = mutation({` → `export const postLeadAgentMessage = internalMutation({` (line 155)
    5. Change `export const postSystemError = mutation({` → `export const postSystemError = internalMutation({` (line 120)
    6. Leave `postUserPlanMessage`, `postComment`, `sendThreadMessage` as `mutation` — called from frontend `ThreadInput.tsx`
    7. Leave `listByTask` as `query`
  - Notes: These 4 mutations are only called from `nanobot/mc/bridge.py` methods.

- [ ] **Phase 2, Task 8: Convert `chats.ts` backend-only mutation to `internalMutation`**
  - File: `dashboard/convex/chats.ts`
  - Action:
    1. Add `internalMutation` to the import (line 1)
    2. Change `export const updateStatus = mutation({` → `export const updateStatus = internalMutation({` (line 60)
    3. Leave `send` as `mutation` — called from `ChatPanel.tsx`
    4. Leave `listByAgent` as `query`
  - Notes: `updateStatus` is only called from the Python bridge for chat processing lifecycle.

- [ ] **Phase 2, Task 9: Convert `skills.ts` backend-only mutations to `internalMutation`**
  - File: `dashboard/convex/skills.ts`
  - Action:
    1. Add `internalMutation` to the import (line 1)
    2. Change `export const upsertByName = mutation({` → `export const upsertByName = internalMutation({` (line 11)
    3. Change `export const deactivateExcept = mutation({` → `export const deactivateExcept = internalMutation({` (line 53)
    4. Leave `list` as `query`
  - Notes: Both mutations are only called from `gateway.py` during skill sync at startup.

- [ ] **Phase 2, Task 10: Convert `boards.ts` backend-only mutation to `internalMutation`**
  - File: `dashboard/convex/boards.ts`
  - Action:
    1. Add `internalMutation` to the import (line 2)
    2. Change `export const ensureDefaultBoard = mutation({` → `export const ensureDefaultBoard = internalMutation({` (line 176)
    3. Leave `create`, `update`, `softDelete`, `setDefault` as `mutation` — called from frontend components
    4. Leave queries as `query`
  - Notes: `ensureDefaultBoard` is only called from `bridge.ensure_default_board()`.

- [ ] **Phase 3, Task 11: Make `CONVEX_ADMIN_KEY` required in `gateway.py`**
  - File: `nanobot/mc/gateway.py`
  - Action:
    1. After the `convex_url` check (line 1157-1162), add a check for `admin_key`:
       ```python
       admin_key = os.environ.get("CONVEX_ADMIN_KEY")
       if not admin_key:
           logger.error(
               "[gateway] Cannot start: CONVEX_ADMIN_KEY not set. "
               "Set CONVEX_ADMIN_KEY env var for server-side auth."
           )
           return
       ```
    2. Move the existing `admin_key = os.environ.get("CONVEX_ADMIN_KEY")` line (1164) into this check block
  - Notes: After converting mutations to `internalMutation`, the gateway cannot function without admin auth. Failing early with a clear message prevents confusing runtime errors.

- [ ] **Phase 3, Task 12: Add warning log in `bridge.py` when no admin key**
  - File: `nanobot/mc/bridge.py`
  - Action:
    1. In `ConvexBridge.__init__` (line 67-78), add a warning when `admin_key` is None or empty:
       ```python
       if not admin_key:
           logger.warning(
               "ConvexBridge initialized WITHOUT admin key — "
               "internal mutations will fail. Set CONVEX_ADMIN_KEY."
           )
       ```
    2. Add this after the existing `if admin_key:` block (line 76-77)
  - Notes: This is a defense-in-depth measure. The gateway already checks for admin key (Task 11), but the warning helps diagnose issues if `ConvexBridge` is instantiated from other contexts.

### Acceptance Criteria

- [ ] **AC 1:** Given the Convex deployment is updated, when an unauthenticated client calls `terminalSessions:upsert`, `terminalSessions:registerTerminal`, or `terminalSessions:disconnectTerminal` without admin auth, then the call fails with a permission error.

- [ ] **AC 2:** Given the Convex deployment is updated, when the dashboard frontend calls `terminalSessions:sendInput`, `terminalSessions:get`, and `terminalSessions:listSessions`, then they succeed without admin auth (still public).

- [ ] **AC 3:** Given `terminal_bridge.py` is started without `CONVEX_ADMIN_KEY`, then it exits immediately with a clear error message before attempting any Convex calls.

- [ ] **AC 4:** Given `terminal_bridge.py` is started without `CONVEX_URL` and no `--convex-url` flag, then it exits immediately with a clear error message (no hardcoded fallback).

- [ ] **AC 5:** Given `terminal_bridge.py` is started with both `CONVEX_URL` and `CONVEX_ADMIN_KEY`, then it connects and functions normally — registering, polling, and disconnecting terminal sessions.

- [ ] **AC 6:** Given the Phase 2 mutations are converted to `internalMutation`, when running `npx convex run steps:create '{"taskId":"...","title":"test","description":"test","assignedAgent":"test","order":0}'` from the CLI without admin auth, then the call fails with a permission error.

- [ ] **AC 7:** Given all Phase 2 mutations are converted, when the Python gateway runs with `CONVEX_ADMIN_KEY`, then all agent sync, skill sync, task execution, step creation, and message posting operations succeed normally.

- [ ] **AC 8:** Given `gateway.py` is started without `CONVEX_ADMIN_KEY`, then it logs an error and exits before attempting agent/skill sync.

- [ ] **AC 9:** Given all changes are deployed, the dashboard UI functions normally — task creation, kanban drag-drop, terminal panel, agent sidebar, chat, activity feed, and all user-facing features work without regression.

- [ ] **AC 10:** Given all changes are deployed, `npx convex dev` deploys without TypeScript or schema errors.

## Additional Context

### Dependencies

- No new packages required — `internalMutation` is already exported by Convex's `_generated/server`
- Phase 1 (Tasks 1-3) is independent and should be deployed first due to critical risk
- Phase 2 (Tasks 4-10) depends on the gateway and bridge already using admin auth (which they do when `CONVEX_ADMIN_KEY` is set)
- Phase 3 (Tasks 11-12) should be deployed last, after verifying all environments have `CONVEX_ADMIN_KEY` configured

### Testing Strategy

- **Automated tests:**
  1. `uv run pytest tests/mc/ -v` — all existing bridge tests must pass (they mock `ConvexClient`, so internal vs public is transparent)
  2. `npx convex dev` — deployment must succeed without errors

- **Manual testing steps:**
  1. Deploy with `npx convex dev` — verify no TypeScript errors
  2. Open the dashboard — verify task creation, kanban board, activity feed work
  3. Open a terminal panel — verify `sendInput` still works (type a command, see output)
  4. Start `terminal_bridge.py` with admin key — verify it registers and polls normally
  5. Start `terminal_bridge.py` without admin key — verify it exits with clear error
  6. Start `terminal_bridge.py` without `CONVEX_URL` — verify it exits with clear error
  7. Start the gateway with admin key — verify agent/skill sync succeeds
  8. Start the gateway without admin key — verify it exits with clear error
  9. From CLI, try `npx convex run steps:create` without admin auth — verify it fails
  10. From CLI, try `npx convex run terminalSessions:upsert` without admin auth — verify it fails

### Notes

- The `internalMutation` change is purely a Convex-level access control change. The Python `ConvexClient` calls internal functions the same way as public ones — the difference is that internal functions require `set_admin_auth()` to have been called on the client.
- Queries are intentionally left as public `query()` in this story. They are read-only and lower risk. A future story could convert backend-only queries to `internalQuery` for defense-in-depth.
- `tasks:updateExecutionPlan` (line 416) was not in the original plan but is also backend-only — it's included in Task 6 for completeness.
- `agents:upsertByName` (line 12) is also backend-only (only called from gateway sync) — it's included in Task 5.
- Some Phase 2 mutations (`updateTaskOutputFiles`, `markStalled`, `chats:updateStatus`) may be unused code. Converting them to `internalMutation` is still correct — if they're unused, they're harmless as internal; if they're used later, they'll require admin auth by default.
