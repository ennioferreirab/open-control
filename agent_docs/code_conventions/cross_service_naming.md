# Cross-Service Naming Contract

This document defines the **single source of truth** for naming across all three layers: Python (`mc/`), Convex (`dashboard/convex/`), and TypeScript (`dashboard/`).

## The Conversion Rule

Each layer uses its native naming convention. The bridge converts automatically:

```
Python (snake_case)  ←→  Bridge  ←→  Convex/TypeScript (camelCase)
```

| Layer | Key convention | Example |
|-------|---------------|---------|
| Python | `snake_case` | `assigned_agent`, `state_version` |
| Convex schema | `camelCase` | `assignedAgent`, `stateVersion` |
| TypeScript | `camelCase` | `assignedAgent`, `stateVersion` |

**The bridge handles conversion automatically.** Python code must never produce camelCase keys for Convex calls. Convex/TypeScript code must never produce snake_case keys.

### Special case: Convex system fields

| Convex field | Python field | Rule |
|-------------|-------------|------|
| `_id` | `id` | Leading underscore stripped |
| `_creationTime` | `creation_time` | Leading underscore stripped |

### Special case: Nested objects

The bridge converts keys recursively. If a value is a dict, its keys are also converted. This means:
- **Do NOT manually pre-convert keys to camelCase** before sending to Convex. The bridge will do it.
- **Do NOT manually convert keys to snake_case** after receiving from Convex. The bridge does it.
- If you use `to_dict()` on a dataclass that produces camelCase (e.g., `ExecutionPlan.to_dict()`), the bridge will try to re-convert but it's idempotent for already-camelCase keys. Prefer producing snake_case and letting the bridge handle it.

## Status Values — The Shared Vocabulary

Status strings are **never converted** — they are values, not keys. They must be **identical** across all three layers. Use `snake_case` for multi-word statuses.

### TaskStatus

```
ready | inbox | assigned | in_progress | review | done | failed | retrying | crashed | deleted
```

### StepStatus

```
planned | assigned | running | review | completed | crashed | blocked | waiting_human | deleted
```

### AgentStatus

```
active | idle | crashed
```

### MessageType

```
user | assistant | system | tool_call | tool_result | comment
```

### TrustLevel

```
autonomous | supervised | manual
```

### RoutingMode

```
auto | human
```

### ReviewPhase

```
pending | in_review | approved | revision_requested
```

**Rules:**
- When adding a new status value, add it to **all three layers simultaneously**: Python enum, Convex schema validator, and TypeScript constants.
- Never use a status string literal inline — always reference the enum (Python) or constant (TypeScript) or validator (Convex).
- All status values are lowercase `snake_case`. No camelCase, no UPPER_CASE.

## ActivityEventType — The Event Catalog

Activity events track what happened in the system. They must be consistent across layers.

### Entity lifecycle events

```
task_created | task_updated | task_status_changed | task_deleted | task_restored
task_reassigned | task_merged | task_dispatch_started
step_created | step_status_changed | step_dispatched | step_started
step_completed | step_unblocked
agent_created | agent_updated | agent_deleted | agent_restored | agent_output
board_created | board_updated | board_deleted
```

### User interaction events

```
manual_task_status_changed | file_attached | comment_added
```

**Rules:**
- All event types are `snake_case`.
- Format: `<entity>_<action>` (e.g., `task_created`, `step_unblocked`).
- When adding a new event type, add it to: Python `ActivityEventType` enum, Convex `schema.ts` event type validator, and TypeScript constants (if the frontend needs it).
- TypeScript only needs events it renders in the UI. Python and Convex must have the complete set.

## Entity Naming

### Type names by layer

| Entity | Python type | Convex table | TypeScript type | Notes |
|--------|------------|-------------|-----------------|-------|
| Task | `TaskData` | `tasks` | `Doc<"tasks">` | |
| Step | `StepData` | `steps` | `Doc<"steps">` | |
| Agent | `AgentData` | `agents` | `Doc<"agents">` | |
| Message | `MessageData` | `messages` | `Doc<"messages">` | |
| Activity | `ActivityData` | `activities` | `Doc<"activities">` | |
| Board | `BoardData` | `boards` | `Doc<"boards">` | |
| ExecutionPlan | `ExecutionPlan` | stored on task | `ExecutionPlan` | Same name both layers |
| Plan Step | `ExecutionPlanStep` | nested in plan | `ExecutionPlanStep` | **Must match** |

**Rules:**
- Python dataclasses use `<Entity>Data` suffix (e.g., `TaskData`).
- Convex tables are plural lowercase (`tasks`, `agents`).
- TypeScript uses `Doc<"tableName">` for Convex documents. For extended/derived types, use `<Entity><Qualifier>` (e.g., `TaskWithSteps`, `AgentSummary`).
- If Python and TypeScript both define a type for the same data (e.g., `ExecutionPlan`), use the **same name** to reduce cognitive overhead.

### Field name mapping

These are the canonical field names. Each layer uses its native casing.

| Concept | Python | Convex/TS | Type |
|---------|--------|-----------|------|
| Document ID | `id` | `_id` | `str` / `Id<"table">` |
| Task reference | `task_id` | `taskId` | `str` / `Id<"tasks">` |
| Step reference | `step_id` | `stepId` | `str` / `Id<"steps">` |
| Agent reference | `agent_id` | `agentId` | `str` / `Id<"agents">` |
| Board reference | `board_id` | `boardId` | `str` / `Id<"boards">` |
| Agent name | `agent_name` | `agentName` | `str` / `string` |
| Display name | `display_name` | `displayName` | `str` / `string` |
| Assigned agent | `assigned_agent` | `assignedAgent` | `str` / `string` |
| Status | `status` | `status` | Status enum |
| State version | `state_version` | `stateVersion` | `int` / `number` |
| Trust level | `trust_level` | `trustLevel` | TrustLevel enum |
| Review phase | `review_phase` | `reviewPhase` | ReviewPhase enum |
| Routing mode | `routing_mode` | `routingMode` | RoutingMode enum |
| Execution plan | `execution_plan` | `executionPlan` | `ExecutionPlan` |
| Created at | `created_at` | `createdAt` | ISO 8601 string |
| Updated at | `updated_at` | `updatedAt` | ISO 8601 string |
| Deleted at | `deleted_at` | `deletedAt` | ISO 8601 string / null |
| Is system | `is_system` | `isSystem` | `bool` / `boolean` |
| Parallel group | `parallel_group` | `parallelGroup` | `int` / `number` |
| Blocked by | `blocked_by` | `blockedBy` | `list[str]` / `string[]` |
| Idempotency key | `idempotency_key` | `idempotencyKey` | `str` / `string` |

## Anti-Patterns

### Never do dual-key lookups

```python
# WRONG — signals inconsistent data source
value = data.get("assigned_agent") or data.get("assignedAgent")

# CORRECT — data should always arrive in one format
value = data["assigned_agent"]  # always snake_case in Python
```

If you find yourself checking both conventions, the data source is not going through the bridge properly. Fix the source, not the consumer.

### Never manually convert keys

```python
# WRONG — manual conversion
args = {"taskId": task_id, "fromStatus": from_status}
result = await client.mutation("tasks:transition", args)

# CORRECT — let the bridge convert
args = {"task_id": task_id, "from_status": from_status}
result = await client.mutation("tasks:transition", args)
```

### Never use inline string literals for statuses

```python
# WRONG
if task["status"] == "in_progress":

# CORRECT
if task["status"] == TaskStatus.IN_PROGRESS:
```

```typescript
// WRONG
if (task.status === "in_progress")

// CORRECT
import { TASK_STATUS } from "@/lib/constants";
if (task.status === TASK_STATUS.IN_PROGRESS)
```

## Adding a New Field or Status

Checklist when adding a new field to a shared entity:

1. **Convex schema** (`schema.ts`): add the field with a typed validator
2. **Python type** (`mc/types.py`): add to the dataclass with snake_case naming
3. **TypeScript** (if needed in UI): the `Doc<>` type auto-updates from schema
4. **No bridge changes needed** — key conversion is automatic

Checklist when adding a new status value:

1. **Convex schema** (`schema.ts`): add to the validator union
2. **Python enum** (`mc/types.py`): add the new member
3. **TypeScript constants** (`lib/constants.ts`): add if the frontend uses it
4. **Convex mutations**: update inline validators if not using shared validator (and fix them to use shared)
