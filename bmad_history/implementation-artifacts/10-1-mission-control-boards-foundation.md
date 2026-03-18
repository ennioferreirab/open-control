# Story 10.1: Mission Control Boards — Schema & CRUD Foundation

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Mission Control user**,
I want to create and manage boards that group tasks and scope agent visibility,
so that I can organize work into separate contexts where each board has its own set of enabled agents and isolated agent memory.

## Acceptance Criteria

### AC1: Convex Schema — `boards` Table

**Given** the existing Convex schema with tasks, agents, messages, activities, skills, taskTags, settings tables
**When** the schema is extended
**Then** a new `boards` table is created with:
- `name`: string (unique board name, kebab-case, e.g. "project-alpha")
- `displayName`: string (human-readable, e.g. "Project Alpha")
- `description`: optional string
- `enabledAgents`: string[] (array of agent names enabled on this board)
- `isDefault`: optional boolean (marks the default board — exactly one board must be default)
- `createdAt`: string (ISO 8601)
- `updatedAt`: string (ISO 8601)
- `deletedAt`: optional string (soft-delete, consistent with tasks/agents pattern)
**And** indexes: `by_name` (unique lookup), `by_isDefault`
**And** the Convex dev server starts without schema validation errors
**And** existing data continues to work — all pre-existing tasks and agents remain functional

### AC2: Default Board Auto-Creation

**Given** the system starts and no boards exist in Convex
**When** the gateway sync runs (or the dashboard loads for the first time)
**Then** a default board is created: `{ name: "default", displayName: "Default", isDefault: true, enabledAgents: [] }`
**And** an empty `enabledAgents` array on the default board means ALL registered agents are enabled (open-access semantics)
**And** system agents (lead-agent, mc-agent) are ALWAYS available on every board regardless of `enabledAgents`

### AC3: Board CRUD Mutations

**Given** the boards table exists
**When** Convex mutations are created
**Then** the following mutations are available:
- `boards.create`: Create a new board (validates unique name, kebab-case)
- `boards.update`: Update board displayName, description, enabledAgents
- `boards.softDelete`: Soft-delete a board (cannot delete the default board)
- `boards.setDefault`: Change which board is the default (unsets previous default)
**And** the following queries are available:
- `boards.list`: List all non-deleted boards
- `boards.getByName`: Get a single board by name
- `boards.getDefault`: Get the default board
**And** every mutation writes a corresponding activity event (consistent with existing patterns)

### AC4: Task-Board Association

**Given** the tasks table exists
**When** the schema is extended
**Then** the `tasks` table gains a `boardId` field: optional `Id<"boards">`
**And** existing tasks without a boardId are treated as belonging to the default board (backward compatible)
**And** when a new task is created, if no boardId is specified, it is assigned to the currently active board
**And** an index `by_boardId` is added for efficient board-scoped queries

### AC5: Board-Scoped Agent Filtering

**Given** a board has `enabledAgents: ["research-agent", "dev-agent"]`
**When** the orchestrator routes a task on that board
**Then** only "research-agent", "dev-agent", AND system agents (lead-agent, mc-agent) are considered for routing
**And** agents NOT in the board's enabledAgents list are excluded from task planning/assignment
**And** if `enabledAgents` is empty (`[]`), ALL registered agents are eligible (open-access default)

### AC6: Board-Scoped Memory Directories

**Given** a board exists and an agent is enabled on it
**When** the agent executes a task on that board for the first time
**Then** the system creates a board-scoped memory directory: `~/.nanobot/boards/{board-name}/agents/{agent-name}/memory/`
**And** a `MEMORY.md` and `HISTORY.md` are initialized in the board-scoped memory directory
**And** the agent's session key for MC tasks is scoped: `mc:board:{board-name}:task:{agent-name}`
**And** memory consolidation writes to the board-scoped `MEMORY.md` and `HISTORY.md`
**And** the agent's global workspace (`~/.nanobot/agents/{agent-name}/`) remains untouched — board memory is additive, not replacing

### AC7: Agent Context Injection with Board Memory

**Given** an agent is executing a task on a board
**When** the agent loop builds the system prompt
**Then** the `MEMORY.md` loaded into context comes from `~/.nanobot/boards/{board-name}/agents/{agent-name}/memory/MEMORY.md`
**And** if the board-scoped MEMORY.md doesn't exist yet, the system falls back to the agent's global `~/.nanobot/agents/{agent-name}/memory/MEMORY.md`
**And** the agent can write to its board-scoped memory directory via file tools

### AC8: Dashboard — Board Selector in Header

**Given** the dashboard loads
**When** boards exist in Convex
**Then** a board selector dropdown appears in the dashboard header (next to the logo/title)
**And** it shows the current active board name
**And** clicking it shows all available boards
**And** selecting a board switches the view — kanban shows only tasks for that board
**And** the selected board persists in localStorage (survives page refresh)
**And** on first load with no stored preference, the default board is selected

## Tasks / Subtasks

- [x] **Task 1: Extend Convex Schema** (AC: #1, #4)
  - [x] 1.1 Add `boards` table to `convex/schema.ts` with all fields: name, displayName, description, enabledAgents, isDefault, createdAt, updatedAt, deletedAt
  - [x] 1.2 Add indexes: `by_name`, `by_isDefault`
  - [x] 1.3 Add `boardId` optional field (`v.optional(v.id("boards"))`) to `tasks` table
  - [x] 1.4 Add `by_boardId` index to tasks table
  - [x] 1.5 Add new activity event types: `board_created`, `board_updated`, `board_deleted` to the `eventType` union in activities table
  - [x] 1.6 Verify `npx convex dev` starts without errors and existing data is unaffected

- [x] **Task 2: Board CRUD Convex Functions** (AC: #2, #3)
  - [x] 2.1 Create `convex/boards.ts` with mutations: `create`, `update`, `softDelete`, `setDefault`
  - [x] 2.2 Add queries: `list`, `getByName`, `getDefault`
  - [x] 2.3 Validate unique board name (kebab-case pattern: `^[a-z0-9]+(-[a-z0-9]+)*$`)
  - [x] 2.4 Prevent deletion of the default board
  - [x] 2.5 `setDefault` must unset previous default board's `isDefault` flag atomically
  - [x] 2.6 Write activity events for every mutation (reuse `activities.ts` `createActivity` pattern)
  - [x] 2.7 Add `ensureDefaultBoard` internal function — creates default board if none exists

- [x] **Task 3: Task-Board Association** (AC: #4)
  - [x] 3.1 Update `convex/tasks.ts` `createTask` mutation to accept optional `boardId` parameter
  - [x] 3.2 If no `boardId` provided, assign the default board's ID
  - [x] 3.3 Add `listByBoard` query that filters tasks by boardId (used by kanban)
  - [x] 3.4 Ensure existing task queries (`listByStatus`, etc.) continue to work for backward compatibility — they should accept optional boardId filter

- [x] **Task 4: Board-Scoped Agent Filtering in Orchestrator** (AC: #5)
  - [x] 4.1 In `nanobot/mc/orchestrator.py`, when fetching enabled agents for routing, also fetch the task's board config
  - [x] 4.2 Filter agents by board's `enabledAgents` list (if non-empty)
  - [x] 4.3 Always include system agents (`lead-agent`, `mc-agent`) regardless of board config
  - [x] 4.4 Pass board context through to `TaskPlanner` so planning respects board-scoped agents

- [x] **Task 5: Board-Scoped Memory Directories** (AC: #6, #7)
  - [x] 5.1 In `nanobot/mc/executor.py`, resolve board name from task's boardId before running agent
  - [x] 5.2 Create board-scoped memory directory: `~/.nanobot/boards/{board-name}/agents/{agent-name}/memory/` (idempotent)
  - [x] 5.3 Pass board-scoped workspace path to `AgentLoop` instead of global agent workspace
  - [x] 5.4 Update session key format to `mc:board:{board-name}:task:{agent-name}`
  - [x] 5.5 Implement fallback: if board-scoped `MEMORY.md` doesn't exist, copy from global agent memory as initial seed (one-time bootstrap)
  - [x] 5.6 Ensure `end_task_session()` consolidates to board-scoped memory files

- [x] **Task 6: Default Board Bootstrap in Gateway** (AC: #2)
  - [x] 6.1 In `nanobot/mc/gateway.py` `sync_agent_registry()`, after agent sync, call `ensureDefaultBoard` to guarantee default board exists
  - [x] 6.2 Log board creation: "Created default board"

- [x] **Task 7: Dashboard — Board Selector UI** (AC: #8)
  - [x] 7.1 Create `components/BoardSelector.tsx` — dropdown/combobox in the dashboard header
  - [x] 7.2 Use Convex `useQuery` for `boards.list` to populate options
  - [x] 7.3 Store selected boardId in localStorage key `nanobot-active-board`
  - [x] 7.4 On first load: if no stored preference, select default board (query `boards.getDefault`)
  - [x] 7.5 Create React context `BoardContext` (or use zustand store) to provide active boardId across components
  - [x] 7.6 Update `TaskBoard.tsx` (kanban) to use `listByBoard` query filtered by active boardId
  - [x] 7.7 Update `TaskInput` to pass active boardId when creating tasks

- [x] **Task 8: Dashboard — Board Agent Management** (AC: #3, #5)
  - [x] 8.1 Create `components/BoardSettingsSheet.tsx` — slide-over panel for board config
  - [x] 8.2 Show board name, display name, description (editable)
  - [x] 8.3 Show agent multi-select checklist: all registered agents with checkboxes (system agents shown as always-on, non-toggleable)
  - [x] 8.4 Save changes via `boards.update` mutation
  - [x] 8.5 Add "Board Settings" gear icon next to the board selector dropdown

## Dev Notes

### Critical Architecture Decisions

**Board-Scoped Workspace Strategy:**
The agent's workspace is currently a single directory: `~/.nanobot/agents/{agent-name}/`. This story introduces a **hybrid workspace** approach:

```
~/.nanobot/agents/{agent-name}/          ← GLOBAL (unchanged)
  ├── config.yaml                        ← Shared across boards
  ├── SOUL.md                            ← Shared across boards
  ├── skills/                            ← Shared across boards
  └── memory/                            ← Global fallback memory (kept intact)
      ├── MEMORY.md
      └── HISTORY.md

~/.nanobot/boards/{board-name}/          ← NEW: per-board
  └── agents/{agent-name}/
      ├── memory/                        ← Board-scoped memory
      │   ├── MEMORY.md
      │   └── HISTORY.md
      └── sessions/                      ← Board-scoped sessions
          └── mc_board_{board}_task_{agent}.jsonl
```

**Why hybrid, not full isolation:** Agent identity (config, soul, skills) is the same across boards — only memory and sessions diverge per board context. This avoids config duplication and keeps agent updates atomic (edit once, applies everywhere).

**AgentLoop Workspace Override:**
The executor currently passes `workspace = Path.home() / ".nanobot" / "agents" / agent_name`. For board-scoped execution, the workspace must be composed from TWO paths:
1. **Config source**: `~/.nanobot/agents/{agent-name}/` (for config.yaml, SOUL.md, skills)
2. **Memory/session source**: `~/.nanobot/boards/{board-name}/agents/{agent-name}/` (for memory/, sessions/)

The `AgentLoop` constructor currently takes a single `workspace` param. You have two options:
- **Option A (recommended):** Add an optional `memory_workspace` param to AgentLoop. When set, MemoryStore and SessionManager use this path instead of `workspace`. All other bootstrap files (SOUL.md, skills, config) still read from `workspace`.
- **Option B:** Symlink approach — create symlinks in the board-scoped dir pointing to global config files. More fragile, not recommended.

**Session Key Format Change:**
- Current: `mc:task:{agent-name}`
- New: `mc:board:{board-name}:task:{agent-name}`
- The session manager uses this key for JSONL filename via `safe_filename()`. Verify the colon-replacement produces unique filenames.

**Memory Bootstrap (First Run on Board):**
When an agent runs on a board for the first time and no board-scoped MEMORY.md exists:
1. Check if global `~/.nanobot/agents/{agent-name}/memory/MEMORY.md` exists
2. If yes, **copy** it as the initial seed (not symlink — memories diverge from this point)
3. If no, create empty MEMORY.md
4. HISTORY.md always starts empty per board (history is board-specific)

**Backward Compatibility — Default Board:**
- All existing tasks have no `boardId` → treated as default board
- The `listByBoard` query must handle `boardId === undefined` as "default board"
- Existing `listByStatus` query stays unchanged for backward compat; new `listByBoard` is additive
- Agents running tasks without boardId use global workspace (no regression)

### Convex Schema Patterns to Follow

- Soft-delete with `deletedAt` timestamp (same as tasks, agents)
- Activity events for every mutation (same as all existing tables)
- kebab-case name validation (same pattern as agent names: `^[a-z0-9]+(-[a-z0-9]+)*$`)
- Timestamps as ISO 8601 strings (same as tasks.createdAt)
- Use `v.optional()` for new fields on existing tables (backward compatible)

### Architecture Compliance

**Architectural Boundaries — MUST follow:**

| Boundary | Rule | Impact on This Story |
|----------|------|---------------------|
| Bridge is the ONLY Python-Convex integration point | All Convex reads/writes go through `nanobot/mc/bridge.py` | Board queries from orchestrator/executor MUST use bridge methods, not direct SDK |
| One-directional metadata flow: filesystem → bridge → Convex → dashboard | Board memory dirs are filesystem; manifest in Convex | Board creation in Convex triggers NO filesystem action; filesystem dirs created lazily by executor |
| Every mutation writes an activity event | Architectural invariant | All board mutations (create, update, delete, setDefault) must write activities |
| 500-line module limit | New modules stay under 500 lines | `convex/boards.ts` should be well under limit; watch `executor.py` growth |
| camelCase in TypeScript, snake_case in Python, PascalCase for React components | Naming conventions | `boardId` in TS, `board_id` in Python, `BoardSelector.tsx` for component |
| Bridge auto-converts snake_case ↔ camelCase | Key conversion in bridge.py | Board data from Convex arrives as snake_case in Python — no manual conversion needed |

**Executor Changes — Minimal Surface:**
The executor (`nanobot/mc/executor.py`) needs to:
1. Fetch board info for the task (one additional bridge query)
2. Resolve board-scoped memory workspace path
3. Pass it to AgentLoop

Do NOT restructure the executor. Add a helper method `_resolve_board_workspace()` that returns the memory workspace path given a board name and agent name. Keep the change surgical.

**Orchestrator Changes — Agent Filter Injection:**
The orchestrator (`nanobot/mc/orchestrator.py`) already fetches enabled agents from Convex. The change is:
1. After fetching agents, also fetch the task's board config
2. Filter the agent list by board's `enabledAgents` (if non-empty)
3. Pass filtered list to `TaskPlanner`

This is a ~10-line change in the routing flow. Do NOT refactor the orchestrator.

**Dashboard State Management:**
The active board selection is a **global UI concern** (affects kanban, task creation, activity feed, agent sidebar). Use one of:
- React Context (`BoardContext`) — simplest, consistent with existing patterns (no state lib in use)
- localStorage for persistence across refreshes

Do NOT use zustand/jotai/redux — the project doesn't use external state management and shouldn't start now.

### Project Structure Notes

**Files to CREATE:**
- `dashboard/convex/boards.ts` — Board CRUD mutations + queries
- `dashboard/components/BoardSelector.tsx` — Header dropdown component
- `dashboard/components/BoardSettingsSheet.tsx` — Board config slide-over

**Files to MODIFY:**
- `dashboard/convex/schema.ts` — Add boards table + boardId on tasks
- `dashboard/convex/tasks.ts` — Add boardId to createTask, add listByBoard query
- `dashboard/convex/activities.ts` — Add board event types to union (if hardcoded)
- `dashboard/components/DashboardLayout.tsx` (or equivalent header component) — Mount BoardSelector
- `dashboard/components/TaskBoard.tsx` — Filter by active boardId
- `dashboard/components/TaskInput.tsx` — Pass boardId on task creation
- `nanobot/mc/executor.py` — Board workspace resolution + memory_workspace param
- `nanobot/mc/orchestrator.py` — Board-scoped agent filtering
- `nanobot/mc/bridge.py` — Add board query/mutation methods
- `nanobot/mc/gateway.py` — Call ensureDefaultBoard during sync
- `nanobot/agent/loop.py` — Accept optional `memory_workspace` param, pass to MemoryStore/SessionManager

**Files to NOT TOUCH:**
- `nanobot/agent/memory.py` — MemoryStore already takes a workspace path; just pass the board-scoped one
- `nanobot/session/manager.py` — SessionManager already resolves paths from workspace; no changes needed
- `nanobot/agent/context.py` — ContextBuilder reads MEMORY.md from workspace; if workspace is board-scoped, it just works
- Agent YAML configs — remain global, untouched

### Library & Framework Requirements

**No new dependencies required.** This story uses only existing libraries:

| Concern | Library | Already in Project |
|---------|---------|-------------------|
| Convex schema/mutations | `convex` | Yes — `dashboard/convex/` |
| UI components (dropdown, sheet, checkbox) | ShadCN/Radix | Yes — `dashboard/components/ui/` |
| Styling | Tailwind CSS | Yes |
| Python filesystem | `pathlib`, `shutil` | Yes — stdlib |
| Python async | `asyncio` | Yes |

**ShadCN components to use:**
- `DropdownMenu` or `Select` — for BoardSelector
- `Sheet` — for BoardSettingsSheet (same pattern as AgentConfigSheet, TaskDetailSheet)
- `Checkbox` — for agent multi-select in board settings
- `Badge` — for system agent "always on" indicator
- `Button`, `Input`, `Label` — standard form elements

### File Structure Requirements

**New Convex module pattern** — follow existing patterns exactly:

```typescript
// convex/boards.ts — follow same structure as convex/agents.ts
import { v } from "convex/values";
import { mutation, query, internalMutation } from "./_generated/server";

// Queries first, then mutations, then internal functions
// Each mutation: validate → perform action → write activity → return
```

**New React component pattern** — follow existing Sheet pattern:

```
BoardSelector.tsx      → Similar to agent status dropdown patterns
BoardSettingsSheet.tsx → Similar to AgentConfigSheet.tsx (slide-over, form, save)
```

**Python changes** — follow existing patterns:

```python
# bridge.py — add methods following existing pattern:
async def get_board(self, board_name: str) -> dict | None:
async def get_board_by_id(self, board_id: str) -> dict | None:
async def ensure_default_board(self) -> None:

# executor.py — add helper:
def _resolve_board_workspace(self, board_name: str, agent_name: str) -> Path:

# orchestrator.py — modify _route_task() to filter agents by board
```

### Testing Requirements

**Convex Functions (manual verification):**
- Create board → verify in Convex dashboard data viewer
- Create task with boardId → verify association
- Update board enabledAgents → verify in data viewer
- Delete board → verify soft-delete (deletedAt set, still queryable)
- Cannot delete default board → verify error
- Activity events written for each board mutation

**Python (pytest — `uv run pytest`):**
- `_resolve_board_workspace()` returns correct path for given board + agent
- Board-scoped session key format: `mc:board:{board}:task:{agent}`
- Agent filter respects board enabledAgents (mock bridge response)
- System agents always pass filter regardless of enabledAgents
- Empty enabledAgents means all agents pass filter
- Memory bootstrap: copies global MEMORY.md when board-scoped doesn't exist
- Memory bootstrap: creates empty MEMORY.md when no global exists either

**Dashboard (manual verification):**
- Board selector appears in header
- Selecting board filters kanban to show only that board's tasks
- Creating task assigns active boardId
- Board settings sheet opens and shows agent checklist
- System agents shown as always-on (non-toggleable)
- Toggling agents and saving persists to Convex
- Page refresh preserves selected board (localStorage)
- First load with no stored preference selects default board

### References

- [Source: dashboard/convex/schema.ts] — Existing schema (tasks, agents, activities tables)
- [Source: dashboard/convex/agents.ts] — Agent CRUD pattern (upsertByName, softDelete, setEnabled)
- [Source: dashboard/convex/tasks.ts] — Task mutations and queries pattern
- [Source: dashboard/convex/activities.ts] — Activity event creation pattern
- [Source: dashboard/components/AgentConfigSheet.tsx] — Sheet panel UI pattern
- [Source: dashboard/components/AgentSidebar.tsx] — Agent listing with system/registered sections
- [Source: dashboard/lib/constants.ts] — SYSTEM_AGENT_NAMES set
- [Source: nanobot/mc/executor.py] — Task execution flow, AgentLoop instantiation
- [Source: nanobot/mc/orchestrator.py] — Inbox routing, agent filtering, TaskPlanner
- [Source: nanobot/mc/bridge.py] — Python-Convex bridge methods, retry logic
- [Source: nanobot/mc/gateway.py] — Agent registry sync, ensureDefaultBoard insertion point
- [Source: nanobot/agent/loop.py] — AgentLoop constructor (workspace param), end_task_session
- [Source: nanobot/agent/memory.py] — MemoryStore (takes workspace path, consolidation logic)
- [Source: nanobot/agent/context.py] — ContextBuilder (loads MEMORY.md from workspace)
- [Source: nanobot/session/manager.py] — SessionManager (session keys, JSONL storage)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — all tasks completed cleanly. 14/14 new tests passed; 233 regression tests passed.

### Completion Notes List

- **Convex schema**: Added `boards` table with all required fields, `by_name`/`by_isDefault` indexes, `boardId` on tasks with `by_boardId` index, and board activity event types.
- **`convex/boards.ts`** (new): Full CRUD — queries (`list`, `getByName`, `getDefault`, `getById`) + mutations (`create`, `update`, `softDelete`, `setDefault`, `ensureDefaultBoard`). Validates kebab-case name, prevents deleting default board, writes activity events for all mutations.
- **`convex/tasks.ts`**: `create` mutation now accepts optional `boardId`; auto-assigns default board if omitted. Added `listByBoard` query with `includeNoBoardId` for default board backward compat.
- **`nanobot/agent/loop.py`**: Added `memory_workspace: Path | None` param. `ContextBuilder`, `SessionManager`, and `_consolidate_memory` now use `self.memory_workspace` (defaults to `workspace` if not provided — fully backward compatible).
- **`nanobot/mc/executor.py`**: Added `_resolve_board_workspace()` helper that creates board-scoped `memory/` and `sessions/` dirs, bootstraps `MEMORY.md` (copies from global if present, creates empty otherwise), and creates empty `HISTORY.md`. Board session key format: `mc:board:{board_name}:task:{agent_name}`.
- **`nanobot/mc/bridge.py`**: Added `get_board_by_id()` and `ensure_default_board()` methods.
- **`nanobot/mc/orchestrator.py`**: Board-scoped agent filtering — fetches board by `board_id` from task data, filters agents by `enabledAgents` (if non-empty), system agents always pass.
- **`nanobot/mc/gateway.py`**: Calls `bridge.ensure_default_board()` during startup sync.
- **`components/BoardContext.tsx`** (new): React context providing `activeBoardId`, `isDefaultBoard`, `setActiveBoardId`. Persists selection to `localStorage` key `nanobot-active-board`.
- **`components/BoardSelector.tsx`** (new): Header dropdown for board selection with gear icon to open board settings.
- **`components/BoardSettingsSheet.tsx`** (new): Board settings slide-over — editable displayName/description, agent checklist with system agents shown as always-on.
- **`components/KanbanBoard.tsx`**: Uses `listByBoard` query when a board is active; falls back to `list` for no-board context.
- **`components/TaskInput.tsx`**: Passes `boardId` from board context when creating tasks.
- **`components/DashboardLayout.tsx`**: Wrapped with `BoardProvider`, added `BoardSelector` in header, added `BoardSettingsSheet`.
- **Key decision**: `memory_workspace` in AgentLoop separates memory/session path from the global agent workspace (skills, SOUL.md, config remain global). This avoids touching `context.py`, `memory.py`, or `session/manager.py`.

### File List

**Created:**
- `dashboard/convex/boards.ts`
- `dashboard/components/BoardContext.tsx`
- `dashboard/components/BoardSelector.tsx`
- `dashboard/components/BoardSettingsSheet.tsx`
- `tests/mc/test_boards.py`

**Modified:**
- `dashboard/convex/schema.ts`
- `dashboard/convex/tasks.ts`
- `dashboard/lib/constants.ts`
- `dashboard/components/KanbanBoard.tsx`
- `dashboard/components/TaskInput.tsx`
- `dashboard/components/DashboardLayout.tsx`
- `nanobot/agent/loop.py`
- `nanobot/mc/executor.py`
- `nanobot/mc/bridge.py`
- `nanobot/mc/orchestrator.py`
- `nanobot/mc/gateway.py`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

**Deleted:**
- None
