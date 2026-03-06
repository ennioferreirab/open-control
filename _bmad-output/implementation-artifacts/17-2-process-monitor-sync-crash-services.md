# Story 17.2: Process Monitor, Sync and Crash Services

Status: ready-for-dev

## Story

As a **maintainer**,
I want monitoring, sync and retry logic extracted from process_monitor,
so that runtime supervision is modular.

## Acceptance Criteria

### AC1: Agent Sync Service

**Given** `mc/process_monitor.py` currently contains agent/skills/settings/model-tier sync logic
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

**Given** `mc/process_monitor.py` contains crash detection, retry policy, and escalation logic
**When** this refactor is complete
**Then** `mc/services/crash_recovery.py` (CrashRecoveryService) contains:
- Crash detection logic
- Retry count tracking and policy
- Crash thread message posting
- Escalation to human when retry limit exceeded
**And** the current retry semantics are preserved exactly

### AC3: Plan Negotiation Supervisor

**Given** `mc/process_monitor.py` contains plan negotiation helpers
**When** this refactor is complete
**Then** `mc/services/plan_negotiation.py` (PlanNegotiationSupervisor) contains:
- Plan negotiation monitoring logic
- Plan approval/rejection handling
**And** it uses existing services and repositories

### AC4: Process Monitor Becomes Thin Coordinator

**Given** all the logic has been extracted
**When** this refactor is complete
**Then** `mc/process_monitor.py` becomes a thin coordinator that:
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

- [ ] **Task 1: Analyze process_monitor.py** (AC: #1, #2, #3)
  - [ ] 1.1 Read `mc/process_monitor.py` completely -- categorize every method: sync vs crash vs plan negotiation vs coordination
  - [ ] 1.2 Read `mc/agent_sync.py` if it exists -- understand current sync patterns
  - [ ] 1.3 Read `mc/plan_negotiator.py` if it exists -- understand current plan negotiation
  - [ ] 1.4 Map dependencies: what does process_monitor import and use from bridge, gateway, etc.
  - [ ] 1.5 Document the extraction plan

- [ ] **Task 2: Create AgentSyncService** (AC: #1)
  - [ ] 2.1 Create `mc/services/__init__.py`
  - [ ] 2.2 Create `mc/services/agent_sync.py` with AgentSyncService class
  - [ ] 2.3 Extract agent sync logic (new/changed/deleted agents, skills, settings, model tiers, embeddings)
  - [ ] 2.4 Write unit tests in `tests/mc/services/test_agent_sync.py`
  - [ ] 2.5 Ensure cleanup of deleted agents works correctly

- [ ] **Task 3: Create CrashRecoveryService** (AC: #2)
  - [ ] 3.1 Create `mc/services/crash_recovery.py` with CrashRecoveryService class
  - [ ] 3.2 Extract crash detection, retry count, retry policy logic
  - [ ] 3.3 Extract crash thread message posting
  - [ ] 3.4 Extract escalation-to-human logic
  - [ ] 3.5 Write unit tests in `tests/mc/services/test_crash_recovery.py`

- [ ] **Task 4: Create PlanNegotiationSupervisor** (AC: #3)
  - [ ] 4.1 Create `mc/services/plan_negotiation.py` with PlanNegotiationSupervisor class
  - [ ] 4.2 Extract plan negotiation monitoring logic
  - [ ] 4.3 Write unit tests in `tests/mc/services/test_plan_negotiation.py`

- [ ] **Task 5: Slim down process_monitor.py** (AC: #4)
  - [ ] 5.1 Replace extracted logic with delegation to new services
  - [ ] 5.2 Process monitor constructor takes service instances
  - [ ] 5.3 Monitoring loop delegates to services
  - [ ] 5.4 Run full test suite to verify no regressions

- [ ] **Task 6: Final verification** (AC: #5)
  - [ ] 6.1 Run full test suite
  - [ ] 6.2 Run linter
  - [ ] 6.3 Verify process_monitor.py is thin (mostly coordination, no dense logic)

## Dev Notes

### Architecture Patterns

**Service Extraction:** Each service has clear constructor dependencies (bridge, config, etc.) and methods that perform one focused task. The process monitor becomes the composition root for runtime supervision.

**Preserve Semantics:** The retry count behavior, crash thread messages, and escalation timing must be preserved EXACTLY. No behavior changes in this story.

**This story can run parallel to 16.1 and 18.1** since it doesn't touch executor, dispatcher, or Convex code.

**Key Files to Read First:**
- `mc/process_monitor.py` -- the main file being decomposed
- `mc/agent_sync.py` -- may already have partial sync logic
- `mc/plan_negotiator.py` -- may already have plan negotiation logic
- `mc/bridge.py` (or `mc/bridge/` if 15.3 is merged) -- data access used by monitor
- `mc/tier_resolver.py` -- model tier resolution

### Project Structure Notes

**Files to CREATE:**
- `mc/services/__init__.py`
- `mc/services/agent_sync.py`
- `mc/services/crash_recovery.py`
- `mc/services/plan_negotiation.py`
- `tests/mc/services/__init__.py`
- `tests/mc/services/test_agent_sync.py`
- `tests/mc/services/test_crash_recovery.py`
- `tests/mc/services/test_plan_negotiation.py`

**Files to MODIFY:**
- `mc/process_monitor.py` -- slim down to coordinator

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log
