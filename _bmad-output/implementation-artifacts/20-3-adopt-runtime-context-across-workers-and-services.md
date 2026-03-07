# Story 20.3: Adopt RuntimeContext Across Workers and Services

Status: review

## Story

As a **maintainer**,
I want workers and services to receive RuntimeContext instead of bare bridge,
so that dependency injection is standardized and services can access shared configuration without coupling to gateway.

## Acceptance Criteria

### AC1: RuntimeContext Is the Standard Dependency

**Given** `mc/infrastructure/runtime_context.py` defines RuntimeContext (bridge, agents_dir, admin_key, admin_url, services)
**When** the adoption is complete
**Then** all workers in `mc/workers/` accept RuntimeContext in their constructor
**And** all services that currently receive `bridge` directly accept RuntimeContext instead
**And** RuntimeContext is created once in gateway and passed down

### AC2: Gateway Creates RuntimeContext

**Given** the gateway currently creates workers with bare bridge
**When** the adoption is complete
**Then** `mc/gateway.py` creates a single RuntimeContext instance
**And** passes it to all workers and services during composition

### AC3: Workers Use RuntimeContext

**Given** workers in `mc/workers/` (inbox, planning, review, kickoff) receive bare bridge
**When** the adoption is complete
**Then** they receive RuntimeContext
**And** access bridge via `ctx.bridge`
**And** can access agents_dir, admin_key, and shared services via RuntimeContext

### AC4: No Behavior Change

**Given** this is a pure refactoring
**When** the adoption is complete
**Then** all existing tests pass without modification (except constructor signature changes)
**And** runtime behavior is identical

## Tasks / Subtasks

- [x] **Task 1: Review RuntimeContext definition** (AC: #1)
  - [x] 1.1 Read `mc/infrastructure/runtime_context.py`
  - [x] 1.2 Determine if current fields are sufficient or need extension
  - [x] 1.3 Identify all workers and services that receive bare bridge

- [x] **Task 2: Update RuntimeContext if needed** (AC: #1)
  - [x] 2.1 Add any missing fields needed by workers/services
  - [x] 2.2 Keep it minimal -- only shared concerns

- [x] **Task 3: Update workers** (AC: #3)
  - [x] 3.1 Update InboxWorker constructor to accept RuntimeContext
  - [x] 3.2 Update PlanningWorker constructor
  - [x] 3.3 Update ReviewWorker constructor
  - [x] 3.4 Update KickoffResumeWorker constructor
  - [x] 3.5 Update internal bridge references to `self._ctx.bridge`

- [x] **Task 4: Update gateway composition** (AC: #2)
  - [x] 4.1 Create RuntimeContext in gateway
  - [x] 4.2 Pass RuntimeContext to all workers
  - [x] 4.3 Pass RuntimeContext to services that need it

- [x] **Task 5: Update tests** (AC: #4)
  - [x] 5.1 Update worker test fixtures to provide RuntimeContext
  - [x] 5.2 Run full test suite
  - [x] 5.3 Verify no behavior changes

## Dev Notes

### Architecture Patterns

**RuntimeContext is a simple dataclass.** It replaces ad-hoc parameter passing. Workers access `ctx.bridge`, `ctx.agents_dir`, etc. instead of receiving each as separate parameters.

**Minimal scope.** Only convert workers and services that currently receive bridge directly. Don't convert everything at once -- this is the first adoption pass.

**Key Files to Read First:**
- `mc/infrastructure/runtime_context.py` -- current RuntimeContext (39 lines)
- `mc/gateway.py` -- where workers are created
- `mc/workers/inbox.py` -- InboxWorker constructor
- `mc/workers/planning.py` -- PlanningWorker constructor
- `mc/workers/review.py` -- ReviewWorker constructor
- `mc/workers/kickoff.py` -- KickoffResumeWorker constructor

### Project Structure Notes

**Files to MODIFY:**
- `mc/infrastructure/runtime_context.py` -- extend if needed
- `mc/gateway.py` -- create and pass RuntimeContext
- `mc/workers/inbox.py`, `planning.py`, `review.py`, `kickoff.py` -- accept RuntimeContext
- Worker test files

### References

- [Source: mc/infrastructure/runtime_context.py] -- RuntimeContext definition
- [Source: docs/ARCHITECTURE.md] -- infrastructure layer

## Dev Agent Record

### Agent Model Used
claude-opus-4-6

### Debug Log References
N/A

### Completion Notes List
- RuntimeContext fields (bridge, agents_dir, admin_key, admin_url, services) were sufficient; no extensions needed
- All 4 workers updated to accept RuntimeContext as first constructor arg
- Workers store `self._ctx` and set `self._bridge = ctx.bridge` for internal use
- TaskOrchestrator updated with backward-compatible constructor: accepts either RuntimeContext or bare bridge
- Gateway creates RuntimeContext with bridge, AGENTS_DIR, admin_key, and admin_url
- 8 new tests verify RuntimeContext acceptance across all workers
- 36 existing worker tests updated to pass RuntimeContext instead of bare bridge
- 12 orchestrator tests pass unchanged (backward-compatible constructor)
- 1 gateway test updated to verify RuntimeContext is passed
- Full test suite: 2092 passed, 2 pre-existing failures, 0 regressions

### File List
- `mc/workers/inbox.py` -- accept RuntimeContext
- `mc/workers/planning.py` -- accept RuntimeContext
- `mc/workers/review.py` -- accept RuntimeContext
- `mc/workers/kickoff.py` -- accept RuntimeContext
- `mc/orchestrator.py` -- accept RuntimeContext or bridge (backward compat)
- `mc/gateway.py` -- create RuntimeContext and pass to orchestrator
- `tests/mc/workers/test_inbox.py` -- updated fixtures
- `tests/mc/workers/test_planning.py` -- updated fixtures
- `tests/mc/workers/test_review.py` -- updated fixtures
- `tests/mc/workers/test_kickoff.py` -- updated fixtures
- `tests/mc/workers/test_runtime_context_adoption.py` -- new: 8 tests
- `tests/mc/test_gateway.py` -- updated assertion for RuntimeContext
- `_bmad-output/implementation-artifacts/20-3-adopt-runtime-context-across-workers-and-services.md` -- story

## Change Log
- 2026-03-07: All tasks completed. Workers accept RuntimeContext, gateway creates it, tests updated and passing.
