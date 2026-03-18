---
title: 'Cron Jobs Agent Targeting'
slug: 'cron-agent-targeting'
created: '2026-02-28'
status: 'ready-for-dev'
tech_stack: ['Python']
files_to_modify:
  - nanobot/cron/types.py
  - nanobot/cron/service.py
  - nanobot/agent/tools/cron.py
  - nanobot/agent/loop.py
  - nanobot/mc/executor.py
  - nanobot/mc/gateway.py
  - dashboard/app/api/cron/route.ts
  - tests/test_cron_service.py
  - tests/mc/test_gateway_cron_delivery.py
code_patterns:
  - bridge auto-converts snake_case<->camelCase (always snake_case in Python)
  - dataclass field with None default for backward compat
  - instance-variable threading on AgentLoop (same pattern as task_id)
  - CronTool.set_context receives session state from AgentLoop._set_tool_context
  - Convex tasks:create already accepts assignedAgent as v.optional(v.string())
test_patterns:
  - pytest with MagicMock/AsyncMock for gateway tests
  - _make_cron_job helper in test_gateway_cron_delivery.py
  - tmp_path fixture for CronService tests
---

# Tech-Spec: Cron Jobs Agent Targeting

**Created:** 2026-02-28

## Overview

### Problem Statement

When an agent (e.g., `youtube-summarizer`) creates a cron job, the system does not record which agent created it. When the cron fires in MC mode, `on_cron_job()` in `gateway.py` creates a new task via `tasks:create` without `assignedAgent`. This causes the task to enter the planning flow, where the planner/fallback assigns it to `nanobot` (the default agent) instead of the originating agent.

Observed symptom: `youtube-summarizer` scheduled a daily cron at 08:30. When it fired, `nanobot` picked up the task and tried to interpret YouTube channel handles (`@AIJasonZ`, `@QuantBrasil`) as agent names, producing "Agent @aijasonz not found" errors.

### Solution

Thread the **agent name** through the entire cron creation and execution pipeline:
1. Add `agent` field to `CronPayload` — stores which agent created the job
2. Auto-capture the creating agent's name in `CronTool.set_context()`
3. When the cron fires, pass `assigned_agent` to `tasks:create` so the task skips planning and goes directly to the correct agent

### Scope

**In Scope:**
- Add `agent` field to CronPayload + serialize/deserialize in jobs.json
- Thread agent_name: AgentLoop → CronTool.set_context → CronService.add_job
- gateway.py on_cron_job: pass assigned_agent when creating new tasks
- gateway.py _requeue_cron_task: pass agent in fallback task creation paths
- API /api/cron: include agent in normalized legacy payload
- Update existing tests + add new tests for agent targeting

**Out of Scope:**
- Dashboard CronJobsModal UI changes (displaying agent name is a cosmetic enhancement)
- Changing existing cron jobs that are already stored without an agent field (backward-compatible)
- CLI mode changes (CLI has only one agent, no routing needed)

---

## Context for Development

### Codebase Patterns

- Bridge key conversion (CRITICAL): `_convert_keys_to_camel` on args TO Convex; `_convert_keys_to_snake` on results FROM Convex. Always snake_case in Python. So `assigned_agent` in Python → `assignedAgent` in Convex.
- CronPayload fields use `None` defaults for optional fields — backward compatible with old jobs.json
- `CronTool.set_context()` is called from `AgentLoop._set_tool_context()` at line 173 of loop.py — this is where session state is injected
- `_run_agent_on_task()` in executor.py already receives `agent_name` as its first parameter (line 136) — it just needs to be passed to AgentLoop
- Convex `tasks:create` already accepts `assignedAgent: v.optional(v.string())` at line 100 of tasks.ts — no Convex changes needed
- Orchestrator at line 210: `next_status = "assigned" if assigned_agent else "planning"` — so setting `assignedAgent` causes the task to skip planning entirely

### Files to Reference

| File | Purpose |
| ---- | ------- |
| nanobot/cron/types.py | CronPayload dataclass — add `agent` field after `task_id` (line 30) |
| nanobot/cron/service.py | add_job() line 328 — add `agent` param; _save_store() line 193 — serialize; _parse_raw_job() line 74 — deserialize |
| nanobot/agent/tools/cron.py | CronTool.__init__ line 13, set_context line 19, _add_job line 126 |
| nanobot/agent/loop.py | __init__ line 47 — add agent_name param; _set_tool_context line 173 — pass to CronTool |
| nanobot/mc/executor.py | _run_agent_on_task line 135 — has agent_name, pass to AgentLoop; AgentLoop() constructor line 202 |
| nanobot/mc/gateway.py | on_cron_job line 1005 — use payload.agent; _requeue_cron_task line 940 — fallback paths at lines 958, 963 |
| dashboard/app/api/cron/route.ts | normalizeJob line 8 — add agent to legacy payload |
| dashboard/convex/tasks.ts | tasks:create line 95 — already accepts assignedAgent |
| tests/test_cron_service.py | CronService unit tests |
| tests/mc/test_gateway_cron_delivery.py | Gateway on_cron_job tests with _make_cron_job helper |

### Technical Decisions

- `agent` field uses `str | None = None` — existing jobs without this field default to `None` (current planning behavior preserved)
- AgentLoop receives `agent_name` as constructor param (same pattern as `cron_service`, `memory_workspace`, etc.)
- `_requeue_cron_task` receives `agent` as optional 4th parameter for fallback paths that create new tasks
- No Convex schema changes needed — `assignedAgent` field already exists on tasks table

---

## Implementation Plan

### Tasks (ordered by dependency)

- [ ] T1 — nanobot/cron/types.py: Add `agent: str | None = None` as last field of CronPayload after `task_id` (line 30)

- [ ] T2a — nanobot/cron/service.py: add_job() — add `agent: str | None = None` param after `task_id` (line 337); pass `agent=agent` in CronPayload() constructor (line 355)

- [ ] T2b — nanobot/cron/service.py: _save_store() — add `"agent": j.payload.agent` to payload dict after `"taskId"` line (line 199)

- [ ] T2c — nanobot/cron/service.py: _parse_raw_job() — add `agent=raw_payload.get("agent")` in the isinstance(raw_payload, dict) branch (line 80, after `task_id=raw_payload.get("taskId")`)

- [ ] T3a — nanobot/agent/tools/cron.py: add `self._agent_name: str | None = None` in __init__ after `self._task_id` (line 17)

- [ ] T3b — nanobot/agent/tools/cron.py: add `agent_name: str | None = None` param to set_context (line 19); store as `self._agent_name = agent_name`

- [ ] T3c — nanobot/agent/tools/cron.py: pass `agent=self._agent_name` in _add_job's `self._cron.add_job()` call (line 134, after `task_id=self._task_id`)

- [ ] T4a — nanobot/agent/loop.py: add `agent_name: str | None = None` param to AgentLoop.__init__() (after `reasoning_level` param, line 68); store as `self._agent_name = agent_name` in body

- [ ] T4b — nanobot/agent/loop.py: update _set_tool_context line 175 to pass agent_name: `cron_tool.set_context(channel, chat_id, task_id=self._current_task_id, agent_name=self._agent_name)`

- [ ] T5 — nanobot/mc/executor.py: pass `agent_name=agent_name` to AgentLoop() constructor (line 211, after `cron_service=cron_service`). The `agent_name` variable is already available as the first parameter of `_run_agent_on_task()`.

- [ ] T6a — nanobot/mc/gateway.py: update `_requeue_cron_task` signature (line 940) to accept `agent: str | None = None` as 4th param

- [ ] T6b — nanobot/mc/gateway.py: in `_requeue_cron_task` fallback paths (lines 958, 963) where new tasks are created, build `create_args` dict and include `"assigned_agent": agent` if agent is not None:
```python
create_args: dict = {"title": message}
if agent:
    create_args["assigned_agent"] = agent
await asyncio.to_thread(b.mutation, "tasks:create", create_args)
```

- [ ] T6c — nanobot/mc/gateway.py: in `on_cron_job()` (line 1011), pass `agent=job.payload.agent` to `_requeue_cron_task()` call

- [ ] T6d — nanobot/mc/gateway.py: in `on_cron_job()` (line 1015-1017), when creating a new task, build `create_args` dict and include `assigned_agent`:
```python
create_args: dict = {"title": job.payload.message}
if job.payload.agent:
    create_args["assigned_agent"] = job.payload.agent
new_id = await asyncio.to_thread(
    bridge.mutation, "tasks:create", create_args,
)
```

- [ ] T7 — dashboard/app/api/cron/route.ts: add `agent: null` to legacy normalizeJob payload object (line 37, after `taskId: null`)

- [ ] T8a — tests/test_cron_service.py: add test `test_add_job_with_agent_roundtrips` — create job with `agent="youtube-summarizer"`, reload from disk, verify `job.payload.agent == "youtube-summarizer"`

- [ ] T8b — tests/test_cron_service.py: add test `test_parse_old_job_without_agent_defaults_none` — write old-format JSON without `agent` key, load, verify `payload.agent is None`

- [ ] T9a — tests/mc/test_gateway_cron_delivery.py: update `_make_cron_job` helper to accept `agent: str | None = None` param and pass to CronPayload

- [ ] T9b — tests/mc/test_gateway_cron_delivery.py: add test `test_cron_job_with_agent_passes_assigned_agent_to_task_create` — create job with `agent="youtube-summarizer"`, fire on_job, verify bridge.mutation was called with `{"title": ..., "assigned_agent": "youtube-summarizer"}`

- [ ] T9c — tests/mc/test_gateway_cron_delivery.py: add test `test_cron_job_without_agent_creates_task_without_assigned_agent` — create job with `agent=None`, fire on_job, verify bridge.mutation called with just `{"title": ...}` (backward compat)

---

### Acceptance Criteria

- [ ] AC1 — Given an agent named "youtube-summarizer" calls the cron tool with action="add". When cron job is created. Then ~/.nanobot/cron/jobs.json contains `"agent": "youtube-summarizer"` in the job's payload object.

- [ ] AC2 — Given jobs.json has a job with payload.agent set. When the cron job fires and creates a new task (no task_id). Then bridge.mutation("tasks:create", ...) is called with `assigned_agent` equal to the payload agent value.

- [ ] AC3 — Given a cron job with payload.agent fires and creates a task with assignedAgent set. When the orchestrator processes the task. Then task status transitions directly to "assigned" (skipping "planning"), and the correct agent executes it.

- [ ] AC4 — Given an old cron job in jobs.json without an "agent" field. When the job is loaded. Then payload.agent is None, and when it fires, the task is created without assignedAgent (current planning behavior preserved).

- [ ] AC5 — Given a cron job with task_id set (re-queue path) where the original task is not found. When _requeue_cron_task creates a fallback task. Then the fallback task includes assignedAgent from the cron payload.

- [ ] AC6 — All existing tests pass without modification (backward compatibility).

---

## Additional Context

### Dependencies

- No new packages required
- No Convex schema changes required (assignedAgent already exists)
- Existing jobs without agent field handled gracefully (None default)

### Testing Strategy

- Python unit tests: T8a-T8b for CronService, T9a-T9c for gateway
- Manual verification: create cron via youtube-summarizer agent → check jobs.json has agent field → let cron fire → verify task is assigned directly to youtube-summarizer
- Run: `uv run pytest tests/test_cron_service.py tests/mc/test_gateway_cron_delivery.py -v`

### Data Flow Diagram

```
Agent creates cron job:
  AgentLoop.__init__(agent_name="youtube-summarizer")
    └→ _set_tool_context()
        └→ CronTool.set_context(channel, chat_id, task_id, agent_name="youtube-summarizer")
            └→ _add_job()
                └→ CronService.add_job(agent="youtube-summarizer")
                    └→ CronPayload(agent="youtube-summarizer")
                        └→ Saved to jobs.json: {"agent": "youtube-summarizer"}

Cron fires:
  CronService._execute_job()
    └→ on_cron_job(job)  [gateway.py]
        └→ job.payload.agent == "youtube-summarizer"
        └→ bridge.mutation("tasks:create", {
              "title": "...",
              "assigned_agent": "youtube-summarizer"  ← NEW
           })
        └→ Orchestrator: assignedAgent is set → status = "assigned" (skip planning)
        └→ Executor: youtube-summarizer runs the task ✓
```
