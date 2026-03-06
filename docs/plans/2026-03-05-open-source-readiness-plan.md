# Open-Source Readiness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prepare nanobot-ennio for public GitHub release as `nanobot-mcontrol`

**Architecture:** 4-phase refactoring: security/hygiene first, then code splits, then documentation, then tests. Each phase builds on the previous. Code splits are mechanical moves (extract functions/classes to new files, update imports) — no behavioral changes.

**Tech Stack:** Python 3.11+, uv, pytest, ruff, Next.js (dashboard), Convex

**Design doc:** `docs/plans/2026-03-05-open-source-readiness-design.md`

---

## Phase 1: Security & Hygiene

### Task 1: Update .gitignore and clean sensitive files

**Files:**
- Modify: `.gitignore`
- Delete: `dashboard/.env.local` (if exists locally — NOT tracked in git)

**Step 1: Update .gitignore**

Add these lines to the end of `.gitignore`:

```
node_modules/
.next/
*.zip
.env.local
CLAUDE.md.bkp
```

**Step 2: Delete local .env.local**

```bash
rm -f dashboard/.env.local
```

**Step 3: Verify no secrets in git history**

```bash
git log -S "rugged-mink" --oneline
```

Expected: only the design doc commit (no actual key commits).

**Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore: update .gitignore for open-source release"
```

---

### Task 2: Clean large artifacts from git history

**Step 1: Check if BFG is needed**

```bash
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | awk '/^blob/ {print $3, $4}' | sort -rn | head -20
```

If `node_modules/` or `.next/` objects appear with large sizes, proceed with BFG cleanup. Otherwise skip.

**Step 2: Run BFG if needed**

```bash
brew install bfg  # if not installed
bfg --delete-folders node_modules --delete-folders .next --delete-files '*.zip' --no-blob-protection
git reflog expire --expire=now --all && git gc --prune=now --aggressive
```

**Step 3: Verify cleanup**

```bash
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | awk '/^blob/ {print $3, $4}' | sort -rn | head -5
```

Expected: no objects > 10MB.

---

### Task 3: Remove internal references and rename package

**Files:**
- Modify: `mc/chat_handler.py:9`
- Modify: `mc/gateway.py:274`
- Modify: `tests/test_email_channel.py:19,23`
- Modify: `tests/mc/test_bridge.py:337`
- Modify: `pyproject.toml:2`

**Step 1: Clean TODO ticket references**

In `mc/chat_handler.py:9`, replace:
```python
TODO (CC-6 H2): Thread replies to tasks assigned to claude-code (backend="claude-code")
```
with:
```python
TODO: Thread replies to tasks assigned to claude-code (backend="claude-code")
```

In `mc/gateway.py:274`, replace:
```python
# TODO (CC-6 H1): Clean up cc_session:{name}:* keys from Convex settings
```
with:
```python
# TODO: Clean up cc_session:{name}:* keys from Convex settings
```

**Step 2: Update test credentials**

In `tests/test_email_channel.py`, change `"secret"` to `"test-password"` for `imap_password` and `smtp_password`.

In `tests/mc/test_bridge.py`, change `"secret123"` to `"test-admin-key"`.

**Step 3: Rename package**

In `pyproject.toml:2`, change:
```toml
name = "nanobot-ennio"
```
to:
```toml
name = "nanobot-mcontrol"
```

**Step 4: Run tests to verify nothing broke**

```bash
uv run pytest tests/mc/ -x -q --timeout=30
```

Expected: all tests pass.

**Step 5: Commit**

```bash
git add mc/chat_handler.py mc/gateway.py tests/test_email_channel.py tests/mc/test_bridge.py pyproject.toml
git commit -m "chore: rename to nanobot-mcontrol, remove internal refs, sanitize test creds"
```

---

## Phase 2: Code Refactoring

### Task 4: Split executor.py (2129 LOC)

**Files:**
- Modify: `mc/executor.py` — keep task execution core (~700 LOC)
- Create: `mc/cc_executor.py` — Claude Code integration (~500 LOC)
- Create: `mc/output_enricher.py` — file uploads, output formatting (~300 LOC)
- Modify: all files that import from `mc.executor` — update if needed

**Step 1: Identify extraction boundaries**

Read `mc/executor.py` and identify:
1. CC-specific functions/classes (anything referencing `CCWorkspaceManager`, `ClaudeCodeProvider`, `MCSocketServer`, `CCMemoryConsolidator`) → `cc_executor.py`
2. Output enrichment functions (file upload, output formatting, artifact handling) → `output_enricher.py`
3. Everything else stays in `executor.py`

**Step 2: Create `mc/cc_executor.py`**

Move CC-related functions. Add imports back to `executor.py` for backward compatibility:
```python
# At the bottom of executor.py, for backward compat during transition:
from mc.cc_executor import *  # noqa: F401,F403
```

**Step 3: Create `mc/output_enricher.py`**

Move output/file functions. Same backward compat import.

**Step 4: Update imports across codebase**

Search for all `from mc.executor import` and `from mc import executor` across `mc/` and `tests/`. Update to point to new modules where applicable.

```bash
uv run python -c "import mc.executor; import mc.cc_executor; import mc.output_enricher; print('OK')"
```

**Step 5: Run tests**

```bash
uv run pytest tests/mc/test_executor.py tests/mc/test_executor_cc.py -v --timeout=30
```

Expected: all pass.

**Step 6: Verify line counts**

```bash
wc -l mc/executor.py mc/cc_executor.py mc/output_enricher.py
```

Expected: each file < 600 LOC.

**Step 7: Commit**

```bash
git add mc/executor.py mc/cc_executor.py mc/output_enricher.py
git commit -m "refactor: split executor.py into cc_executor and output_enricher"
```

---

### Task 5: Split gateway.py (1522 LOC)

**Files:**
- Modify: `mc/gateway.py` — keep main loop + agent sync (~800 LOC)
- Create: `mc/process_monitor.py` — subprocess monitoring, crash detection (~400 LOC)
- Modify: imports in other mc/ files

**Step 1: Identify extraction boundaries**

Read `mc/gateway.py`. Extract process monitoring and crash detection logic into `mc/process_monitor.py`.

**Step 2: Create `mc/process_monitor.py`** and move functions.

**Step 3: Update imports and add backward compat re-exports if needed.**

**Step 4: Run tests**

```bash
uv run pytest tests/mc/test_gateway.py tests/mc/test_gateway_*.py -v --timeout=30
```

**Step 5: Verify line counts**

```bash
wc -l mc/gateway.py mc/process_monitor.py
```

Expected: each < 600 LOC.

**Step 6: Commit**

```bash
git add mc/gateway.py mc/process_monitor.py
git commit -m "refactor: extract process_monitor from gateway.py"
```

---

### Task 6: Split cli.py (1547 LOC)

**Files:**
- Modify: `mc/cli.py` — core commands: start/stop/status/logs (~500 LOC)
- Create: `mc/cli_agents.py` — agent management: create/list/sync/assist (~500 LOC)
- Create: `mc/cli_config.py` — config/model management (~400 LOC)

**Step 1: Read `mc/cli.py` and identify function groupings.**

Group 1 (keep in cli.py): `up()`, `stop()`, `down()`, `status()`, `logs()`, `restart()`
Group 2 (cli_agents.py): `sessions()`, `sync_agents()`, `list_agents()`, `create_agent()`, `assist_agent()`, `_save_assisted_agent()`
Group 3 (cli_config.py): config/model management functions

**Step 2: Create new files, move functions, register Typer sub-apps.**

**Step 3: Run CLI tests**

```bash
uv run pytest tests/mc/test_cli_*.py -v --timeout=30
```

**Step 4: Verify line counts**

```bash
wc -l mc/cli.py mc/cli_agents.py mc/cli_config.py
```

**Step 5: Commit**

```bash
git add mc/cli.py mc/cli_agents.py mc/cli_config.py
git commit -m "refactor: split cli.py into cli_agents and cli_config"
```

---

### Task 7: Split bridge.py (1022 LOC)

**Files:**
- Modify: `mc/bridge.py` — core read/write (~600 LOC)
- Create: `mc/bridge_subscriptions.py` — subscriptions + sync ops (~400 LOC)

**Step 1: Read `mc/bridge.py`. Extract subscription-related methods.**

Move subscription polling, sync operations, and long-running watchers to `bridge_subscriptions.py`. Keep core query/mutation methods in `bridge.py`.

**Step 2: Create `mc/bridge_subscriptions.py`** as a mixin or companion class.

**Step 3: Update imports.**

**Step 4: Run tests**

```bash
uv run pytest tests/mc/test_bridge.py -v --timeout=30
```

**Step 5: Commit**

```bash
git add mc/bridge.py mc/bridge_subscriptions.py
git commit -m "refactor: extract bridge_subscriptions from bridge.py"
```

---

### Task 8: Split planner.py (850 LOC)

**Files:**
- Modify: `mc/planner.py` — LLM decomposition core (~500 LOC)
- Create: `mc/plan_parser.py` — extraction/parsing helpers (~350 LOC)

**Step 1: Read `mc/planner.py`. Extract parsing/extraction functions.**

Move helper functions that parse LLM responses, extract plan steps, and validate plan structure to `plan_parser.py`.

**Step 2: Create `mc/plan_parser.py`** and move functions.

**Step 3: Run tests**

```bash
uv run pytest tests/mc/test_planner.py -v --timeout=30
```

**Step 4: Commit**

```bash
git add mc/planner.py mc/plan_parser.py
git commit -m "refactor: extract plan_parser from planner.py"
```

---

### Task 9: Group ask_user modules into sub-package

**Files:**
- Create: `mc/ask_user/__init__.py`
- Move: `mc/ask_user_handler.py` → `mc/ask_user/handler.py`
- Move: `mc/ask_user_registry.py` → `mc/ask_user/registry.py`
- Move: `mc/ask_user_watcher.py` → `mc/ask_user/watcher.py`
- Delete: old files
- Modify: all imports referencing `mc.ask_user_handler`, `mc.ask_user_registry`, `mc.ask_user_watcher`

**Step 1: Create sub-package directory**

```bash
mkdir -p mc/ask_user
```

**Step 2: Move files**

```bash
mv mc/ask_user_handler.py mc/ask_user/handler.py
mv mc/ask_user_registry.py mc/ask_user/registry.py
mv mc/ask_user_watcher.py mc/ask_user/watcher.py
```

**Step 3: Create `mc/ask_user/__init__.py`**

```python
"""Ask-user subsystem — interactive question routing to human users."""

from mc.ask_user.handler import AskUserHandler
from mc.ask_user.registry import AskUserRegistry
from mc.ask_user.watcher import AskUserReplyWatcher

__all__ = ["AskUserHandler", "AskUserRegistry", "AskUserReplyWatcher"]
```

**Step 4: Update all imports across the codebase**

Search and replace:
- `from mc.ask_user_handler import` → `from mc.ask_user.handler import`
- `from mc.ask_user_registry import` → `from mc.ask_user.registry import`
- `from mc.ask_user_watcher import` → `from mc.ask_user.watcher import`
- `import mc.ask_user_handler` → `import mc.ask_user.handler`

Check both `mc/` and `tests/` and `vendor/`.

```bash
grep -rn "ask_user_handler\|ask_user_registry\|ask_user_watcher" mc/ tests/ vendor/ --include="*.py"
```

**Step 5: Run tests**

```bash
uv run pytest tests/mc/ -x -q --timeout=30
```

**Step 6: Commit**

```bash
git add mc/ask_user/ mc/ tests/ vendor/
git rm mc/ask_user_handler.py mc/ask_user_registry.py mc/ask_user_watcher.py
git commit -m "refactor: group ask_user modules into mc/ask_user/ sub-package"
```

---

### Task 10: Group mention modules into sub-package

**Files:**
- Create: `mc/mentions/__init__.py`
- Move: `mc/mention_handler.py` → `mc/mentions/handler.py`
- Move: `mc/mention_watcher.py` → `mc/mentions/watcher.py`
- Delete: old files
- Modify: all imports

**Step 1: Create sub-package**

```bash
mkdir -p mc/mentions
```

**Step 2: Move files**

```bash
mv mc/mention_handler.py mc/mentions/handler.py
mv mc/mention_watcher.py mc/mentions/watcher.py
```

**Step 3: Create `mc/mentions/__init__.py`**

```python
"""Mentions subsystem — @mention detection and routing across task threads."""

from mc.mentions.handler import handle_mention, extract_mentions, is_mention_message
from mc.mentions.watcher import MentionWatcher

__all__ = ["handle_mention", "extract_mentions", "is_mention_message", "MentionWatcher"]
```

**Step 4: Update all imports**

```bash
grep -rn "mention_handler\|mention_watcher" mc/ tests/ vendor/ --include="*.py"
```

Replace `mc.mention_handler` → `mc.mentions.handler`, `mc.mention_watcher` → `mc.mentions.watcher`.

**Step 5: Run tests**

```bash
uv run pytest tests/mc/ -x -q --timeout=30
```

**Step 6: Commit**

```bash
git add mc/mentions/ mc/ tests/ vendor/
git rm mc/mention_handler.py mc/mention_watcher.py
git commit -m "refactor: group mention modules into mc/mentions/ sub-package"
```

---

### Task 11: Define public API and clean up code

**Files:**
- Modify: `mc/__init__.py` — add `__all__`
- Modify: `mc/hooks/__init__.py` — add `__all__`
- Create: `mc/utils.py` — shared helpers
- Modify: `mc/chat_handler.py` — remove unused imports
- Modify: `mc/executor.py` — remove unused imports
- Modify: `mc/types.py` — remove unused `Path` import
- Modify: `mc/mention_handler.py` → now `mc/mentions/handler.py` — remove unused import
- Modify: `mc/plan_negotiator.py` — remove unused imports
- Modify: `mc/orientation.py` → rename to `mc/agent_orientation.py`
- Modify: `mc/memory/index.py` — extract magic numbers to constants
- Modify: `mc/memory/store.py` — composition instead of inheritance

**Step 1: Add `__all__` to `mc/__init__.py`**

Read `mc/types.py` to identify all public types, enums, and constants. Then update `mc/__init__.py`:

```python
__all__ = [
    # Core
    "ConvexBridge",
    # Enums
    "TaskStatus", "StepStatus", "TrustLevel", "AgentStatus", "MessageType", "ThreadMessageType",
    # Data classes
    "TaskData", "AgentData", "ArtifactData", "MessageData",
    "ExecutionPlan", "ExecutionPlanStep",
    # Constants
    "LEAD_AGENT_NAME", "NANOBOT_AGENT_NAME",
    # Sub-packages
    "memory",
]
```

**Step 2: Add `__all__` to `mc/hooks/__init__.py`**

```python
from mc.hooks.handler import BaseHandler
from mc.hooks.discovery import discover_handlers

__all__ = ["BaseHandler", "discover_handlers"]
```

**Step 3: Create `mc/utils.py` with shared helpers**

```python
"""Shared utility functions for the mc package."""


def as_positive_int(value: object, *, default: int) -> int:
    """Convert a value to a positive integer, falling back to default."""
    try:
        n = int(value)  # type: ignore[arg-type]
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default
```

Then update `executor.py`, `step_dispatcher.py`, `plan_materializer.py`, `planner.py` to import from `mc.utils`.

**Step 4: Remove unused imports**

- `mc/chat_handler.py:26` — remove `datetime, timezone` from `from datetime import datetime, timezone`
- `mc/executor.py` — remove unused `CCTaskResult`
- `mc/types.py` — remove unused `Path`
- `mc/mentions/handler.py` — remove unused `LEAD_AGENT_NAME`
- `mc/plan_negotiator.py` — remove unused `LEAD_AGENT_NAME`, `ConvexBridge`

**Step 5: Rename `orientation.py`**

```bash
git mv mc/orientation.py mc/agent_orientation.py
```

Update all imports: `grep -rn "mc.orientation\|mc\.orientation" mc/ tests/ vendor/ --include="*.py"`

**Step 6: Extract magic numbers in `memory/index.py`**

Add at module level:
```python
_DEFAULT_CHUNK_SIZE = 500
_DEFAULT_CHUNK_OVERLAP = 50
```

Replace hardcoded values at lines ~244, ~264, ~317.

**Step 7: Refactor HybridMemoryStore to use composition**

In `mc/memory/store.py`, change from:
```python
class HybridMemoryStore(MemoryStore):
```
to wrapping MemoryStore as a private field and delegating calls.

**Step 8: Add CC abbreviation comment**

In `mc/types.py`, at the first `CC_` constant, add:
```python
# CC = Claude Code
CC_MODEL_PREFIX = ...
```

**Step 9: Run full test suite**

```bash
uv run pytest tests/mc/ -x -q --timeout=30
```

**Step 10: Run ruff**

```bash
uv run ruff check mc/ --fix
```

**Step 11: Commit**

```bash
git add mc/ tests/
git commit -m "refactor: define public API, extract utils, clean imports, rename orientation"
```

---

## Phase 3: Documentation

### Task 12: Rewrite CLAUDE.md

**Files:**
- Backup: `CLAUDE.md` → `CLAUDE.md.bkp`
- Rewrite: `CLAUDE.md`

**Step 1: Backup current**

```bash
cp CLAUDE.md CLAUDE.md.bkp
```

**Step 2: Write new CLAUDE.md**

Structure:
- Feature Development Process (BMad workflow, without internal details)
- Dev agent models: `gpt-5.4` and `claude-sonnet-4-6`; Opus as orchestrator
- Python Environment (`uv run python`, `uv run pytest`)
- Project Structure (mc/, vendor/, dashboard/, boot.py)
- Code Conventions (ruff, type hints, 100-char lines)
- Upstream Sync instructions

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: rewrite CLAUDE.md for public open-source use"
```

---

### Task 13: Create ARCHITECTURE.md

**Files:**
- Create: `docs/ARCHITECTURE.md`

**Content structure:**
1. High-level system overview (ASCII diagram)
2. Core components: Bridge, Orchestrator, Executor, Gateway, Memory, Hooks
3. Data flow: Task creation → Planning → Step dispatch → Agent execution → Completion
4. State machines: Task lifecycle (inbox → assigned → in_progress → done/crashed), Step lifecycle
5. Extension points: adding agents, hooks, skills
6. Vendor relationship: nanobot upstream, claude-code backend

**Step 1: Read key source files for accurate descriptions**

Read module docstrings from: `mc/bridge.py`, `mc/orchestrator.py`, `mc/executor.py`, `mc/gateway.py`, `mc/memory/__init__.py`, `mc/hooks/handler.py`, `mc/state_machine.py`

**Step 2: Write `docs/ARCHITECTURE.md`**

**Step 3: Commit**

```bash
git add -f docs/ARCHITECTURE.md
git commit -m "docs: add ARCHITECTURE.md with component overview and data flow"
```

---

### Task 14: Create CONTRIBUTING.md, CHANGELOG.md, KNOWN_ISSUES.md

**Files:**
- Create: `CONTRIBUTING.md`
- Create: `CHANGELOG.md`
- Create: `KNOWN_ISSUES.md`

**Step 1: Write CONTRIBUTING.md**

Sections: Prerequisites, Development Setup (`uv sync`), Code Style (ruff config), Testing (`uv run pytest`), PR Workflow (fork → branch → PR), Adding Features (agents, hooks, skills).

**Step 2: Write CHANGELOG.md**

```markdown
# Changelog

## [0.1.0] - 2026-03-05

### Added
- Multi-agent task orchestration with LLM-based planning
- Hybrid memory system (BM25 + vector search)
- Task state machines with review routing
- Agent Gateway with process monitoring and auto-restart
- Hook system for extensible event handling
- ConvexBridge for backend communication
- CLI for lifecycle management
- Next.js + Convex dashboard
```

**Step 3: Write KNOWN_ISSUES.md**

Document the 3 pending TODOs and pre-existing test failures from MEMORY.md.

**Step 4: Commit**

```bash
git add CONTRIBUTING.md CHANGELOG.md KNOWN_ISSUES.md
git commit -m "docs: add CONTRIBUTING, CHANGELOG, and KNOWN_ISSUES"
```

---

### Task 15: Update README.md

**Files:**
- Modify: `README.md`

**Step 1: Read current README.md**

Understand existing structure and nanobot sections to preserve.

**Step 2: Add/update sections**

- Update project name references to `nanobot-mcontrol`
- Add "Mission Control" section: what it is, components, quickstart
- Add "Dashboard" section: setup, structure, connection to backend
- Add "Development" section: unified dev instructions
- Link to ARCHITECTURE.md, CONTRIBUTING.md

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with Mission Control, Dashboard, and Development sections"
```

---

### Task 16: Add module docstrings to 31 files

**Files:**
- Modify: all 31 files in `mc/` currently missing module docstrings

**Step 1: Identify files without docstrings**

```bash
for f in $(find mc -name "*.py" -not -path "*__pycache__*"); do
  head -1 "$f" | grep -q '"""' || echo "$f"
done
```

**Step 2: Add 1-2 line module docstrings to each file**

Read each file briefly to understand its purpose, then add a module docstring.

**Step 3: Run ruff**

```bash
uv run ruff check mc/ --fix
```

**Step 4: Commit**

```bash
git add mc/
git commit -m "docs: add module docstrings to all mc/ source files"
```

---

## Phase 4: Tests

### Task 17: Add tests for memory/policy.py and memory/service.py

**Files:**
- Read: `mc/memory/policy.py`
- Read: `mc/memory/service.py`
- Create: `tests/mc/memory/test_policy.py`
- Create: `tests/mc/memory/test_service.py`

**Step 1: Read source files to understand functions/classes**

**Step 2: Write failing tests for policy.py**

Test `is_memory_markdown_file()`, `is_allowed_memory_file()`, `find_invalid_memory_files()` with valid and invalid inputs.

**Step 3: Run tests to verify they pass** (these are tests for existing code)

```bash
uv run pytest tests/mc/memory/test_policy.py -v --timeout=30
```

**Step 4: Write failing tests for service.py**

Test core service functions with mocked dependencies.

**Step 5: Run tests**

```bash
uv run pytest tests/mc/memory/test_service.py -v --timeout=30
```

**Step 6: Commit**

```bash
git add tests/mc/memory/test_policy.py tests/mc/memory/test_service.py
git commit -m "test: add unit tests for memory policy and service modules"
```

---

### Task 18: Add tests for hooks subsystem

**Files:**
- Read: `mc/hooks/dispatcher.py`, `mc/hooks/discovery.py`, `mc/hooks/handler.py`, `mc/hooks/config.py`, `mc/hooks/context.py`, `mc/hooks/ipc_sync.py`
- Create: `tests/mc/hooks/__init__.py`
- Create: `tests/mc/hooks/test_dispatcher.py`
- Create: `tests/mc/hooks/test_discovery.py`
- Create: `tests/mc/hooks/test_handler.py`
- Create: `tests/mc/hooks/test_config.py`
- Create: `tests/mc/hooks/test_context.py`
- Create: `tests/mc/hooks/test_ipc_sync.py`

**Step 1: Create test directory**

```bash
mkdir -p tests/mc/hooks/handlers
touch tests/mc/hooks/__init__.py
touch tests/mc/hooks/handlers/__init__.py
```

**Step 2: Read each source file and write tests**

For each file, test the public API with mocked dependencies. Focus on:
- `BaseHandler` subclassing and method dispatch
- `discover_handlers()` finding handlers in the handlers/ directory
- `HookDispatcher` routing events to correct handlers
- `HookConfig` dataclass construction
- `HookContext` lifecycle
- `ipc_sync` client behavior with mocked socket

**Step 3: Run tests**

```bash
uv run pytest tests/mc/hooks/ -v --timeout=30
```

**Step 4: Commit**

```bash
git add tests/mc/hooks/
git commit -m "test: add unit tests for hooks subsystem"
```

---

### Task 19: Add tests for hook handlers

**Files:**
- Read: `mc/hooks/handlers/agent_tracker.py`, `plan_capture.py`, `plan_tracker.py`, `skill_tracker.py`
- Create: `tests/mc/hooks/handlers/test_agent_tracker.py`
- Create: `tests/mc/hooks/handlers/test_plan_capture.py`
- Create: `tests/mc/hooks/handlers/test_plan_tracker.py`
- Create: `tests/mc/hooks/handlers/test_skill_tracker.py`

**Step 1: Read each handler source file**

**Step 2: Write tests for each handler**

Test event handling methods with mocked bridge/context.

**Step 3: Run tests**

```bash
uv run pytest tests/mc/hooks/handlers/ -v --timeout=30
```

**Step 4: Commit**

```bash
git add tests/mc/hooks/handlers/
git commit -m "test: add unit tests for hook handler implementations"
```

---

### Task 20: Add tests for mention_watcher

**Files:**
- Read: `mc/mentions/watcher.py` (was `mc/mention_watcher.py`)
- Create: `tests/mc/test_mention_watcher.py`

**Step 1: Read source, identify public methods**

**Step 2: Write tests with mocked bridge**

Test polling behavior, mention detection, routing logic.

**Step 3: Run tests**

```bash
uv run pytest tests/mc/test_mention_watcher.py -v --timeout=30
```

**Step 4: Commit**

```bash
git add tests/mc/test_mention_watcher.py
git commit -m "test: add unit tests for MentionWatcher"
```

---

### Task 21: Fix existing test failures and reorganize test files

**Files:**
- Modify: `tests/mc/test_cli_tasks.py` — fix `test_create_with_title` assertion
- Modify: `mc/executor.py` — fix async mock warning at line ~1659
- Move: 12 test files from `tests/` root to `tests/mc/`

**Step 1: Fix CLI test**

Read `tests/mc/test_cli_tasks.py` and the CLI code it tests. Fix the assertion to match actual output (either fix the test expectation or fix the CLI output to include "Status: inbox").

**Step 2: Fix async mock warning**

Read `mc/executor.py` around line 1659. Ensure `set_ask_user_handler` properly handles async callables.

**Step 3: Move root-level test files**

```bash
git mv tests/test_channel_manager_mc.py tests/mc/
git mv tests/test_cli_input.py tests/mc/
git mv tests/test_commands.py tests/mc/
git mv tests/test_consolidate_offset.py tests/mc/
git mv tests/test_cron_commands.py tests/mc/
git mv tests/test_cron_service.py tests/mc/
git mv tests/test_cron_tool.py tests/mc/
git mv tests/test_email_channel.py tests/mc/
git mv tests/test_filesystem_memory_guard.py tests/mc/
git mv tests/test_init_wizard.py tests/mc/
git mv tests/test_mc_channel.py tests/mc/
git mv tests/test_tool_validation.py tests/mc/
```

**Step 4: Fix any broken imports in moved test files**

**Step 5: Run full test suite**

```bash
uv run pytest tests/mc/ -v --timeout=30
```

Expected: 0 failures.

**Step 6: Commit**

```bash
git add tests/
git commit -m "test: fix failing tests and reorganize test files into tests/mc/"
```

---

### Task 22: Improve test infrastructure

**Files:**
- Modify: `tests/conftest.py`

**Step 1: Identify common mock patterns**

```bash
grep -rn "_make_bridge\|MagicMock.*bridge\|mock_bridge" tests/mc/ --include="*.py" | head -20
```

**Step 2: Add shared fixtures to conftest.py**

```python
@pytest.fixture
def mock_bridge():
    """Create a mock ConvexBridge for tests."""
    bridge = MagicMock()
    bridge.list_agents = AsyncMock(return_value=[])
    bridge.query_tasks = AsyncMock(return_value=[])
    return bridge
```

**Step 3: Run full test suite to verify fixtures don't break anything**

```bash
uv run pytest tests/mc/ -x -q --timeout=30
```

**Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add shared mock fixtures to conftest.py"
```

---

### Task 23: Final verification

**Step 1: Run full test suite**

```bash
uv run pytest tests/mc/ -v --timeout=60
```

Expected: 1082+ tests, 0 failures.

**Step 2: Run ruff on all code**

```bash
uv run ruff check mc/ tests/ --fix
```

**Step 3: Verify no file in mc/ exceeds 600 LOC**

```bash
wc -l mc/*.py mc/**/*.py | sort -rn | head -10
```

**Step 4: Verify all docs exist**

```bash
ls -la CLAUDE.md CONTRIBUTING.md CHANGELOG.md KNOWN_ISSUES.md README.md docs/ARCHITECTURE.md
```

**Step 5: Verify package name**

```bash
grep "^name" pyproject.toml
```

Expected: `name = "nanobot-mcontrol"`

**Step 6: Final commit if any remaining changes**

```bash
git status
```
