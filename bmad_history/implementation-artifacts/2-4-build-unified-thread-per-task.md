# Story 2.4: Build Unified Thread per Task

Status: ready

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want a single thread per task where all agents, the system, and I can communicate,
So that I have one place to follow the entire execution story.

## Acceptance Criteria

1. **All messages share one thread per task** — Given a task exists in Convex, when any participant (agent, user, system, Lead Agent) posts a message, then the message is stored in the `messages` table with the task's `taskId` and all messages for the task are queryable via the existing `by_taskId` index (FR24).

2. **User can post messages to the thread** — Given a task is being executed, when the user types a message in the thread input and submits, then the message is stored with `authorType: "user"`, `type: "user_message"`, and `messageType: "user_message"` (FR26), and the message appears in the thread in real-time via Convex reactive query.

3. **Lead Agent plan messages use structured type** — Given the Lead Agent generates or updates a plan, when the plan message is posted, then it is stored with `authorType: "system"`, `authorName: "lead-agent"`, and `type: "lead_agent_plan"` or `type: "lead_agent_chat"` as appropriate.

4. **Agent step completion messages use structured type** — Given an agent completes a step, when a completion message is posted to the thread, then it includes `authorType: "agent"`, `type: "step_completion"`, the agent's name as `authorName`, and the step's `stepId` linking it to the specific step.

5. **System error messages use structured type** — Given a step crashes or a system error occurs, when an error message is posted to the thread, then it is stored with `authorType: "system"` and `type: "system_error"`.

6. **Single chronological stream** — Given multiple agents work on steps for the same task, when they each post messages to the thread, then all messages appear in a single chronological stream ordered by `timestamp` — no separate per-agent or per-step threads.

7. **Bridge supports new message type field** — Given the Python bridge `send_message` method is extended, when the bridge posts a message with the new `type` field, then the Convex `messages:create` mutation accepts and stores it correctly alongside the existing `messageType` field.

8. **Bridge supports step completion messages** — Given the Python bridge has a new `post_step_completion` method, when called with `task_id`, `step_id`, `agent_name`, `content`, and optional `artifacts`, then a message is created with all unified thread fields populated (`type: "step_completion"`, `stepId`, `artifacts`).

9. **Convex messages:create mutation extended** — Given the `messages:create` mutation receives optional `type`, `stepId`, and `artifacts` args, when the mutation executes, then these fields are stored on the message document alongside existing fields.

10. **Backward compatibility preserved** — Given existing code calls `messages:create` without the new optional fields, when the mutation executes, then it succeeds with `type`, `stepId`, and `artifacts` remaining `undefined` — no breaking changes.

## Tasks / Subtasks

- [ ] **Task 1: Extend `messages:create` mutation to accept unified thread fields** (AC: 1, 9, 10)
  - [ ] 1.1 Add optional `type` arg to `messages:create` with validator matching the schema union: `v.optional(v.union(v.literal("step_completion"), v.literal("user_message"), v.literal("system_error"), v.literal("lead_agent_plan"), v.literal("lead_agent_chat")))`
  - [ ] 1.2 Add optional `stepId` arg as `v.optional(v.id("steps"))`
  - [ ] 1.3 Add optional `artifacts` arg as `v.optional(v.array(v.object({...})))` matching the schema definition
  - [ ] 1.4 Pass all new fields through to `ctx.db.insert("messages", {...})` so they are persisted
  - [ ] 1.5 Verify existing callers (Python bridge `send_message`, `sendThreadMessage`, inline `ctx.db.insert` calls in `tasks.ts`) still work without the new fields

- [ ] **Task 2: Add `postStepCompletion` mutation to `messages.ts`** (AC: 4, 6)
  - [ ] 2.1 Create a new `postStepCompletion` mutation in `dashboard/convex/messages.ts` following the architecture pattern
  - [ ] 2.2 Required args: `taskId`, `stepId`, `agentName`, `content`; optional: `artifacts`
  - [ ] 2.3 The mutation inserts a message with `authorType: "agent"`, `type: "step_completion"`, `messageType: "work"`, the agent's name as `authorName`, the step's `stepId`, and the provided `artifacts`
  - [ ] 2.4 Create activity event `thread_message_sent` for observability

- [ ] **Task 3: Add `postSystemError` mutation to `messages.ts`** (AC: 5)
  - [ ] 3.1 Create a new `postSystemError` mutation in `dashboard/convex/messages.ts`
  - [ ] 3.2 Required args: `taskId`, `content`; optional: `stepId`
  - [ ] 3.3 The mutation inserts a message with `authorType: "system"`, `authorName: "System"`, `type: "system_error"`, `messageType: "system_event"`

- [ ] **Task 4: Add `postLeadAgentMessage` mutation to `messages.ts`** (AC: 3)
  - [ ] 4.1 Create a new `postLeadAgentMessage` mutation in `dashboard/convex/messages.ts`
  - [ ] 4.2 Required args: `taskId`, `content`, `type` (union of `"lead_agent_plan"` | `"lead_agent_chat"`)
  - [ ] 4.3 The mutation inserts a message with `authorType: "system"`, `authorName: "lead-agent"`, the provided `type`, `messageType: "system_event"`

- [ ] **Task 5: Extend `sendThreadMessage` for user-initiated unified thread messages** (AC: 2)
  - [ ] 5.1 Update `sendThreadMessage` in `messages.ts` to also set `type: "user_message"` on the inserted message document
  - [ ] 5.2 Verify the existing behavior (task status transition to "assigned", activity event creation) is preserved

- [ ] **Task 6: Extend Python bridge `send_message` to support new `type` field** (AC: 7, 10)
  - [ ] 6.1 Add optional `type` parameter to `ConvexBridge.send_message()` in `nanobot/mc/bridge.py`
  - [ ] 6.2 When `type` is provided, include it in the mutation args dict
  - [ ] 6.3 When `type` is not provided, omit it from args (backward compatible)
  - [ ] 6.4 Verify all existing callers of `send_message` in `executor.py` and `gateway.py` continue working

- [ ] **Task 7: Add `post_step_completion` method to Python bridge** (AC: 8)
  - [ ] 7.1 Add `post_step_completion(task_id, step_id, agent_name, content, artifacts=None)` to `ConvexBridge`
  - [ ] 7.2 This method calls `messages:postStepCompletion` Convex mutation with properly-cased args
  - [ ] 7.3 The `artifacts` parameter accepts a list of dicts with keys `path`, `action`, `description`, `diff`
  - [ ] 7.4 Include retry logic via `_mutation_with_retry` and logging via `_log_state_transition`

- [ ] **Task 8: Add `post_lead_agent_message` method to Python bridge** (AC: 3)
  - [ ] 8.1 Add `post_lead_agent_message(task_id, content, msg_type)` to `ConvexBridge`
  - [ ] 8.2 This method calls `messages:postLeadAgentMessage` Convex mutation
  - [ ] 8.3 `msg_type` accepts `"lead_agent_plan"` or `"lead_agent_chat"`

- [ ] **Task 9: Update Python types for new message fields** (AC: 7, 8)
  - [ ] 9.1 Add `ThreadMessageType` StrEnum to `nanobot/mc/types.py` with values: `"step_completion"`, `"user_message"`, `"system_error"`, `"lead_agent_plan"`, `"lead_agent_chat"`
  - [ ] 9.2 Extend `MessageData` dataclass with optional `type`, `step_id`, and `artifacts` fields
  - [ ] 9.3 Add `ArtifactData` dataclass with fields: `path`, `action`, `description` (optional), `diff` (optional)

- [ ] **Task 10: Write tests** (AC: 1-10)
  - [ ] 10.1 Add unit tests in `dashboard/convex/messages.test.ts` (co-located) for `postStepCompletion`, `postSystemError`, `postLeadAgentMessage`
  - [ ] 10.2 Add unit tests for extended `messages:create` with and without optional fields (backward compat)
  - [ ] 10.3 Add Python unit tests in `nanobot/mc/test_bridge.py` for `post_step_completion` and `post_lead_agent_message`
  - [ ] 10.4 Verify `sendThreadMessage` sets `type: "user_message"` on the message

## Dev Notes

### Critical: Schema Already Extended in Story 1.1

The `messages` table schema already includes the unified thread fields added in Story 1.1:

```typescript
// Already in schema.ts — DO NOT add again
stepId: v.optional(v.id("steps")),
type: v.optional(v.union(
  v.literal("step_completion"),
  v.literal("user_message"),
  v.literal("system_error"),
  v.literal("lead_agent_plan"),
  v.literal("lead_agent_chat"),
)),
artifacts: v.optional(v.array(v.object({
  path: v.string(),
  action: v.union(
    v.literal("created"),
    v.literal("modified"),
    v.literal("deleted"),
  ),
  description: v.optional(v.string()),
  diff: v.optional(v.string()),
}))),
```

This story is about making the **mutations, bridge methods, and types** actually USE these fields. The schema is ready; the plumbing is not.

### Two `type` Systems: `messageType` vs `type`

The messages table has TWO type fields, and this is intentional:

| Field | Purpose | Origin | Values |
|-------|---------|--------|--------|
| `messageType` | **Legacy** classification used by existing thread UI (ThreadMessage.tsx styles) | Pre-architecture, original codebase | `"work"`, `"review_feedback"`, `"approval"`, `"denial"`, `"system_event"`, `"user_message"` |
| `type` | **New** unified thread message type from the architecture spec | Story 1.1 schema extension | `"step_completion"`, `"user_message"`, `"system_error"`, `"lead_agent_plan"`, `"lead_agent_chat"` |

**Why both?** The `messageType` field drives the existing `ThreadMessage.tsx` component styling (background colors, labels like "Review", "Approved", "Denied"). Changing it would break the existing UI. The `type` field is the architecture-aligned classification that will be used by Story 2.7 (thread rendering) to display structured completion messages, artifact renderers, and Lead Agent plan messages. Both fields will coexist.

**Mapping rules for new mutations:**

| New mutation | `messageType` value | `type` value |
|---|---|---|
| `postStepCompletion` | `"work"` | `"step_completion"` |
| `postSystemError` | `"system_event"` | `"system_error"` |
| `postLeadAgentMessage` (plan) | `"system_event"` | `"lead_agent_plan"` |
| `postLeadAgentMessage` (chat) | `"system_event"` | `"lead_agent_chat"` |
| `sendThreadMessage` (user) | `"user_message"` | `"user_message"` |

### Existing Code That Touches This Story

| File | What exists | What changes |
|---|---|---|
| `dashboard/convex/messages.ts` | `create` mutation (6 args, no `type`/`stepId`/`artifacts`), `sendThreadMessage` (user messages), `listByTask` query | EXTEND `create` with optional args; ADD `postStepCompletion`, `postSystemError`, `postLeadAgentMessage` mutations; EXTEND `sendThreadMessage` to set `type: "user_message"` |
| `dashboard/convex/schema.ts` | Messages table already has `stepId`, `type`, `artifacts` fields | No changes — schema is ready from Story 1.1 |
| `nanobot/mc/bridge.py` | `send_message(task_id, author_name, author_type, content, message_type)` | EXTEND `send_message` with optional `type` param; ADD `post_step_completion()`, `post_lead_agent_message()` |
| `nanobot/mc/types.py` | `MessageType`, `AuthorType`, `MessageData` | ADD `ThreadMessageType` StrEnum; EXTEND `MessageData`; ADD `ArtifactData` dataclass |
| `nanobot/mc/executor.py` | Calls `bridge.send_message()` for work/system messages | No changes in this story — callers updated in Story 2.5 (structured completion) |
| `dashboard/components/ThreadMessage.tsx` | Renders messages using `messageType` for styling | No changes in this story — rendering updates in Story 2.7 |
| `dashboard/components/ThreadInput.tsx` | Calls `messages.sendThreadMessage` | No changes — the mutation is updated server-side |

### Bridge Pattern: snake_case to camelCase

The Python bridge auto-converts snake_case keys to camelCase. When calling `messages:postStepCompletion`, the bridge method should use snake_case args:

```python
def post_step_completion(
    self,
    task_id: str,
    step_id: str,
    agent_name: str,
    content: str,
    artifacts: list[dict[str, Any]] | None = None,
) -> Any:
    args: dict[str, Any] = {
        "task_id": task_id,
        "step_id": step_id,
        "agent_name": agent_name,
        "content": content,
    }
    if artifacts:
        args["artifacts"] = artifacts
    result = self._mutation_with_retry("messages:postStepCompletion", args)
    self._log_state_transition(
        "message",
        f"Step completion posted by {agent_name} on task {task_id}",
    )
    return result
```

The `_convert_keys_to_camel` in the bridge will convert `task_id` to `taskId`, `step_id` to `stepId`, `agent_name` to `agentName`. The `artifacts` list items will also have their keys converted (e.g., `description` stays as `description`, but if any key were snake_case it would be converted).

### Architecture Pattern: postStepCompletion Mutation

The architecture document specifies this exact pattern (see architecture.md, "Step Completion with Structured Message Pattern"):

```typescript
export const postStepCompletion = mutation({
  args: {
    taskId: v.id("tasks"),
    stepId: v.id("steps"),
    agentName: v.string(),
    content: v.string(),
    artifacts: v.optional(v.array(v.object({
      path: v.string(),
      action: v.union(
        v.literal("created"),
        v.literal("modified"),
        v.literal("deleted"),
      ),
      description: v.optional(v.string()),
      diff: v.optional(v.string()),
    }))),
  },
  handler: async (ctx, args) => {
    const timestamp = new Date().toISOString();
    await ctx.db.insert("messages", {
      taskId: args.taskId,
      stepId: args.stepId,
      authorName: args.agentName,
      authorType: "agent",
      content: args.content,
      messageType: "work",       // Legacy field for existing UI
      type: "step_completion",   // New unified thread type
      artifacts: args.artifacts,
      timestamp,
    });
  },
});
```

Note: the architecture sample uses `role` instead of `authorType` — the actual schema uses `authorType`. Always follow the schema.

### The `authorType` Field: No "lead_agent" Value

The `authorType` field in the schema is a union of `"agent"`, `"user"`, `"system"`. There is NO `"lead_agent"` value. The Lead Agent's messages use `authorType: "system"` and `authorName: "lead-agent"` — the distinction between Lead Agent messages and other system messages is via the `type` field (`"lead_agent_plan"` vs `"lead_agent_chat"` vs `"system_error"`).

### Existing `sendThreadMessage` Behavior — Preserve Carefully

The `sendThreadMessage` mutation in `messages.ts` does more than just insert a message. It atomically:

1. Creates the user message
2. Transitions the task to "assigned" status (unless already assigned)
3. Clears `executionPlan` and `stalledAt`
4. Creates an activity event

This story adds `type: "user_message"` to the message insert in step 1 but must NOT change steps 2-4. The behavior is correct for the single-agent legacy flow. In the multi-step flow (Story 2.4+), user messages during execution may need different handling (e.g., not clearing the plan, not re-assigning the task). That is a future concern — this story only adds the `type` field.

### Index Efficiency

The `by_taskId` index on the `messages` table is the primary query path for loading a task's thread. All messages for a task are fetched in one query:

```typescript
const messages = await ctx.db
  .query("messages")
  .withIndex("by_taskId", (q) => q.eq("taskId", args.taskId))
  .collect();
```

This returns all messages chronologically (Convex default sort by `_creationTime`). The `listByTask` query already exists and works correctly — no index changes needed.

### Real-Time Thread Updates

Convex reactive queries (`useQuery`) automatically re-fire when the underlying data changes. The `TaskDetailSheet.tsx` component already uses:

```typescript
const messages = useQuery(api.messages.listByTask, taskId ? { taskId } : "skip");
```

When a new message is inserted (by any mutation — user, agent, or system), the reactive query fires and the component re-renders with the new message. Auto-scroll to bottom is already implemented via `threadEndRef`. No additional work is needed for real-time updates.

### Testing Strategy

- **Convex mutation tests:** Use vitest with Convex test helpers. Test that `postStepCompletion` creates a message with correct `type`, `stepId`, `artifacts`. Test that `create` works with and without optional fields.
- **Python bridge tests:** Mock the Convex client. Test that `post_step_completion` calls `_mutation_with_retry` with correct camelCase args. Test that `send_message` with optional `type` includes it in args.
- **Integration:** After implementation, manually verify in the Convex dashboard that messages have the new fields populated.

### What This Story Does NOT Cover

- **Story 2.5** — Actually posting structured completion messages from the agent execution pipeline (calling `post_step_completion` from `executor.py` or `step_dispatcher.py`)
- **Story 2.6** — Building enhanced thread context with predecessor step completions
- **Story 2.7** — Rendering structured messages in the UI with artifact display, Lead Agent plan display, and visual distinction per author/type

This story builds the **plumbing** (mutations, bridge methods, types). Subsequent stories use that plumbing.

### Git Intelligence (Recent Commits)

```
830fd64 fix card ui
e685c07 Fix Design broken
acc0318 wip: alinhamento do design da dashboard
823f0a7 feat: Implement cron job task linking and output file syncing
479bc23 feat: highlight prompt variables with amber color
```

Recent work has been UI alignment and cron job features. No conflicts expected with message mutation changes.

### Project Structure Notes

- **Convex mutations:** `dashboard/convex/messages.ts` — all message-related queries and mutations
- **Python bridge:** `nanobot/mc/bridge.py` — single integration point between Python runtime and Convex
- **Python types:** `nanobot/mc/types.py` — shared type definitions mirroring Convex schema
- **No frontend changes** in this story — ThreadMessage rendering updates are Story 2.7
- **No executor changes** in this story — agent completion message posting is Story 2.5

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Communication Patterns] — postStepCompletion mutation pattern
- [Source: _bmad-output/planning-artifacts/architecture.md#Thread Message Types] — MessageType enum values
- [Source: _bmad-output/planning-artifacts/architecture.md#Data Model Decisions] — messages table as unified thread
- [Source: _bmad-output/planning-artifacts/prd.md#FR24-FR28] — Unified Thread & Agent Communication requirements
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.4] — Full BDD acceptance criteria
- [Source: dashboard/convex/schema.ts] — Messages table with stepId, type, artifacts fields (from Story 1.1)
- [Source: dashboard/convex/messages.ts] — Existing create/sendThreadMessage/listByTask
- [Source: nanobot/mc/bridge.py] — Existing send_message, snake_case to camelCase conversion
- [Source: nanobot/mc/types.py] — Existing MessageType, AuthorType, MessageData
- [Source: nanobot/mc/executor.py:168-223] — Existing _build_thread_context() pattern

## Change Log

- 2026-02-25: Story created. Schema already extended in Story 1.1; this story adds mutations, bridge methods, and types to use the unified thread fields.
