# Story 15.3: Bridge Split into Client, Repositories and Subscriptions

Status: review

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

- [x] **Task 1: Audit bridge.py and plan split** (AC: #1)
  - [x] 1.1 Read `mc/bridge.py` completely and categorize every method: client infra vs retry vs key conversion vs task repo vs step repo vs message repo vs agent repo vs board repo vs settings repo vs subscription
  - [x] 1.2 Read `mc/bridge_subscriptions.py` to understand subscription/polling patterns
  - [x] 1.3 Grep for all `from mc.bridge import` and `from mc import bridge` to map all consumers
  - [x] 1.4 Document the split plan: which methods go where

- [x] **Task 2: Create bridge package structure** (AC: #2)
  - [x] 2.1 Convert `mc/bridge.py` to `mc/bridge/__init__.py` (the facade)
  - [x] 2.2 Create `mc/bridge/client.py` -- extract raw Convex client (connection, auth, raw query/mutation calls)
  - [x] 2.3 Create `mc/bridge/retry.py` -- extract retry/backoff logic
  - [x] 2.4 Create `mc/bridge/key_conversion.py` -- extract camelCase/snake_case conversion utilities
  - [x] 2.5 Write tests for client, retry, and key_conversion modules

- [x] **Task 3: Extract repositories** (AC: #3)
  - [x] 3.1 Create `mc/bridge/repositories/__init__.py`
  - [x] 3.2 Create `mc/bridge/repositories/tasks.py` -- extract task-related methods
  - [x] 3.3 Create `mc/bridge/repositories/steps.py` -- extract step-related methods
  - [x] 3.4 Create `mc/bridge/repositories/messages.py` -- extract message-related methods
  - [x] 3.5 Create `mc/bridge/repositories/agents.py` -- extract agent sync/query methods
  - [x] 3.6 Create `mc/bridge/repositories/boards.py` -- extract board-related methods
  - [x] 3.7 Create `mc/bridge/repositories/settings.py` -- extract settings methods
  - [x] 3.8 Write tests for each repository

- [x] **Task 4: Extract subscriptions** (AC: #4)
  - [x] 4.1 Create `mc/bridge/subscriptions.py` -- move polling/subscription logic from bridge.py
  - [x] 4.2 Update the facade to delegate to subscriptions module
  - [x] 4.3 Write tests for subscription logic

- [x] **Task 5: Wire facade and verify compatibility** (AC: #5, #6)
  - [x] 5.1 Update `mc/bridge/__init__.py` to import and re-export all public API from sub-modules
  - [x] 5.2 Verify all existing call sites work without changes (grep and test)
  - [x] 5.3 Run full test suite to verify no regressions
  - [x] 5.4 Verify `mc/bridge_subscriptions.py` is either removed or reduced to a thin import shim

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
claude-opus-4-6

### Debug Log References
- No `mc/bridge_subscriptions.py` exists -- all subscription logic was in `mc/bridge.py`
- Tests using `object.__new__(ConvexBridge)` and `MagicMock(spec=ConvexBridge)` patterns required lazy repo initialization via `_ensure_repos()`
- `_BridgeClientAdapter` handles both normal and test-mock scenarios

### Completion Notes List
- Bridge split into 12 new files across client, retry, key_conversion, subscriptions, and 7 repository modules
- Added ChatRepository (not in original plan) since bridge had chat methods
- Facade uses `_ensure_repos()` lazy init pattern to handle `object.__new__()` test patterns
- 5 bridge-specific test methods in test_chat_handler.py updated (allowed by AC5)
- All 97 original bridge tests pass unchanged
- 94 new tests added for sub-modules
- 3 pre-existing failures unrelated to this story

### File List
**Created:**
- `mc/bridge/__init__.py` -- facade (replaces mc/bridge.py)
- `mc/bridge/client.py` -- standalone BridgeClient wrapper
- `mc/bridge/retry.py` -- retry/backoff logic with constants
- `mc/bridge/key_conversion.py` -- camelCase/snake_case utilities
- `mc/bridge/subscriptions.py` -- SubscriptionManager (sync + async polling)
- `mc/bridge/repositories/__init__.py` -- re-exports all repositories
- `mc/bridge/repositories/tasks.py` -- TaskRepository
- `mc/bridge/repositories/steps.py` -- StepRepository
- `mc/bridge/repositories/messages.py` -- MessageRepository
- `mc/bridge/repositories/agents.py` -- AgentRepository
- `mc/bridge/repositories/boards.py` -- BoardRepository
- `mc/bridge/repositories/chats.py` -- ChatRepository
- `mc/bridge/repositories/settings.py` -- SettingsRepository (placeholder)
- `tests/mc/bridge/__init__.py`
- `tests/mc/bridge/test_key_conversion.py`
- `tests/mc/bridge/test_retry.py`
- `tests/mc/bridge/test_client.py`
- `tests/mc/bridge/test_repositories.py`
- `tests/mc/bridge/test_subscriptions.py`
- `tests/mc/bridge/test_backward_compat.py`

**Removed:**
- `mc/bridge.py` -- replaced by `mc/bridge/` package

**Modified:**
- `tests/mc/test_chat_handler.py` -- 5 bridge-specific tests updated for delegation pattern

## Change Log
- 2026-03-06: Story implemented -- bridge split into package with facade pattern
