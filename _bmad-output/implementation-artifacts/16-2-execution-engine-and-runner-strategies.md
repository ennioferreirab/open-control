# Story 16.2: Execution Engine and Runner Strategies

Status: ready-for-dev

## Story

As a **maintainer**,
I want a single execution engine with explicit runner strategies,
so that nanobot, Claude Code and human execution follow one contract.

## Acceptance Criteria

### AC1: ExecutionEngine Class

**Given** execution logic is scattered across executor.py, cc_executor.py, cc_step_runner.py
**When** the engine is created
**Then** `mc/application/execution/engine.py` contains an `ExecutionEngine` class with:
- `run(request: ExecutionRequest) -> ExecutionResult` as the single entry point
- Strategy selection based on request attributes (runner type)
- Centralized error categorization (tier, provider, runner, workflow)
**And** the engine handles session finalization, memory consolidation, and artifact sync

### AC2: Explicit Runner Strategies

**Given** different execution backends exist
**When** the strategies are implemented
**Then** explicit strategy classes exist:
- `mc/application/execution/strategies/nanobot.py` -- NanobotRunnerStrategy
- `mc/application/execution/strategies/claude_code.py` -- ClaudeCodeRunnerStrategy
- `mc/application/execution/strategies/human.py` -- HumanRunnerStrategy
**And** each strategy implements a common `RunnerStrategy` protocol/interface
**And** the human strategy NEVER spawns a process (returns transition to waiting_human)

### AC3: Centralized Error Handling

**Given** error handling is currently spread across executors
**When** the engine is created
**Then** errors are normalized into categories: `tier`, `provider`, `runner`, `workflow`
**And** tier resolution, provider error handling, and retry decisions are centralized in the engine
**And** the engine uses `mc/tier_resolver.py` for model tier decisions

### AC4: Centralized Post-Execution

**Given** session finalization, memory consolidation, and artifact sync are duplicated
**When** the engine is created
**Then** post-execution steps (memory consolidation, artifact sync, session cleanup) run once through the engine
**And** they work identically for task execution and step execution

### AC5: Test Coverage

**Given** the new engine and strategies
**When** tests are written
**Then** they cover:
- Nanobot strategy happy path and error paths
- Claude Code strategy happy path and error paths
- Human strategy (returns waiting_human, no process)
- Error categorization
- Post-execution pipeline (memory, artifacts, cleanup)
**And** all existing tests pass

## Tasks / Subtasks

- [ ] **Task 1: Analyze current execution patterns** (AC: #1, #2)
  - [ ] 1.1 Read `mc/executor.py` -- identify execution logic, session management, post-processing
  - [ ] 1.2 Read `mc/cc_executor.py` -- identify CC-specific execution
  - [ ] 1.3 Read `mc/cc_step_runner.py` -- identify CC step execution
  - [ ] 1.4 Read `mc/output_enricher.py` -- post-processing logic
  - [ ] 1.5 Read `mc/tier_resolver.py` -- model tier resolution
  - [ ] 1.6 Document: shared patterns, strategy-specific logic, post-execution steps

- [ ] **Task 2: Create RunnerStrategy protocol and strategies** (AC: #2)
  - [ ] 2.1 Create `mc/application/execution/strategies/__init__.py`
  - [ ] 2.2 Create `mc/application/execution/strategies/base.py` with RunnerStrategy protocol
  - [ ] 2.3 Create `mc/application/execution/strategies/nanobot.py` -- extract nanobot execution
  - [ ] 2.4 Create `mc/application/execution/strategies/claude_code.py` -- extract CC execution
  - [ ] 2.5 Create `mc/application/execution/strategies/human.py` -- returns waiting_human transition
  - [ ] 2.6 Write tests for each strategy

- [ ] **Task 3: Create ExecutionEngine** (AC: #1, #3, #4)
  - [ ] 3.1 Create `mc/application/execution/engine.py` with ExecutionEngine class
  - [ ] 3.2 Implement strategy selection in `run()` method
  - [ ] 3.3 Implement centralized error categorization and handling
  - [ ] 3.4 Implement post-execution pipeline (memory consolidation, artifact sync, session cleanup)
  - [ ] 3.5 Write tests for the engine

- [ ] **Task 4: Migrate helpers from scattered locations** (AC: #3, #4)
  - [ ] 4.1 Move session finalization logic from executor/cc_executor to engine
  - [ ] 4.2 Move memory consolidation to engine post-execution
  - [ ] 4.3 Move artifact sync to engine post-execution
  - [ ] 4.4 Move error handling/categorization from executor to engine
  - [ ] 4.5 Run full test suite

- [ ] **Task 5: Final verification** (AC: #5)
  - [ ] 5.1 Run full test suite
  - [ ] 5.2 Run linter
  - [ ] 5.3 Verify all strategies follow the same protocol

## Dev Notes

### Architecture Patterns

**Strategy Pattern:** The engine delegates to strategies via a common protocol. Strategy selection is based on the ExecutionRequest's runner type (determined by agent config or step config).

**Human strategy is special:** It NEVER spawns a process. It simply returns an ExecutionResult with a status transition to `waiting_human`. The orchestrator handles the rest.

**This story depends on 16.1** (ExecutionRequest/ExecutionResult from context pipeline).

**Key Files to Read First:**
- `mc/executor.py` -- main executor
- `mc/cc_executor.py` -- Claude Code executor
- `mc/cc_step_runner.py` -- Claude Code step runner
- `mc/output_enricher.py` -- post-processing
- `mc/tier_resolver.py` -- model tier resolution
- `mc/application/execution/request.py` -- from story 16.1

### Project Structure Notes

**Files to CREATE:**
- `mc/application/execution/engine.py`
- `mc/application/execution/strategies/__init__.py`
- `mc/application/execution/strategies/base.py`
- `mc/application/execution/strategies/nanobot.py`
- `mc/application/execution/strategies/claude_code.py`
- `mc/application/execution/strategies/human.py`
- Tests for each module

**Files to MODIFY:**
- `mc/executor.py` -- extract execution logic to engine (NOT delegation yet, that's 16.3)
- `mc/cc_executor.py` -- extract to strategy
- `mc/cc_step_runner.py` -- extract to strategy
- `mc/output_enricher.py` -- move post-execution logic to engine

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log
