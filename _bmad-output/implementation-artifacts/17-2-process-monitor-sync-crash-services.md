# Story 17.2: Process Monitor, Sync and Crash Services

Status: review

## Story

As a **maintainer**,
I want monitoring, sync and retry logic extracted from process_monitor,
so that runtime supervision is modular.

## Acceptance Criteria

### AC1: Agent Sync Service

**Given** `mc/gateway.py` currently contains agent/skills/settings/model-tier sync logic
**When** this refactor is complete
**Then** `mc/services/agent_sync.py` (AgentSyncService) contains:
- Agent sync (detect new/changed/deleted agents from YAML files)
- Skills sync
- Settings sync
- Model tier sync
- Embedding settings sync
**And** the service has clear input/output contracts
**And** cleanup of deleted agents is handled properly

### AC2: Crash Recovery Service

**Given** `mc/gateway.py` contains crash detection, retry policy, and escalation logic
**When** this refactor is complete
**Then** `mc/services/crash_recovery.py` (CrashRecoveryService) contains:
- Crash detection logic
- Retry count tracking and policy
- Crash thread message posting
- Escalation to human when retry limit exceeded
**And** the current retry semantics are preserved exactly

### AC3: Plan Negotiation Supervisor

**Given** `mc/gateway.py` contains plan negotiation helpers
**When** this refactor is complete
**Then** `mc/services/plan_negotiation.py` (PlanNegotiationSupervisor) contains:
- Plan negotiation monitoring logic
- Plan approval/rejection handling
**And** it uses existing services and repositories

### AC4: Process Monitor Becomes Thin Coordinator

**Given** all the logic has been extracted
**When** this refactor is complete
**Then** `mc/gateway.py` becomes a thin coordinator that:
- Runs the monitoring loop
- Delegates to AgentSyncService, CrashRecoveryService, PlanNegotiationSupervisor
- Contains no dense domain logic itself
**And** the monitoring loop behavior is unchanged from the user's perspective

### AC5: Test Coverage

**Given** the new service modules
**When** tests are written
**Then** they cover:
- Agent sync happy path and crash path (deleted agents cleanup)
- Crash recovery: retry count, crash message, escalation
- Model tier and embedding settings sync
- Process monitor coordination (delegates correctly)
**And** all existing tests pass

## Tasks / Subtasks

- [x] **Task 1: Analyze gateway.py** (AC: #1, #2, #3)
  - [x] 1.1 Read `mc/gateway.py` completely -- categorize every method: sync vs crash vs plan negotiation vs coordination
  - [x] 1.2 Note: `mc/agent_sync.py` does not exist — sync logic is entirely in gateway.py
  - [x] 1.3 Read `mc/plan_negotiator.py` -- understand current plan negotiation
  - [x] 1.4 Map dependencies: gateway imports bridge, orchestrator, timeout_checker, executor, yaml_validator
  - [x] 1.5 Document extraction plan: AgentGateway -> CrashRecoveryService, sync_* -> AgentSyncService, _run_plan_negotiation_manager -> PlanNegotiationSupervisor

- [x] **Task 2: Create AgentSyncService** (AC: #1)
  - [x] 2.1 Create `mc/services/__init__.py`
  - [x] 2.2 Create `mc/services/agent_sync.py` with AgentSyncService class
  - [x] 2.3 Extract agent sync logic (new/changed/deleted agents, skills, settings, model tiers, embeddings)
  - [x] 2.4 Write unit tests in `tests/mc/services/test_agent_sync.py` (12 tests)
  - [x] 2.5 Ensure cleanup of deleted agents works correctly

- [x] **Task 3: Create CrashRecoveryService** (AC: #2)
  - [x] 3.1 Create `mc/services/crash_recovery.py` with CrashRecoveryService class
  - [x] 3.2 Extract crash detection, retry count, retry policy logic
  - [x] 3.3 Extract crash thread message posting
  - [x] 3.4 Extract escalation-to-human logic
  - [x] 3.5 Write unit tests in `tests/mc/services/test_crash_recovery.py` (11 tests)

- [x] **Task 4: Create PlanNegotiationSupervisor** (AC: #3)
  - [x] 4.1 Create `mc/services/plan_negotiation.py` with PlanNegotiationSupervisor class
  - [x] 4.2 Extract plan negotiation monitoring logic
  - [x] 4.3 Write unit tests in `tests/mc/services/test_plan_negotiation.py` (10 tests)

- [x] **Task 5: Slim down gateway.py** (AC: #4)
  - [x] 5.1 Replace extracted logic with delegation to new services
  - [x] 5.2 AgentGateway delegates to CrashRecoveryService
  - [x] 5.3 _run_plan_negotiation_manager delegates to PlanNegotiationSupervisor
  - [x] 5.4 main() uses AgentSyncService for sync operations
  - [x] 5.5 Run full test suite to verify no regressions (1087 passed)

- [x] **Task 6: Final verification** (AC: #5)
  - [x] 6.1 Run full test suite (1087 passed, 1 pre-existing failure in test_cli_tasks.py)
  - [x] 6.2 Run linter (all new files clean, no new errors introduced)
  - [x] 6.3 Verify gateway.py is thinner (AgentGateway: 15 lines vs 80+, _run_plan_negotiation_manager: 7 lines vs 55+)

## Dev Notes

### Architecture Patterns

**Service Extraction:** Each service has clear constructor dependencies (bridge, config, etc.) and methods that perform one focused task. gateway.py becomes the composition root for runtime supervision.

**Preserve Semantics:** The retry count behavior, crash thread messages, and escalation timing are preserved EXACTLY. No behavior changes in this story.

**Actual source file:** The story referenced `mc/process_monitor.py` but the actual file is `mc/gateway.py` (process_manager.py manages subprocesses, not agent monitoring). All extraction was done from `mc/gateway.py`.

### Project Structure Notes

**Files CREATED:**
- `mc/services/__init__.py`
- `mc/services/agent_sync.py`
- `mc/services/crash_recovery.py`
- `mc/services/plan_negotiation.py`
- `tests/mc/services/__init__.py`
- `tests/mc/services/test_agent_sync.py`
- `tests/mc/services/test_crash_recovery.py`
- `tests/mc/services/test_plan_negotiation.py`

**Files MODIFIED:**
- `mc/gateway.py` — slimmed down to coordinator (delegates to services)

## Dev Agent Record

### Agent Model Used
claude-opus-4-6

### Debug Log References

### Completion Notes List
- All 33 service tests pass
- All 1087 existing tests pass (1 pre-existing failure in test_cli_tasks.py excluded)
- No new lint errors introduced
- Backward compatibility maintained: AgentGateway, sync_agent_registry, etc. still work as before

### File List
- `mc/services/__init__.py` — package init with exports
- `mc/services/agent_sync.py` — AgentSyncService (agent, skills, settings, model-tier, embedding sync)
- `mc/services/crash_recovery.py` — CrashRecoveryService (crash detection, retry, escalation)
- `mc/services/plan_negotiation.py` — PlanNegotiationSupervisor (per-task negotiation loop management)
- `mc/gateway.py` — slimmed coordinator (delegates to services)
- `tests/mc/services/__init__.py` — test package init
- `tests/mc/services/test_agent_sync.py` — 12 tests for AgentSyncService
- `tests/mc/services/test_crash_recovery.py` — 11 tests for CrashRecoveryService
- `tests/mc/services/test_plan_negotiation.py` — 10 tests for PlanNegotiationSupervisor

## Change Log
- 2026-03-06: Initial implementation complete — all tasks done, tests passing
