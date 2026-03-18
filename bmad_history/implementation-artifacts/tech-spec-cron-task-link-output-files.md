---
title: 'Cron Jobs Task Link + Output Files Sync'
slug: 'cron-task-link-output-files'
created: '2026-02-23'
status: 'review'
stepsCompleted: [1, 2, 3, 4]
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
  - dashboard/components/CronJobsModal.test.tsx
  - dashboard/components/DashboardLayout.tsx
code_patterns:
  - bridge auto-converts snake_case<->camelCase (always snake_case in Python)
  - dataclass field with None default
  - instance-variable task_id threading on AgentLoop
  - Convex schema v.optional(v.string())
  - sync_task_output_files pattern (scan->fetch->merge->mutate)
test_patterns:
  - vitest + @testing-library/react + userEvent
  - vi.stubGlobal fetch mocking
  - onTaskClick={vi.fn()} required on all CronJobsModal renders
---

# Tech-Spec: Cron Jobs Task Link + Output Files Sync

**Created:** 2026-02-23

## Overview

### Problem Statement

Scheduled cron jobs have no link back to the originating task (the task that created them). Additionally, when a cron job fires and creates a new task whose agent produces output files, those files are only attached to the new (ephemeral) cron-triggered task — they never surface in the original parent task's Files tab.

### Solution

1. **Task link in cron jobs**: thread `task_id` through the cron job creation path so each job stores which Convex task ID created it. Display a clickable ExternalLink icon button in CronJobsModal that opens the originating task's TaskDetailSheet.
2. **Output files from cron runs → original task**: when on_cron_job fires, pass the originating task_id as cron_parent_task_id on the new task. After that task executes, sync its output files to both itself and the parent task in Convex.

### Scope

**In Scope:**
- Add task_id to CronPayload + serialize/deserialize in jobs.json
- Thread task_id: executor._execute_task → _run_agent_on_task → AgentLoop.process_direct (self._current_task_id) → _set_tool_context → CronTool.set_context → cron_service.add_job
- API /api/cron: include taskId in normalized payload
- CronJobsModal: required onTaskClick prop + Task column with ExternalLink
- CronJobsModal.test.tsx: add onTaskClick to all renders + 2 new tests
- DashboardLayout: wire onTaskClick to setSelectedTaskId
- Convex schema: cronParentTaskId: v.optional(v.string())
- tasks:create: accept cronParentTaskId
- gateway.py on_cron_job: pass cron_parent_task_id
- bridge.py: new sync_output_files_to_parent() method
- executor.py: call parent sync after sync_task_output_files

**Out of Scope:** cron history per task, bidirectional visualization, scheduling logic changes

---

## Context for Development

### Codebase Patterns

- Bridge key conversion (CRITICAL): _convert_keys_to_camel on args TO Convex; _convert_keys_to_snake on results. Always snake_case in Python. task_data from async_subscribe has snake_case keys (e.g. cron_parent_task_id)
- Bridge function name strings are NOT key-converted — use exact Convex names ("tasks:getById" not "tasks:get_by_id")
- tasks:updateTaskOutputFiles REPLACES all output files (keeps attachments) — when syncing to parent, fetch parent's existing output files and pass merged set
- tasks:getById takes {taskId: v.id("tasks")} — in Python: self.query("tasks:getById", {"task_id": id})
- ctx.db.insert("tasks", {...}) at line 118 in tasks.ts — uses spread: ...(args.field !== undefined ? {field: args.field} : {})
- CronJobsModal.test.tsx: 10 existing renders with render(<CronJobsModal open={...} onClose={...} />) — all need onTaskClick={vi.fn()} added

### Files to Reference

| File | Purpose |
| ---- | ------- |
| nanobot/cron/types.py | CronPayload dataclass |
| nanobot/agent/tools/cron.py | CronTool.__init__, set_context, _add_job |
| nanobot/cron/service.py | add_job() line 325, _save_store() line 171, _parse_raw_job() line 48 |
| nanobot/agent/loop.py | __init__ line 46, process_direct line 474, _set_tool_context line 147 (cron call at line 159) |
| nanobot/mc/executor.py | _run_agent_on_task line 85, _execute_task line 368, sync call line 486 |
| nanobot/mc/bridge.py | sync_task_output_files line 489, key converters lines 26-61 |
| nanobot/mc/gateway.py | on_cron_job lines 453-464 |
| dashboard/convex/schema.ts | tasks table lines 18-58 |
| dashboard/convex/tasks.ts | create mutation line 73, ctx.db.insert line 118 |
| dashboard/app/api/cron/route.ts | CronPayload interface, normalizeJob |
| dashboard/components/CronJobsModal.tsx | full component |
| dashboard/components/CronJobsModal.test.tsx | SAMPLE_JOB line 11, all renders |
| dashboard/components/DashboardLayout.tsx | CronJobsModal usage line 144 |

### Technical Decisions

- task_id threading via instance variable: process_direct stores as self._current_task_id; _set_tool_context reads it — avoids changing _process_message signature
- Parent output sync: append-only merge — fetch parent existing files, add new filenames only, call updateTaskOutputFiles with merged set
- cronParentTaskId as v.optional(v.string()) not v.id("tasks") — matches Python bridge string IDs
- onTaskClick required prop — only DashboardLayout uses CronJobsModal
- Close-then-navigate: onClick calls onClose() then onTaskClick(id)

---

## Implementation Plan

### Tasks (ordered by dependency)

- [x] T1 — nanobot/cron/types.py: Add task_id: str | None = None as last field of CronPayload after `to`

- [x] T2a — nanobot/cron/service.py: add_job() — add task_id: str | None = None param after delete_after_run; pass task_id=task_id in CronPayload() constructor

- [x] T2b — nanobot/cron/service.py: _save_store() — add "taskId": j.payload.task_id to payload dict

- [x] T2c — nanobot/cron/service.py: _parse_raw_job() — add task_id=raw_payload.get("taskId") in isinstance(raw_payload, dict) branch

- [x] T3 — nanobot/agent/tools/cron.py: (1) add self._task_id: str | None = None in __init__ after self._chat_id = ""; (2) add task_id: str | None = None param to set_context, store as self._task_id; (3) pass task_id=self._task_id in _add_job cron.add_job() call

- [x] T4a — nanobot/agent/loop.py: add self._current_task_id: str | None = None just before self._register_default_tools() (line 106)

- [x] T4b — nanobot/agent/loop.py: add task_id: str | None = None param to process_direct; add self._current_task_id = task_id as first line of body before await self._connect_mcp()

- [x] T4c — nanobot/agent/loop.py: change cron_tool.set_context(channel, chat_id) at line 159 to cron_tool.set_context(channel, chat_id, task_id=self._current_task_id)

- [x] T5 — nanobot/mc/executor.py: (1) add task_id: str | None = None as last param to _run_agent_on_task; (2) pass task_id=task_id to loop.process_direct(); (3) pass task_id=task_id in _execute_task's call to _run_agent_on_task()

- [x] T6 — nanobot/mc/bridge.py: add sync_output_files_to_parent(source_task_id, parent_task_id, agent_name) method after sync_task_output_files (full impl in Notes)

- [x] T7 — nanobot/mc/executor.py: after sync_task_output_files try/except (~line 492), add: cron_parent_task_id = (task_data or {}).get("cron_parent_task_id"); if set, call self._bridge.sync_output_files_to_parent(task_id, cron_parent_task_id, agent_name) in asyncio.to_thread with try/except

- [x] T8 — nanobot/mc/gateway.py: replace on_cron_job body — build create_args dict starting with {"title": job.payload.message}; if job.payload.task_id: add create_args["cron_parent_task_id"] = job.payload.task_id; pass create_args to bridge.mutation("tasks:create", ...)

- [x] T9 — dashboard/convex/schema.ts: add cronParentTaskId: v.optional(v.string()), after boardId line 46; then run: cd dashboard && npx convex dev

- [x] T10 — dashboard/convex/tasks.ts: (1) add cronParentTaskId: v.optional(v.string()), to create mutation args; (2) add ...(args.cronParentTaskId !== undefined ? { cronParentTaskId: args.cronParentTaskId } : {}), in ctx.db.insert after files spread

- [x] T11 — dashboard/app/api/cron/route.ts: (1) add taskId: string | null to CronPayload interface; (2) add taskId: null to legacy normalizeJob payload object

- [x] T12 — dashboard/components/CronJobsModal.tsx: (1) add ExternalLink to lucide-react import; (2) add taskId: string | null to local CronPayload interface; (3) add onTaskClick: (taskId: string) => void to Props; (4) destructure onTaskClick; (5) add Task <th> before actions <th>; (6) add task link <td> before delete <td> (see T12 impl in Notes)

- [x] T13 — dashboard/components/CronJobsModal.test.tsx: (1) add taskId: null to SAMPLE_JOB.payload; (2) add onTaskClick={vi.fn()} to all 10 render/rerender calls; (3) add 2 new tests (see T13 impl in Notes)

- [x] T14 — dashboard/components/DashboardLayout.tsx: add onTaskClick={(taskId) => { setCronOpen(false); setSelectedTaskId(taskId as Id<"tasks">); }} to <CronJobsModal>

---

### Acceptance Criteria

- [x] AC1 — Given agent running a task calls cron tool with action="add". When cron job created. Then ~/.nanobot/cron/jobs.json contains "taskId": "<convex_task_id>" in job's payload object.

- [x] AC2 — Given jobs.json has a job with payload.taskId set. When frontend fetches /api/cron. Then response includes payload.taskId as non-null string.

- [x] AC3 — Given cron job with payload.taskId in modal. When rendered. Then ExternalLink button (aria-label="Open originating task") appears in Task column. And clicking closes modal and opens TaskDetailSheet for that task.

- [x] AC4 — Given cron job with payload.taskId = null. When rendered. Then Task column shows "—".

- [x] AC5 — Given cron job with payload.task_id = "abc" fires. When on_cron_job creates new task. Then new task has cronParentTaskId: "abc".

- [x] AC6 — Given cron-triggered task (with cron_parent_task_id) completes with files in output/. When _execute_task finishes. Then files appear in parent task's Files tab Outputs section. And parent's pre-existing output files are preserved.

- [x] AC7 — Given normal (non-cron) task completes. When _execute_task checks task_data.get("cron_parent_task_id"). Then no error; parent sync skipped.

---

## Additional Context

### Dependencies

- No new packages required
- Existing jobs without taskId handled gracefully (null)
- Run `cd dashboard && npx convex dev` after T9+T10 before testing T7

### Testing Strategy

- Manual AC1-AC4: create task → agent cron add → check jobs.json → open modal → verify/click link
- Manual AC5-AC6: trigger cron job → check Convex cronParentTaskId → check parent Files tab
- TypeScript unit: T13 — 2 new + fix all existing renders
- Python: all new params optional (None default) — no existing tests break
- Run frontend tests: cd dashboard && npx vitest run components/CronJobsModal.test.tsx

### Notes

**T6 sync_output_files_to_parent full implementation:**
```python
def sync_output_files_to_parent(
    self, source_task_id: str, parent_task_id: str, agent_name: str = "agent"
) -> None:
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
                    "name": entry.name, "type": mime,
                    "size": entry.stat().st_size, "subfolder": "output", "uploaded_at": now,
                })
    except OSError as exc:
        logger.error("[bridge] Failed to scan source output dir %s: %s", source_output_dir, exc)
        return
    if not source_files:
        return
    try:
        parent_task = self.query("tasks:getById", {"task_id": parent_task_id})
        parent_files = (parent_task or {}).get("files") or []
    except Exception:
        logger.warning("[bridge] Could not fetch parent task %s", parent_task_id)
        parent_files = []
    existing_output = [f for f in parent_files if f.get("subfolder") == "output"]
    existing_names = {f["name"] for f in existing_output}
    truly_new = [f for f in source_files if f["name"] not in existing_names]
    if not truly_new:
        return
    merged_output = existing_output + truly_new
    try:
        self._mutation_with_retry("tasks:updateTaskOutputFiles", {
            "task_id": parent_task_id, "output_files": merged_output,
        })
        logger.info("[bridge] Synced %d file(s) from cron task %s to parent %s",
                    len(truly_new), source_task_id, parent_task_id)
    except Exception as exc:
        logger.error("[bridge] Failed to sync to parent %s: %s", parent_task_id, exc)
        return
    if truly_new:
        file_names = ", ".join(f["name"] for f in truly_new)
        try:
            self.create_activity("agent_output",
                f"{agent_name} produced {len(truly_new)} file(s) via cron: {file_names}",
                task_id=parent_task_id)
        except Exception:
            pass
```

**T12 task link <td>:**
```tsx
<td className="py-2 pr-4">
  {job.payload.taskId ? (
    <Button variant="ghost" size="icon" aria-label="Open originating task"
      className="h-7 w-7 text-muted-foreground hover:text-foreground"
      onClick={() => { onClose(); onTaskClick(job.payload.taskId!); }}>
      <ExternalLink className="h-3.5 w-3.5" />
    </Button>
  ) : (
    <span className="text-xs text-muted-foreground">—</span>
  )}
</td>
```

**T13 new tests:**
```typescript
it("shows dash in Task column for jobs without taskId", async () => {
  mockFetchWith({ jobs: [SAMPLE_JOB] });
  render(<CronJobsModal open={true} onClose={vi.fn()} onTaskClick={vi.fn()} />);
  await waitFor(() => expect(screen.getByText("Check GitHub Stars")).toBeInTheDocument());
  expect(screen.queryByRole("button", { name: "Open originating task" })).not.toBeInTheDocument();
});

it("clicking task link button calls onClose and onTaskClick with correct id", async () => {
  const jobWithTask = { ...SAMPLE_JOB, payload: { ...SAMPLE_JOB.payload, taskId: "task-abc-123" } };
  mockFetchWith({ jobs: [jobWithTask] });
  const onClose = vi.fn();
  const onTaskClick = vi.fn();
  render(<CronJobsModal open={true} onClose={onClose} onTaskClick={onTaskClick} />);
  await waitFor(() => expect(screen.getByText("Check GitHub Stars")).toBeInTheDocument());
  await userEvent.click(screen.getByRole("button", { name: "Open originating task" }));
  expect(onClose).toHaveBeenCalledTimes(1);
  expect(onTaskClick).toHaveBeenCalledWith("task-abc-123");
});
```
