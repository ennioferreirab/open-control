# Story 16.3: Executor and Dispatcher Migration

Status: ready-for-dev

## Story

As a **maintainer**,
I want task and step execution to delegate to the same engine,
so that execution semantics stop diverging.

## Acceptance Criteria

### AC1: TaskExecutor Delegates to ExecutionEngine

**Given** the ExecutionEngine exists from story 16.2
**When** TaskExecutor is rewritten
**Then** it is responsible only for:
- Task pickup (claiming tasks from inbox/assigned)
- State progression (updating task status before/after execution)
- Delegating to ExecutionEngine.run() for actual execution
**And** it no longer contains execution logic, context building, or post-processing
**And** lead-agent reroute behavior is preserved

### AC2: StepDispatcher Delegates to ExecutionEngine

**Given** the ExecutionEngine exists from story 16.2
**When** StepDispatcher is rewritten
**Then** it is responsible only for:
- Step dispatch decisions (which steps to run next)
- State progression (updating step status before/after execution)
- Delegating to ExecutionEngine.run() for actual execution
**And** it no longer contains execution logic or context building
**And** there is no private import from step_dispatcher to executor

### AC3: Artifact and Message Posting Unified

**Given** artifact posting and message posting are currently handled differently by executor and dispatcher
**When** the migration is complete
**Then** a single flow handles:
- Artifact posting (output files, enriched outputs)
- Message posting (completion messages, error messages)
- Post-session cleanup
**And** this flow is part of the ExecutionEngine pipeline (from 16.2)

### AC4: Behavior Preservation

**Given** this is a structural migration
**When** complete
**Then** the following behaviors are preserved exactly:
- Lead-agent reroute (task assigned to lead → rerouted to specialist)
- Human steps (waiting_human transition)
- Pause/resume (task/step pause and resume flow)
- Retry logic (crashed task/step retry)
**And** all existing tests pass

### AC5: No Cross-Import

**Given** the new architecture
**When** the migration is complete
**Then** there is NO import from `mc.step_dispatcher` to `mc.executor` or vice versa
**And** both depend on `mc.application.execution.engine` (the shared engine)

## Tasks / Subtasks

- [ ] **Task 1: Rewrite TaskExecutor** (AC: #1, #4)
  - [ ] 1.1 Read current `mc/executor.py` completely
  - [ ] 1.2 Identify: pickup logic, state progression, execution logic, post-processing
  - [ ] 1.3 Rewrite to delegate execution to ExecutionEngine.run()
  - [ ] 1.4 Preserve lead-agent reroute behavior
  - [ ] 1.5 Preserve human step handling
  - [ ] 1.6 Preserve pause/resume flow
  - [ ] 1.7 Write/update tests for the rewritten TaskExecutor
  - [ ] 1.8 Run tests to verify no regressions

- [ ] **Task 2: Rewrite StepDispatcher** (AC: #2, #4)
  - [ ] 2.1 Read current `mc/step_dispatcher.py` completely
  - [ ] 2.2 Identify: dispatch logic, state progression, execution logic
  - [ ] 2.3 Rewrite to delegate execution to ExecutionEngine.run()
  - [ ] 2.4 Remove any private imports from executor
  - [ ] 2.5 Preserve retry behavior for steps
  - [ ] 2.6 Write/update tests for the rewritten StepDispatcher
  - [ ] 2.7 Run tests to verify no regressions

- [ ] **Task 3: Unify artifact and message posting** (AC: #3)
  - [ ] 3.1 Identify all artifact posting code in executor and dispatcher
  - [ ] 3.2 Identify all message posting code
  - [ ] 3.3 Ensure the ExecutionEngine pipeline handles these uniformly
  - [ ] 3.4 Remove duplicated posting logic from executor/dispatcher
  - [ ] 3.5 Write tests for unified posting

- [ ] **Task 4: Verify no cross-imports and full regression** (AC: #5)
  - [ ] 4.1 Grep for any import between executor and step_dispatcher
  - [ ] 4.2 Run full test suite
  - [ ] 4.3 Run linter
  - [ ] 4.4 Verify all behavior tests pass (reroute, human, pause/resume, retry)

## Dev Notes

### Architecture Patterns

**Thin Executor/Dispatcher Pattern:** After this story, executor and dispatcher are thin orchestrators that handle state progression and delegate to the engine for execution. They are analogous to "controllers" in MVC.

**This story depends on 16.2** (ExecutionEngine and runner strategies) and transitively on 16.1 (context pipeline). It should be the LAST story in the 16.x lane.

**Key Files to Read First:**
- `mc/executor.py` -- TaskExecutor
- `mc/step_dispatcher.py` -- StepDispatcher
- `mc/application/execution/engine.py` -- from story 16.2
- `mc/application/execution/context_builder.py` -- from story 16.1

### Project Structure Notes

**Files to MODIFY:**
- `mc/executor.py` -- major rewrite (thin executor)
- `mc/step_dispatcher.py` -- major rewrite (thin dispatcher)

**Files that may need adjustments:**
- `mc/application/execution/engine.py` -- may need small tweaks
- Test files for executor and dispatcher

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log
