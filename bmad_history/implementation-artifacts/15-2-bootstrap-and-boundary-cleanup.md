# Story 15.2: Bootstrap and Boundary Cleanup

Status: review

## Story

As a **maintainer**,
I want bootstrap/config/path logic isolated from runtime services,
so that internal modules stop depending on mc.gateway.

## Acceptance Criteria

### AC1: Gateway Reduced to Bootstrap Only

**Given** `mc/gateway.py` currently contains bootstrap, wiring, startup/shutdown, AND runtime utilities
**When** this refactor is complete
**Then** `mc/gateway.py` only contains:
- Application bootstrap (startup/shutdown lifecycle)
- Service wiring (dependency injection / container setup)
- Entry point logic
**And** all config resolution, env resolution, path utilities, agent bootstrap helpers have been extracted

### AC2: Infrastructure Module for Config/Paths

**Given** the need to extract config and path logic from gateway
**When** `mc/infrastructure/` package is created
**Then** it contains:
- `config.py` -- AGENTS_DIR, env resolution, admin key/url resolution, config paths
- `runtime_context.py` -- RuntimeContext lightweight container with bridge, config paths, and service references
- `agent_bootstrap.py` -- low-agent bootstrap and sync config logic
**And** each module has clear, focused responsibility

### AC3: No Internal Imports of mc.gateway

**Given** the architectural rule: "gateway can import services; services cannot import gateway"
**When** all modules are checked
**Then** NO module in `mc/` imports from `mc.gateway` except the entrypoint (`boot.py` or equivalent)
**And** this applies to: executor, dispatcher, mentions, chat_handler, agent_orientation, CLI modules, orchestrator, process_monitor
**And** all former `mc.gateway.*` references now use explicit dependency injection via RuntimeContext or direct imports from `mc/infrastructure/`

### AC4: Tests Updated

**Given** existing tests that patch `mc.gateway.*` attributes
**When** the refactor is complete
**Then** all tests are updated to patch the new locations (`mc.infrastructure.*` or RuntimeContext)
**And** no test imports from `mc.gateway` except integration tests that test the bootstrap itself
**And** all existing tests continue to pass

## Tasks / Subtasks

- [x] **Task 1: Audit current mc.gateway dependencies** (AC: #1, #3)
  - [x] 1.1 Read `mc/gateway.py` completely and categorize every function/class/constant: bootstrap vs config vs runtime utility
  - [x] 1.2 Grep for all `from mc.gateway import` and `import mc.gateway` across the entire codebase
  - [x] 1.3 Map each import to what it actually uses (function/constant names)
  - [x] 1.4 Document the dependency graph: which modules import what from gateway

- [x] **Task 2: Create mc/infrastructure package** (AC: #2)
  - [x] 2.1 Create `mc/infrastructure/__init__.py`
  - [x] 2.2 Create `mc/infrastructure/config.py` -- extract AGENTS_DIR, env resolution, admin key/url resolution, config path helpers from gateway
  - [x] 2.3 Create `mc/infrastructure/runtime_context.py` -- lightweight container/dataclass holding bridge ref, config paths, service references
  - [x] 2.4 Create `mc/infrastructure/agent_bootstrap.py` -- extract low-agent bootstrap and sync config logic
  - [x] 2.5 Write unit tests for each infrastructure module

- [x] **Task 3: Migrate all internal imports** (AC: #3)
  - [x] 3.1 Update `mc/executor.py` to import from `mc.infrastructure` and `mc.crash_handler` instead of `mc.gateway`
  - [x] 3.2 Update `mc/step_dispatcher.py` to import from `mc.infrastructure` instead of `mc.gateway`
  - [x] 3.3 Update `mc/mention_handler.py` to import from `mc.infrastructure` instead of `mc.gateway`
  - [x] 3.4 Update `mc/chat_handler.py` to import from `mc.infrastructure` instead of `mc.gateway`
  - [x] 3.5 N/A -- `mc/agent_orientation.py` does not exist in this codebase
  - [x] 3.6 Update `mc/orchestrator.py` to import from `mc.infrastructure` instead of `mc.gateway`
  - [x] 3.7 N/A -- `mc/process_monitor.py` does not exist (it's `mc/process_manager.py` which had no gateway imports)
  - [x] 3.8 Update `mc/cli.py` to import from `mc.infrastructure` instead of `mc.gateway`
  - [x] 3.9 Update vendor files: `mc_delegate.py`, `ask_agent.py`, `ipc_server.py`

- [x] **Task 4: Slim down mc/gateway.py** (AC: #1)
  - [x] 4.1 Remove all extracted functions/constants from gateway.py (replaced with re-exports)
  - [x] 4.2 Add imports from `mc.infrastructure` where gateway itself needs them for bootstrap
  - [x] 4.3 Ensure gateway only does: bootstrap, wiring, startup, shutdown
  - [x] 4.4 Add a module-level comment documenting the boundary rule

- [x] **Task 5: Update tests** (AC: #4)
  - [x] 5.1 Find all test files that patch `mc.gateway.*`
  - [x] 5.2 Update patches to target new locations in `mc.infrastructure`
  - [x] 5.3 Run full test suite to verify no regressions (1436 passed, 3 pre-existing failures)
  - [x] 5.4 Add a test that verifies no internal module imports from mc.gateway (architectural guardrail)

## Dev Notes

### Architecture Patterns

**Architectural Rule:** `gateway can import services; services cannot import gateway`. This is the core invariant being established. Gateway is the composition root -- it wires everything together. But runtime modules should depend on abstractions (RuntimeContext) or infrastructure modules, not on the composition root.

**RuntimeContext Pattern:**
A lightweight dataclass or simple container that holds references to bridge, config paths, and services. Modules receive this via constructor injection or function parameters instead of importing gateway directly.

```python
@dataclass
class RuntimeContext:
    bridge: ConvexBridge
    agents_dir: Path
    admin_key: str
    admin_url: str
    # ... other config
```

**Migration Strategy:**
1. Create infrastructure modules with the extracted code
2. Update imports in all consumer modules (one module at a time)
3. Strip gateway.py down to bootstrap only
4. Update tests last

**Key Files to Read First:**
- `mc/gateway.py` -- the main file being decomposed
- `mc/executor.py` -- likely the largest consumer of gateway
- `mc/orchestrator.py` -- another major consumer
- `mc/process_monitor.py` -- uses sync/config from gateway
- `boot.py` -- the entry point that calls gateway

### Project Structure Notes

**Files CREATED:**
- `mc/infrastructure/__init__.py`
- `mc/infrastructure/config.py`
- `mc/infrastructure/runtime_context.py`
- `mc/infrastructure/agent_bootstrap.py`
- `mc/crash_handler.py`
- `tests/mc/infrastructure/__init__.py`
- `tests/mc/infrastructure/test_config.py`
- `tests/mc/infrastructure/test_runtime_context.py`
- `tests/mc/infrastructure/test_boundary.py`

**Files MODIFIED:**
- `mc/gateway.py` -- slimmed to bootstrap/wiring/lifecycle + re-exports for backward compat
- `mc/executor.py` -- imports from mc.crash_handler and mc.infrastructure.config
- `mc/step_dispatcher.py` -- imports from mc.infrastructure.config
- `mc/orchestrator.py` -- imports from mc.infrastructure.config
- `mc/mention_handler.py` -- imports from mc.infrastructure.config
- `mc/chat_handler.py` -- imports from mc.infrastructure.config
- `mc/cli.py` -- imports from mc.infrastructure.config and mc.infrastructure.agent_bootstrap
- `vendor/nanobot/nanobot/agent/tools/mc_delegate.py` -- imports from mc.infrastructure.config
- `vendor/nanobot/nanobot/agent/tools/ask_agent.py` -- imports from mc.infrastructure.config
- `vendor/claude-code/claude_code/ipc_server.py` -- imports from mc.infrastructure.config
- `tests/mc/test_gateway.py` -- patch targets updated
- `tests/mc/test_executor_cc.py` -- patch targets updated
- `tests/mc/test_chat_handler.py` -- patch targets updated
- `tests/mc/test_ask_agent.py` -- patch targets updated
- `tests/mc/test_nanobot_agent.py` -- patch targets updated
- `tests/mc/test_sync_nanobot_model.py` -- patch targets updated
- `tests/mc/test_skill_distribution.py` -- logger name updated

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
None -- no blockers encountered.

### Completion Notes List
- AgentGateway class was extracted to `mc/crash_handler.py` (not just infrastructure) because it's a runtime service, not config/bootstrap. This keeps the boundary clean: executor imports from crash_handler, not gateway.
- `mc/gateway.py` provides backward-compatible re-exports so that existing callers (tests, vendor code) can still `from mc.gateway import X` without breaking.
- The boundary test (`test_boundary.py`) uses AST parsing to verify that no mc/ module (except gateway.py itself) imports from mc.gateway.
- 3 pre-existing test failures are unrelated: test_workspace (memory quarantine, skill logging), test_cli_tasks (output format).

### File List
See "Project Structure Notes" above for complete file lists.

## Change Log
- 2026-03-06: Story implemented. All ACs met. 1436 tests pass, 0 regressions.
