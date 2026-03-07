# Story 20.1: Integrate cc_step_runner and chat_handler into ExecutionEngine

Status: review

## Story

As a **maintainer**,
I want cc_step_runner and chat_handler to route execution through ExecutionEngine,
so that ExecutionEngine.run() is truly the sole execution path and the "single entrypoint" criterion is met.

## Acceptance Criteria

### AC1: cc_step_runner Uses ExecutionEngine

**Given** `mc/cc_step_runner.py` currently calls `_collect_output_artifacts()` and `_relocate_invalid_memory_files()` directly from executor
**When** the migration is complete
**Then** `execute_step_via_cc()` delegates to ExecutionEngine with a ClaudeCodeRunnerStrategy
**And** post-execution hooks (artifact collection, memory relocation) are handled by the engine's hook system
**And** no direct calls to executor private functions remain in cc_step_runner.py

### AC2: chat_handler Uses ExecutionEngine

**Given** `mc/chat_handler.py` currently runs a direct agent loop bypassing ExecutionEngine
**When** the migration is complete
**Then** chat-initiated execution flows through ExecutionEngine.run()
**And** the chat handler builds an ExecutionRequest with appropriate context
**And** post-execution hooks apply uniformly to chat-initiated execution
**And** session persistence across chat messages is preserved

### AC3: output_enricher Cleanup

**Given** `mc/output_enricher.py` contains a duplicate `_run_agent_on_task()` definition
**When** cleanup is complete
**Then** the duplicate is removed
**And** output_enricher uses the canonical path (runtime.py facade or ExecutionEngine)

### AC4: No Direct Executor Private Function Calls

**Given** the migration is complete
**When** scanning all production code (excluding tests)
**Then** no module outside of `mc/executor.py` and `mc/application/execution/runtime.py` calls:
- `executor._run_agent_on_task()`
- `executor._collect_output_artifacts()`
- `executor._relocate_invalid_memory_files()`
- `executor._background_tasks`
**And** architecture tests enforce this

### AC5: All Tests Pass

**Given** the migration is complete
**When** the full test suite runs
**Then** all existing tests pass
**And** new tests cover cc_step_runner and chat_handler ExecutionEngine integration

## Tasks / Subtasks

- [x] **Task 1: Analyze current cc_step_runner** (AC: #1)
  - [x] 1.1 Read `mc/cc_step_runner.py` completely
  - [x] 1.2 Map all direct calls to executor private functions
  - [x] 1.3 Identify how to build ExecutionRequest for CC step execution

- [x] **Task 2: Migrate cc_step_runner to ExecutionEngine** (AC: #1)
  - [x] 2.1 Replace direct executor calls with ExecutionEngine.run()
  - [x] 2.2 Build proper ExecutionRequest with CC step context
  - [x] 2.3 Ensure post-execution hooks handle artifact collection and memory relocation
  - [x] 2.4 Write tests for the new path

- [x] **Task 3: Analyze current chat_handler** (AC: #2)
  - [x] 3.1 Read `mc/chat_handler.py` completely
  - [x] 3.2 Map the direct agent loop execution path
  - [x] 3.3 Understand session persistence requirements across chat messages
  - [x] 3.4 Identify what ExecutionRequest fields are needed

- [x] **Task 4: Migrate chat_handler to ExecutionEngine** (AC: #2)
  - [x] 4.1 Build ExecutionRequest for chat-initiated execution
  - [x] 4.2 Route execution through ExecutionEngine.run()
  - [x] 4.3 Preserve session persistence across chat messages
  - [x] 4.4 Write tests for chat_handler ExecutionEngine integration

- [x] **Task 5: Clean up output_enricher** (AC: #3)
  - [x] 5.1 Remove duplicate `_run_agent_on_task()` from output_enricher.py
  - [x] 5.2 Route through canonical path

- [x] **Task 6: Add architecture guardrail** (AC: #4)
  - [x] 6.1 Add test to `tests/mc/test_architecture.py` prohibiting direct executor private function calls from production modules
  - [x] 6.2 Verify the test catches violations and passes on clean code

- [x] **Task 7: Full regression** (AC: #5)
  - [x] 7.1 Run `uv run pytest tests/` -- 1889 passed, 2 skipped (1 pre-existing failure excluded)
  - [x] 7.2 Run dashboard tests -- N/A (no dashboard changes)
  - [x] 7.3 Verify mention, chat, CC step scenarios work end-to-end

## Dev Notes

### Architecture Patterns

**ExecutionEngine is the single entrypoint.** All execution -- task, step, chat, CC -- must flow through `ExecutionEngine.run()`. The engine selects the appropriate RunnerStrategy and runs post-execution hooks uniformly.

**Chat handler special case:** Chat execution has session persistence across messages. The ExecutionRequest must carry session context, and the strategy must preserve it. This may require a new field on ExecutionRequest or a chat-specific strategy adapter.

**Key Files to Read First:**
- `mc/cc_step_runner.py` -- current CC step execution
- `mc/chat_handler.py` -- current chat execution
- `mc/output_enricher.py` -- duplicate code to clean
- `mc/application/execution/engine.py` -- ExecutionEngine
- `mc/application/execution/strategies/claude_code.py` -- CC strategy
- `mc/application/execution/request.py` -- ExecutionRequest model
- `mc/application/execution/runtime.py` -- runtime facades

### Project Structure Notes

**Files to MODIFY:**
- `mc/cc_step_runner.py` -- migrate to ExecutionEngine
- `mc/chat_handler.py` -- migrate to ExecutionEngine
- `mc/output_enricher.py` -- remove duplicate
- `tests/mc/test_architecture.py` -- add guardrail

**Files to CREATE:**
- Tests for new integration paths

### References

- [Source: mc/application/execution/engine.py] -- ExecutionEngine.run()
- [Source: mc/application/execution/strategies/] -- existing strategies
- [Source: docs/ARCHITECTURE.md] -- execution runtime section

## Dev Agent Record

### Agent Model Used
claude-opus-4-6

### Debug Log References
N/A

### Completion Notes List
- cc_step_runner now builds ExecutionRequest(entity_type=STEP, runner_type=CLAUDE_CODE) and delegates to ExecutionEngine.run() with a ClaudeCodeRunnerStrategy
- chat_handler routes CC chats through ExecutionEngine with CLAUDE_CODE runner, nanobot chats through NANOBOT runner
- CC chat session persistence preserved: session_id from ExecutionResult stored via bridge.mutation("settings:set")
- Duplicate _run_agent_on_task removed from output_enricher.py (~170 lines of dead code)
- output_enricher._enrich_nanobot_description updated to use runtime adapters instead of mc.executor references
- Architecture guardrail test_no_direct_executor_private_calls scans all mc/ production code for executor._ references
- Pre-existing test failure in test_gateway_cron_delivery (unrelated ValueError unpacking) excluded from regression

### File List
- mc/cc_step_runner.py (modified)
- mc/chat_handler.py (modified)
- mc/output_enricher.py (modified)
- tests/mc/test_architecture.py (modified)
- tests/mc/test_chat_handler.py (modified)
- tests/mc/test_cc_step_runner.py (created)

## Change Log
- 2026-03-07: Story implemented by dev agent (claude-opus-4-6)
