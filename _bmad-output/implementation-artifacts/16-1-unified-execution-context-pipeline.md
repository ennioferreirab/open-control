# Story 16.1: Unified Execution Context Pipeline

Status: ready-for-dev

## Story

As a **runtime maintainer**,
I want one shared pipeline for building execution context,
so that tasks and steps receive context the same way.

## Acceptance Criteria

### AC1: ExecutionRequest Data Model

**Given** tasks and steps currently build execution context independently
**When** the unified context pipeline is created
**Then** an `ExecutionRequest` dataclass exists in `mc/application/execution/request.py` with normalized fields:
- `entity_type` (task | step)
- `entity_id` (task_id or step_id)
- `board` (board data)
- `files` (file manifest)
- `thread_context` (assembled thread messages)
- `predecessor_context` (previous step results for steps)
- `skills` (agent skills)
- `prompt` (assembled final prompt)
- `model` (resolved model identifier)
- `agent` (agent config)
- `tags` / `tag_attributes`
**And** an `ExecutionResult` dataclass exists for the return value

### AC2: Unified Context Builders

**Given** context enrichment is currently duplicated between TaskExecutor and StepDispatcher
**When** the pipeline is created
**Then** shared builder modules exist in `mc/application/execution/`:
- `context_builder.py` -- orchestrates the full context assembly pipeline
- `file_enricher.py` -- file manifest, board workspace resolution
- `thread_context_builder.py` -- thread context assembly (shared between mentions, assigned-agent, direct context)
- `roster_builder.py` -- agent roster/capability enrichment
- `artifact_collector.py` -- artifact preparation and collection
**And** each builder has a clear input/output contract
**And** mention context and assigned-agent context share the same ThreadContextBuilder

### AC3: TaskExecutor and StepDispatcher Stop Having Parallel Builders

**Given** TaskExecutor and StepDispatcher currently have their own context building logic
**When** the migration is complete
**Then** both delegate to the unified context pipeline
**And** there is no duplicated enrichment logic between them
**And** CC (Claude Code) execution and human-step execution also use the same pipeline

### AC4: Test Coverage

**Given** the new context pipeline
**When** tests are written
**Then** they cover:
- Task context assembly (full pipeline)
- Step context assembly (with predecessor context)
- CC execution context
- Human-step context (minimal, no process spawn)
- Mention context reusing ThreadContextBuilder
**And** all existing tests continue to pass

## Tasks / Subtasks

- [ ] **Task 1: Analyze current context building patterns** (AC: #1, #3)
  - [ ] 1.1 Read `mc/executor.py` completely -- identify all context building logic (prompt assembly, file enrichment, thread context, artifact prep)
  - [ ] 1.2 Read `mc/step_dispatcher.py` completely -- identify parallel context building logic
  - [ ] 1.3 Read `mc/cc_executor.py` and `mc/cc_step_runner.py` -- identify CC-specific context patterns
  - [ ] 1.4 Read `mc/thread_context.py` -- understand ThreadContextBuilder
  - [ ] 1.5 Read `mc/output_enricher.py` -- understand artifact/output enrichment
  - [ ] 1.6 Document: what is shared, what diverges, what can be unified

- [ ] **Task 2: Create ExecutionRequest and ExecutionResult models** (AC: #1)
  - [ ] 2.1 Create `mc/application/__init__.py`
  - [ ] 2.2 Create `mc/application/execution/__init__.py`
  - [ ] 2.3 Create `mc/application/execution/request.py` with ExecutionRequest dataclass
  - [ ] 2.4 Create `mc/application/execution/result.py` with ExecutionResult dataclass
  - [ ] 2.5 Write tests for the data models

- [ ] **Task 3: Create unified context builders** (AC: #2)
  - [ ] 3.1 Create `mc/application/execution/context_builder.py` -- main pipeline orchestrator
  - [ ] 3.2 Create `mc/application/execution/file_enricher.py` -- extract file/manifest/workspace logic
  - [ ] 3.3 Create `mc/application/execution/thread_context_builder.py` -- unify thread context assembly
  - [ ] 3.4 Create `mc/application/execution/roster_builder.py` -- agent roster enrichment
  - [ ] 3.5 Create `mc/application/execution/artifact_collector.py` -- artifact preparation
  - [ ] 3.6 Write tests for each builder module

- [ ] **Task 4: Integrate pipeline into executor and dispatcher** (AC: #3)
  - [ ] 4.1 Modify `mc/executor.py` to delegate context building to the unified pipeline
  - [ ] 4.2 Modify `mc/step_dispatcher.py` to delegate context building to the unified pipeline
  - [ ] 4.3 Verify CC execution path uses the unified pipeline
  - [ ] 4.4 Verify human-step path uses the unified pipeline
  - [ ] 4.5 Run full test suite to verify no regressions

- [ ] **Task 5: Final verification** (AC: #4)
  - [ ] 5.1 Run full test suite
  - [ ] 5.2 Verify no duplicated context-building logic remains in executor/dispatcher
  - [ ] 5.3 Run linter

## Dev Notes

### Architecture Patterns

**Pipeline Pattern:** The context builder follows a pipeline pattern: raw entity data → enriched data → assembled prompt → ExecutionRequest. Each stage is a separate module.

**This story does NOT change the runner.** It only changes context PREPARATION. The actual execution (spawning nanobot, Claude Code, etc.) stays the same until story 16.2.

**Key Files to Read First:**
- `mc/executor.py` -- TaskExecutor with context building in `_execute_task()`
- `mc/step_dispatcher.py` -- StepDispatcher with parallel context building
- `mc/cc_executor.py` -- Claude Code executor
- `mc/cc_step_runner.py` -- Claude Code step runner
- `mc/thread_context.py` -- ThreadContextBuilder
- `mc/output_enricher.py` -- output/artifact enrichment

### Depends On
- Story 15.2 (bootstrap cleanup) -- for clean infrastructure imports
- Story 15.3 (bridge split) -- for repository-based data access

### Project Structure Notes

**Files to CREATE:**
- `mc/application/__init__.py`
- `mc/application/execution/__init__.py`
- `mc/application/execution/request.py`
- `mc/application/execution/result.py`
- `mc/application/execution/context_builder.py`
- `mc/application/execution/file_enricher.py`
- `mc/application/execution/thread_context_builder.py`
- `mc/application/execution/roster_builder.py`
- `mc/application/execution/artifact_collector.py`
- `tests/mc/application/execution/` -- test files

**Files to MODIFY:**
- `mc/executor.py` -- delegate to unified pipeline
- `mc/step_dispatcher.py` -- delegate to unified pipeline

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log
