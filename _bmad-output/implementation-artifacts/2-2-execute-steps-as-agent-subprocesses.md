# Story 2.2: Execute Steps as Agent Subprocesses

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want steps to execute as isolated agent subprocesses with parallel dispatch for independent steps,
So that agents run concurrently without contention and a failure in one doesn't crash others.

## Acceptance Criteria

1. **Parallel steps launch simultaneously** -- Given the step dispatcher receives a set of steps to execute, when multiple steps share the same `parallelGroup` and all have status "assigned", then the dispatcher launches all of them simultaneously using `asyncio.gather()` with `return_exceptions=True` (FR21).

2. **Each agent runs in its own workspace** -- Given an agent subprocess starts for a step, when the subprocess is created, then the agent runs in an isolated workspace under `~/.nanobot/agents/{agentName}/` with no shared state between concurrent agent subprocesses (NFR8).

3. **Sequential groups execute in order** -- Given steps are in different parallel groups with sequential dependencies, when the dispatcher processes them, then it dispatches parallel group 1 first, waits for all steps in that group to complete, then dispatches parallel group 2, and so on (FR22).

4. **Step transitions to "running" on start** -- Given an agent subprocess starts for a step, when the subprocess begins execution, then the step's status is updated to "running" in Convex via the bridge, and an activity event is created: "Agent {agentName} started step: {stepTitle}".

5. **Step transitions to "completed" on success** -- Given an agent subprocess completes successfully, when the completion is detected, then the step's status is updated to "completed" in Convex, and an activity event is created: "Agent {agentName} completed step: {stepTitle}".

6. **Step transitions to "crashed" on failure** -- Given an agent subprocess crashes (exception, timeout, provider error), when the failure is detected, then the step's status is updated to "crashed" with `errorMessage` populated, and other running subprocesses in the same parallel group continue unaffected (NFR8).

7. **Crash isolation via return_exceptions** -- Given an agent subprocess crashes during a parallel group dispatch, when `asyncio.gather()` returns, then the exception is captured as the result for that step (not raised), and sibling steps in the same group are not cancelled or affected.

8. **Step dispatcher triggered after materialization** -- Given the plan materializer has created step records for an autonomous task, when materialization completes, then the step dispatcher is automatically invoked to begin dispatching assigned steps.

9. **Blocked steps remain untouched** -- Given the dispatcher receives steps for a task, when some steps have status "blocked", then the dispatcher skips them entirely and only dispatches steps with status "assigned".

10. **Bridge methods for step status updates** -- Given the Python backend needs to update step statuses, when `bridge.update_step_status()` is called, then it calls the Convex `steps:updateStatus` mutation with the correct step ID and status, using the bridge's retry and snake/camel conversion logic.

## Tasks / Subtasks

- [x] **Task 1: Add step status bridge methods** (AC: 10)
  - [x] 1.1 Add `update_step_status(step_id, status, error_message=None)` method to `ConvexBridge` in `nanobot/mc/bridge.py` that calls `steps:updateStatus` mutation
  - [x] 1.2 Add `get_steps_by_task(task_id)` method to `ConvexBridge` that calls `steps:getByTask` query and returns a list of step dicts with snake_case keys
  - [x] 1.3 Add `check_and_unblock_dependents(step_id)` method to `ConvexBridge` that calls `steps:checkAndUnblockDependents` mutation

- [x] **Task 2: Add StepStatus enum and step activity types to types.py** (AC: 4, 5, 6)
  - [x] 2.1 Add `StepStatus` StrEnum to `nanobot/mc/types.py` with values: `PLANNED = "planned"`, `ASSIGNED = "assigned"`, `RUNNING = "running"`, `COMPLETED = "completed"`, `CRASHED = "crashed"`, `BLOCKED = "blocked"`
  - [x] 2.2 Add `STEP_STARTED`, `STEP_COMPLETED`, `STEP_CRASHED` values to `ActivityEventType` in `types.py` (these map to existing `step_status_changed` Convex event type)
  - [x] 2.3 Update the Convex `activities:create` validator to accept the new event type values (if needed; currently `step_status_changed` already exists)

- [x] **Task 3: Create StepDispatcher class** (AC: 1, 2, 3, 7, 8, 9)
  - [x] 3.1 Create `nanobot/mc/step_dispatcher.py` with `StepDispatcher` class that accepts a `ConvexBridge` instance
  - [x] 3.2 Implement `dispatch_task(task_id)` method that fetches all steps for a task, groups by `parallel_group`, and dispatches groups sequentially
  - [x] 3.3 Implement `_dispatch_parallel_group(steps)` method that uses `asyncio.gather(*tasks, return_exceptions=True)` to launch all steps in a group simultaneously
  - [x] 3.4 Implement `_execute_step(step)` method that: (a) updates step status to "running", (b) creates activity event, (c) calls the existing `_run_agent_on_task()` function from executor.py, (d) updates step status to "completed" or "crashed" based on result
  - [x] 3.5 Skip blocked steps -- only dispatch steps with status "assigned"
  - [x] 3.6 After each parallel group completes, call `check_and_unblock_dependents()` for each completed step, then check for newly assigned steps to include in the next dispatch cycle

- [x] **Task 4: Wire step dispatcher into execution flow** (AC: 8)
  - [x] 4.1 Create a `start_step_dispatch_loop()` method in `StepDispatcher` that subscribes to tasks in "running" status (or similar) and dispatches their steps
  - [x] 4.2 Integrate `StepDispatcher` into `run_gateway()` in `nanobot/mc/gateway.py` as a new asyncio task alongside the orchestrator and executor
  - [x] 4.3 Ensure the orchestrator's autonomous flow (after materialization) triggers the step dispatcher for the task

- [x] **Task 5: Implement step-level agent execution** (AC: 2, 4, 5, 6)
  - [x] 5.1 Refactor `_run_agent_on_task()` or create a wrapper `_run_agent_on_step()` in `step_dispatcher.py` that adapts the step's description, assigned agent, and workspace to the existing agent execution function
  - [x] 5.2 Inject thread context from the unified task thread (reuse `_build_thread_context()` from executor.py)
  - [x] 5.3 Handle board-scoped workspaces: resolve the board workspace for the step's assigned agent
  - [x] 5.4 Load agent config (prompt, model, skills) from YAML for the step's assigned agent
  - [x] 5.5 Apply global orientation injection for non-lead agents
  - [x] 5.6 Post the agent's output as a message to the unified task thread on completion

- [x] **Task 6: Handle provider errors at step level** (AC: 6, 7)
  - [x] 6.1 Catch provider-specific errors (`ProviderError`, `AnthropicOAuthExpired`) and transition step to "crashed" with actionable error message
  - [x] 6.2 Post a system message to the task thread with provider error details and recovery instructions
  - [x] 6.3 Create a `system_error` activity event for provider errors at step level

- [x] **Task 7: Write tests for StepDispatcher** (AC: 1, 3, 7, 9)
  - [x] 7.1 Create `nanobot/mc/test_step_dispatcher.py` with unit tests
  - [x] 7.2 Test parallel group dispatch: multiple steps in same group launch via gather
  - [x] 7.3 Test sequential group ordering: group 1 completes before group 2 starts
  - [x] 7.4 Test crash isolation: one step crashes, siblings in same group continue
  - [x] 7.5 Test blocked steps are skipped
  - [x] 7.6 Test step status transitions: assigned -> running -> completed/crashed

## Dev Agent Record

Implementado pela Story 2.1 (Codex implementation) — StepDispatcher cobre todos os ACs desta story. O StepDispatcher implementa parallel dispatch via asyncio.gather(return_exceptions=True), crash isolation, sequential group ordering, step status transitions, bridge methods, e 93 testes passando.

## Dev Notes

### How executor.py Currently Spawns Agents

The current `executor.py` is a **task-level** executor that subscribes to tasks with status "assigned" and runs agents on entire tasks. The key function is `_run_agent_on_task()` (line 91-165) which:

1. Creates a workspace at `~/.nanobot/agents/{agentName}/`
2. Builds the message from task title + description
3. Prefixes the agent's system prompt
4. Creates an `AgentLoop` with the LLM provider from user config
5. Calls `loop.process_direct()` to run the agent
6. Calls `loop.end_task_session()` to consolidate memory

This function is the core that the step dispatcher will reuse. The step dispatcher will NOT replace the task executor -- it will operate at a different level (step-level vs task-level).

```python
# Current flow (task-level, in executor.py):
# assigned task -> _pickup_task() -> _execute_task() -> _run_agent_on_task()

# New flow (step-level, in step_dispatcher.py):
# materialized steps -> dispatch_task() -> _dispatch_parallel_group() -> _execute_step() -> _run_agent_on_task()
```

### The asyncio.gather() Pattern with return_exceptions=True

The architecture specifies `asyncio.gather(*tasks, return_exceptions=True)` for parallel groups. This is critical because:

- **Without** `return_exceptions=True`: if one coroutine raises, `gather()` cancels all remaining coroutines. This would violate NFR8 (crash isolation).
- **With** `return_exceptions=True`: exceptions are returned as values in the results list. Each result is either the return value or an `Exception` instance.

Reference implementation from architecture:

```python
async def dispatch_parallel_group(steps: list[Step]):
    tasks = [run_agent_subprocess(step) for step in steps]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for step, result in zip(steps, results):
        if isinstance(result, Exception):
            await mark_step_crashed(step, result)
        else:
            await mark_step_completed(step)
            await unblock_dependents(step)
```

### Subprocess Isolation

Each agent gets its own workspace under `~/.nanobot/agents/{agentName}/`. Key isolation properties:
- No shared state between concurrent agent subprocesses
- Each agent has its own `AgentLoop` instance, `MessageBus`, and LLM provider
- Memory consolidation (`end_task_session()`) happens only after the agent completes its step
- Thread is the ONLY inter-agent communication channel during execution

Board-scoped workspaces are used when the task belongs to a board: `~/.nanobot/boards/{boardName}/agents/{agentName}/`

### Step Status Updates via Bridge

The bridge currently has NO step-specific methods. This story adds three new methods:

| New Method | Convex Mutation/Query | Purpose |
|---|---|---|
| `update_step_status(step_id, status, error_message)` | `steps:updateStatus` | Transition step status |
| `get_steps_by_task(task_id)` | `steps:getByTask` | Fetch all steps for a task |
| `check_and_unblock_dependents(step_id)` | `steps:checkAndUnblockDependents` | Trigger dependency unblocking |

The bridge handles snake_case -> camelCase conversion and retry logic. The Convex `steps:updateStatus` mutation already validates transitions (e.g. `assigned -> running` is valid, `completed -> running` is not).

### Activity Events for Step Status Changes

The Convex schema already has `step_status_changed` as a valid activity event type (added in Story 1.1). The `logStepStatusChange()` helper in `steps.ts` handles this internally when `steps:updateStatus` is called. However, the Python side should ALSO create activity events for step-level start/complete/crash to ensure visibility in the activity feed via the bridge.

Activity events to create:
- **Step started**: `"step_status_changed"` -- "Agent {agentName} started step: {stepTitle}"
- **Step completed**: `"step_status_changed"` -- "Agent {agentName} completed step: {stepTitle}"
- **Step crashed**: `"step_status_changed"` -- "Agent {agentName} crashed on step: {stepTitle}: {errorMessage}"

Note: The Convex `steps:updateStatus` mutation already calls `logStepStatusChange()` internally, which creates an activity event. The Python side should NOT double-log. The step dispatcher should rely on the Convex mutation's internal activity logging rather than making separate `create_activity` calls for status changes.

### How Parallel Groups Work

Steps with the same `parallelGroup` number are launched simultaneously. Different groups execute sequentially in ascending order.

Example with a 4-step plan:
```
Step A: parallelGroup=1, blockedBy=[]       -> assigned
Step B: parallelGroup=1, blockedBy=[]       -> assigned
Step C: parallelGroup=2, blockedBy=[A, B]   -> blocked
Step D: parallelGroup=3, blockedBy=[C]      -> blocked
```

Dispatch sequence:
1. Group 1: dispatch A and B simultaneously via `asyncio.gather()`
2. Wait for A and B to complete
3. `checkAndUnblockDependents(A)` and `checkAndUnblockDependents(B)` -> C unblocked -> status becomes "assigned"
4. Group 2: dispatch C
5. Wait for C to complete
6. `checkAndUnblockDependents(C)` -> D unblocked -> status becomes "assigned"
7. Group 3: dispatch D

The dispatcher should NOT hardcode group numbers. Instead, it should:
1. Fetch current step statuses from Convex
2. Collect all "assigned" steps
3. Group them by `parallelGroup`
4. Dispatch the lowest-numbered group
5. After completion, re-fetch statuses (unblocking may have created new "assigned" steps)
6. Repeat until no "assigned" steps remain

### Error Handling: Individual Crashes Don't Affect Siblings

This is guaranteed by `return_exceptions=True` in `asyncio.gather()`. When step B crashes while step A is still running in the same parallel group:
- Step B's exception is captured as a result value
- Step A continues running uninterrupted
- After gather returns, step B is marked "crashed" and step A is marked "completed"
- Steps that depend on step B remain "blocked"
- Steps that depend on step A (but not B) can be unblocked

### Lead Agent Invariant

The step dispatcher MUST enforce the pure orchestrator invariant: Lead Agent never executes. If a step is assigned to `lead-agent`, the dispatcher should re-route to `general-agent` (or raise an error). The existing `_run_agent_on_task()` already raises `LeadAgentExecutionError` if called with the lead agent name -- this guard is sufficient.

### Existing Code That Touches This Story

| File | What exists | What changes |
|---|---|---|
| `nanobot/mc/bridge.py` | ConvexBridge with task and agent methods | ADD `update_step_status()`, `get_steps_by_task()`, `check_and_unblock_dependents()` |
| `nanobot/mc/types.py` | TaskStatus, ActivityEventType, ExecutionPlan | ADD `StepStatus` StrEnum |
| `nanobot/mc/executor.py` | TaskExecutor, `_run_agent_on_task()`, `_build_thread_context()` | No direct changes -- step_dispatcher imports and reuses `_run_agent_on_task()` |
| `nanobot/mc/gateway.py` | `run_gateway()` wires orchestrator + executor | ADD StepDispatcher instantiation and its asyncio loop |
| `nanobot/mc/orchestrator.py` | TaskOrchestrator with plan materialization | Wire post-materialization dispatch trigger |
| `nanobot/mc/plan_materializer.py` | PlanMaterializer creating step records | No changes -- returns step IDs which trigger dispatch |
| `dashboard/convex/steps.ts` | `updateStatus`, `getByTask`, `checkAndUnblockDependents` | No changes -- already has the mutations this story calls |
| `dashboard/convex/activities.ts` | Activity event creation with `step_status_changed` | No changes -- already supports step events |
| `dashboard/convex/schema.ts` | Steps table, activities table | No changes -- schema already supports all needed fields |

### New File: `nanobot/mc/step_dispatcher.py`

This is the primary deliverable. Estimated ~200-300 lines. Structure:

```python
class StepDispatcher:
    def __init__(self, bridge: ConvexBridge) -> None: ...

    async def dispatch_task(self, task_id: str) -> None:
        """Dispatch all steps for a task, respecting parallel groups."""

    async def _dispatch_parallel_group(self, task_id: str, steps: list[dict]) -> None:
        """Launch all steps in a group via asyncio.gather(return_exceptions=True)."""

    async def _execute_step(self, step: dict, task_id: str) -> str:
        """Run a single step: update status, run agent, handle result."""

    async def start_dispatch_loop(self) -> None:
        """Subscribe to tasks needing dispatch and process them."""
```

### Dispatch Trigger Mechanism

The step dispatcher needs to know when to dispatch steps for a task. Two approaches:

**Option A (recommended): Direct invocation after materialization.**
The orchestrator calls `step_dispatcher.dispatch_task(task_id)` immediately after `plan_materializer.materialize()` returns for autonomous tasks. This is simpler and avoids polling.

**Option B: Subscription-based.**
The step dispatcher subscribes to tasks with status "running" and dispatches their assigned steps. This is more decoupled but adds latency.

For MVP, Option A is recommended. The orchestrator already knows the task_id and supervision mode, so it can trigger dispatch directly.

### Thread Context Injection for Steps

Each agent executing a step should receive the unified thread context so it can see what prior agents have done. The existing `_build_thread_context()` function in `executor.py` already handles this:
- Truncates to last 20 messages
- Separates latest user message into `[Latest Follow-up]` section
- Prepends `"(N earlier messages omitted)"` for long threads

The step dispatcher should call `bridge.get_task_messages(task_id)` before each step execution and inject the thread context into the step description.

### Testing Strategy

- **Unit tests** (`test_step_dispatcher.py`): Mock the bridge and `_run_agent_on_task()`, verify:
  - Parallel group dispatch uses `asyncio.gather()`
  - Sequential group ordering
  - Crash isolation (one step crashes, others complete)
  - Blocked steps are skipped
  - Step status transitions
- **Integration test (manual)**: Create a task with multiple steps, verify they dispatch correctly and Kanban cards move through statuses
- **Test runner**: `uv run pytest nanobot/mc/test_step_dispatcher.py`

### Git Intelligence (Recent Commits)

```
830fd64 fix card ui
e685c07 Fix Design broken
acc0318 wip: alinhamento do design da dashboard
823f0a7 feat: Implement cron job task linking and output file syncing
479bc23 feat: highlight prompt variables with amber color
```

Recent work has been UI alignment and cron job features. Step dispatcher is new infrastructure with no expected conflicts.

### Project Structure Notes

- **New file:** `nanobot/mc/step_dispatcher.py` -- core step dispatch logic
- **New file:** `nanobot/mc/test_step_dispatcher.py` -- unit tests
- **Modified files:** `bridge.py` (add step methods), `types.py` (add StepStatus), `gateway.py` (wire dispatcher), `orchestrator.py` (trigger dispatch after materialization)
- **No frontend changes** in this story -- Kanban updates are handled by Convex reactive queries watching step status changes
- **No Convex changes** -- all needed mutations/queries already exist from Story 1.1

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Subprocess Model for Parallel Steps] -- asyncio.gather() pattern, crash isolation
- [Source: _bmad-output/planning-artifacts/architecture.md#Process Architecture] -- Agent Gateway process model
- [Source: _bmad-output/planning-artifacts/architecture.md#Implementation Sequence] -- step_dispatcher.py as item 4
- [Source: _bmad-output/planning-artifacts/prd.md#FR21] -- Parallel steps launch simultaneously as separate processes
- [Source: _bmad-output/planning-artifacts/prd.md#FR22] -- Sequential steps execute in dependency order
- [Source: _bmad-output/planning-artifacts/prd.md#NFR8] -- Agent subprocesses run in isolation
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.2] -- Full BDD acceptance criteria
- [Source: nanobot/mc/executor.py:91-165] -- Existing `_run_agent_on_task()` function
- [Source: nanobot/mc/executor.py:168-223] -- Existing `_build_thread_context()` function
- [Source: nanobot/mc/bridge.py:318-365] -- Existing step bridge methods (create_step, batch_create_steps, kick_off_task)
- [Source: nanobot/mc/plan_materializer.py] -- PlanMaterializer that precedes dispatch
- [Source: nanobot/mc/gateway.py:612-746] -- run_gateway() where StepDispatcher will be wired
- [Source: dashboard/convex/steps.ts:349-401] -- updateStatus mutation with transition validation
- [Source: dashboard/convex/steps.ts:403-462] -- checkAndUnblockDependents mutation
