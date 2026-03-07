# Clean `mc/` Root Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove concrete modules from the `mc/` root, move them into canonical architecture packages, and leave only a minimal compatibility surface at the root.

**Architecture:** The cleanup keeps `runtime`, `contexts`, `infrastructure`, `domain`, `application`, and `cli` as ownership boundaries. Root modules become compatibility shims or disappear after imports move to canonical packages.

**Tech Stack:** Python, pytest, git worktrees, architecture guardrail tests

---

### Task 1: Move CLI-owned root modules

**Files:**
- Create: `mc/cli/agent_assist.py`
- Create: `mc/cli/init_wizard.py`
- Create: `mc/cli/process_manager.py`
- Modify: `mc/agent_assist.py`
- Modify: `mc/init_wizard.py`
- Modify: `mc/process_manager.py`
- Modify: `mc/cli/__init__.py`
- Test: `tests/mc/test_agent_assist.py`
- Test: `tests/mc/test_init_wizard.py`
- Test: `tests/mc/test_process_manager.py`

**Step 1: Write or update failing import-path tests**

Add assertions that canonical CLI modules are importable and root modules are facades only.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/mc/test_agent_assist.py tests/mc/test_init_wizard.py tests/mc/test_process_manager.py -q`
Expected: import path or architecture assertions fail before the move.

**Step 3: Write minimal implementation**

Move module bodies into `mc/cli/*`, then replace root files with thin facades.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/mc/test_agent_assist.py tests/mc/test_init_wizard.py tests/mc/test_process_manager.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add mc/cli mc/agent_assist.py mc/init_wizard.py mc/process_manager.py tests/mc
git commit -m "refactor: move cli helpers out of mc root"
```

### Task 2: Move infrastructure-owned root modules

**Files:**
- Create: `mc/infrastructure/boards.py`
- Create: `mc/infrastructure/orientation.py`
- Create: `mc/infrastructure/providers/factory.py`
- Create: `mc/infrastructure/providers/tier_resolver.py`
- Create: `mc/infrastructure/agents/yaml_validator.py`
- Modify: `mc/board_utils.py`
- Modify: `mc/agent_orientation.py`
- Modify: `mc/provider_factory.py`
- Modify: `mc/tier_resolver.py`
- Modify: `mc/yaml_validator.py`
- Modify: all import sites using the old paths
- Test: `tests/mc/test_board_utils.py`
- Test: `tests/mc/test_orientation.py`
- Test: `tests/mc/test_provider_factory.py`
- Test: `tests/mc/test_tier_resolver.py`
- Test: `tests/mc/test_yaml_validator.py`

**Step 1: Write failing import-path and guardrail tests**

Add checks for canonical infrastructure import paths and root facade thinness.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/mc/test_board_utils.py tests/mc/test_orientation.py tests/mc/test_provider_factory.py tests/mc/test_tier_resolver.py tests/mc/test_yaml_validator.py -q`
Expected: FAIL on unresolved canonical imports before the move.

**Step 3: Write minimal implementation**

Move module bodies, rewrite imports, and keep root facades only where compatibility is required.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/mc/test_board_utils.py tests/mc/test_orientation.py tests/mc/test_provider_factory.py tests/mc/test_tier_resolver.py tests/mc/test_yaml_validator.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add mc/infrastructure mc/board_utils.py mc/agent_orientation.py mc/provider_factory.py mc/tier_resolver.py mc/yaml_validator.py tests/mc
git commit -m "refactor: move infrastructure helpers out of mc root"
```

### Task 3: Move planning and execution leftovers

**Files:**
- Create: `mc/contexts/planning/parser.py`
- Create: `mc/contexts/execution/post_processing.py`
- Create: `mc/contexts/execution/crash_recovery.py`
- Modify: `mc/plan_parser.py`
- Modify: `mc/output_enricher.py`
- Modify: `mc/crash_handler.py`
- Modify: `mc/contexts/planning/planner.py`
- Modify: `mc/contexts/execution/executor.py`
- Modify: `mc/contexts/execution/cc_executor.py`
- Modify: `mc/contexts/execution/step_dispatcher.py`
- Test: `tests/mc/test_process_monitor_decomposition.py`
- Test: `tests/mc/test_thread_context.py`
- Test: execution-related tests that import the moved modules

**Step 1: Write failing import-path tests**

Add targeted checks that planning/execution use canonical modules instead of root implementations.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/mc/test_process_monitor_decomposition.py tests/mc/test_chat_handler.py tests/mc/test_gateway.py -q`
Expected: FAIL before canonical moves are wired.

**Step 3: Write minimal implementation**

Move the concrete module bodies to planning/execution packages and convert the root files to facades.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/mc/test_process_monitor_decomposition.py tests/mc/test_chat_handler.py tests/mc/test_gateway.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add mc/contexts mc/plan_parser.py mc/output_enricher.py mc/crash_handler.py tests/mc
git commit -m "refactor: move planning and execution leftovers out of mc root"
```

### Task 4: Move workflow and runtime shared modules

**Files:**
- Create: `mc/application/execution/thread_context.py`
- Create: `mc/domain/workflow/state_machine.py`
- Create: `mc/runtime/timeout_checker.py`
- Modify: `mc/thread_context.py`
- Modify: `mc/state_machine.py`
- Modify: `mc/timeout_checker.py`
- Modify: import sites using the old paths
- Test: `tests/mc/test_thread_context.py`
- Test: `tests/mc/test_state_machine.py`
- Test: `tests/mc/test_task_state_machine.py`
- Test: `tests/mc/test_step_state_machine.py`
- Test: `tests/mc/test_timeout_checker.py`

**Step 1: Write failing import-path tests**

Add checks for canonical application/domain/runtime import paths.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/mc/test_thread_context.py tests/mc/test_state_machine.py tests/mc/test_task_state_machine.py tests/mc/test_step_state_machine.py tests/mc/test_timeout_checker.py -q`
Expected: FAIL before the move.

**Step 3: Write minimal implementation**

Move the module bodies and rewrite imports to the new canonical packages.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/mc/test_thread_context.py tests/mc/test_state_machine.py tests/mc/test_task_state_machine.py tests/mc/test_step_state_machine.py tests/mc/test_timeout_checker.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add mc/application mc/domain mc/runtime mc/thread_context.py mc/state_machine.py mc/timeout_checker.py tests/mc
git commit -m "refactor: move workflow and runtime helpers out of mc root"
```

### Task 5: Remove or absorb generic root utilities

**Files:**
- Modify: `mc/utils.py`
- Modify: modules importing `mc.utils`
- Test: any tests covering positive-int parsing or affected consumers

**Step 1: Write failing test**

Add or update a small test that proves the helper lives at its canonical destination.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/mc/test_planner.py tests/mc/test_plan_materializer.py -q`
Expected: FAIL before import rewrites.

**Step 3: Write minimal implementation**

Absorb `as_positive_int` into the nearest canonical module or replace `mc/utils.py` with a thin facade.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/mc/test_planner.py tests/mc/test_plan_materializer.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add mc/utils.py mc/contexts mc/domain tests/mc
git commit -m "refactor: remove generic root utils"
```

### Task 6: Strengthen architecture guardrails and docs

**Files:**
- Modify: `tests/mc/test_architecture.py`
- Modify: `tests/mc/test_module_reorganization.py`
- Modify: `docs/ARCHITECTURE.md`

**Step 1: Write failing architecture assertions**

Add allowlist-based checks for the root and forbid old root imports from canonical layers.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/mc/test_architecture.py tests/mc/test_module_reorganization.py -q`
Expected: FAIL until the root allowlist and canonical imports are enforced.

**Step 3: Write minimal implementation**

Update guardrails and docs to match the cleaned architecture.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/mc/test_architecture.py tests/mc/test_module_reorganization.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/mc docs/ARCHITECTURE.md
git commit -m "test: enforce clean mc root architecture"
```

### Task 7: Full verification and branch checkpoint

**Files:**
- Modify: any remaining files discovered during integration

**Step 1: Run the full backend suite**

Run: `uv run pytest tests/mc -q`
Expected: PASS with existing known warnings only.

**Step 2: Inspect the final root**

Run: `find mc -maxdepth 1 -type f | sort`
Expected: only allowlisted root files plus thin facades remain.

**Step 3: Review import boundaries**

Run: `uv run pytest tests/mc/test_architecture.py tests/mc/test_module_reorganization.py -q`
Expected: PASS

**Step 4: Commit final integration**

```bash
git add mc tests/mc docs/ARCHITECTURE.md docs/plans
git commit -m "refactor: clean mc root ownership boundaries"
```
