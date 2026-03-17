# Story 33.6: Fix Remaining Python Ruff Violations

Status: ready-for-dev

## Story

As a developer,
I want all ruff violations resolved so the linter passes clean,
so that CI can enforce zero-tolerance on lint errors going forward.

## Current State

62 violations across 28 files. All are manual-fix only (auto-fix already applied).

## Acceptance Criteria

1. `uv run ruff check mc/ tests/mc/` passes with zero errors
2. No behavioral changes — only lint compliance fixes

## Tasks / Subtasks

- [ ] Task 1: Fix B904 `raise-without-from-inside-except` (19 instances)
  - [ ] `mc/cli/config.py` — 9 instances: add `from exc` to `raise typer.Exit(1)` inside `except` blocks
  - [ ] `mc/cli/lifecycle.py` — 4 instances: same pattern
  - [ ] `mc/cli/tasks.py` — 2 instances: same pattern
  - [ ] `mc/contexts/execution/executor.py` — 1 instance
  - [ ] `mc/contexts/planning/supervisor.py` — 1 instance
  - [ ] `mc/memory/store.py` — 1 instance
  - [ ] `tests/mc/bridge/test_retry.py` — 1 instance

- [ ] Task 2: Fix RUF012 `mutable-class-default` (30 instances)
  - [ ] `mc/hooks/handler.py` — 1 instance: annotate with `ClassVar`
  - [ ] `mc/hooks/handlers/*.py` — 5 instances across agent_tracker, mc_plan_sync, plan_capture, plan_tracker, skill_tracker
  - [ ] `tests/mc/hooks/test_handler.py` — 11 instances
  - [ ] `tests/mc/hooks/test_dispatcher.py` — 5 instances
  - [ ] `tests/mc/test_hook_factory.py` — 3 instances
  - [ ] `tests/mc/provider_cli/test_tui_retirement.py` — 1 instance
  - [ ] `tests/mc/test_cli_lifecycle.py` — 1 instance
  - [ ] Pattern: add `ClassVar[list[...]]` annotation or move to `__init__`

- [ ] Task 3: Fix RUF006 `asyncio-dangling-task` (5 instances)
  - [ ] `mc/runtime/workers/kickoff.py` — 2 instances: store task reference or add `# noqa: RUF006` with comment
  - [ ] `mc/contexts/interactive/adapters/claude_code.py` — 1 instance
  - [ ] `mc/contexts/interactive/adapters/codex.py` — 1 instance
  - [ ] `mc/contexts/interactive/adapters/nanobot.py` — 1 instance

- [ ] Task 4: Fix remaining minor violations (8 instances)
  - [ ] `mc/bridge/facade_mixins.py` — F811: remove duplicate `list_active_registry_view`
  - [ ] `mc/cli/agents.py` — RUF001: replace ambiguous EN DASH with HYPHEN-MINUS
  - [ ] `tests/mc/infrastructure/providers/test_tool_adapters.py` — RUF002: same in docstring
  - [ ] `tests/mc/test_gateway.py` — RUF002: same in docstring
  - [ ] `tests/mc/test_bridge.py` — B017 x2: use specific exception instead of `Exception`
  - [ ] `tests/mc/test_interactive_claude_adapter.py` — RUF043: use raw string in `pytest.raises(match=)`

## Dev Notes

- B904 fixes are mechanical: `raise typer.Exit(1)` → `raise typer.Exit(1) from exc` (or `from None` if the original error is already logged)
- RUF012: for test classes where `events = [...]` is a class-level list, add `ClassVar` annotation. Import from `typing` if needed.
- RUF006: fire-and-forget tasks are intentional in some cases. Use `# noqa: RUF006` with a comment explaining why, or store the task reference.
