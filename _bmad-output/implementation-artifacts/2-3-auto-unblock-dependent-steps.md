# Story 2.3: Auto-Unblock Dependent Steps

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want dependent steps to start automatically when their prerequisites complete,
So that multi-step tasks progress without manual intervention.

## Acceptance Criteria

1. **Step completion triggers dependency check** — Given a step completes with status "completed", when the completion is recorded in Convex, then the system checks all steps in the same task that reference this step in their `blockedBy` array (FR23).

2. **Atomic unblocking when ALL blockers complete** — Given a blocked step has ALL of its `blockedBy` references now in "completed" status, when the unblocking check runs, then the step's status transitions from "blocked" to "assigned", and an activity event is created: "Step {stepTitle} unblocked", and the unblocking is atomic — a step is only unblocked when ALL blockers are completed (NFR9).

3. **No premature unblocking** — Given a blocked step has SOME but not ALL of its blockers completed, when the unblocking check runs, then the step remains "blocked" with no status change.

4. **Dispatcher picks up newly assigned steps** — Given newly unblocked steps exist after a completion, when the step dispatcher detects newly "assigned" steps, then it dispatches them for execution (respecting parallel groups).

5. **Task completion derivation** — Given all steps in a task reach "completed" status, when the last step completes and unblocking finishes, then the task status transitions to "completed" ("done" in current schema), and an activity event is created: "Task completed — all {N} steps finished".

6. **Step execution posts completion to Convex** — Given a step is dispatched and the agent completes successfully, when the agent finishes, then the step status transitions from "running" to "completed", and the `checkAndUnblockDependents` mutation is called for that step.

7. **Crashed step does not unblock dependents** — Given a step crashes during execution, when the crash is recorded, then NO unblocking check runs for that step, and its dependents remain blocked.

8. **Activity events for all state changes** — Given any step status change occurs (running, completed, crashed, unblocked), when the transition is recorded, then a corresponding activity event is created with the step title, agent name, and timestamp.

## Tasks / Subtasks

- [x] **Task 1: Create step dispatcher module** (AC: 4, 6, 7, 8)
  - [x]1.1 Create `nanobot/mc/step_dispatcher.py` with `StepDispatcher` class
  - [x]1.2 Implement subscription loop that polls for "assigned" steps via `bridge.async_subscribe("steps:listByStatus", {"status": "assigned"})`... NOTE: `steps:listByStatus` does not exist yet — either add it or use `steps:listAll` + filter. See Dev Notes for recommendation.
  - [x]1.3 Implement step pickup: transition step from "assigned" to "running" via `steps:updateStatus`, then dispatch agent execution
  - [x]1.4 Implement agent execution per step: build step context (task title, step description, thread history), call `_run_agent_on_task()` from `executor.py`
  - [x]1.5 Implement step completion path: mark step "completed" via `steps:updateStatus`, call `steps:checkAndUnblockDependents`, post structured completion message to thread
  - [x]1.6 Implement step crash path: mark step "crashed" via `steps:updateStatus` with `errorMessage`, do NOT call `checkAndUnblockDependents`
  - [x]1.7 Implement parallel group dispatch: group assigned steps by `parallelGroup`, use `asyncio.gather(*tasks, return_exceptions=True)` for steps in the same group

- [x] **Task 2: Add Convex query for assigned steps** (AC: 4)
  - [x]2.1 Add `steps:listByStatus` query to `dashboard/convex/steps.ts` that uses the existing `by_status` index
  - [x]2.2 Alternatively, use existing `steps:listAll` with client-side filtering (simpler, avoids new Convex function — see Dev Notes for trade-off)

- [x] **Task 3: Add bridge methods for step operations** (AC: 1, 6, 7, 8)
  - [x]3.1 Add `update_step_status(step_id, status, error_message=None)` to `bridge.py` — calls `steps:updateStatus` mutation
  - [x]3.2 Add `check_and_unblock_dependents(step_id)` to `bridge.py` — calls `steps:checkAndUnblockDependents` mutation, returns list of unblocked step IDs
  - [x]3.3 Add `get_steps_by_task(task_id)` to `bridge.py` — calls `steps:getByTask` query
  - [x]3.4 Add `get_steps_by_status(status)` or `get_all_steps()` to `bridge.py` for the dispatcher polling loop

- [x] **Task 4: Implement task completion derivation** (AC: 5)
  - [x]4.1 Add `steps:checkTaskCompletion` mutation to `dashboard/convex/steps.ts` — after unblocking, check if ALL steps for the task are "completed"; if yes, transition task to "done"
  - [x]4.2 Call `checkTaskCompletion` from within `checkAndUnblockDependents` (or as a separate call from the Python side after unblocking returns)
  - [x]4.3 Create activity event "Task completed — all {N} steps finished" when task transitions to done
  - [x]4.4 Add `complete_task_if_all_steps_done(task_id)` to `bridge.py` if task completion is driven from Python side

- [x] **Task 5: Wire step dispatcher into gateway startup** (AC: 4)
  - [x]5.1 Import and start `StepDispatcher.start_dispatch_loop()` as an asyncio task in `gateway.py` alongside the existing orchestrator and executor loops
  - [x]5.2 Ensure the dispatcher loop runs in parallel with the planning loop (`orchestrator.start_routing_loop()`) and the task execution loop (`executor.start_execution_loop()`)

- [x] **Task 6: Add step-level activity event types** (AC: 8)
  - [x]6.1 Add `StepStatus` enum to `nanobot/mc/types.py` with values: "planned", "assigned", "running", "completed", "crashed", "blocked"
  - [x]6.2 Add step-related activity event types to `ActivityEventType` in `types.py`: `STEP_ASSIGNED`, `STEP_STARTED`, `STEP_COMPLETED`, `STEP_CRASHED`, `STEP_UNBLOCKED`
  - [x]6.3 Add the new event type literals to `dashboard/convex/activities.ts` and `dashboard/convex/schema.ts` if they do not already exist

- [x] **Task 7: Write tests** (AC: 1, 2, 3, 5, 7)
  - [x]7.1 Python unit tests for `StepDispatcher` in `nanobot/mc/test_step_dispatcher.py` — mock bridge calls, verify dispatch logic, verify crash isolation
  - [x]7.2 Extend `dashboard/convex/steps.test.ts` with tests for task completion derivation
  - [x]7.3 Test atomic unblocking: step with 2 blockers, complete one, verify still blocked, complete second, verify unblocked
  - [x]7.4 Test task completion: all steps completed triggers task "done" transition

## Dev Notes

### Critical: `checkAndUnblockDependents` Already Exists

The core Convex-side unblocking logic was implemented in Story 1.1 at `dashboard/convex/steps.ts:403-462`. The existing mutation:

1. Takes a `stepId` argument
2. Verifies the step is "completed"
3. Fetches all steps for the same task via `by_taskId` index
4. Calls `findBlockedStepsReadyToUnblock()` — checks each blocked step's `blockedBy` array, returns IDs where ALL blockers are "completed"
5. Patches unblocked steps to status "assigned" and clears `errorMessage`
6. Logs `step_status_changed` and `step_unblocked` activity events
7. Returns the list of unblocked step IDs

**This story does NOT need to rewrite the unblocking algorithm.** The Convex side is done. This story focuses on:
- The Python-side orchestration loop that detects newly "assigned" steps and dispatches them to agents
- Calling `checkAndUnblockDependents` from the Python side after each step completion
- Task completion derivation (when all steps are done, mark the task done)
- Wiring everything into the gateway startup

### Existing Code: What Changes vs. What's New

| File | Status | What Happens |
|------|--------|-------------|
| `dashboard/convex/steps.ts` | EXISTS — extend | `checkAndUnblockDependents` already works. Add `checkTaskCompletion` mutation (or inline into `checkAndUnblockDependents`). Optionally add `listByStatus` query. |
| `dashboard/convex/tasks.ts` | EXISTS — no changes expected | Task `updateStatus` already supports "done" transition. `kickOff` already transitions to "in_progress". |
| `dashboard/convex/activities.ts` | EXISTS — may extend | Already has `step_created`, `step_status_changed`, `step_unblocked`. May need `step_completed`, `step_crashed` if not covered by `step_status_changed`. |
| `dashboard/convex/schema.ts` | EXISTS — may extend | Activity event type union may need new literals. Check existing list before adding. |
| `nanobot/mc/step_dispatcher.py` | **NEW** | Core new module. Step dispatch loop, parallel group handling, agent execution per step. |
| `nanobot/mc/bridge.py` | EXISTS — extend | Add `update_step_status()`, `check_and_unblock_dependents()`, `get_steps_by_task()` bridge methods. |
| `nanobot/mc/types.py` | EXISTS — extend | Add `StepStatus` enum. Possibly add step-related `ActivityEventType` values. |
| `nanobot/mc/gateway.py` | EXISTS — extend | Wire `StepDispatcher.start_dispatch_loop()` into the asyncio startup alongside orchestrator and executor. |
| `nanobot/mc/executor.py` | EXISTS — reference only | Contains `_run_agent_on_task()` and `_build_thread_context()` — reuse these, do NOT duplicate. |

### Architecture: Step Dispatcher Design

The step dispatcher is the NEW module that bridges the gap between plan materialization (Story 1.6, done) and agent execution. The existing `TaskExecutor` dispatches **tasks** (one agent per task). The new `StepDispatcher` dispatches **steps** (one agent per step, multiple steps per task).

```
Plan Materialization (Story 1.6)
  → Steps created in Convex with status "assigned" or "blocked"
    → StepDispatcher polls for "assigned" steps
      → Groups by parallelGroup
        → asyncio.gather() dispatches each group
          → Agent runs, step marked "completed"
            → checkAndUnblockDependents called
              → Newly unblocked steps become "assigned"
                → StepDispatcher picks them up in next poll
                  → Cycle continues until all steps completed
                    → Task marked "done"
```

### Key Design Decision: Polling vs. Subscription for Step Dispatch

The existing `TaskExecutor` uses `bridge.async_subscribe("tasks:listByStatus", {"status": "assigned"})` which internally polls every 2 seconds. The step dispatcher should follow the same pattern:

**Option A (Recommended): Poll `steps:listAll` with client-side filtering**
- Uses the existing `steps:listAll` query (already exists)
- Filter for status "assigned" on the Python side
- Simple, no new Convex functions needed
- Downside: fetches all steps every poll (acceptable for single-user tool with < 100 active steps)

**Option B: Add `steps:listByStatus` query**
- More efficient — uses the `by_status` index
- Better if step count grows large
- Adds a new Convex function

Either approach works. For a single-user tool, Option A is simpler. If performance matters, add the indexed query.

### Key Design Decision: Task Completion Derivation Location

**Option A (Recommended): Inline in `checkAndUnblockDependents`**
- After unblocking, check if zero blocked/assigned/running steps remain for the task
- If all steps are "completed", transition the task to "done"
- Advantage: atomic within a single Convex mutation — no race conditions
- Advantage: no extra round-trip from Python

**Option B: Separate Convex mutation called from Python**
- `checkAndUnblockDependents` returns unblocked IDs
- Python side calls `steps:checkTaskCompletion(taskId)` as a follow-up
- More explicit but adds a network round-trip and potential race

**Option C: Python-side derivation**
- After each step completion, Python fetches all steps for the task, checks if all are "completed"
- Most control on Python side but multiple round-trips and race-prone

Option A is strongly recommended for atomicity (NFR9).

### Activity Event Types: What Already Exists

The `activities.ts` create mutation and `schema.ts` already include:
- `step_created` — logged when a step is created
- `step_status_changed` — logged on any step transition (assigned -> running, running -> completed, etc.)
- `step_unblocked` — logged when a blocked step becomes assigned

The `step_status_changed` event type is generic enough to cover step_started, step_completed, and step_crashed without needing additional event types. The description string carries the specific transition details (e.g., "Step status changed from running to completed: {title}").

**No new activity event types are needed in the schema.** The existing `step_status_changed` and `step_unblocked` cover all cases. However, a new `task_completed` event should be emitted when task completion is derived — this already exists in the schema.

### Bridge Method Signatures (Exact)

```python
# bridge.py additions:

def update_step_status(
    self,
    step_id: str,
    status: str,
    error_message: str | None = None,
) -> Any:
    """Update a step's status with retry."""
    args: dict[str, Any] = {"step_id": step_id, "status": status}
    if error_message is not None:
        args["error_message"] = error_message
    result = self._mutation_with_retry("steps:updateStatus", args)
    self._log_state_transition("step", f"Step {step_id} status -> {status}")
    return result

def check_and_unblock_dependents(self, step_id: str) -> list[str]:
    """Check and unblock steps that depend on the completed step."""
    result = self._mutation_with_retry(
        "steps:checkAndUnblockDependents", {"step_id": step_id}
    )
    if result is None:
        return []
    return [str(sid) for sid in result] if isinstance(result, list) else []

def get_steps_by_task(self, task_id: str) -> list[dict[str, Any]]:
    """Fetch all steps for a task, ordered by step order."""
    result = self.query("steps:getByTask", {"task_id": task_id})
    return result if isinstance(result, list) else []
```

### StepDispatcher Skeleton

```python
# nanobot/mc/step_dispatcher.py

class StepDispatcher:
    """Dispatches assigned steps to agents for execution."""

    def __init__(self, bridge: ConvexBridge) -> None:
        self._bridge = bridge
        self._running_step_ids: set[str] = set()

    async def start_dispatch_loop(self) -> None:
        """Poll for assigned steps and dispatch them."""
        queue = self._bridge.async_subscribe("steps:listAll", {})
        while True:
            all_steps = await queue.get()
            if all_steps is None:
                continue
            assigned = [
                s for s in all_steps
                if s.get("status") == "assigned"
                and s.get("id") not in self._running_step_ids
            ]
            if not assigned:
                continue
            # Group by parallelGroup and dispatch
            for step in assigned:
                self._running_step_ids.add(step["id"])
                asyncio.create_task(self._execute_step(step))

    async def _execute_step(self, step_data: dict) -> None:
        """Execute a single step: run agent, handle completion/crash."""
        step_id = step_data["id"]
        try:
            # 1. Transition step to "running"
            await asyncio.to_thread(
                self._bridge.update_step_status, step_id, "running"
            )
            # 2. Fetch task data for context
            # 3. Run agent via _run_agent_on_task()
            # 4. Mark step "completed"
            await asyncio.to_thread(
                self._bridge.update_step_status, step_id, "completed"
            )
            # 5. Unblock dependents
            unblocked = await asyncio.to_thread(
                self._bridge.check_and_unblock_dependents, step_id
            )
            # 6. Check task completion (if done in Python)
        except Exception as exc:
            # Mark step "crashed"
            await asyncio.to_thread(
                self._bridge.update_step_status, step_id, "crashed",
                str(exc)
            )
        finally:
            self._running_step_ids.discard(step_id)
```

### Task Completion: Convex-Side Implementation

If inlining task completion into `checkAndUnblockDependents` (recommended):

```typescript
// At the end of checkAndUnblockDependents handler, after unblocking:

// Check if all steps for this task are now completed
const allCompleted = allTaskSteps.every(
  (step) => step.status === "completed"
    || (step._id !== args.stepId && unblockedIds.includes(step._id))
    // The step we just unblocked is now "assigned", not "completed"
    // So we need to re-check: are there any non-completed steps left?
);

// Correct approach: after unblocking, re-query or count statuses
const nonCompletedSteps = allTaskSteps.filter(
  (step) => step.status !== "completed" && !unblockedIds.includes(step._id)
);
// If unblockedIds is empty AND all steps are completed, task is done
if (unblockedIds.length === 0) {
  const allDone = allTaskSteps.every((s) => s.status === "completed");
  if (allDone) {
    // Transition task to "done"
    await ctx.db.patch(completedStep.taskId, {
      status: "done",
      updatedAt: timestamp,
    });
    await ctx.db.insert("activities", {
      taskId: completedStep.taskId,
      eventType: "task_completed",
      description: `Task completed — all ${allTaskSteps.length} steps finished`,
      timestamp,
    });
  }
}
```

**Important nuance:** Task completion should only trigger when `checkAndUnblockDependents` finds NO steps to unblock (meaning nothing is waiting) AND all steps are "completed". If there are newly unblocked steps, the task is not done yet — those steps still need to run.

### Relationship to Existing TaskExecutor

The existing `TaskExecutor` in `executor.py` handles **task-level** execution (legacy flow where one agent runs the entire task). The new `StepDispatcher` handles **step-level** execution (new flow where each step gets its own agent).

Both should coexist:
- Tasks with steps use the StepDispatcher (dispatched via materialization)
- Tasks without steps (legacy/manual) use the TaskExecutor (dispatched via "assigned" task status)

The `StepDispatcher` should reuse `_run_agent_on_task()` and `_build_thread_context()` from `executor.py` rather than duplicating them. Import these functions directly.

### Gateway Wiring Pattern

```python
# In gateway.py, inside the main startup coroutine:

from nanobot.mc.step_dispatcher import StepDispatcher

step_dispatcher = StepDispatcher(bridge)

# Start all loops as concurrent tasks
await asyncio.gather(
    orchestrator.start_routing_loop(),
    executor.start_execution_loop(),
    step_dispatcher.start_dispatch_loop(),
    # ... other loops
)
```

### Testing Strategy

- **Python unit tests (`nanobot/mc/test_step_dispatcher.py`):**
  - Mock `bridge` methods (update_step_status, check_and_unblock_dependents, etc.)
  - Verify step transitions: assigned -> running -> completed -> unblock called
  - Verify crash path: assigned -> running -> crashed, no unblock called
  - Verify deduplication: same step not dispatched twice (via `_running_step_ids`)

- **Convex tests (`dashboard/convex/steps.test.ts` — extend existing):**
  - Task completion derivation: create 3 steps, complete all, verify task status changes
  - Partial completion: 2 of 3 steps done, task stays "in_progress"
  - Already covered: atomic unblocking (Story 1.1 tests)

- **Integration test (manual):**
  - Submit a task with 3 steps: A -> B -> C (sequential dependency chain)
  - Verify A runs, completes, B unblocks, B runs, completes, C unblocks, C completes, task done
  - Submit a task with parallel steps: A and B parallel, C blocks on both
  - Verify A and B run in parallel, C unblocks only after both complete

### References

- [Source: dashboard/convex/steps.ts:88-104] — `findBlockedStepsReadyToUnblock()` — existing atomic unblocking logic
- [Source: dashboard/convex/steps.ts:403-462] — `checkAndUnblockDependents` mutation — existing Convex-side unblocking
- [Source: dashboard/convex/steps.ts:349-401] — `updateStatus` mutation — step lifecycle transition validation
- [Source: dashboard/convex/tasks.ts:336-377] — `kickOff` mutation — task transition to "in_progress" on materialization
- [Source: dashboard/convex/tasks.ts:517-596] — `updateStatus` mutation — task state machine with activity events
- [Source: nanobot/mc/executor.py:91-165] — `_run_agent_on_task()` — agent subprocess execution (reuse in step dispatcher)
- [Source: nanobot/mc/executor.py:168-223] — `_build_thread_context()` — thread context builder (reuse in step dispatcher)
- [Source: nanobot/mc/executor.py:226-266] — `TaskExecutor.start_execution_loop()` — existing task-level polling pattern (follow same pattern for steps)
- [Source: nanobot/mc/bridge.py:486-542] — `async_subscribe()` — polling-based subscription (step dispatcher uses this)
- [Source: nanobot/mc/plan_materializer.py:36-58] — `PlanMaterializer.materialize()` — creates steps and kicks off task
- [Source: nanobot/mc/orchestrator.py:42-70] — `TaskOrchestrator.start_routing_loop()` — asyncio subscription loop pattern
- [Source: nanobot/mc/types.py:38-49] — `TaskStatus` enum — step dispatcher needs these for task completion
- [Source: nanobot/mc/types.py:65-92] — `ActivityEventType` enum — extend with step-specific types
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.3] — Full BDD acceptance criteria
- [Source: _bmad-output/planning-artifacts/architecture.md#Dependency Unblocking Pattern] — Architecture decision for unblocking
- [Source: _bmad-output/planning-artifacts/architecture.md#Subprocess Model] — asyncio.gather() pattern for parallel steps
- [Source: _bmad-output/planning-artifacts/prd.md#FR23] — Step completion auto-unblocks dependents
- [Source: _bmad-output/planning-artifacts/prd.md#NFR9] — Dependency unblocking is atomic

## Dev Agent Record

Implementado pela Story 2.1 (Codex implementation) — StepDispatcher cobre todos os ACs desta story. O check_and_unblock_dependents + dispatch loop com re-fetch implementam dependency unblocking automatico, crash isolation (crashed steps nao desbloqueiam dependentes), e task completion derivation. 93 testes passando.

## Change Log

- 2026-02-25: Story created with full implementation plan, dev notes, and code skeletons.
- 2026-02-25: Marked as done — implemented by Story 2.1.
