# Story 8.4: Fix Orchestrator & Bridge Reliability

Status: done

## Story

As a **user**,
I want the gateway's orchestrator and bridge to be resilient to race conditions and connection drops,
So that tasks reliably flow through inbox → assigned → in_progress without crashing or hanging.

## Problem Statement

Adversarial code review of Story 8.1 found critical reliability issues:

1. **Double activity events**: Both the Convex `tasks:updateStatus` mutation AND Python code write activity events, doubling every feed entry.
2. **Orchestrator crash on race**: The routing loop has no inbox task deduplication. Stale subscription data causes invalid state transitions that crash the loop permanently — root cause of "tasks not reaching assigned" bug.
3. **Silent subscription death**: If the Convex connection drops, `async_subscribe()` swallows the error and the consuming loops hang forever with no recovery.
4. **Empty agent_name**: Bridge sends `""` instead of omitting `agent_name` when None.
5. **Deprecated API**: `async_subscribe` uses `get_event_loop()` instead of `get_running_loop()`.

## Acceptance Criteria

1. **Given** the orchestrator routes a task from inbox → assigned, **Then** exactly ONE activity event is created (not two)
2. **Given** the orchestrator's inbox subscription fires with a task that was already routed, **Then** the orchestrator skips it without crashing
3. **Given** a Convex subscription thread dies (connection drop, error), **Then** `async_subscribe` automatically reconnects with exponential backoff and logs a warning
4. **Given** `update_task_status` is called with `agent_name=None`, **Then** the `agent_name` field is omitted from the mutation args (not sent as `""`)
5. **Given** the bridge creates an async subscription, **Then** it uses `asyncio.get_running_loop()` instead of `asyncio.get_event_loop()`
6. **Given** the executor picks up an assigned task, **Then** exactly ONE `task_started` activity event is created (not two)
7. **Given** an agent completes a task, **Then** exactly ONE `task_completed` activity event is created (not two)

## Tasks / Subtasks

- [x] Task 1: Remove duplicate activity event writes from orchestrator (AC: #1)
  - [x] 1.1: In `orchestrator.py:_process_inbox_task()`, remove the 3 explicit `bridge.create_activity(TASK_ASSIGNED, ...)` calls (lines ~230-236, ~267-273, ~307-313) — the Convex `tasks:updateStatus` mutation already writes activity events
  - [x] 1.2: In `orchestrator.py:_handle_review_transition()`, keep only the `create_activity` calls that have NO corresponding `update_task_status` (e.g. `HITL_REQUESTED`, `REVIEW_REQUESTED` which are standalone events without a status transition)
  - [x] 1.3: Verify the Convex `tasks:updateStatus` mutation handles all transition event types correctly in `TRANSITION_EVENT_MAP`

- [x] Task 2: Remove duplicate activity event writes from executor (AC: #6, #7)
  - [x] 2.1: In `executor.py:_pickup_task()`, remove the explicit `bridge.create_activity(TASK_STARTED, ...)` call — `update_task_status` already writes it
  - [x] 2.2: In `executor.py:_execute_task()`, remove the explicit `bridge.create_activity(TASK_COMPLETED, ...)` call — `update_task_status` already writes it
  - [x] 2.3: Verify the executor's `send_message` calls are still needed (they are — messages and activities are different)

- [x] Task 3: Add inbox task deduplication to orchestrator (AC: #2)
  - [x] 3.1: Add `_known_inbox_ids: set[str] = set()` to `TaskOrchestrator.__init__()`
  - [x] 3.2: In `start_routing_loop()`, skip tasks whose ID is already in `_known_inbox_ids`
  - [x] 3.3: Add task ID to `_known_inbox_ids` before calling `_process_inbox_task()`
  - [x] 3.4: Wrap `_process_inbox_task()` call in try/except to prevent loop crash on any error — log warning and continue
  - [x] 3.5: Discard task ID from `_known_inbox_ids` after the task leaves inbox (transitions to assigned/crashed/etc.) — can be done via a small delay or by checking transition success

- [x] Task 4: Add subscription reconnection to bridge (AC: #3, #5)
  - [x] 4.1: Replace `asyncio.get_event_loop()` with `asyncio.get_running_loop()` in `async_subscribe()`
  - [x] 4.2: Wrap the subscription `_run()` thread in a reconnection loop: on exception, wait with exponential backoff (1s, 2s, 4s, max 30s), then retry `self.subscribe()`
  - [x] 4.3: Push a sentinel error value (e.g. `{"_error": True, "message": str(exc)}`) to the queue on persistent failure so consuming loops can detect and log
  - [x] 4.4: Add a `max_reconnect_attempts` parameter (default 10) after which the thread pushes a fatal sentinel and exits

- [x] Task 5: Fix empty agent_name in bridge (AC: #4)
  - [x] 5.1: In `bridge.py:update_task_status()`, change `"agent_name": agent_name or ""` to conditionally include the field only when agent_name is not None
  - [x] 5.2: Same pattern for any other bridge method that sends optional fields as empty strings

- [x] Task 6: Update tests
  - [x] 6.1: Update existing tests that assert `create_activity` calls — many should be removed since the Python side no longer writes them
  - [x] 6.2: Add test for orchestrator deduplication (second routing of same task is skipped)
  - [x] 6.3: Add test for orchestrator error resilience (exception in `_process_inbox_task` doesn't crash the loop)
  - [x] 6.4: Add test for subscription reconnection (thread restarts after simulated error)

## Dev Notes

### Critical Architecture Requirements

- **Single integration point**: ALL Convex access goes through `ConvexBridge` (`nanobot/mc/bridge.py`).
- **Activity event ownership**: After this fix, activity events for state transitions are written ONLY by the Convex `tasks:updateStatus` mutation. Python code writes `create_activity` ONLY for standalone events (review_requested, hitl_requested, etc.) that don't correspond to a status transition.
- **500-line module limit** (NFR21): orchestrator.py is at ~692 lines — keep changes minimal to avoid needing further extraction.

### Key File References

| Component | File | What to change |
|-----------|------|----------------|
| Orchestrator routing | `nanobot/mc/orchestrator.py:188-314` | Add deduplication, remove duplicate activity writes |
| Executor pickup/completion | `nanobot/mc/executor.py:160-297` | Remove duplicate activity writes |
| Bridge async_subscribe | `nanobot/mc/bridge.py:337-368` | Reconnection loop, get_running_loop |
| Bridge update_task_status | `nanobot/mc/bridge.py:176-192` | Fix agent_name handling |
| Convex updateStatus | `dashboard/convex/tasks.ts:294-363` | Reference only — already writes activities correctly |
| Tests | `tests/mc/test_gateway.py` | Update assertions, add new tests |

## File List

| File | Action | Description |
|------|--------|-------------|
| `nanobot/mc/orchestrator.py` | Modified | Removed 4 duplicate `create_activity` calls (3 TASK_ASSIGNED + 1 TASK_COMPLETED), added `_known_inbox_ids` deduplication set, added try/except error handling in routing loop, added set pruning for re-inbox scenarios |
| `nanobot/mc/executor.py` | Modified | Removed 2 duplicate `create_activity` calls (TASK_STARTED in `_pickup_task`, TASK_COMPLETED in `_execute_task`) |
| `nanobot/mc/bridge.py` | Modified | Fixed `update_task_status` to conditionally include `agent_name` only when not None (was sending `""`), replaced `get_event_loop()` with `get_running_loop()` in `async_subscribe`, added reconnection loop with exponential backoff and `max_reconnect_attempts` parameter, added error sentinel on persistent failure |
| `tests/mc/test_gateway.py` | Modified | Updated 2 existing tests (`test_assigned_task_creates_started_activity` -> `test_assigned_task_does_not_duplicate_started_activity`, `test_execution_creates_completed_activity` -> `test_execution_does_not_duplicate_completed_activity`), added 15 new tests across 5 test classes |
| `dashboard/convex/tasks.ts` | Not modified | Verified TRANSITION_EVENT_MAP covers all transitions (reference only) |

## Change Log

- **Task 1**: Removed 3 duplicate `create_activity(TASK_ASSIGNED, ...)` calls from `_process_inbox_task` (explicit assignment, best-match routing, fallback routing) and 1 from the multi-step execution plan path. Removed 1 `create_activity(TASK_COMPLETED, ...)` from `complete_step`. Verified `_handle_review_transition` correctly keeps standalone `create_activity` calls for REVIEW_REQUESTED and HITL_REQUESTED (no corresponding status transition).
- **Task 2**: Removed `create_activity(TASK_STARTED, ...)` from `_pickup_task` and `create_activity(TASK_COMPLETED, ...)` from `_execute_task`. Verified `send_message` calls remain (messages are separate from activities).
- **Task 3**: Added `_known_inbox_ids: set[str]` to `TaskOrchestrator.__init__`. In `start_routing_loop`, tasks are skipped if their ID is already in the set. IDs are pruned when tasks leave inbox (set intersection with current subscription data). Each task processing is wrapped in try/except to prevent loop crashes.
- **Task 4**: Replaced `asyncio.get_event_loop()` with `asyncio.get_running_loop()`. Added reconnection loop with exponential backoff (1s, 2s, 4s, ... max 30s). Added `max_reconnect_attempts` parameter (default 10). On exhaustion, pushes `{"_error": True, "message": ...}` sentinel to queue. On clean generator exit with no data, thread exits without reconnecting.
- **Task 5**: Changed `"agent_name": agent_name or ""` to conditionally include `agent_name` only when not None. Verified no other bridge methods have the same pattern.
- **Task 6**: Updated 2 existing tests to assert `create_activity` is NOT called. Added 15 new tests: 5 for no-duplicate orchestrator activity, 3 for no-duplicate executor activity, 2 for inbox deduplication and error resilience, 3 for bridge async_subscribe (source inspection, reconnection, exhaustion sentinel), 2 for bridge agent_name handling.
