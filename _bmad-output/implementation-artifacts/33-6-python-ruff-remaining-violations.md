# Story 33.6: Fix Remaining Python Ruff Violations

Status: ready-for-dev

## Story

As a developer,
I want all ruff violations resolved so the linter passes clean,
so that CI can enforce zero-tolerance on lint errors going forward.

## Acceptance Criteria

1. `uv run ruff check mc/ tests/mc/` passes with zero errors
2. No behavioral changes — only lint compliance fixes
3. `uv run ruff format mc/ tests/mc/` stays clean

## Tasks / Subtasks

### Task 1: Fix B904 `raise-without-from-inside-except` (19 instances)

All follow the same pattern: `raise typer.Exit(1)` inside an `except` block without chaining. Fix: add `from None` (the error is already logged via `console.print`).

| File | Lines | Fix |
|------|-------|-----|
| `mc/cli/config.py` | 155, 311, 337, 356, 377, 398, 420, 439, 458 | `raise typer.Exit(1) from None` |
| `mc/cli/lifecycle.py` | 49, 72, 97, 248 | `raise typer.Exit(1) from None` |
| `mc/cli/tasks.py` | 65, 99 | `raise typer.Exit(1) from None` |
| `mc/contexts/execution/executor.py` | 565 | `raise LeadAgentExecutionError(...) from exc` |
| `mc/contexts/planning/supervisor.py` | 113 | `raise LeadAgentExecutionError(...) from exc` |
| `mc/memory/store.py` | 135 | `raise` → `raise ... from exc` |
| `tests/mc/bridge/test_retry.py` | 28 | `raise ConnectionError("fail") from None` |

### Task 2: Fix RUF012 `mutable-class-default` (30 instances)

Add `ClassVar[...]` annotation. Import `from typing import ClassVar` in each file.

**Production code (6 instances):**

| File | Line | Current | Fix |
|------|------|---------|-----|
| `mc/hooks/handler.py` | 23 | `events = []` | `events: ClassVar[list[tuple[str, str \| None]]] = []` |
| `mc/hooks/handlers/agent_tracker.py` | 16 | `events = [("AgentOutput", None)]` | `events: ClassVar[list[tuple[str, str \| None]]] = [("AgentOutput", None)]` |
| `mc/hooks/handlers/mc_plan_sync.py` | 24 | `events = [("PostToolUse", "Write"), ...]` | Same pattern with `ClassVar` |
| `mc/hooks/handlers/plan_capture.py` | 15 | `events = [("PostToolUse", "Write")]` | Same pattern |
| `mc/hooks/handlers/plan_tracker.py` | 16 | `events = [("PlanUpdate", None)]` | Same pattern |
| `mc/hooks/handlers/skill_tracker.py` | 18 | `events = [("SkillOutput", None)]` | Same pattern |

**Test code (24 instances):**

| File | Lines | Fix |
|------|-------|-----|
| `tests/mc/hooks/test_handler.py` | 22, 33, 44, 54, 64, 77, 87, 93, 103, 113 | Add `ClassVar` to each inner class `events = [...]` |
| `tests/mc/hooks/test_dispatcher.py` | 16, 22, 28, 34, 40 | Same pattern |
| `tests/mc/test_hook_factory.py` | 129, 137, 145 | Same pattern |
| `tests/mc/provider_cli/test_tui_retirement.py` | 88 | `FORBIDDEN_PATTERNS: ClassVar[list[str]] = [...]` |
| `tests/mc/test_cli_lifecycle.py` | 16 | `instances: ClassVar[list[_FakeProcessManager]] = []` |

### Task 3: Fix RUF006 `asyncio-dangling-task` (5 instances)

These are intentional fire-and-forget tasks. Add `# noqa: RUF006` with explanatory comment.

| File | Line | Comment |
|------|------|---------|
| `mc/runtime/workers/kickoff.py` | 119 | `# noqa: RUF006 -- fire-and-forget: dispatch runs independently` |
| `mc/runtime/workers/kickoff.py` | 171 | Same |
| `mc/contexts/interactive/adapters/claude_code.py` | ~320 | `# noqa: RUF006 -- fire-and-forget: supervision loop runs independently` |
| `mc/contexts/interactive/adapters/codex.py` | ~280 | Same |
| `mc/contexts/interactive/adapters/nanobot.py` | ~250 | Same |

### Task 4: Fix F811 duplicate definition (1 instance)

| File | Line | Fix |
|------|------|-----|
| `mc/bridge/facade_mixins.py` | 275-277 | Delete duplicate `list_active_registry_view` (keep the first at line 267) |

### Task 5: Fix B017 `assert-raises-exception` (3 instances)

| File | Line | Fix |
|------|------|-----|
| `tests/mc/test_bridge.py` | 505 | `pytest.raises(Exception)` → `pytest.raises(RuntimeError)` or the specific exception the bridge raises |
| `tests/mc/test_bridge.py` | 574 | Same |
| `tests/mc/test_bridge.py` | (check for 3rd) | Same pattern |

### Task 6: Fix RUF001/RUF002 ambiguous unicode (3 instances)

| File | Line | Current | Fix |
|------|------|---------|-----|
| `mc/cli/agents.py` | 646 | `–` (EN DASH U+2013) | `−` → `-` (HYPHEN-MINUS U+002D) |
| `tests/mc/infrastructure/providers/test_tool_adapters.py` | 1 | `–` in docstring | Replace with `-` |
| `tests/mc/test_gateway.py` | 1 | `–` in docstring | Replace with `-` |

### Task 7: Fix RUF043 pytest-raises ambiguous pattern (1 instance)

| File | Line | Current | Fix |
|------|------|---------|-----|
| `tests/mc/test_interactive_claude_adapter.py` | 225 | `match="CLAUDE.md generation failed"` | `match=r"CLAUDE\.md generation failed"` |

### Task 8: Verify

- `uv run ruff check mc/ tests/mc/` — zero errors
- `uv run ruff format --check mc/ tests/mc/` — all formatted
