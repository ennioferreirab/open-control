# Story 1.1: Extend Convex Schema for Task/Step Hierarchy

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want the Convex schema to support steps as first-class entities with task relationships and structured message types,
So that the system can track individual work units assigned to agents and their dependencies.

## Acceptance Criteria

1. **Steps table created with required fields** — Given the existing Convex schema with `tasks`, `messages`, and `agents` tables, when the schema is extended, then a new `steps` table is created with fields: `taskId` (reference to tasks), `title` (string), `description` (string), `assignedAgent` (string), `status` (string — one of "planned", "assigned", "running", "completed", "crashed", "blocked"), `blockedBy` (optional array of step IDs), `parallelGroup` (number), `order` (number).

2. **Steps table indexed by taskId** — Given the new `steps` table exists, when the schema is deployed, then the `steps` table has an index `by_taskId` for querying steps by parent task.

3. **Tasks table extended** — Given the existing `tasks` table, when the schema is extended, then the `tasks` table gains: `executionPlan` (optional object — already exists, verify type), `supervisionMode` (optional string — "autonomous" or "supervised").

4. **Messages table extended** — Given the existing `messages` table, when the schema is extended, then the `messages` table gains: `stepId` (optional reference to steps), `type` (optional string — one of "step_completion", "user_message", "system_error", "lead_agent_plan", "lead_agent_chat"), `artifacts` (optional array of objects with path, action, description, diff).

5. **Schema validation passes** — Given the extended Convex schema, when the Convex dev server starts, then it starts without schema validation errors.

6. **Backward compatibility preserved** — Given the extended schema with new optional fields, when existing data is queried, then existing data in all tables continues to work (all new fields are optional).

7. **Efficient querying by task** — Given the new schema is deployed, when a developer queries the steps table with `by_taskId` index, then steps for a specific task are returned efficiently.

## Tasks / Subtasks

- [x] **Task 1: Create `steps` table in Convex schema** (AC: 1, 2, 7)
  - [x] 1.1 Add `steps` table definition to `dashboard/convex/schema.ts` with all required fields and validators
  - [x] 1.2 Add `by_taskId` index to `steps` table
  - [x] 1.3 Add `by_status` index to `steps` table (for orchestration queries)

- [x] **Task 2: Extend `tasks` table schema** (AC: 3, 6)
  - [x] 2.1 Add `supervisionMode` field as `v.optional(v.string())` — validates "autonomous" | "supervised"
  - [x] 2.2 Verify existing `executionPlan` field typing matches the `ExecutionPlan` TypeScript type from architecture (currently `v.optional(v.any())` — consider tightening to `v.optional(v.object(...))`)

- [x] **Task 3: Extend `messages` table schema** (AC: 4, 6)
  - [x] 3.1 Add `stepId` field as `v.optional(v.id("steps"))`
  - [x] 3.2 Add `type` field as `v.optional(v.string())` — for structured message classification
  - [x] 3.3 Add `artifacts` field as `v.optional(v.array(v.object({...})))` — for structured completion messages

- [x] **Task 4: Create `steps` CRUD functions** (AC: 1, 5, 7)
  - [x] 4.1 Create `dashboard/convex/steps.ts` with basic mutations: `create`, `updateStatus`, `getByTask`
  - [x] 4.2 Implement `checkAndUnblockDependents` mutation — when a step completes, check if any steps that reference it in `blockedBy` can now be unblocked
  - [x] 4.3 Add activity logging for all step status changes

- [x] **Task 5: Validate schema deployment** (AC: 5, 6)
  - [x] 5.1 Run `npx convex dev` and confirm no validation errors
  - [x] 5.2 Verify existing task/message queries still work with extended schema
  - [x] 5.3 Test creating a step record and querying it by taskId

## Dev Notes

### Critical: Schema Tension Between Existing and New Status Values

**The biggest risk in this story is the gap between existing and architecture-specified status values.** The developer MUST understand this clearly:

**Task Status — EXISTING vs. ARCHITECTURE:**

| Existing (in code today) | Architecture (target) | Notes |
|---|---|---|
| `inbox` | `planning` | Equivalent for new flow |
| `assigned` | `reviewing_plan` | Supervised mode only |
| `in_progress` | `running` | Renamed |
| `review` | _(removed)_ | Replaced by step-level review |
| `done` | `completed` | Renamed |
| `retrying` | _(handled at step level)_ | Step retry, not task retry |
| `crashed` | `failed` | Renamed |
| `deleted` | _(soft-delete preserved)_ | Keep existing pattern |
| _(new)_ | `ready` | Plan approved, pre-dispatch |

**DECISION REQUIRED:** This story should **ADD** the new `supervisionMode` field and the `steps` table WITHOUT changing existing task status values. Status value migration is a separate concern that touches the entire state machine, Kanban board, and Python backend. Changing statuses here would break everything.

**Step Status Values (NEW — no conflict):**
- `planned` — Initial state from ExecutionPlan (pre-materialization)
- `assigned` — Step record exists, waiting for dispatch (no blockers)
- `blocked` — Step has unresolved dependencies
- `running` — Agent subprocess is executing
- `completed` — Agent completed successfully
- `crashed` — Agent subprocess failed

### Existing Code That Touches This Story

| File | What exists | What changes |
|---|---|---|
| `dashboard/convex/schema.ts` | Tasks, messages, agents, activities, settings, boards, skills, taskTags tables | ADD `steps` table; EXTEND tasks with `supervisionMode`; EXTEND messages with `stepId`, `type`, `artifacts` |
| `dashboard/convex/tasks.ts` | Task CRUD, state machine, `updateExecutionPlan`, `markPlanStepsCompleted` | No changes in this story — step functions go in new file |
| `dashboard/convex/messages.ts` | Message CRUD, author types: "agent" \| "user" \| "system" | No changes — new fields are schema-only |
| `nanobot/mc/types.py` | `ExecutionPlanStep`, `ExecutionPlan` dataclasses | No changes in this story — Python types updated in Story 1.5/1.6 |
| `nanobot/mc/bridge.py` | ConvexBridge with snake_case ↔ camelCase conversion | No changes in this story — step mutations added in Story 1.6 |

### Architecture Patterns to Follow

1. **Table naming:** camelCase, plural → `steps`
2. **Field naming:** camelCase → `taskId`, `assignedAgent`, `blockedBy`, `parallelGroup`
3. **Function file:** One file per table → `dashboard/convex/steps.ts`
4. **Function naming:** verb-first camelCase → `steps.create`, `steps.updateStatus`, `steps.getByTask`
5. **Foreign keys:** `v.id("table")` for type-safe references
6. **Status values:** String literals, not enums — exact values across all systems
7. **Timestamps:** ISO 8601 strings (`2026-02-24T10:30:00Z`)
8. **Activity logging:** Every status change MUST create an activity event
9. **Indexes:** `by_taskId` for step queries by parent task

### ExecutionPlan Type (Architecture Reference)

```typescript
type ExecutionPlan = {
  steps: Array<{
    tempId: string           // Temporary ID for pre-kickoff editing
    title: string
    description: string
    assignedAgent: string
    blockedBy: string[]      // References other tempIds
    parallelGroup: number
    order: number
    attachedFiles?: string[] // File paths attached to this specific step
  }>
  generatedAt: string        // ISO 8601
  generatedBy: "lead-agent"
}
```

### Step Table Schema (Exact Implementation)

```typescript
steps: defineTable({
  taskId: v.id("tasks"),
  title: v.string(),
  description: v.string(),
  assignedAgent: v.string(),
  status: v.string(), // "planned" | "assigned" | "running" | "completed" | "crashed" | "blocked"
  blockedBy: v.optional(v.array(v.id("steps"))),
  parallelGroup: v.number(),
  order: v.number(),
  createdAt: v.string(),
  startedAt: v.optional(v.string()),
  completedAt: v.optional(v.string()),
  errorMessage: v.optional(v.string()),
})
  .index("by_taskId", ["taskId"])
  .index("by_status", ["status"])
```

### Messages Table Extension (Exact Implementation)

```typescript
// ADD to existing messages table definition:
stepId: v.optional(v.id("steps")),
type: v.optional(v.string()), // "step_completion" | "user_message" | "system_error" | "lead_agent_plan" | "lead_agent_chat"
artifacts: v.optional(v.array(v.object({
  path: v.string(),
  action: v.string(), // "created" | "modified" | "deleted"
  description: v.optional(v.string()),
  diff: v.optional(v.string()),
}))),
```

### Tasks Table Extension (Exact Implementation)

```typescript
// ADD to existing tasks table definition:
supervisionMode: v.optional(v.string()), // "autonomous" | "supervised"
// executionPlan already exists as v.optional(v.any()) — keep as-is for now
```

### Key `checkAndUnblockDependents` Algorithm

```typescript
// When a step completes:
// 1. Find all steps for the same task
// 2. For each step with status "blocked":
//    a. Check if ALL steps in its blockedBy array are "completed"
//    b. If yes → update status to "assigned"
// 3. Log activity event for each unblocked step
```

### Testing Strategy

- **Schema validation:** Run `npx convex dev` — confirms schema compiles
- **Step CRUD:** Create step, query by taskId, update status
- **Dependency resolution:** Create steps with blockedBy, complete a blocker, verify unblocking
- **Backward compat:** Query existing tasks/messages — all still work
- **Manual testing:** No automated E2E tests required for schema-only story

### Git Intelligence (Recent Commits)

```
830fd64 fix card ui
e685c07 Fix Design broken
acc0318 wip: alinhamento do design da dashboard
823f0a7 feat: Implement cron job task linking and output file syncing
479bc23 feat: highlight prompt variables with amber color
```

Recent work has been UI alignment and cron job features. No conflicts expected with schema changes.

### Project Structure Notes

- **Convex schema:** `dashboard/convex/schema.ts` — single schema file, all tables defined here
- **New file:** `dashboard/convex/steps.ts` — step queries, mutations, and dependency logic
- **No Python changes** in this story — bridge/types updated in later stories (1.5, 1.6)
- **No frontend changes** in this story — StepCard, Kanban updates are Story 1.7
- **Existing `executionPlan`** on tasks is `v.optional(v.any())` — keep loose typing for now; tighten when the full ExecutionPlan type stabilizes in Story 1.5

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Data Model Decisions] — Task/Step hierarchy, field definitions, index requirements
- [Source: _bmad-output/planning-artifacts/architecture.md#Convex Schema Patterns] — Table naming, field naming, validator patterns
- [Source: _bmad-output/planning-artifacts/architecture.md#Step Status Lifecycle] — Status values and transitions
- [Source: _bmad-output/planning-artifacts/prd.md#FR1-FR5] — Task & Step Management requirements
- [Source: _bmad-output/planning-artifacts/prd.md#FR29-FR34] — Step Lifecycle & Error Handling
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 1 Story 1.1] — Full BDD acceptance criteria
- [Source: dashboard/convex/schema.ts] — Existing schema to extend
- [Source: dashboard/convex/tasks.ts] — Existing task mutations (reference for patterns)
- [Source: nanobot/mc/types.py:98-150] — Existing ExecutionPlanStep Python types
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#TaskCard] — Step progress display patterns

## Dev Agent Record

### Agent Model Used

GPT-5 Codex (CLI coding agent)

### Debug Log References

- `npm test -- steps.test.ts` (red then green; final: 4/4 passed)
- `npm test` (full dashboard suite: 20 files, 223 tests passed)
- `npx convex dev --once` (schema/functions validation passed)
- `npx convex codegen` (generated API bindings and typecheck passed)
- `npx convex run tasks:create`, `steps:create`, `steps:getByTask` (step CRUD verification)
- `npx convex run steps:updateStatus`, `steps:checkAndUnblockDependents` (dependency unblocking verification)
- `npx convex run messages:create`, `messages:listByTask`, `tasks:getById` (backward compatibility verification)
- `npm run lint` (fails due to existing repository lint issues unrelated to this story; new `steps.ts` file passes targeted lint)
- `npx convex run` validation for review fixes:
  - cross-task `blockedBy` rejection
  - invalid step transition rejection
  - blocked-without-dependencies rejection
- `npm test` rerun after review fixes (21 files, 242 tests passed)
- `npx eslint convex/schema.ts convex/steps.ts convex/steps.test.ts convex/activities.ts` (passed)

### Completion Notes List

- Added `steps` table to Convex schema with required fields and indexes: `by_taskId`, `by_status`.
- Extended `tasks` schema with optional `supervisionMode` while keeping `executionPlan` as `v.optional(v.any())` for compatibility.
- Extended `messages` schema with optional `stepId`, `type`, and structured `artifacts`.
- Added step lifecycle activity events (`step_created`, `step_status_changed`, `step_unblocked`) to schema and `activities.create` validator.
- Implemented new Convex module `dashboard/convex/steps.ts` with `create`, `getByTask`, `updateStatus`, and `checkAndUnblockDependents`.
- Implemented status validation helper and dependency-resolution helper used by `checkAndUnblockDependents`.
- Added strict step transition validation in `steps.updateStatus` to enforce lifecycle integrity.
- Added dependency ownership validation in `steps.create` to prevent cross-task `blockedBy` links.
- Added initial status resolution guardrails in `steps.create` so dependency presence and status are consistent.
- Tightened schema literal validation for:
  - `tasks.supervisionMode`
  - `steps.status`
  - `messages.type`
  - `messages.artifacts[].action`
- Added unit tests for step status validation and dependency-unblock selection logic in `dashboard/convex/steps.test.ts`.
- Manually verified runtime behavior against Convex deployment: step creation/query, task/message query compatibility, and blocked-step auto-unblocking.

### File List

- dashboard/convex/schema.ts
- dashboard/convex/activities.ts
- dashboard/convex/steps.ts
- dashboard/convex/steps.test.ts
- dashboard/convex/_generated/api.d.ts

## Change Log

- 2026-02-25: Implemented Story 1.1 schema extensions and step CRUD/unblock logic; added step-focused unit tests and validated Convex deployment/runtime flows.
- 2026-02-25: Senior code-review fixes applied (schema literal constraints, dependency integrity validation, lifecycle transition guards) and revalidated tests/runtime checks.

## Senior Developer Review (AI)

### Review Date

2026-02-25

### Reviewer

Senior Developer (AI)

### Outcome

Approve

### Findings Summary

- **High fixed:** AC constraint enforcement gaps in schema validators.
- **High fixed:** Cross-task dependency integrity hole in `steps.create`.
- **Medium fixed:** `blockedBy`/status consistency enforcement in creation path.
- **Medium fixed:** Missing lifecycle transition guards in `steps.updateStatus`.
- **Medium fixed:** Story audit transparency improved by documenting that the workspace contains unrelated pre-existing modified files outside this story scope; review and file list remain limited to Story 1.1 implementation files.

### Verification Evidence

- Unit + regression tests passed after fixes (`vitest`: 242/242).
- Convex schema/function validation passed (`npx convex dev --once`, `npx convex codegen`).
- Runtime negative tests confirmed guardrails reject invalid operations:
  - cross-task dependencies
  - invalid transitions
  - blocked status without dependencies
