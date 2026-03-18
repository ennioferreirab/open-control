---
title: 'Cron Jobs Task Link + Output Files Sync'
slug: 'cron-task-link-output-files'
created: '2026-02-23'
status: 'in-progress'
stepsCompleted: [1, 2]
tech_stack: ['Python', 'TypeScript', 'Next.js', 'Convex']
files_to_modify:
  - nanobot/cron/types.py
  - nanobot/agent/tools/cron.py
  - nanobot/cron/service.py
  - nanobot/agent/loop.py
  - nanobot/mc/executor.py
  - nanobot/mc/bridge.py
  - nanobot/mc/gateway.py
  - dashboard/convex/schema.ts
  - dashboard/convex/tasks.ts
  - dashboard/app/api/cron/route.ts
  - dashboard/components/CronJobsModal.tsx
  - dashboard/components/DashboardLayout.tsx
code_patterns:
  - dataclass field addition with default None
  - optional param threading (task_id through call chain)
  - Convex schema v.optional(v.string())
  - bridge.sync_task_output_files pattern
test_patterns: []
---

# Tech-Spec: Cron Jobs Task Link + Output Files Sync

**Created:** 2026-02-23

## Overview

### Problem Statement

Scheduled cron jobs have no link back to the originating task (the task that created them). Additionally, when a cron job fires and creates a new task whose agent produces output files, those files are only attached to the new (ephemeral) cron-triggered task — they never surface in the original parent task's Files tab.

### Solution

Two additions:
1. **Task link in cron jobs**: thread `task_id` through the cron job creation path so each job stores which Convex task ID created it. Display a clickable link in `CronJobsModal` that opens the originating task's `TaskDetailSheet`.
2. **Output files from cron runs → original task**: when `on_cron_job` fires, pass the originating `task_id` as `cronParentTaskId` on the new cron-triggered task. After the new task executes, sync its output files not only to itself but also to the parent task in Convex.

### Scope

**In Scope:**
- Add `task_id` field to `CronPayload` (Python) + serialization/deserialization
- Thread `task_id` from `executor._execute_task` → `_run_agent_on_task` → `AgentLoop.process_direct` → `_set_tool_context` → `CronTool.set_context` → `cron_service.add_job`
- API route `/api/cron` (GET): include `task_id` in normalized payload
- `CronJobsModal`: add `onTaskClick` prop + "Task" column with link button
- `DashboardLayout`: wire `onTaskClick` to open `TaskDetailSheet`
- Convex schema: add `cronParentTaskId: v.optional(v.string())` to tasks table
- `tasks:create` mutation: accept and store `cronParentTaskId`
- `gateway.py` `on_cron_job`: pass `cronParentTaskId` from `job.payload.task_id`
- `bridge.py`: add `sync_output_files_to_parent()` helper
- `executor.py`: after `sync_task_output_files`, call parent sync if `cronParentTaskId` set

**Out of Scope:**
- Showing cron job history per task
- Bidirectional parent-child task visualization
- Any changes to cron job scheduling logic

---

## Context for Development

### Codebase Patterns

- Python dataclasses in `nanobot/cron/types.py` use `field(default=None)` for optional fields
- `CronTool.set_context(channel, chat_id)` is called from `loop._set_tool_context` each message turn
- `AgentLoop` is instantiated fresh per task in `_run_agent_on_task`; safe to set instance vars before `process_direct`
- `sync_task_output_files(task_id, task_data, agent_name)` scans `~/.nanobot/tasks/{safe_id}/output/` and calls `tasks:updateTaskOutputFiles` Convex mutation
- `tasks:updateTaskOutputFiles` REPLACES all output files but preserves attachments — do not call it for parent without merging existing parent output files
- Convex mutation args use camelCase; bridge calls use camelCase keys directly (`bridge.mutation("tasks:create", {"cronParentTaskId": ...})`)
- `normalizeJob()` in `route.ts` handles legacy flat format; new format (has nested schedule/payload/state) returns early — `taskId` in payload will pass through automatically
- Bridge **auto-converts snake_case → camelCase** for all query/mutation args (`_convert_keys_to_camel`)
- Bridge **auto-converts camelCase → snake_case** for all query/mutation return values (`_convert_keys_to_snake`)
- Therefore, Python always uses snake_case; Convex TypeScript always uses camelCase — bridge handles the mapping
- `task_data` from Convex subscription is snake_case (e.g. `board_id`, `cron_parent_task_id`)
- Pass `"cron_parent_task_id"` (snake_case) to `bridge.mutation`/`bridge.query` — bridge converts to `"cronParentTaskId"`

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `nanobot/cron/types.py` | `CronPayload` dataclass — add `task_id` field |
| `nanobot/agent/tools/cron.py` | `CronTool.set_context` + `_add_job` — add task_id |
| `nanobot/cron/service.py` | `add_job()`, `_save_store()`, `_parse_raw_job()` |
| `nanobot/agent/loop.py` | `process_direct` (line 474), `_set_tool_context` (line 147) |
| `nanobot/mc/executor.py` | `_run_agent_on_task` (line 85), `_execute_task` (line 368) |
| `nanobot/mc/bridge.py` | `sync_task_output_files` (line 489) |
| `nanobot/mc/gateway.py` | `on_cron_job` (line 453) |
| `dashboard/convex/schema.ts` | tasks table (lines 18–58) |
| `dashboard/convex/tasks.ts` | `create` mutation (line 73), `updateTaskOutputFiles` (line 736) |
| `dashboard/app/api/cron/route.ts` | `CronPayload` interface, `normalizeJob` |
| `dashboard/components/CronJobsModal.tsx` | full component |
| `dashboard/components/DashboardLayout.tsx` | `CronJobsModal` usage (line 144) |

### Technical Decisions

- **`task_id` threading via instance variable on AgentLoop**: `process_direct` stores `task_id` as `self._current_task_id`. `_set_tool_context` reads it and passes to `CronTool`. This avoids changing `_process_message` signature (which is also called from the interactive event loop path).
- **Parent output sync strategy**: scan the cron-triggered task's output dir (`~/.nanobot/tasks/{new_task_id}/output/`), fetch parent's existing file manifest from Convex, merge (append only new filenames), then call `updateTaskOutputFiles` for parent. Preserves parent's existing output files.
- **Convex schema**: `cronParentTaskId` stored as `v.optional(v.string())` (string, not `v.id("tasks")`) — Python bridge passes plain string IDs.
- **`CronJobsModal` task link**: add `onTaskClick: (taskId: string) => void` prop. Render `ExternalLink` icon button in new "Task" column; only when `job.payload.taskId` is set. On click: close modal, then call `onTaskClick`.

---

## Implementation Plan

### Tasks

**T1 — `nanobot/cron/types.py`: Add `task_id` to `CronPayload`**

Add `task_id: str | None = None` as the last field of `CronPayload`:

```python
@dataclass
class CronPayload:
    kind: Literal["system_event", "agent_turn"] = "agent_turn"
    message: str = ""
    deliver: bool = False
    channel: str | None = None
    to: str | None = None
    task_id: str | None = None   # NEW
```

---

**T2 — `nanobot/cron/service.py`: Thread `task_id` through add/save/parse**

**(a) `add_job()` signature** — add `task_id: str | None = None` after `delete_after_run`:

```python
def add_job(
    self,
    name: str,
    schedule: CronSchedule,
    message: str,
    deliver: bool = False,
    channel: str | None = None,
    to: str | None = None,
    delete_after_run: bool = False,
    task_id: str | None = None,   # NEW
) -> CronJob:
```

Inside `add_job`, update `CronPayload(...)`:
```python
payload=CronPayload(
    kind="agent_turn",
    message=message,
    deliver=deliver,
    channel=channel,
    to=to,
    task_id=task_id,   # NEW
),
```

**(b) `_save_store()` payload dict** — add `"taskId": j.payload.task_id`:
```python
"payload": {
    "kind": j.payload.kind,
    "message": j.payload.message,
    "deliver": j.payload.deliver,
    "channel": j.payload.channel,
    "to": j.payload.to,
    "taskId": j.payload.task_id,   # NEW
},
```

**(c) `_parse_raw_job()` — in the `isinstance(raw_payload, dict)` branch**, add `task_id=raw_payload.get("taskId")`:
```python
payload = CronPayload(
    kind=raw_payload.get("kind", "agent_turn"),
    message=raw_payload.get("message", ""),
    deliver=raw_payload.get("deliver", False),
    channel=raw_payload.get("channel"),
    to=raw_payload.get("to"),
    task_id=raw_payload.get("taskId"),   # NEW
)
```

---

**T3 — `nanobot/agent/tools/cron.py`: Accept `task_id` in `set_context` + pass to `add_job`**

Add `self._task_id: str | None = None` after `self._chat_id = ""` in `__init__`.

Update `set_context`:
```python
def set_context(self, channel: str, chat_id: str, task_id: str | None = None) -> None:
    self._channel = channel
    self._chat_id = chat_id
    self._task_id = task_id   # NEW
```

Update `_add_job` — add `task_id=self._task_id` to `cron.add_job(...)` call:
```python
job = self._cron.add_job(
    name=message[:30],
    schedule=schedule,
    message=message,
    deliver=True,
    channel=self._channel,
    to=self._chat_id,
    delete_after_run=delete_after,
    task_id=self._task_id,   # NEW
)
```

---

**T4 — `nanobot/agent/loop.py`: Store `task_id` as instance var, pass to CronTool**

**(a)** Add `self._current_task_id: str | None = None` to `__init__`. Insert it just before `self._register_default_tools()` at line 106 (after all the other instance variable assignments).

**(b)** Update `process_direct` — add `task_id: str | None = None` param and store it:
```python
async def process_direct(
    self,
    content: str,
    session_key: str = "cli:direct",
    channel: str = "cli",
    chat_id: str = "direct",
    on_progress: Callable[[str], Awaitable[None]] | None = None,
    task_id: str | None = None,   # NEW
) -> str:
    self._current_task_id = task_id   # NEW
    await self._connect_mcp()
    msg = InboundMessage(channel=channel, sender_id="user", chat_id=chat_id, content=content)
    response = await self._process_message(msg, session_key=session_key, on_progress=on_progress)
    return response.content if response else ""
```

**(c)** Update `_set_tool_context` — pass `self._current_task_id` to `CronTool`:
```python
if cron_tool := self.tools.get("cron"):
    if isinstance(cron_tool, CronTool):
        cron_tool.set_context(channel, chat_id, task_id=self._current_task_id)   # CHANGED
```
(was: `cron_tool.set_context(channel, chat_id)`)

---

**T5 — `nanobot/mc/executor.py`: Pass `task_id` through `_run_agent_on_task`**

**(a)** Update `_run_agent_on_task` signature — add `task_id: str | None = None` as the last param:
```python
async def _run_agent_on_task(
    agent_name: str,
    agent_prompt: str | None,
    agent_model: str | None,
    task_title: str,
    task_description: str | None,
    agent_skills: list[str] | None = None,
    board_name: str | None = None,
    memory_workspace: Path | None = None,
    cron_service: Any | None = None,
    task_id: str | None = None,   # NEW
) -> str:
```

**(b)** Inside `_run_agent_on_task`, pass `task_id` to `loop.process_direct`:
```python
result = await loop.process_direct(
    content=message,
    session_key=session_key,
    channel="mc",
    chat_id=agent_name,
    task_id=task_id,   # NEW
)
```

**(c)** In `_execute_task`, pass `task_id` to `_run_agent_on_task` (inside the `try:` block):
```python
result = await _run_agent_on_task(
    agent_name=agent_name,
    agent_prompt=agent_prompt,
    agent_model=agent_model,
    task_title=title,
    task_description=description,
    agent_skills=agent_skills,
    board_name=board_name,
    memory_workspace=memory_workspace,
    cron_service=self._cron_service,
    task_id=task_id,   # NEW
)
```

---

**T6 — `nanobot/mc/bridge.py`: Add `sync_output_files_to_parent` method**

Add the following method after `sync_task_output_files` (after line ~568 where the existing method ends):

```python
def sync_output_files_to_parent(
    self, source_task_id: str, parent_task_id: str, agent_name: str = "agent"
) -> None:
    """Append cron-triggered task output files to the parent task's Convex record.

    Scans source_task_id's output dir, fetches parent's existing file manifest,
    merges (new filenames only), then calls updateTaskOutputFiles for the parent.
    Does not remove parent's pre-existing output files.
    """
    EXT_MIME: dict[str, str] = {
        "pdf": "application/pdf", "md": "text/markdown", "markdown": "text/markdown",
        "html": "text/html", "htm": "text/html", "txt": "text/plain",
        "csv": "text/csv", "json": "application/json", "yaml": "text/yaml",
        "yml": "text/yaml", "xml": "application/xml", "py": "text/x-python",
        "ts": "text/typescript", "tsx": "text/typescript", "js": "text/javascript",
        "jsx": "text/javascript", "go": "text/x-go", "rs": "text/x-rust",
        "sh": "text/x-sh", "bash": "text/x-sh",
    }

    safe_source_id = re.sub(r"[^\w\-]", "_", source_task_id)
    source_output_dir = Path.home() / ".nanobot" / "tasks" / safe_source_id / "output"

    if not source_output_dir.exists():
        return

    now = datetime.utcnow().isoformat() + "Z"
    source_files: list[dict] = []
    try:
        for entry in source_output_dir.iterdir():
            if entry.is_file():
                ext = entry.suffix.lstrip(".").lower()
                mime = EXT_MIME.get(ext, "application/octet-stream")
                source_files.append({
                    "name": entry.name,
                    "type": mime,
                    "size": entry.stat().st_size,
                    "subfolder": "output",
                    "uploaded_at": now,
                })
    except OSError as exc:
        logger.error("[bridge] Failed to scan source output dir %s: %s", source_output_dir, exc)
        return

    if not source_files:
        return

    # Fetch parent's current output files from Convex
    try:
        parent_task = self.query("tasks:getById", {"task_id": parent_task_id})
        parent_files = (parent_task or {}).get("files") or []
    except Exception:
        logger.warning("[bridge] Could not fetch parent task %s for output merge", parent_task_id)
        parent_files = []

    existing_output = [f for f in parent_files if f.get("subfolder") == "output"]
    existing_names = {f["name"] for f in existing_output}
    truly_new = [f for f in source_files if f["name"] not in existing_names]

    if not truly_new:
        return

    merged_output = existing_output + truly_new

    try:
        self._mutation_with_retry("tasks:updateTaskOutputFiles", {
            "task_id": parent_task_id,
            "output_files": merged_output,
        })
        logger.info(
            "[bridge] Synced %d output file(s) from cron task %s → parent %s",
            len(truly_new), source_task_id, parent_task_id,
        )
    except Exception as exc:
        logger.error(
            "[bridge] Failed to sync output files to parent %s: %s", parent_task_id, exc
        )
        return

    if truly_new:
        file_names = ", ".join(f["name"] for f in truly_new)
        msg = f"{agent_name} produced {len(truly_new)} file(s) via cron: {file_names}"
        try:
            self.create_activity("agent_output", msg, task_id=parent_task_id)
        except Exception:
            pass
```

---

**T7 — `nanobot/mc/executor.py`: Sync output files to parent after task completes**

In `_execute_task`, inside the `try:` block after the existing `sync_task_output_files` call (around line 492), add:

```python
# Sync output files to cron parent task if applicable
cron_parent_task_id = (task_data or {}).get("cronParentTaskId")
if cron_parent_task_id:
    try:
        await asyncio.to_thread(
            self._bridge.sync_output_files_to_parent,
            task_id,
            cron_parent_task_id,
            agent_name,
        )
    except Exception:
        logger.exception(
            "[executor] Failed to sync output files to parent task '%s'",
            cron_parent_task_id,
        )
```

Note: `task_data.get("cron_parent_task_id")` — snake_case, because the bridge's `async_subscribe` applies `_convert_keys_to_snake` to all returned documents.

---

**T8 — `nanobot/mc/gateway.py`: Pass `cronParentTaskId` when creating cron-triggered task**

Replace the existing `on_cron_job` body (lines 453–464):

```python
async def on_cron_job(job: CronJob) -> str | None:
    """Create a Convex task when a cron job fires."""
    logger.info("[gateway] Cron job '%s' fired — creating task", job.name)
    try:
        create_args: dict = {"title": job.payload.message}
        if job.payload.task_id:
            create_args["cron_parent_task_id"] = job.payload.task_id  # bridge converts to camelCase
        await asyncio.to_thread(
            bridge.mutation,
            "tasks:create",
            create_args,
        )
    except Exception:
        logger.exception("[gateway] Failed to create task for cron job '%s'", job.name)
    return None
```

---

**T9 — `dashboard/convex/schema.ts`: Add `cronParentTaskId` to tasks table**

In the tasks `defineTable({...})` block, add after `boardId: v.optional(v.id("boards"))` (line 46):

```typescript
cronParentTaskId: v.optional(v.string()),
```

---

**T10 — `dashboard/convex/tasks.ts`: Accept `cronParentTaskId` in `create` mutation**

**(a)** In the `create` mutation `args` (line 73), add:
```typescript
cronParentTaskId: v.optional(v.string()),
```

**(b)** In the `create` mutation `handler`, find `ctx.db.insert("tasks", {...})` and add `cronParentTaskId` to the insert object:
```typescript
...(args.cronParentTaskId !== undefined ? { cronParentTaskId: args.cronParentTaskId } : {}),
```

To find the right place: search for `ctx.db.insert("tasks",` in `tasks.ts` and add this spread inside the object literal passed to it.

---

**T11 — `dashboard/app/api/cron/route.ts`: Add `taskId` to payload interface**

**(a)** Update `CronPayload` interface — add `taskId: string | null`:
```typescript
interface CronPayload {
  kind: string;
  message: string;
  deliver: boolean;
  channel: string | null;
  to: string | null;
  taskId: string | null;   // NEW
}
```

**(b)** In `normalizeJob`, update the legacy flat-format `payload` object — add `taskId: null`:
```typescript
payload: {
    kind: "agent_turn",
    message: raw.message ?? "",
    deliver: false,
    channel: null,
    to: null,
    taskId: null,   // NEW
},
```

The new format (when `raw.schedule && raw.payload && raw.state` is truthy) returns `raw` unchanged, so `taskId` inside `payload` passes through automatically.

---

**T12 — `dashboard/components/CronJobsModal.tsx`: Add task link column**

**(a)** Update `Props` interface — add `onTaskClick`:
```typescript
interface Props {
  open: boolean;
  onClose: () => void;
  onTaskClick: (taskId: string) => void;   // NEW
}
```

**(b)** Update `CronPayload` interface — add `taskId: string | null`:
```typescript
interface CronPayload {
  kind: string;
  message: string;
  deliver: boolean;
  channel: string | null;
  to: string | null;
  taskId: string | null;   // NEW
}
```

**(c)** Destructure `onTaskClick` in the component signature:
```typescript
export function CronJobsModal({ open, onClose, onTaskClick }: Props) {
```

**(d)** Add `ExternalLink` to lucide-react import (line 22):
```typescript
import { X, Trash2, ExternalLink } from "lucide-react";
```

**(e)** Add `<th>` for "Task" column in `<thead>` — insert before the empty `<th>`:
```tsx
<th className="text-left pb-2 pr-4 font-medium">Task</th>
```

**(f)** Add `<td>` for each row — insert before the delete button `<td>` (inside `{jobs.map(...)}`):
```tsx
<td className="py-2 pr-4">
  {job.payload.taskId ? (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Open originating task"
      className="h-7 w-7 text-muted-foreground hover:text-foreground"
      onClick={() => {
        onClose();
        onTaskClick(job.payload.taskId!);
      }}
    >
      <ExternalLink className="h-3.5 w-3.5" />
    </Button>
  ) : (
    <span className="text-xs text-muted-foreground">—</span>
  )}
</td>
```

---

**T13 — `dashboard/components/DashboardLayout.tsx`: Wire `onTaskClick` to `CronJobsModal`**

Update the `CronJobsModal` usage (line 144):
```tsx
<CronJobsModal
  open={cronOpen}
  onClose={() => setCronOpen(false)}
  onTaskClick={(taskId) => {
    setCronOpen(false);
    setSelectedTaskId(taskId as Id<"tasks">);
  }}
/>
```

---

### Acceptance Criteria

**AC1 — `task_id` stored in cron job payload**
- Given: an agent running a task calls the `cron` tool with `action="add"`
- When: the cron job is created
- Then: `~/.nanobot/cron/jobs.json` contains `"taskId": "<convex_task_id>"` in the job's `payload` object

**AC2 — `GET /api/cron` returns `taskId`**
- Given: `jobs.json` has a job with `payload.taskId` set
- When: frontend fetches `/api/cron`
- Then: response includes `payload.taskId` as a non-null string for that job

**AC3 — CronJobsModal shows task link button**
- Given: a cron job with `payload.taskId` set is displayed
- When: modal renders
- Then: an `ExternalLink` icon button appears in the "Task" column for that row
- And: clicking it closes the modal and opens `TaskDetailSheet` for the correct task ID

**AC4 — CronJobsModal shows dash for jobs without `taskId`**
- Given: a cron job with no `payload.taskId`
- When: modal renders
- Then: the "Task" column shows "—" for that row

**AC5 — Cron-triggered task stores `cronParentTaskId`**
- Given: a cron job with `payload.task_id = "abc"` fires
- When: `on_cron_job` creates the new Convex task
- Then: the new task document has `cronParentTaskId: "abc"`

**AC6 — Output files synced to parent task**
- Given: a cron-triggered task (with `cronParentTaskId`) completes and has files in its `output/` dir
- When: `executor._execute_task` finishes
- Then: those output files appear in the parent task's Files tab → Outputs section
- And: the parent task's own pre-existing output files are not removed

**AC7 — No error when `cronParentTaskId` is absent**
- Given: a normal (non-cron) task completes
- When: `_execute_task` checks `task_data.get("cronParentTaskId")`
- Then: no error is raised; parent sync is skipped silently

---

## Additional Context

### Dependencies

- No new npm or pip packages required
- No migration needed for existing cron jobs (legacy jobs have no `taskId` in payload — treated as null)
- Convex schema change (T9) requires `npx convex dev` or `npx convex deploy` to push schema

### Testing Strategy

- **Manual AC1–AC4**: create a task → have agent use `cron add` → check `jobs.json` → open CronJobsModal → verify link → click it
- **Manual AC5–AC6**: wait for cron trigger or use `cron.run_job()` manually → check parent task Files tab
- **Unit (TypeScript)**: update `CronJobsModal.test.tsx` — add `taskId` to `SAMPLE_JOB.payload`; add test that clicking `ExternalLink` button calls `onTaskClick` with correct id; add test that jobs without `taskId` show "—"
- **Python**: all new params are optional with `None` defaults — existing tests unaffected

### Notes

- `sync_output_files_to_parent` duplicates the MIME lookup map from `sync_task_output_files`. DRY refactor is out of scope.
- The `onTaskClick` callback in T13 calls `setCronOpen(false)` before setting `selectedTaskId` to avoid Dialog/Sheet stacking issues.
- `task_id` in Python snake_case = `taskId` in JSON/TypeScript camelCase (consistent with all other cross-boundary field naming in this codebase).
- After completing T9+T10, run `npx convex dev` in the `dashboard/` directory to push the schema update.
