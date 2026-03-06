# Story 17.1: Orchestrator Worker Extraction

Status: ready-for-dev

## Story

As a **maintainer**,
I want the orchestrator decomposed into focused workers,
so that routing logic becomes testable and isolated.

## Acceptance Criteria

### AC1: Inbox Worker

**Given** the orchestrator handles inbox routing logic
**When** the extraction is complete
**Then** `mc/workers/inbox.py` (InboxWorker) handles:
- New task processing from inbox status
- Initial routing decisions
- Assignment logic
**And** it uses services and repositories (not dense embedded logic)

### AC2: Planning Worker

**Given** the orchestrator handles planning/plan-generation logic
**When** the extraction is complete
**Then** `mc/workers/planning.py` (PlanningWorker) handles:
- Execution plan generation triggering
- Plan materialization decisions
- Plan validation before kickoff
**And** it delegates to existing plan_materializer and planner services

### AC3: Review Worker

**Given** the orchestrator handles review routing
**When** the extraction is complete
**Then** `mc/workers/review.py` (ReviewWorker) handles:
- Review task routing and assignment
- Review completion detection
- Post-review state transitions
**And** it uses services and repositories

### AC4: Kickoff/Resume Worker

**Given** the orchestrator handles task kickoff and resume flows
**When** the extraction is complete
**Then** `mc/workers/kickoff.py` (KickoffResumeWorker) handles:
- Task kickoff (inbox/assigned → in_progress)
- Task resume after pause
- Step dispatch triggering after kickoff
**And** it delegates to executor and step_dispatcher for actual execution

### AC5: Orchestrator Becomes Thin Coordinator

**Given** all workers are extracted
**When** the refactor is complete
**Then** `mc/orchestrator.py` becomes a thin coordinator that:
- Receives events/tasks
- Routes to the appropriate worker
- Contains no dense domain logic
**And** the coordination loop behavior is unchanged

### AC6: Test Coverage

**Given** the new worker modules
**When** tests are written
**Then** each worker has tests covering happy path and crash/error path
**And** all existing orchestrator tests pass

## Tasks / Subtasks

- [ ] **Task 1: Analyze orchestrator.py** (AC: #1, #2, #3, #4)
  - [ ] 1.1 Read `mc/orchestrator.py` completely
  - [ ] 1.2 Categorize every method: inbox routing vs planning vs review vs kickoff/resume vs coordination
  - [ ] 1.3 Map dependencies for each category
  - [ ] 1.4 Document the extraction plan

- [ ] **Task 2: Create InboxWorker** (AC: #1)
  - [ ] 2.1 Create `mc/workers/__init__.py`
  - [ ] 2.2 Create `mc/workers/inbox.py` with InboxWorker class
  - [ ] 2.3 Extract inbox routing logic from orchestrator
  - [ ] 2.4 Write tests in `tests/mc/workers/test_inbox.py`

- [ ] **Task 3: Create PlanningWorker** (AC: #2)
  - [ ] 3.1 Create `mc/workers/planning.py` with PlanningWorker class
  - [ ] 3.2 Extract planning/plan-generation logic from orchestrator
  - [ ] 3.3 Ensure it delegates to `mc/plan_materializer.py` and `mc/planner.py`
  - [ ] 3.4 Write tests in `tests/mc/workers/test_planning.py`

- [ ] **Task 4: Create ReviewWorker** (AC: #3)
  - [ ] 4.1 Create `mc/workers/review.py` with ReviewWorker class
  - [ ] 4.2 Extract review routing logic from orchestrator
  - [ ] 4.3 Write tests in `tests/mc/workers/test_review.py`

- [ ] **Task 5: Create KickoffResumeWorker** (AC: #4)
  - [ ] 5.1 Create `mc/workers/kickoff.py` with KickoffResumeWorker class
  - [ ] 5.2 Extract kickoff and resume logic from orchestrator
  - [ ] 5.3 Write tests in `tests/mc/workers/test_kickoff.py`

- [ ] **Task 6: Slim down orchestrator.py** (AC: #5)
  - [ ] 6.1 Replace extracted logic with delegation to workers
  - [ ] 6.2 Orchestrator constructor takes worker instances
  - [ ] 6.3 Event routing loop delegates to workers
  - [ ] 6.4 Run full test suite

- [ ] **Task 7: Final verification** (AC: #6)
  - [ ] 7.1 Run full test suite
  - [ ] 7.2 Run linter
  - [ ] 7.3 Verify orchestrator.py is thin

## Dev Notes

### Architecture Patterns

**Worker Pattern:** Each worker handles one concern. Workers receive dependencies via constructor (services, repositories, bridge). The orchestrator is the composition root that creates workers and routes events to them.

**Reuse existing states.** Do NOT redesign the state machine or product behavior. This is purely structural.

**Key Files to Read First:**
- `mc/orchestrator.py` -- the main file being decomposed
- `mc/plan_materializer.py` -- plan materialization
- `mc/planner.py` -- plan generation
- `mc/review_handler.py` -- review handling (may already exist)
- `mc/executor.py` -- task execution (workers delegate to this)

### Project Structure Notes

**Files to CREATE:**
- `mc/workers/__init__.py`
- `mc/workers/inbox.py`
- `mc/workers/planning.py`
- `mc/workers/review.py`
- `mc/workers/kickoff.py`
- `tests/mc/workers/` -- test files

**Files to MODIFY:**
- `mc/orchestrator.py` -- slim down to coordinator

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log
