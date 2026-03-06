# Story 15.3: Bridge Split into Client, Repositories and Subscriptions

Status: ready-for-dev

## Story

As a **backend maintainer**,
I want the bridge separated by responsibility,
so that data access stops being a god module.

## Acceptance Criteria

### AC1: Bridge Becomes Thin Facade

**Given** `mc/bridge.py` currently contains raw Convex client, retry logic, key conversion, subscriptions, and all data access methods
**When** this refactor is complete
**Then** `mc/bridge.py` becomes a thin facade that delegates to specialized modules
**And** all existing call sites (`bridge.query(...)`, `bridge.mutation(...)`, etc.) continue to work without changes
**And** the facade imports and re-exposes the same public API

### AC2: Raw Client and Infrastructure Split

**Given** the bridge contains low-level Convex client logic
**When** the split is complete
**Then** `mc/bridge/client.py` contains the raw Convex client wrapper (connection, auth, raw query/mutation)
**And** `mc/bridge/retry.py` contains retry logic and error handling
**And** `mc/bridge/key_conversion.py` contains camelCase/snake_case key conversion utilities

### AC3: Repository Pattern for Data Access

**Given** the bridge contains methods for tasks, steps, messages, agents, boards, settings
**When** the split is complete
**Then** repositories exist as separate modules:
- `mc/bridge/repositories/tasks.py` -- task CRUD and queries
- `mc/bridge/repositories/steps.py` -- step CRUD and queries
- `mc/bridge/repositories/messages.py` -- message posting and queries
- `mc/bridge/repositories/agents.py` -- agent sync and queries
- `mc/bridge/repositories/boards.py` -- board-related queries
- `mc/bridge/repositories/settings.py` -- settings queries
**And** each repository uses the raw client and retry infrastructure
**And** repositories follow a consistent pattern (constructor takes client reference)

### AC4: Subscriptions Split

**Given** `mc/bridge_subscriptions.py` or subscription logic in bridge.py
**When** the split is complete
**Then** `mc/bridge/subscriptions.py` contains all polling/subscription logic
**And** it is cleanly separated from the CRUD repositories

### AC5: Backward Compatibility

**Given** many modules import from `mc.bridge` directly
**When** the refactor is complete
**Then** `mc/bridge.py` (now `mc/bridge/__init__.py`) re-exports everything for backward compatibility
**And** NO external call site needs to change in this story
**And** all existing tests pass without modification (except bridge-specific unit tests)

### AC6: Repository Tests

**Given** the new repository structure
**When** tests are added
**Then** each repository has focused unit tests
**And** the existing bridge smoke tests continue to pass
**And** test coverage for data access methods improves

## Tasks / Subtasks

- [ ] **Task 1: Audit bridge.py and plan split** (AC: #1)
  - [ ] 1.1 Read `mc/bridge.py` completely and categorize every method: client infra vs retry vs key conversion vs task repo vs step repo vs message repo vs agent repo vs board repo vs settings repo vs subscription
  - [ ] 1.2 Read `mc/bridge_subscriptions.py` to understand subscription/polling patterns
  - [ ] 1.3 Grep for all `from mc.bridge import` and `from mc import bridge` to map all consumers
  - [ ] 1.4 Document the split plan: which methods go where

- [ ] **Task 2: Create bridge package structure** (AC: #2)
  - [ ] 2.1 Convert `mc/bridge.py` to `mc/bridge/__init__.py` (the facade)
  - [ ] 2.2 Create `mc/bridge/client.py` -- extract raw Convex client (connection, auth, raw query/mutation calls)
  - [ ] 2.3 Create `mc/bridge/retry.py` -- extract retry/backoff logic
  - [ ] 2.4 Create `mc/bridge/key_conversion.py` -- extract camelCase/snake_case conversion utilities
  - [ ] 2.5 Write tests for client, retry, and key_conversion modules

- [ ] **Task 3: Extract repositories** (AC: #3)
  - [ ] 3.1 Create `mc/bridge/repositories/__init__.py`
  - [ ] 3.2 Create `mc/bridge/repositories/tasks.py` -- extract task-related methods
  - [ ] 3.3 Create `mc/bridge/repositories/steps.py` -- extract step-related methods
  - [ ] 3.4 Create `mc/bridge/repositories/messages.py` -- extract message-related methods
  - [ ] 3.5 Create `mc/bridge/repositories/agents.py` -- extract agent sync/query methods
  - [ ] 3.6 Create `mc/bridge/repositories/boards.py` -- extract board-related methods
  - [ ] 3.7 Create `mc/bridge/repositories/settings.py` -- extract settings methods
  - [ ] 3.8 Write tests for each repository

- [ ] **Task 4: Extract subscriptions** (AC: #4)
  - [ ] 4.1 Create `mc/bridge/subscriptions.py` -- move polling/subscription logic from bridge_subscriptions.py and bridge.py
  - [ ] 4.2 Update the facade to delegate to subscriptions module
  - [ ] 4.3 Write tests for subscription logic

- [ ] **Task 5: Wire facade and verify compatibility** (AC: #5, #6)
  - [ ] 5.1 Update `mc/bridge/__init__.py` to import and re-export all public API from sub-modules
  - [ ] 5.2 Verify all existing call sites work without changes (grep and test)
  - [ ] 5.3 Run full test suite to verify no regressions
  - [ ] 5.4 Verify `mc/bridge_subscriptions.py` is either removed or reduced to a thin import shim

## Dev Notes

### Architecture Patterns

**God Module Decomposition:**
`mc/bridge.py` is the most critical module to split because it's the foundation for workers, read models, and the execution engine in later stories. Every data access in the system flows through it.

**Package Conversion:**
When converting `mc/bridge.py` to `mc/bridge/__init__.py`, Git will see this as a delete + create. Be careful to preserve git history context. The facade pattern ensures zero breaking changes.

**Repository Pattern:**
Each repository class takes a client reference in its constructor:
```python
class TaskRepository:
    def __init__(self, client: ConvexClient):
        self._client = client

    async def get_task(self, task_id: str) -> dict:
        return await self._client.query("tasks:get", {"taskId": task_id})
```

**Backward Compatibility via __init__.py:**
The `mc/bridge/__init__.py` facade instantiates all repositories and delegates. Existing code that does `from mc.bridge import ConvexBridge` or `bridge.query_tasks(...)` continues to work.

**Key Files to Read First:**
- `mc/bridge.py` -- the god module being split (~800+ lines likely)
- `mc/bridge_subscriptions.py` -- subscription/polling logic already partially separated
- `mc/executor.py` -- major bridge consumer
- `mc/orchestrator.py` -- major bridge consumer
- `mc/process_monitor.py` -- bridge consumer for sync operations

### Project Structure Notes

**Files to CREATE:**
- `mc/bridge/__init__.py` (replacing mc/bridge.py)
- `mc/bridge/client.py`
- `mc/bridge/retry.py`
- `mc/bridge/key_conversion.py`
- `mc/bridge/subscriptions.py`
- `mc/bridge/repositories/__init__.py`
- `mc/bridge/repositories/tasks.py`
- `mc/bridge/repositories/steps.py`
- `mc/bridge/repositories/messages.py`
- `mc/bridge/repositories/agents.py`
- `mc/bridge/repositories/boards.py`
- `mc/bridge/repositories/settings.py`
- `tests/mc/bridge/` -- test files for each module

**Files to MODIFY/REMOVE:**
- `mc/bridge.py` -- converted to package __init__.py
- `mc/bridge_subscriptions.py` -- contents moved to mc/bridge/subscriptions.py

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log
