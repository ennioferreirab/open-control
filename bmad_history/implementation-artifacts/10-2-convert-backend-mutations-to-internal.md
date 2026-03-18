# Story 10.2: Convert Backend-Only Mutations to internalMutation

Status: ready-for-dev

## Story

As the system operator,
I want all 23 backend-only Convex mutations (in steps, agents, tasks, messages, chats, skills, and boards) converted from public `mutation()` to `internalMutation()`,
so that only the Python bridge with admin auth can call these functions, preventing unauthorized data manipulation from any browser.

## Acceptance Criteria

1. **AC 6:** Given the Phase 2 mutations are converted to `internalMutation`, when running `npx convex run steps:create '{"taskId":"...","title":"test","description":"test","assignedAgent":"test","order":0}'` from the CLI without admin auth, then the call fails with a permission error.

2. **AC 7:** Given all Phase 2 mutations are converted, when the Python gateway runs with `CONVEX_ADMIN_KEY`, then all agent sync, skill sync, task execution, step creation, and message posting operations succeed normally.

3. **AC 9:** Given all changes are deployed, the dashboard UI functions normally — task creation, kanban drag-drop, terminal panel, agent sidebar, chat, activity feed, and all user-facing features work without regression.

4. **AC 10:** Given all changes are deployed, `npx convex dev` deploys without TypeScript or schema errors.

## Tasks / Subtasks

- [ ] Task 4: Convert `steps.ts` backend-only mutations (AC: 6, 7)
  - [ ] 4.1 Add `internalMutation` to import: `import { mutation, query, internalMutation } from "./_generated/server";` (line 4)
  - [ ] 4.2 `create` (line 244): `mutation` → `internalMutation`
  - [ ] 4.3 `batchCreate` (line 303): `mutation` → `internalMutation`
  - [ ] 4.4 `updateStatus` (line 375): `mutation` → `internalMutation`
  - [ ] 4.5 `checkAndUnblockDependents` (line 546): `mutation` → `internalMutation`
  - [ ] 4.6 LEAVE as `mutation`: `acceptHumanStep` (line 431, called from `ExecutionPlanTab.tsx`), `deleteStep` (line 516, called from `StepCard.tsx`)
  - [ ] 4.7 LEAVE all queries as `query`

- [ ] Task 5: Convert `agents.ts` backend-only mutations (AC: 7, 9)
  - [ ] 5.1 Add `internalMutation` to import (line 1)
  - [ ] 5.2 `updateStatus` (line 85): `mutation` → `internalMutation`
  - [ ] 5.3 `deactivateExcept` (line 351): `mutation` → `internalMutation`
  - [ ] 5.4 `archiveAgentData` (line 240): `mutation` → `internalMutation`
  - [ ] 5.5 `clearAgentArchive` (line 329): `mutation` → `internalMutation`
  - [ ] 5.6 `upsertByName` (line 12): `mutation` → `internalMutation` — only called from gateway sync
  - [ ] 5.7 LEAVE as `mutation`: `updateConfig`, `setEnabled`, `softDeleteAgent`, `restoreAgent` (called from frontend)
  - [ ] 5.8 LEAVE `list` as `query`

- [ ] Task 6: Convert `tasks.ts` backend-only mutations (AC: 7, 9)
  - [ ] 6.1 Add `internalMutation` to import (line 1)
  - [ ] 6.2 `updateStatus` (line 770): `mutation` → `internalMutation`
  - [ ] 6.3 `kickOff` (line 449): `mutation` → `internalMutation`
  - [ ] 6.4 `updateTaskOutputFiles` (line 1065): `mutation` → `internalMutation`
  - [ ] 6.5 `markStalled` (line 973): `mutation` → `internalMutation`
  - [ ] 6.6 `updateExecutionPlan` (line 416): `mutation` → `internalMutation` — backend-only, called from `bridge.update_execution_plan()`
  - [ ] 6.7 LEAVE as `mutation`: `create`, `toggleFavorite`, `updateTags`, `pauseTask`, `resumeTask`, `approveAndKickOff`, `retry`, `approve`, `manualMove`, `deny`, `returnToLeadAgent`, `softDelete`, `clearAllDone`, `addTaskFiles`, `removeTaskFile`, `restore`, `updateTitle`, `updateDescription` (all called from frontend)
  - [ ] 6.8 LEAVE all queries as `query`

- [ ] Task 7: Convert `messages.ts` backend-only mutations (AC: 7)
  - [ ] 7.1 Add `internalMutation` to import (line 1)
  - [ ] 7.2 `create` (line 37): `mutation` → `internalMutation`
  - [ ] 7.3 `postStepCompletion` (line 81): `mutation` → `internalMutation`
  - [ ] 7.4 `postLeadAgentMessage` (line 155): `mutation` → `internalMutation`
  - [ ] 7.5 `postSystemError` (line 120): `mutation` → `internalMutation`
  - [ ] 7.6 LEAVE as `mutation`: `postUserPlanMessage`, `postComment`, `sendThreadMessage` (called from frontend `ThreadInput.tsx`)
  - [ ] 7.7 LEAVE `listByTask` as `query`

- [ ] Task 8: Convert `chats.ts` backend-only mutation (AC: 7)
  - [ ] 8.1 Add `internalMutation` to import (line 1)
  - [ ] 8.2 `updateStatus` (line 60): `mutation` → `internalMutation`
  - [ ] 8.3 LEAVE `send` as `mutation` (called from `ChatPanel.tsx`)
  - [ ] 8.4 LEAVE `listByAgent` as `query`

- [ ] Task 9: Convert `skills.ts` backend-only mutations (AC: 7)
  - [ ] 9.1 Add `internalMutation` to import (line 1)
  - [ ] 9.2 `upsertByName` (line 11): `mutation` → `internalMutation`
  - [ ] 9.3 `deactivateExcept` (line 53): `mutation` → `internalMutation`
  - [ ] 9.4 LEAVE `list` as `query`

- [ ] Task 10: Convert `boards.ts` backend-only mutation (AC: 7)
  - [ ] 10.1 Add `internalMutation` to import (line 2)
  - [ ] 10.2 `ensureDefaultBoard` (line 176): `mutation` → `internalMutation`
  - [ ] 10.3 LEAVE as `mutation`: `create`, `update`, `softDelete`, `setDefault` (called from frontend)
  - [ ] 10.4 LEAVE all queries as `query`

## Dev Notes

### Critical Context

This is **Phase 2 (High Priority)** of Convex Security Hardening. These 23 mutations are only called from the Python bridge (`nanobot/mc/bridge.py` and `nanobot/mc/gateway.py`), never from frontend components. Converting them to `internalMutation` means they require admin auth, preventing unauthorized data manipulation.

**Prerequisite**: Story 10-1 must be deployed first (terminal session lockdown is the critical security vector).

### Codebase Patterns

- **`mutation()` vs `internalMutation()`**: Both exported from `"./_generated/server"`. The ONLY code change is the function wrapper — `mutation({...})` → `internalMutation({...})`. Args, handler, return type all stay identical. The Python bridge calls them the same way via `self._client.mutation("module:function", args)`.

- **Import pattern**: Each file already imports `mutation` from `"./_generated/server"`. Add `internalMutation` to the same import destructure. Example: `import { mutation, query, internalMutation } from "./_generated/server";`

- **Python bridge callers**: `nanobot/mc/bridge.py` methods call Convex functions via `self._client.mutation("steps:create", {...})`. The function name format is identical for internal mutations. The bridge works with admin auth when `CONVEX_ADMIN_KEY` is set (which it already is in production).

### Frontend Caller Safety Check

Before converting ANY function, verify it's not called from a `.tsx` component. The following frontend callers MUST remain public:

| Frontend Component | Convex Function | Must Stay Public |
|---|---|---|
| `ExecutionPlanTab.tsx` | `steps:acceptHumanStep` | Yes |
| `StepCard.tsx` | `steps:deleteStep` | Yes |
| `AgentConfigEditor.tsx` | `agents:updateConfig` | Yes |
| `AgentSidebarItem.tsx` | `agents:setEnabled`, `agents:softDeleteAgent`, `agents:restoreAgent` | Yes |
| `TaskCreation*.tsx` | `tasks:create` | Yes |
| `KanbanBoard.tsx` | `tasks:manualMove` | Yes |
| `TaskDetailSheet.tsx` | `tasks:updateTitle`, `tasks:updateDescription`, `tasks:softDelete`, `tasks:toggleFavorite`, `tasks:updateTags`, etc. | Yes |
| `ThreadInput.tsx` | `messages:postUserPlanMessage`, `messages:postComment`, `messages:sendThreadMessage` | Yes |
| `ChatPanel.tsx` | `chats:send` | Yes |
| `BoardManager.tsx` | `boards:create`, `boards:update`, `boards:softDelete`, `boards:setDefault` | Yes |

### Files to Modify

| File | Functions to Convert | Count |
|------|---------------------|-------|
| `dashboard/convex/steps.ts` | `create`, `batchCreate`, `updateStatus`, `checkAndUnblockDependents` | 4 |
| `dashboard/convex/agents.ts` | `updateStatus`, `deactivateExcept`, `archiveAgentData`, `clearAgentArchive`, `upsertByName` | 5 |
| `dashboard/convex/tasks.ts` | `updateStatus`, `kickOff`, `updateTaskOutputFiles`, `markStalled`, `updateExecutionPlan` | 5 |
| `dashboard/convex/messages.ts` | `create`, `postStepCompletion`, `postLeadAgentMessage`, `postSystemError` | 4 |
| `dashboard/convex/chats.ts` | `updateStatus` | 1 |
| `dashboard/convex/skills.ts` | `upsertByName`, `deactivateExcept` | 2 |
| `dashboard/convex/boards.ts` | `ensureDefaultBoard` | 1 |
| **Total** | | **22** |

### Testing

- `npx convex dev` — must deploy without TypeScript errors
- `uv run pytest tests/mc/ -v` — all bridge tests must pass
- Manual: open dashboard → verify task creation, kanban, activity feed, terminal panel, agent sidebar, chat all work
- Manual: `npx convex run steps:create` without admin auth → should fail

### Project Structure Notes

- All Convex functions in `dashboard/convex/` directory
- Each file has its own imports — add `internalMutation` to each file independently
- No schema changes needed — `internalMutation` uses the same validators

### References

- [Source: _bmad-output/implementation-artifacts/tech-spec-convex-security-hardening.md#Phase 2]
- [Source: dashboard/convex/steps.ts:244,303,375,546]
- [Source: dashboard/convex/agents.ts:12,85,240,329,351]
- [Source: dashboard/convex/tasks.ts:416,449,770,973,1065]
- [Source: dashboard/convex/messages.ts:37,81,120,155]
- [Source: dashboard/convex/chats.ts:60]
- [Source: dashboard/convex/skills.ts:11,53]
- [Source: dashboard/convex/boards.ts:176]
- [Source: nanobot/mc/bridge.py:67-78]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
