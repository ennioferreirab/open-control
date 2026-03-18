# Story 2.1: Dispatch Steps in Autonomous Mode

Status: done

## Story

As a **user**,
I want my task to start executing immediately after the plan is generated in autonomous mode,
So that I don't have to manually trigger execution for straightforward goals.

## Acceptance Criteria

1. **Autonomous dispatch triggers automatically** -- Given a task was created with `supervisionMode: "autonomous"`, when the plan materializer finishes creating step records (Story 1.6), then the step dispatcher is triggered automatically with no user action required (FR20). The task status is already "in_progress" (set by materializer's `kick_off_task`). An activity event is created: "Steps dispatched in autonomous mode".

2. **Assigned steps queued for immediate execution** -- Given steps are dispatched in autonomous mode, when the dispatch begins, then all steps with status "assigned" (no blockers) are queued for immediate execution via `asyncio.gather()` for parallel dispatch within the same `parallelGroup` (FR21).

3. **Blocked steps remain blocked** -- Given steps are dispatched in autonomous mode, when the dispatch begins, then steps with status "blocked" remain blocked until their dependencies complete (FR22, FR23).

4. **Supervised mode skips dispatch** -- Given a task was created with `supervisionMode: "supervised"`, when the plan materializer finishes, then the step dispatcher is NOT triggered -- the task waits for user approval (Epic 4).

5. **Step status transitions on execution start** -- Given a step is dispatched, when the agent subprocess starts, then the step's status is updated from "assigned" to "running" in Convex via the bridge. An activity event is created: "Agent {agentName} started step: {stepTitle}".

6. **Step status transitions on completion** -- Given an agent subprocess completes successfully, when completion is detected, then the step's status is updated to "completed". An activity event is created: "Agent {agentName} completed step: {stepTitle}". The `checkAndUnblockDependents` mutation is called to potentially unblock downstream steps.

7. **Step crash handling** -- Given an agent subprocess crashes, when the failure is detected, then the step's status is updated to "crashed" with the error message. Other running subprocesses in the same parallel group continue unaffected (NFR8). The `asyncio.gather()` call uses `return_exceptions=True`.

8. **Newly unblocked steps are dispatched** -- Given a step completes and `checkAndUnblockDependents` transitions dependent steps from "blocked" to "assigned", then the dispatcher detects and dispatches these newly assigned steps.

9. **Task completes when all steps finish** -- Given all steps in a task reach "completed" status, when the last step completes and unblocking finishes, then the task status transitions to "done". An activity event is created: "Task completed -- all {N} steps finished".

## Dependencies

| Story | What It Provides | What This Story Needs From It |
|-------|-----------------|-------------------------------|
| **1.1: Extend Convex Schema** | `steps` table with lifecycle statuses, `checkAndUnblockDependents` mutation, `getByTask` query, `updateStatus` mutation | Step records to query/dispatch, status update mutations, dependency unblocking logic |
| **1.6: Materialize Plans into Step Records** | `PlanMaterializer.materialize()` that creates step records with "assigned"/"blocked" statuses, `tasks:kickOff` mutation that transitions task to "in_progress" | Step records exist in Convex after materialization. This story picks up where materialization leaves off -- dispatching the "assigned" steps. |

## Tasks / Subtasks

- [x] **Task 1: Create `StepDispatcher` class in `nanobot/mc/step_dispatcher.py`** (AC: 1, 2, 3)
  - [x] 1.1 Create new module `nanobot/mc/step_dispatcher.py` with class `StepDispatcher`
  - [x] 1.2 Implement `dispatch_steps(task_id, step_ids)` main entry point that fetches steps from Convex, groups by `parallelGroup`, and dispatches in order
  - [x] 1.3 Implement `_dispatch_parallel_group(task_id, steps)` that runs all steps in a group concurrently via `asyncio.gather(*tasks, return_exceptions=True)`
  - [x] 1.4 Implement `_execute_step(task_id, step)` that transitions step to "running", runs the agent, handles success/failure

- [x] **Task 2: Implement step execution lifecycle** (AC: 5, 6, 7)
  - [x] 2.1 Add `update_step_status()` bridge method that calls `steps:updateStatus` with snake-to-camel conversion
  - [x] 2.2 Add `get_steps_by_task()` bridge method that calls `steps:getByTask`
  - [x] 2.3 Add `check_and_unblock_dependents()` bridge method that calls `steps:checkAndUnblockDependents`
  - [x] 2.4 In `_execute_step()`: transition step "assigned" -> "running" before agent execution, then "running" -> "completed" on success or "running" -> "crashed" on failure
  - [x] 2.5 On step completion, call `check_and_unblock_dependents()` and collect newly unblocked step IDs

- [x] **Task 3: Implement dependency-aware dispatch loop** (AC: 3, 8, 9)
  - [x] 3.1 After each parallel group completes, re-fetch steps for the task to find newly "assigned" steps
  - [x] 3.2 Continue dispatching newly assigned steps until no more remain
  - [x] 3.3 When all steps are "completed" (or no more runnable), transition task to "done" with activity event

- [x] **Task 4: Integrate dispatcher into orchestrator flow** (AC: 1, 4)
  - [x] 4.1 After `plan_materializer.materialize()` succeeds in autonomous mode, call `step_dispatcher.dispatch_steps(task_id, created_step_ids)`
  - [x] 4.2 Verify supervised mode still skips dispatch (existing guard in orchestrator)
  - [x] 4.3 Fire the dispatch as an `asyncio.create_task()` so the orchestrator routing loop is not blocked

- [x] **Task 5: Add activity event types for step dispatch** (AC: 1, 5, 6, 9)
  - [x] 5.1 Add `STEP_DISPATCHED`, `STEP_STARTED`, `STEP_COMPLETED`, and `TASK_DISPATCH_STARTED` to `ActivityEventType` in `types.py` (and to `activities` schema in `schema.ts`)
  - [x] 5.2 Create activity events at key dispatch milestones (dispatch start, step start, step complete, task complete)

- [x] **Task 6: Write tests for step_dispatcher** (AC: 1-9)
  - [x] 6.1 Test: simple plan with 1 step -- dispatches, completes, task transitions to done
  - [x] 6.2 Test: parallel group with 2 steps -- both dispatched concurrently via gather
  - [x] 6.3 Test: sequential groups -- group 1 dispatched first, group 2 after group 1 completes
  - [x] 6.4 Test: step crash does not cancel siblings (return_exceptions=True)
  - [x] 6.5 Test: blocked step unblocks after dependency completes and gets dispatched
  - [x] 6.6 Test: all steps completed triggers task done transition
  - [x] 6.7 Test: supervised mode task does not trigger dispatch

## Dev Notes

### High-Level Architecture

This story creates the **step dispatcher** -- the component that takes materialized step records (created by Story 1.6) and actually executes them by running agent subprocesses. The dispatcher:

1. Reads "assigned" steps from Convex (via bridge)
2. Groups them by `parallelGroup`
3. Dispatches each group via `asyncio.gather()` (true parallel execution)
4. On step completion, calls `checkAndUnblockDependents` to unblock downstream steps
5. Continues dispatching newly unblocked steps until all are done
6. Transitions the parent task to "done" when all steps complete

### New File: `nanobot/mc/step_dispatcher.py`

This is a **NEW module**. The architecture specifies it at `nanobot/mc/step_dispatcher.py` with class `StepDispatcher`.

The dispatcher is distinct from the existing `TaskExecutor` in `executor.py`. The `TaskExecutor` handles the legacy per-task execution flow (one agent per task). The `StepDispatcher` handles the new step-level execution flow (multiple agents, multiple steps per task, with dependencies). Eventually the `TaskExecutor` will be deprecated in favor of the `StepDispatcher`, but for this story they coexist.

### Relationship to Existing Code

**Current flow (Stories 1.5 + 1.6, already implemented):**

```
orchestrator._process_planning_task()
  -> planner.plan_task()                   # Generate ExecutionPlan
  -> orchestrator._store_execution_plan()  # Write plan to task doc
  -> [autonomous check]
  -> plan_materializer.materialize()       # Create step records in Convex
     -> bridge.batch_create_steps()        # Steps created as "assigned"/"blocked"
     -> bridge.kick_off_task()             # Task -> "in_progress"
```

**What this story adds:**

```
orchestrator._process_planning_task()
  -> ... (existing flow above) ...
  -> plan_materializer.materialize()       # Returns created_step_ids
  -> step_dispatcher.dispatch_steps()      # NEW: Execute the steps
     -> bridge.get_steps_by_task()         # Fetch steps from Convex
     -> group by parallelGroup
     -> for each group:
        -> asyncio.gather(*[_execute_step(s) for s in group])
           -> bridge.update_step_status(step_id, "running")
           -> _run_agent_on_task(...)      # Reuse existing agent runner
           -> bridge.update_step_status(step_id, "completed")
           -> bridge.check_and_unblock_dependents(step_id)
     -> re-fetch steps, dispatch newly assigned ones
     -> when all done: bridge.update_task_status(task_id, "done")
```

### Key Design Decision: Reuse `_run_agent_on_task()` from `executor.py`

The existing `_run_agent_on_task()` function in `executor.py` (lines 91-165) is a standalone async function (not a method on `TaskExecutor`) that:
- Creates the agent workspace
- Loads the agent config (prompt, model, skills)
- Creates the LLM provider
- Runs `AgentLoop.process_direct()`
- Calls `end_task_session()` for memory consolidation

This function is **exactly what the step dispatcher needs** for running an agent on a step. Import it directly:

```python
from nanobot.mc.executor import _run_agent_on_task, _build_thread_context
```

The `_execute_step()` method in the dispatcher wraps this with step-level status transitions and thread context injection.

### Key Design Decision: Dispatch as Fire-and-Forget Task

The orchestrator should NOT await the full dispatch. The dispatch can take minutes (agents running). Instead, launch it as an `asyncio.create_task()`:

```python
# In orchestrator.py, after materialization:
asyncio.create_task(
    self._step_dispatcher.dispatch_steps(task_id, created_step_ids)
)
```

This keeps the orchestrator's routing loop responsive for new tasks.

### Exact Files to Modify/Create

| File | Action | What Changes |
|------|--------|-------------|
| `nanobot/mc/step_dispatcher.py` | **CREATE** | New `StepDispatcher` class with `dispatch_steps()`, `_dispatch_parallel_group()`, `_execute_step()` |
| `nanobot/mc/test_step_dispatcher.py` | **CREATE** | Unit tests using mocked bridge |
| `nanobot/mc/bridge.py` | **EXTEND** | Add `update_step_status()`, `get_steps_by_task()`, `check_and_unblock_dependents()` methods |
| `nanobot/mc/orchestrator.py` | **EXTEND** | Import `StepDispatcher`, instantiate in `__init__`, call `dispatch_steps()` after materialization |
| `nanobot/mc/types.py` | **EXTEND** | Add `StepStatus` enum with step lifecycle values; optionally add new `ActivityEventType` members |
| `dashboard/convex/schema.ts` | **EXTEND** | Add new activity event types if needed (e.g., `step_dispatched`) |
| `dashboard/convex/activities.ts` | **EXTEND** | Add new event type literals to the validator if needed |
| `nanobot/mc/test_orchestrator.py` | **EXTEND** | Add test verifying dispatch is called after materialization |

### Bridge Methods to Add

Add these to `nanobot/mc/bridge.py` (class `ConvexBridge`):

```python
def update_step_status(
    self,
    step_id: str,
    status: str,
    error_message: str | None = None,
) -> Any:
    """Update a step's status via the steps:updateStatus mutation."""
    args: dict[str, Any] = {
        "step_id": step_id,
        "status": status,
    }
    if error_message is not None:
        args["error_message"] = error_message
    result = self._mutation_with_retry("steps:updateStatus", args)
    self._log_state_transition(
        "step", f"Step {step_id} status changed to {status}"
    )
    return result

def get_steps_by_task(self, task_id: str) -> list[dict[str, Any]]:
    """Fetch all steps for a task, ordered by `order`."""
    result = self.query("steps:getByTask", {"task_id": task_id})
    return result if isinstance(result, list) else []

def check_and_unblock_dependents(self, step_id: str) -> list[str]:
    """Check if completing this step unblocks any dependents.

    Returns list of newly unblocked step IDs.
    """
    result = self._mutation_with_retry(
        "steps:checkAndUnblockDependents",
        {"step_id": step_id},
    )
    return result if isinstance(result, list) else []
```

### StepDispatcher Module Template

```python
"""
Step Dispatcher -- executes materialized step records.

After plan materialization (Story 1.6) creates step records in Convex,
the StepDispatcher picks up "assigned" steps and runs them as agent
subprocesses. Parallel groups are dispatched concurrently via
asyncio.gather(). Step completion triggers dependency unblocking and
dispatch of newly assigned steps.

Architecture ref: nanobot/mc/step_dispatcher.py
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nanobot.mc.executor import _run_agent_on_task, _build_thread_context
from nanobot.mc.types import (
    ActivityEventType,
    AuthorType,
    GENERAL_AGENT_NAME,
    LEAD_AGENT_NAME,
    MessageType,
    TaskStatus,
    is_lead_agent,
)

if TYPE_CHECKING:
    from nanobot.mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


class StepDispatcher:
    """Dispatches materialized steps for execution."""

    def __init__(self, bridge: ConvexBridge) -> None:
        self._bridge = bridge

    async def dispatch_steps(
        self, task_id: str, step_ids: list[str]
    ) -> None:
        """Dispatch all assigned steps for a task.

        Groups steps by parallelGroup and dispatches each group
        in sequence. Within each group, steps run in parallel.
        After each group, checks for newly unblocked steps and
        dispatches them. When all steps are done, transitions the
        task to "done".
        """
        logger.info(
            "[dispatcher] Starting step dispatch for task %s (%d steps)",
            task_id,
            len(step_ids),
        )

        try:
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.TASK_STARTED,
                f"Steps dispatched in autonomous mode",
                task_id,
            )

            while True:
                # Fetch current step states
                steps = await asyncio.to_thread(
                    self._bridge.get_steps_by_task, task_id
                )

                assigned_steps = [
                    s for s in steps if s.get("status") == "assigned"
                ]

                if not assigned_steps:
                    break  # No more runnable steps

                # Group by parallelGroup
                groups: dict[int, list[dict]] = {}
                for step in assigned_steps:
                    pg = step.get("parallel_group", 1)
                    groups.setdefault(pg, []).append(step)

                # Dispatch groups in order of parallelGroup number
                for pg_num in sorted(groups.keys()):
                    group_steps = groups[pg_num]
                    logger.info(
                        "[dispatcher] Dispatching parallel group %d "
                        "(%d steps) for task %s",
                        pg_num,
                        len(group_steps),
                        task_id,
                    )
                    await self._dispatch_parallel_group(task_id, group_steps)

            # Check if all steps completed
            final_steps = await asyncio.to_thread(
                self._bridge.get_steps_by_task, task_id
            )
            all_completed = all(
                s.get("status") == "completed" for s in final_steps
            )
            any_crashed = any(
                s.get("status") == "crashed" for s in final_steps
            )

            if all_completed:
                step_count = len(final_steps)
                await asyncio.to_thread(
                    self._bridge.update_task_status,
                    task_id,
                    TaskStatus.DONE,
                    None,
                    f"All {step_count} steps completed",
                )
                await asyncio.to_thread(
                    self._bridge.create_activity,
                    ActivityEventType.TASK_COMPLETED,
                    f"Task completed -- all {step_count} steps finished",
                    task_id,
                )
                logger.info(
                    "[dispatcher] Task %s completed (%d steps)",
                    task_id,
                    step_count,
                )
            elif any_crashed:
                logger.warning(
                    "[dispatcher] Task %s has crashed steps; "
                    "not transitioning to done",
                    task_id,
                )

        except Exception:
            logger.error(
                "[dispatcher] Dispatch failed for task %s",
                task_id,
                exc_info=True,
            )

    async def _dispatch_parallel_group(
        self, task_id: str, steps: list[dict[str, Any]]
    ) -> None:
        """Run all steps in a parallel group concurrently."""
        tasks = [
            self._execute_step(task_id, step) for step in steps
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for step, result in zip(steps, results):
            if isinstance(result, Exception):
                logger.error(
                    "[dispatcher] Step '%s' crashed: %s",
                    step.get("title", step.get("id", "?")),
                    result,
                )

    async def _execute_step(
        self, task_id: str, step: dict[str, Any]
    ) -> None:
        """Execute a single step: transition to running, run agent, handle result."""
        step_id = step.get("id")
        step_title = step.get("title", "Untitled Step")
        agent_name = step.get("assigned_agent") or GENERAL_AGENT_NAME
        description = step.get("description", "")

        if is_lead_agent(agent_name):
            agent_name = GENERAL_AGENT_NAME
            logger.warning(
                "[dispatcher] Step '%s' assigned to lead-agent; "
                "using '%s' (pure orchestrator invariant)",
                step_title,
                agent_name,
            )

        # Transition: assigned -> running
        await asyncio.to_thread(
            self._bridge.update_step_status, step_id, "running"
        )
        await asyncio.to_thread(
            self._bridge.create_activity,
            ActivityEventType.TASK_STARTED,
            f"Agent {agent_name} started step: \"{step_title}\"",
            task_id,
            agent_name,
        )

        try:
            # Load agent config
            from nanobot.mc.executor import TaskExecutor

            executor = TaskExecutor.__new__(TaskExecutor)
            executor._bridge = self._bridge
            agent_prompt, agent_model, agent_skills = executor._load_agent_config(agent_name)
            agent_prompt = executor._maybe_inject_orientation(agent_name, agent_prompt)

            # Build thread context
            thread_messages = await asyncio.to_thread(
                self._bridge.get_task_messages, task_id
            )
            thread_context = _build_thread_context(thread_messages)

            # Build the step's execution message
            task_data = await asyncio.to_thread(
                self._bridge.query,
                "tasks:getById",
                {"task_id": task_id},
            )
            task_title = (task_data or {}).get("title", "Untitled Task")

            # Build task workspace paths
            safe_id = re.sub(r"[^\w\-]", "_", task_id)
            files_dir = str(Path.home() / ".nanobot" / "tasks" / safe_id)
            output_dir = str(Path.home() / ".nanobot" / "tasks" / safe_id / "output")

            step_description = (
                f"You are executing Step: \"{step_title}\"\n"
                f"Step description: {description}\n\n"
                f"This is part of the larger task: \"{task_title}\"\n"
                f"Task workspace: {files_dir}\n"
                f"Save ALL output files to: {output_dir}\n"
            )
            if thread_context:
                step_description += f"\n{thread_context}"

            result = await _run_agent_on_task(
                agent_name=agent_name,
                agent_prompt=agent_prompt,
                agent_model=agent_model,
                task_title=step_title,
                task_description=step_description,
                agent_skills=agent_skills,
                task_id=task_id,
            )

            # Post agent output to unified thread
            await asyncio.to_thread(
                self._bridge.send_message,
                task_id,
                agent_name,
                AuthorType.AGENT,
                result,
                MessageType.WORK,
            )

            # Transition: running -> completed
            await asyncio.to_thread(
                self._bridge.update_step_status, step_id, "completed"
            )
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.TASK_COMPLETED,
                f"Agent {agent_name} completed step: \"{step_title}\"",
                task_id,
                agent_name,
            )

            # Unblock dependents
            unblocked_ids = await asyncio.to_thread(
                self._bridge.check_and_unblock_dependents, step_id
            )
            if unblocked_ids:
                logger.info(
                    "[dispatcher] Step '%s' completion unblocked %d step(s)",
                    step_title,
                    len(unblocked_ids),
                )

        except Exception as exc:
            logger.error(
                "[dispatcher] Agent '%s' crashed on step '%s': %s",
                agent_name,
                step_title,
                exc,
                exc_info=True,
            )
            error_msg = f"{type(exc).__name__}: {exc}"

            # Transition: running -> crashed
            await asyncio.to_thread(
                self._bridge.update_step_status,
                step_id,
                "crashed",
                error_msg,
            )

            # Post error to unified thread
            await asyncio.to_thread(
                self._bridge.send_message,
                task_id,
                "System",
                AuthorType.SYSTEM,
                (
                    f"Step \"{step_title}\" crashed:\n"
                    f"```\n{error_msg}\n```\n"
                    f"Agent: {agent_name}"
                ),
                MessageType.SYSTEM_EVENT,
            )

            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.TASK_CRASHED,
                f"Agent {agent_name} crashed on step: \"{step_title}\"",
                task_id,
                agent_name,
            )
```

### Orchestrator Integration

In `nanobot/mc/orchestrator.py`, after the existing materialization block (lines 205-234), the dispatcher should be called. The current code already has the autonomous/supervised branching. Modify the autonomous path:

```python
# CURRENT CODE (lines 205-216):
try:
    created_step_ids = await asyncio.to_thread(
        self._plan_materializer.materialize,
        task_id,
        plan,
    )
    logger.info(
        "[orchestrator] Task '%s': materialized %d step records",
        title,
        len(created_step_ids),
    )
except Exception as exc:
    # ... error handling ...

# ADD AFTER the materialization success:
# Fire-and-forget: dispatch steps without blocking the routing loop
asyncio.create_task(
    self._step_dispatcher.dispatch_steps(task_id, created_step_ids)
)
logger.info(
    "[orchestrator] Task '%s': step dispatch started (autonomous mode)",
    title,
)
```

The `StepDispatcher` should be instantiated in `TaskOrchestrator.__init__()`:

```python
def __init__(self, bridge: ConvexBridge) -> None:
    self._bridge = bridge
    self._lead_agent_name = LEAD_AGENT_NAME
    self._plan_materializer = PlanMaterializer(bridge)
    self._step_dispatcher = StepDispatcher(bridge)  # NEW
    self._known_planning_ids: set[str] = set()
    self._known_review_task_ids: set[str] = set()
```

### Critical: Agent Config Loading Pattern

The `_execute_step()` method needs to load the agent's config (prompt, model, skills) and apply orientation injection. The existing `TaskExecutor` has methods `_load_agent_config()` and `_maybe_inject_orientation()` that do this. Rather than instantiating a dummy `TaskExecutor`, extract these as module-level functions or import them properly:

**Preferred approach:** Refactor `_load_agent_config()` and `_maybe_inject_orientation()` out of the `TaskExecutor` class into module-level functions in `executor.py`. They don't use `self` (they reference `self._bridge` but that can be removed since `_load_agent_config` only reads from disk, and `_maybe_inject_orientation` only reads from disk).

Looking at the code:
- `_load_agent_config(self, agent_name)` -- reads YAML from `AGENTS_DIR / agent_name / config.yaml`. Does NOT use `self._bridge`. Can be extracted as a module-level function.
- `_maybe_inject_orientation(self, agent_name, agent_prompt)` -- reads from `~/.nanobot/mc/agent-orientation.md`. Does NOT use `self._bridge`. Can be extracted.

**Action:** Either:
1. Extract them as module-level functions in `executor.py` and import into `step_dispatcher.py`
2. Or duplicate them in `step_dispatcher.py` (less DRY but simpler for Story scope)

Option 1 is cleaner. The extraction is safe because these methods have no `self` dependency beyond being on the class.

### Board Workspace Handling

The existing `TaskExecutor._resolve_board_workspace()` handles board-scoped agent workspaces. The `StepDispatcher` should do the same. The step dispatcher can resolve the board from the task data (which has `board_id`).

For MVP, board workspace resolution can be handled the same way as in `_execute_task()` in `executor.py` (lines 697-721). The step dispatcher should fetch the board and resolve the workspace, then pass `memory_workspace` and `board_name` to `_run_agent_on_task()`.

### Task Status Transition: In_Progress -> Done

After all steps complete, the task should transition from "in_progress" to "done". Looking at the task state machine in `dashboard/convex/tasks.ts` (line 8), `in_progress -> done` is a valid transition. The `markPlanStepsCompleted()` function in `tasks.ts` is also called when task goes to "done" -- it marks all plan steps as completed in the `executionPlan` field.

### Interaction with Existing TaskExecutor

The `StepDispatcher` replaces the need for the `TaskExecutor` for tasks that go through the planning/materialization flow. However, the `TaskExecutor` is still needed for legacy tasks that are assigned directly (not through planning). The two coexist:

- Tasks that go through `planning` -> `in_progress` (via materializer): Dispatched by `StepDispatcher`
- Tasks that are directly `assigned` -> `in_progress`: Still handled by `TaskExecutor`

The `TaskExecutor`'s `start_execution_loop()` subscribes to `tasks:listByStatus` with status `"assigned"`. The task status after materialization is `"in_progress"` (set by `kickOff`), so the `TaskExecutor` will NOT pick up materialized tasks. The `StepDispatcher` handles them.

### Step ID Format

Steps returned from `bridge.get_steps_by_task()` will have their Convex `_id` field converted to `id` by the bridge's camelCase-to-snake_case conversion. The step dict will look like:

```python
{
    "id": "jd7abc123xyz",         # Convex _id
    "task_id": "jd7def456uvw",    # Reference to parent task
    "title": "Extract invoice data",
    "description": "...",
    "assigned_agent": "financial-agent",
    "status": "assigned",         # or "blocked", "running", etc.
    "blocked_by": [...],          # Array of step IDs
    "parallel_group": 1,
    "order": 1,
    "created_at": "2026-02-25T10:30:00Z",
}
```

### Activity Event Types

The step lifecycle already has events in the schema:
- `step_created` (Story 1.1)
- `step_status_changed` (Story 1.1)
- `step_unblocked` (Story 1.1)

For this story, reuse existing task-level event types for dispatch milestones:
- `task_started` -- "Steps dispatched in autonomous mode"
- `task_completed` -- "Task completed -- all N steps finished"

For step-level execution events, use `step_status_changed` (already in schema) or the existing `task_started`/`task_completed` with step context in the description. The `logStepStatusChange()` in `steps.ts` already fires `step_status_changed` on every `updateStatus` call, so no additional event types are strictly needed for step start/complete.

However, if more granular step dispatch events are desired, add to `schema.ts` activities `eventType` union:

```typescript
v.literal("step_dispatched"),
```

And add to `types.py` `ActivityEventType`:

```python
STEP_DISPATCHED = "step_dispatched"
```

### Error Handling Strategy

| Error Scenario | Handling | Result |
|---|---|---|
| Agent crash during step execution | `_execute_step` catches exception, transitions step to "crashed", posts error to thread | Step crashed, siblings continue, dependents remain blocked |
| All steps in a group crash | `_dispatch_parallel_group` completes (gather with return_exceptions=True), no more assigned steps | Dispatch loop exits, task stays "in_progress" with crashed steps |
| Bridge error during status update | Bridge retry logic (3x exponential backoff) | Best-effort; if exhausted, logged but dispatch continues |
| Provider error (OAuth, rate limit) | Caught as regular exception in `_execute_step`, step crashes | Same as agent crash -- step marked crashed |
| Dispatch itself crashes | Top-level try/except in `dispatch_steps` | Logged; task stays "in_progress" with whatever steps completed |

### Testing Strategy

**Unit Tests (Python):** `nanobot/mc/test_step_dispatcher.py`

Use `unittest.mock.MagicMock` for the bridge and `unittest.mock.AsyncMock` for async functions. Patch `_run_agent_on_task` to avoid importing the agent runtime.

```python
# Test structure:
class TestStepDispatcher:
    @pytest.mark.asyncio
    async def test_dispatch_single_step_completes_task(self):
        """Single assigned step -> running -> completed -> task done."""

    @pytest.mark.asyncio
    async def test_dispatch_parallel_group(self):
        """Two assigned steps in same group dispatched via gather."""

    @pytest.mark.asyncio
    async def test_dispatch_sequential_groups(self):
        """Group 1 runs first, group 2 runs after group 1 completes."""

    @pytest.mark.asyncio
    async def test_step_crash_does_not_cancel_siblings(self):
        """One step crashes, other step in same group completes."""

    @pytest.mark.asyncio
    async def test_dependency_unblocking_triggers_dispatch(self):
        """Step completes -> dependent unblocks -> dependent dispatched."""

    @pytest.mark.asyncio
    async def test_all_steps_complete_transitions_task_to_done(self):
        """When all steps are completed, task transitions to done."""

    @pytest.mark.asyncio
    async def test_supervised_mode_not_dispatched(self):
        """Verify supervised mode guard in orchestrator (integration test)."""
```

Key mock pattern:

```python
def _make_bridge():
    bridge = MagicMock()
    bridge.get_steps_by_task.return_value = [...]  # Step dicts
    bridge.update_step_status.return_value = None
    bridge.check_and_unblock_dependents.return_value = []
    bridge.update_task_status.return_value = None
    bridge.create_activity.return_value = None
    bridge.send_message.return_value = None
    bridge.get_task_messages.return_value = []
    bridge.query.return_value = {"title": "Test Task"}
    return bridge
```

Patch `_run_agent_on_task` to return immediately:

```python
@patch("nanobot.mc.step_dispatcher._run_agent_on_task", new_callable=AsyncMock)
@patch("nanobot.mc.step_dispatcher.asyncio.to_thread", new=_sync_to_thread)
```

### asyncio.to_thread Pattern

All bridge calls in the dispatcher must use `await asyncio.to_thread(...)` because the bridge's Convex client is synchronous (blocking I/O). This is the established pattern throughout the codebase (see `orchestrator.py`, `executor.py`).

### Thread Context Injection for Steps

Each step's agent should receive the unified thread context so it can see what previous agents did. The existing `_build_thread_context()` function in `executor.py` handles this (truncation to 20 messages, latest user message separation). For Story 2.1, use it as-is. Story 2.6 will enhance it with predecessor-aware injection.

### Provider Error Handling

The existing `TaskExecutor` has specialized handling for provider errors (OAuth, rate limits) via `_PROVIDER_ERRORS` and `_handle_provider_error()`. For Story 2.1 MVP, provider errors in step execution are caught as regular exceptions and the step transitions to "crashed". Story 3.x will add step-level retry and more granular provider error handling.

### Convex Schema Changes

The `activities` table's `eventType` union in `schema.ts` may need new literals if we add `step_dispatched`. Check the current schema and add if not present. The existing `step_status_changed` event from Story 1.1 is already in the schema and covers most step lifecycle events.

### Project Structure Notes

- **New files:** `nanobot/mc/step_dispatcher.py`, `nanobot/mc/test_step_dispatcher.py`
- **Modified files:** `nanobot/mc/orchestrator.py`, `nanobot/mc/bridge.py`, `nanobot/mc/types.py`
- **Potentially modified:** `dashboard/convex/schema.ts`, `dashboard/convex/activities.ts` (if adding new activity event types)
- **Test runner:** `uv run pytest nanobot/mc/test_step_dispatcher.py`
- **Dashboard tests:** `npm test` from `dashboard/` directory

### References

- [Source: _bmad-output/planning-artifacts/architecture.md -- Subprocess Model for Parallel Steps] -- `dispatch_parallel_group` pattern with `asyncio.gather()` and `return_exceptions=True`
- [Source: _bmad-output/planning-artifacts/architecture.md -- File Structure] -- `step_dispatcher.py` location, `StepDispatcher` class naming
- [Source: _bmad-output/planning-artifacts/architecture.md -- Data Flow] -- Complete flow from task creation through step dispatch to completion
- [Source: _bmad-output/planning-artifacts/architecture.md -- Requirements to Structure Mapping] -- `step_dispatcher.py` maps to FR19-FR23 (Agent Orchestration & Dispatch)
- [Source: _bmad-output/planning-artifacts/prd.md -- FR20] -- Autonomous mode dispatches immediately after plan generation
- [Source: _bmad-output/planning-artifacts/prd.md -- FR21] -- Parallel steps launch simultaneously as separate processes
- [Source: _bmad-output/planning-artifacts/prd.md -- FR22] -- Sequential steps execute in dependency order
- [Source: _bmad-output/planning-artifacts/prd.md -- FR23] -- Step completion automatically unblocks dependent steps
- [Source: _bmad-output/planning-artifacts/epics.md -- Story 2.1] -- Full BDD acceptance criteria
- [Source: _bmad-output/planning-artifacts/epics.md -- Story 2.2] -- Parallel dispatch and subprocess model (overlaps with this story)
- [Source: _bmad-output/planning-artifacts/epics.md -- Story 2.3] -- Auto-unblock dependent steps (partially implemented here via `checkAndUnblockDependents`)
- [Source: nanobot/mc/orchestrator.py:196-234] -- Autonomous/supervised branching and materialization call site
- [Source: nanobot/mc/executor.py:91-165] -- `_run_agent_on_task()` function to reuse for step execution
- [Source: nanobot/mc/executor.py:168-223] -- `_build_thread_context()` for thread context injection
- [Source: nanobot/mc/executor.py:436-462] -- `_load_agent_config()` to extract or reuse
- [Source: nanobot/mc/executor.py:557-584] -- `_maybe_inject_orientation()` to extract or reuse
- [Source: nanobot/mc/plan_materializer.py] -- `PlanMaterializer` that creates the step records this story dispatches
- [Source: nanobot/mc/bridge.py:318-365] -- Existing step/kick-off bridge methods
- [Source: nanobot/mc/types.py:38-49] -- `TaskStatus` enum values
- [Source: nanobot/mc/types.py:65-92] -- `ActivityEventType` enum values
- [Source: dashboard/convex/steps.ts:349-401] -- `updateStatus` mutation with lifecycle validation
- [Source: dashboard/convex/steps.ts:403-462] -- `checkAndUnblockDependents` mutation
- [Source: dashboard/convex/tasks.ts:7-17] -- Task state machine valid transitions
- [Source: dashboard/convex/schema.ts:67-89] -- Steps table schema
- [Source: _bmad-output/implementation-artifacts/1-1-extend-convex-schema-for-task-step-hierarchy.md] -- Step lifecycle states and dependency unblocking algorithm
- [Source: _bmad-output/implementation-artifacts/1-6-materialize-plans-into-step-records.md] -- Materialization flow that creates the steps this story dispatches

## Dev Agent Record

### Agent Model Used

GPT-5.3 Codex (dev implementation) + Claude Opus 4.6 (adversarial code review)

### Debug Log References

- `uv run pytest nanobot/mc/test_step_dispatcher.py` — 8/8 passed
- `uv run pytest nanobot/mc/test_bridge.py nanobot/mc/test_orchestrator.py` — 85/85 passed
- Full suite: `uv run pytest nanobot/mc/` — 288 passed, 12 pre-existing failures (test_gateway, test_process_manager)

### Completion Notes List

- Created `StepDispatcher` class with `dispatch_steps()`, `_dispatch_parallel_group()`, `_execute_step()` methods
- Added `StepStatus` enum to types.py matching Convex step lifecycle states
- Added bridge methods: `update_step_status()`, `get_steps_by_task()`, `check_and_unblock_dependents()`
- Integrated dispatcher into orchestrator: `asyncio.create_task()` fires dispatch after materialization in autonomous mode
- Added activity event types: `TASK_DISPATCH_STARTED`, `STEP_DISPATCHED`, `STEP_STARTED`, `STEP_COMPLETED`
- Helper functions extracted as module-level: `_load_agent_config`, `_maybe_inject_orientation`, `_resolve_board_workspace`, `_build_step_thread_context`
- Board workspace resolution included for agent memory isolation
- Thread context injection via `_build_step_thread_context` with 20-message truncation
- Crash handling: step transitions to "crashed", error posted to thread, sibling steps continue
- Dispatch failure notification: system message posted to thread if entire dispatch crashes

### File List

- nanobot/mc/step_dispatcher.py (created)
- nanobot/mc/test_step_dispatcher.py (created)
- nanobot/mc/bridge.py (extended: 3 new methods)
- nanobot/mc/orchestrator.py (extended: dispatcher integration)
- nanobot/mc/test_bridge.py (extended: bridge method tests)
- nanobot/mc/test_orchestrator.py (extended: dispatch integration tests)
- nanobot/mc/types.py (extended: StepStatus enum, activity event types)
- dashboard/convex/schema.ts (extended: new activity event literals)
- dashboard/convex/activities.ts (extended: new activity event literals)

## Change Log

- 2026-02-25: Dev implementation by GPT-5.3 Codex
- 2026-02-25: Adversarial code review by Claude Opus 4.6 — fixed 3 HIGH + 4 MEDIUM issues

## Senior Developer Review (AI)

### Review Date

2026-02-25

### Reviewer

Claude Opus 4.6 (adversarial code review)

### Outcome

Approve (after fixes)

### Findings Summary

- **HIGH fixed (3):** Story tasks not marked complete; story status still "ready-for-dev"; Dev Agent Record empty
- **MEDIUM fixed (4):** Same `STEP_DISPATCHED` event type for both start/completion (added `STEP_STARTED`/`STEP_COMPLETED`); `dispatch_steps` silently swallowed exceptions without user notification (added system message); duplicated helper functions from executor (noted as tech debt); missing supervised mode test (added)
- **LOW noted (1):** `_run_step_agent` wrapper adds unnecessary indirection (deferred)

### Verification Evidence

- All 93 Story 2.1 tests passed after fixes
- Activity event types properly differentiated (STEP_STARTED vs STEP_COMPLETED)
- Dispatch failure now posts system message to task thread
- Supervised mode test validates orchestrator guard
