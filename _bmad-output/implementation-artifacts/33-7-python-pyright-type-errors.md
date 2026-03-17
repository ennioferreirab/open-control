# Story 33.7: Fix Python Pyright Type Errors

Status: ready-for-dev

## Story

As a developer,
I want pyright type checking to pass on the Python codebase,
so that type mismatches are caught before runtime and the codebase has verified type safety.

## Current State

167 errors, 8 warnings across 26 files. The top offender is `facade_mixins.py` (105 errors) — mostly `-> Any` returns from bridge calls.

## Acceptance Criteria

1. `uv run pyright mc/` reports zero errors
2. No `# type: ignore` without a documented reason
3. No behavioral changes — only type annotation fixes

## Tasks / Subtasks

- [ ] Task 1: Fix `mc/bridge/facade_mixins.py` (105 errors)
  - [ ] The majority are `-> Any` return types from Convex bridge calls
  - [ ] Define `TypedDict` types for common Convex document shapes (TaskDoc, AgentDoc, StepDoc, etc.)
  - [ ] Replace `-> Any` with proper return types on public methods
  - [ ] Replace `dict[str, Any]` args with typed alternatives where feasible

- [ ] Task 2: Fix `mc/bridge/__init__.py` (10 errors)
  - [ ] Same pattern as facade_mixins — typed returns for bridge methods

- [ ] Task 3: Fix `mc/contexts/interactive/adapters/codex_app_server.py` (7 errors)
  - [ ] All `reportOptionalMemberAccess` — add null checks before accessing optional members

- [ ] Task 4: Fix `mc/runtime/workers/inbox.py` (6 errors)
  - [ ] `Any | None` passed where `str` expected for `task_id`
  - [ ] Add proper type narrowing: `assert task_id is not None` or early return

- [ ] Task 5: Fix `mc/contexts/provider_cli/providers/nanobot.py` (5 errors)
  - [ ] `bytes | str` type mismatches — decode bytes to str before string operations

- [ ] Task 6: Fix `mc/cli/agents.py` (5 errors)
  - [ ] Optional subscript access — add null checks

- [ ] Task 7: Fix remaining files (29 errors across 18 files)
  - [ ] `mc/runtime/nanobot_interactive_session.py` — 3 errors: `_Environ` vs `dict` type
  - [ ] `mc/contexts/interactive/types.py` — 3 errors
  - [ ] `mc/application/execution/post_processing.py` — 3 errors
  - [ ] `mc/runtime/interactive_transport.py` — 2 errors
  - [ ] `mc/memory/index.py` — 2 errors: `int | None` vs `ConvertibleToInt`
  - [ ] `mc/contexts/provider_cli/providers/claude_code.py` — 2 errors
  - [ ] 12 files with 1 error each — miscellaneous type fixes

## Dev Notes

- Task 1 is the bulk of the work. Consider creating a `mc/bridge/types.py` with TypedDicts for Convex document shapes. This aligns with the Python conventions doc recommendation.
- Many errors are in the bridge layer where Convex returns untyped dicts. The fix is to add proper type annotations, not to suppress errors.
- The `nanobot.py` provider has `bytes | str` issues from subprocess output — needs explicit `.decode()` calls.
- Splitting this into sub-stories (bridge layer, interactive layer, runtime layer) is acceptable.
