# Story 2.5: Post Structured Completion Messages

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want agents to post structured completion messages showing what files they created or modified,
So that I can see exactly what each agent produced and dependent agents get precise context.

## Acceptance Criteria

1. **Structured completion message posted on step completion** — Given an agent completes its step and produced file operations, when the completion message is posted to the unified thread, then the message includes `authorType: "agent"`, `type: "step_completion"`, `authorName` (the agent name), `stepId`, human-readable `content`, and an `artifacts` array (FR25, NFR13).

2. **Artifact entries contain file metadata** — Given a structured completion message with artifacts, when each artifact entry is inspected, then it includes: `path` (file path relative to task directory), `action` ("created" or "modified"), `description` (for created files), `diff` (for modified files).

3. **Steps with no file operations** — Given an agent completes a step with no file operations, when the completion message is posted, then the message includes `content` describing what was done and `artifacts` is an empty array or omitted.

4. **Correct stepId association** — Given multiple agents complete steps on the same task, when their completion messages are posted, then each message is associated with the correct `stepId` in the unified thread.

5. **Chronological ordering** — Given multiple agents complete steps on the same task, when their completion messages are posted, then the chronological order in the thread reflects the actual completion order (guaranteed by ISO 8601 timestamps at message insertion time).

6. **Message format parseable by UI and agents** — Given a structured completion message is stored in Convex, when the UI renders it, then it can display artifacts (file paths, action badges, descriptions, diffs). And when the thread context builder formats it for agent injection, then artifact details are included in a parseable text format (NFR13).

7. **Bridge method for posting structured completion** — Given the Python bridge needs to post a structured completion message, when the new `post_step_completion()` method is called, then it sends the message via Convex mutation with all required fields (taskId, stepId, authorName, authorType, content, messageType, type, artifacts, timestamp).

8. **Convex mutation accepts structured completion fields** — Given the `messages:create` mutation is called with step completion fields, when the mutation executes, then it persists `stepId`, `type`, and `artifacts` alongside the existing required fields.

## Tasks / Subtasks

- [x] **Task 1: Extend Convex `messages:create` mutation to accept structured completion fields** (AC: 1, 8)
  - [x]1.1 Add `stepId` as `v.optional(v.id("steps"))` to the `messages:create` mutation args
  - [x]1.2 Add `type` as `v.optional(v.union(v.literal("step_completion"), ...))` to the `messages:create` mutation args
  - [x]1.3 Add `artifacts` as `v.optional(v.array(v.object({...})))` to the `messages:create` mutation args
  - [x]1.4 Pass the new optional fields through to `ctx.db.insert("messages", ...)` when present
  - [x]1.5 Verify existing callers of `messages:create` (which don't pass these fields) still work

- [x] **Task 2: Add `post_step_completion()` method to ConvexBridge** (AC: 1, 2, 3, 7)
  - [x]2.1 Add `post_step_completion(task_id, step_id, agent_name, content, artifacts)` method to `ConvexBridge`
  - [x]2.2 Method calls `messages:create` with `author_type="agent"`, `message_type="work"`, `type="step_completion"`, and passes `step_id` and `artifacts`
  - [x]2.3 `artifacts` parameter is `list[dict] | None` — each dict has keys: `path`, `action`, `description` (optional), `diff` (optional)
  - [x]2.4 Uses `_mutation_with_retry` for reliability (consistent with all other bridge mutations)
  - [x]2.5 Logs the step completion via `_log_state_transition`

- [x] **Task 3: Add `StepCompletionArtifact` dataclass to types.py** (AC: 2, 6)
  - [x]3.1 Create `StepCompletionArtifact` dataclass with fields: `path: str`, `action: str`, `description: str | None`, `diff: str | None`
  - [x]3.2 Add `StructuredMessageType` StrEnum mirroring the `type` field values from the Convex schema: `STEP_COMPLETION`, `USER_MESSAGE`, `SYSTEM_ERROR`, `LEAD_AGENT_PLAN`, `LEAD_AGENT_CHAT`
  - [x]3.3 Add `to_dict()` method on `StepCompletionArtifact` for serialization to Convex-compatible format

- [x] **Task 4: Collect file artifacts from agent output** (AC: 1, 2, 3, 4)
  - [x]4.1 Create helper function `_collect_output_artifacts(task_id: str, pre_snapshot: dict[str, float] | None) -> list[dict]` in `executor.py`
  - [x]4.2 The function scans the task's `output/` directory and compares against a pre-execution snapshot to detect created/modified files
  - [x]4.3 For **created** files: artifact entry has `action="created"`, `description` with file type and size, `path` relative to task dir
  - [x]4.4 For **modified** files: artifact entry has `action="modified"`, `diff` as a summary of the change (size delta), `path` relative to task dir
  - [x]4.5 Create helper function `_snapshot_output_dir(task_id: str) -> dict[str, float]` that captures file paths and modification times before execution

- [x] **Task 5: Post structured completion message after step execution** (AC: 1, 3, 4, 5)
  - [x]5.1 In `TaskExecutor._execute_task()`, capture output directory snapshot **before** agent execution
  - [x]5.2 After successful agent execution, call `_collect_output_artifacts()` to build the artifacts list
  - [x]5.3 Call `bridge.post_step_completion()` with the agent's text result as `content`, the collected `artifacts`, the `step_id`, and the `agent_name`
  - [x]5.4 Replace the existing `bridge.send_message()` call (the "work" message) with the new structured completion call when a `step_id` is available
  - [x]5.5 When no `step_id` is available (legacy single-task execution), fall back to the existing `send_message()` behavior

- [x] **Task 6: Update `_build_thread_context()` to format artifacts** (AC: 6)
  - [x]6.1 Detect messages with `type == "step_completion"` and non-empty `artifacts` in the thread
  - [x]6.2 Format each artifact as: `  - [action] path: description` or `  - [action] path (diff: summary)`
  - [x]6.3 Append formatted artifacts after the message content line in the thread context string
  - [x]6.4 Non-step-completion messages continue to render as before (backward compatible)

- [x] **Task 7: Write tests** (AC: 1-8)
  - [x]7.1 Unit test for `_collect_output_artifacts()` — verifies created vs. modified detection
  - [x]7.2 Unit test for `_snapshot_output_dir()` — verifies snapshot capture
  - [x]7.3 Unit test for `StepCompletionArtifact.to_dict()` serialization
  - [x]7.4 Unit test for `_build_thread_context()` with step_completion messages containing artifacts
  - [x]7.5 Unit test for `_build_thread_context()` with step_completion messages with empty artifacts
  - [x]7.6 Integration test: `post_step_completion()` bridge method serializes correctly (mock Convex client)

## Dev Notes

### Critical: Mapping Architecture Types to Existing Schema

The architecture document defines a `ThreadMessage` type with a `role` field, but the actual Convex schema (already deployed in Story 1.1) uses `authorType` (matching the existing messages table). The developer MUST map between the architecture's conceptual model and the deployed schema:

| Architecture (`ThreadMessage`) | Deployed Schema (`messages` table) | Notes |
|---|---|---|
| `role: "agent"` | `authorType: "agent"` | Same concept, different field name |
| `agentName` | `authorName` | Agent's name goes in authorName |
| `type: "step_completion"` | `type: "step_completion"` | New optional field from Story 1.1 |
| `stepId` | `stepId` | New optional field from Story 1.1 |
| `content` | `content` | Existing field |
| `artifacts` | `artifacts` | New optional field from Story 1.1 |
| — | `messageType: "work"` | Required existing field — use "work" for step completions |
| — | `timestamp` | Existing required field |

The schema already supports all the fields needed (Story 1.1 added `stepId`, `type`, and `artifacts` to the messages table). This story wires up the Python backend to actually populate them.

### Existing Code Flow (Where Changes Happen)

The current execution flow in `executor.py` (`_execute_task()`) does this on success:

```python
# 1. Run the agent
result = await _run_agent_on_task(...)

# 2. Post the agent's text output as a "work" message (PLAIN TEXT, no structure)
await asyncio.to_thread(
    self._bridge.send_message,
    task_id, agent_name, AuthorType.AGENT, result, MessageType.WORK,
)

# 3. Sync output file manifest to Convex (best-effort)
await asyncio.to_thread(
    self._bridge.sync_task_output_files, task_id, task_data or {}, agent_name,
)
```

This story changes step 2 to post a **structured** completion message (with `step_id`, `type="step_completion"`, and `artifacts` array) instead of a plain work message. The output file sync (step 3) continues unchanged — it updates the task-level file manifest, which is a separate concern from the thread message artifacts.

### Bridge Method: `post_step_completion()`

New method on `ConvexBridge`:

```python
def post_step_completion(
    self,
    task_id: str,
    step_id: str,
    agent_name: str,
    content: str,
    artifacts: list[dict[str, Any]] | None = None,
) -> Any:
    """Post a structured step completion message to the task's unified thread."""
    args: dict[str, Any] = {
        "task_id": task_id,
        "author_name": agent_name,
        "author_type": "agent",
        "content": content,
        "message_type": "work",
        "type": "step_completion",
        "step_id": step_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if artifacts:
        args["artifacts"] = artifacts
    result = self._mutation_with_retry("messages:create", args)
    self._log_state_transition(
        "message",
        f"Step completion posted by {agent_name} for step {step_id} on task {task_id}",
    )
    return result
```

### Convex Mutation Extension

The existing `messages:create` mutation in `dashboard/convex/messages.ts` does NOT currently accept `stepId`, `type`, or `artifacts`. It must be extended to accept these as optional args and pass them through to `ctx.db.insert()`. The schema already supports them (Story 1.1).

```typescript
export const create = mutation({
  args: {
    taskId: v.id("tasks"),
    authorName: v.string(),
    authorType: v.union(v.literal("agent"), v.literal("user"), v.literal("system")),
    content: v.string(),
    messageType: v.union(
      v.literal("work"), v.literal("review_feedback"),
      v.literal("approval"), v.literal("denial"),
      v.literal("system_event"), v.literal("user_message"),
    ),
    timestamp: v.string(),
    // NEW — structured completion fields (all optional for backward compat)
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
      action: v.union(v.literal("created"), v.literal("modified"), v.literal("deleted")),
      description: v.optional(v.string()),
      diff: v.optional(v.string()),
    }))),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: args.authorName,
      authorType: args.authorType,
      content: args.content,
      messageType: args.messageType,
      timestamp: args.timestamp,
      // Pass through structured fields when present
      ...(args.stepId !== undefined ? { stepId: args.stepId } : {}),
      ...(args.type !== undefined ? { type: args.type } : {}),
      ...(args.artifacts !== undefined ? { artifacts: args.artifacts } : {}),
    });
  },
});
```

### Artifact Collection Strategy

Agents produce output files in the task's `output/` directory (`~/.nanobot/tasks/{safe_task_id}/output/`). To build the artifacts array:

1. **Before** agent execution: snapshot the output directory (file paths + mtime)
2. **After** agent execution: re-scan the output directory
3. **Compare**: new files = created, changed mtime = modified
4. For each artifact:
   - `path`: relative to task dir (e.g., `output/report.pdf`)
   - `action`: `"created"` or `"modified"`
   - `description`: file type + size for created files (e.g., `"PDF report, 245 KB"`)
   - `diff`: size delta for modified files (e.g., `"+12 KB"`) — full diffs are impractical for binary files and potentially huge for text files

```python
def _snapshot_output_dir(task_id: str) -> dict[str, float]:
    """Capture {relative_path: mtime} for all files in the task's output dir."""
    import re
    safe_id = re.sub(r"[^\w\-]", "_", task_id)
    output_dir = Path.home() / ".nanobot" / "tasks" / safe_id / "output"
    snapshot: dict[str, float] = {}
    if output_dir.exists():
        for entry in output_dir.rglob("*"):
            if entry.is_file():
                rel = str(entry.relative_to(output_dir.parent.parent))
                snapshot[rel] = entry.stat().st_mtime
    return snapshot


def _collect_output_artifacts(
    task_id: str,
    pre_snapshot: dict[str, float] | None,
) -> list[dict[str, Any]]:
    """Compare post-execution output dir against pre-snapshot to build artifacts."""
    import re
    safe_id = re.sub(r"[^\w\-]", "_", task_id)
    output_dir = Path.home() / ".nanobot" / "tasks" / safe_id / "output"
    artifacts: list[dict[str, Any]] = []
    pre = pre_snapshot or {}

    if not output_dir.exists():
        return artifacts

    for entry in output_dir.rglob("*"):
        if not entry.is_file():
            continue
        rel = str(entry.relative_to(output_dir.parent.parent))  # e.g., "output/report.pdf"
        size = entry.stat().st_size

        if rel not in pre:
            # New file — created
            artifacts.append({
                "path": rel,
                "action": "created",
                "description": f"{entry.suffix.lstrip('.').upper() or 'file'}, {_human_size(size)}",
            })
        elif entry.stat().st_mtime > pre[rel]:
            # Existing file with newer mtime — modified
            artifacts.append({
                "path": rel,
                "action": "modified",
                "diff": f"File updated ({_human_size(size)})",
            })

    return artifacts
```

### Step ID Propagation

**Key question: how does `_execute_task()` know the step_id?**

In the current architecture, `TaskExecutor._execute_task()` receives a `task_data` dict from the Convex subscription for **tasks** (not steps). The step dispatcher (Story 2.1/2.2) will call the executor with step-level context. Until the step dispatcher is built, this story should:

1. Accept an optional `step_id` parameter in `_execute_task()` and `_pickup_task()`
2. When `step_id` is provided, use `post_step_completion()` instead of `send_message()`
3. When `step_id` is absent (legacy single-task flow), fall back to existing `send_message()` behavior

This ensures backward compatibility with the current task-level execution while being ready for step-level execution from the dispatcher.

### Thread Context Formatting for Artifacts

The existing `_build_thread_context()` formats messages as:
```
{author} [{author_type}] ({timestamp}): {content}
```

For step_completion messages with artifacts, the format should be extended:
```
{author} [{author_type}] ({timestamp}) [Step Completion]: {content}
  Artifacts:
  - [created] output/report.pdf: PDF, 245 KB
  - [modified] output/data.json (File updated, 12 KB)
```

This is parseable by both humans (readable) and agents (structured text). The `[Step Completion]` tag and indented artifacts section give the LLM clear structure to parse.

### Handling Steps with No File Operations

Some steps produce no file output (e.g., an agent that sends an email, runs a calculation, or provides advice). In these cases:
- `content` describes what the agent did (the agent's text result from `process_direct()`)
- `artifacts` is either an empty list `[]` or omitted entirely
- The completion message is still posted with `type: "step_completion"` — the type indicates structure, not that files exist

### Existing `send_message()` vs. New `post_step_completion()`

| | `send_message()` | `post_step_completion()` |
|---|---|---|
| Use case | General messages (user, system, agent work without step context) | Agent completing a step with structured output |
| Fields | taskId, authorName, authorType, content, messageType, timestamp | All of send_message + stepId, type, artifacts |
| `type` field | Not set (None) | `"step_completion"` |
| `stepId` field | Not set (None) | Set to the step's Convex _id |
| `artifacts` field | Not set (None) | Array of file artifacts (or empty) |
| Who calls | Executor (system messages), orchestrator (agent messages) | Executor (after step completion) |

Both methods call `messages:create` — `post_step_completion()` just adds the extra structured fields.

### Bridge snake_case -> camelCase Conversion

The bridge's `_mutation_with_retry` automatically converts all dict keys from snake_case to camelCase via `_convert_keys_to_camel()`. So when the Python code passes:

```python
{"task_id": ..., "step_id": ..., "author_name": ..., "message_type": ..., "artifacts": [...]}
```

The bridge converts it to:

```json
{"taskId": ..., "stepId": ..., "authorName": ..., "messageType": ..., "artifacts": [...]}
```

This is critical — the artifact objects inside the array also get their keys converted. Since artifact keys (`path`, `action`, `description`, `diff`) are all single-word, they pass through unchanged. But the developer should verify this in testing.

### Important: No `role` Field in Deployed Schema

The architecture document's `ThreadMessage` type specifies a `role` field, but the deployed Convex schema uses `authorType` for this purpose. The `messages:create` mutation does NOT have a `role` field. The developer must use `authorType: "agent"` (not `role: "agent"`) when posting completion messages. The `authorName` field carries the agent's name.

### Existing Code That Touches This Story

| File | What exists | What changes |
|---|---|---|
| `dashboard/convex/messages.ts` | `create` mutation with basic fields only | EXTEND: add optional `stepId`, `type`, `artifacts` args; pass through to insert |
| `dashboard/convex/schema.ts` | Schema already has `stepId`, `type`, `artifacts` on messages | NO CHANGES — schema is ready |
| `nanobot/mc/bridge.py` | `send_message()` for plain messages | ADD: `post_step_completion()` method |
| `nanobot/mc/types.py` | `MessageData`, `MessageType`, `AuthorType` | ADD: `StepCompletionArtifact` dataclass, `StructuredMessageType` enum |
| `nanobot/mc/executor.py` | `_execute_task()` posts plain work message, `_build_thread_context()` formats plain text | MODIFY: post structured completion when step_id available; EXTEND: `_build_thread_context()` to format artifacts |

### Testing Strategy

- **Convex mutation tests**: Verify `messages:create` accepts and persists `stepId`, `type`, `artifacts` fields. Verify backward compat (omitting new fields still works).
- **Bridge unit tests**: Mock `ConvexClient`, call `post_step_completion()`, verify the mutation is called with correct camelCase args.
- **Artifact collection tests**: Create temp directories with files, run `_snapshot_output_dir()` and `_collect_output_artifacts()`, verify correct created/modified detection.
- **Thread context tests**: Build messages list with step_completion entries containing artifacts, run `_build_thread_context()`, verify artifacts appear in formatted output.
- **Integration**: No E2E tests — manual verification via dashboard thread view after running an agent task.

### Git Intelligence (Recent Commits)

```
830fd64 fix card ui
e685c07 Fix Design broken
acc0318 wip: alinhamento do design da dashboard
823f0a7 feat: Implement cron job task linking and output file syncing
479bc23 feat: highlight prompt variables with amber color
```

Recent work has been UI alignment and cron job features. No conflicts expected with message posting changes. Story 1.1 has already been completed (schema extensions deployed), so all schema fields are available.

### Project Structure Notes

- **Convex messages mutation**: `dashboard/convex/messages.ts` — extend `create` mutation
- **Python bridge**: `nanobot/mc/bridge.py` — add `post_step_completion()` method
- **Python types**: `nanobot/mc/types.py` — add `StepCompletionArtifact`, `StructuredMessageType`
- **Python executor**: `nanobot/mc/executor.py` — modify `_execute_task()` flow, extend `_build_thread_context()`
- **Tests**: `nanobot/mc/test_executor.py` (new or extend existing), `nanobot/mc/test_bridge.py` (extend)
- Python test runner: `uv run pytest`
- TypeScript test runner: `npx vitest` (from `dashboard/` directory)

### Dependencies

- **Story 1.1** (done): Schema extensions — `stepId`, `type`, `artifacts` fields on messages table
- **Story 2.1/2.2** (parallel): Step dispatcher — will provide `step_id` context to the executor. Until then, the `step_id` parameter is optional in `_execute_task()`.
- **Story 2.6** (subsequent): Thread context builder enhancements (predecessor injection) — builds on the artifact formatting added in Task 6 of this story.
- **Story 2.7** (subsequent): Thread view rendering — the UI needs structured messages to exist before it can render them with `ArtifactRenderer`.

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Structured Completion Message Format] — ThreadMessage type definition and postStepCompletion mutation pattern
- [Source: _bmad-output/planning-artifacts/architecture.md#Step Completion with Structured Message Pattern] — Convex mutation code example
- [Source: _bmad-output/planning-artifacts/prd.md#FR25] — Structured completion messages requirement
- [Source: _bmad-output/planning-artifacts/prd.md#NFR13] — Consistent format parseable by UI and agents
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.5] — Full BDD acceptance criteria
- [Source: dashboard/convex/schema.ts:91-127] — Existing messages table schema with stepId, type, artifacts
- [Source: dashboard/convex/messages.ts:15-45] — Existing messages:create mutation (to be extended)
- [Source: nanobot/mc/bridge.py:276-299] — Existing send_message() method (pattern for post_step_completion)
- [Source: nanobot/mc/executor.py:586-811] — _execute_task() flow (where completion messages are posted)
- [Source: nanobot/mc/executor.py:168-223] — _build_thread_context() (to be extended for artifacts)
- [Source: nanobot/mc/types.py:95-109] — Existing MessageType and AuthorType enums

## Change Log

- 2026-02-25: Story created with full implementation specification.
