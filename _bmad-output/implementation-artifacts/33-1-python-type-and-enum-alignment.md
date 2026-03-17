# Story 33.1: Python Type and Enum Alignment

Status: ready-for-dev

## Story

As a developer,
I want all Python enums and types aligned with the cross-service naming contract,
so that Python, Convex, and TypeScript share a single vocabulary without drift.

## Acceptance Criteria

1. `TaskStatus` enum includes `DELETED = "deleted"`
2. `MessageType` enum includes `COMMENT = "comment"`
3. `ActivityEventType` enum includes all 12 missing values from Convex schema
4. StrEnum backport removed (project requires Python 3.11+)
5. All `Optional[X]` replaced with `X | None`
6. All 3 non-init files have `from __future__ import annotations`
7. All dual-key lookups removed — data must arrive in one format
8. Duplicate `list_active_registry_view` removed
9. Unused `asyncio` import removed from `mc/cli/__init__.py`
10. `uv run ruff check mc/` passes with zero errors

## Tasks / Subtasks

- [ ] Task 1: Fix enums in `mc/types.py` (AC: #1, #2, #3)
  - [ ] Add `DELETED = "deleted"` to `TaskStatus` enum after line 96
  - [ ] Add `COMMENT = "comment"` to `MessageType` enum after line 180
  - [ ] Add 12 missing values to `ActivityEventType` enum (lines 136-169):
    - `TASK_REASSIGNED = "task_reassigned"`
    - `AGENT_DELETED = "agent_deleted"`
    - `AGENT_RESTORED = "agent_restored"`
    - `FILE_ATTACHED = "file_attached"`
    - `TASK_MERGED = "task_merged"`
    - `AGENT_OUTPUT = "agent_output"`
    - `BOARD_CREATED = "board_created"`
    - `BOARD_UPDATED = "board_updated"`
    - `BOARD_DELETED = "board_deleted"`
    - `STEP_CREATED = "step_created"`
    - `STEP_STATUS_CHANGED = "step_status_changed"`
    - `STEP_UNBLOCKED = "step_unblocked"`

- [ ] Task 2: Remove StrEnum backport in `mc/types.py` (AC: #4)
  - [ ] Replace lines 16-24 (version check + backport) with `from enum import StrEnum`
  - [ ] Remove `import sys` from line 11 if no longer used elsewhere

- [ ] Task 3: Fix `Optional[]` usages in `mc/infrastructure/agents/yaml_validator.py` (AC: #5)
  - [ ] Remove `from typing import Optional` (line 17)
  - [ ] Add `from __future__ import annotations` at top
  - [ ] Replace all 7 `Optional[X]` with `X | None` (lines 49-55)

- [ ] Task 4: Add missing `from __future__ import annotations` (AC: #6)
  - [ ] `mc/contexts/planning/title_generation.py`
  - [ ] `mc/domain/utils.py`
  - [ ] `mc/hooks/config.py`

- [ ] Task 5: Eliminate dual-key lookups in `mc/types.py` `ExecutionPlan.from_dict()` (AC: #7)
  - [ ] Lines 299-360: Remove all `or raw_step.get("camelCase")` patterns
  - [ ] Ensure callers always send snake_case data (bridge handles conversion)
  - [ ] Document that `ExecutionPlan.from_dict()` only accepts snake_case keys
  - [ ] If LLM-generated plans arrive in camelCase, convert once at the entry point before calling `from_dict()`

- [ ] Task 6: Fix duplicate and unused code (AC: #8, #9)
  - [ ] Remove duplicate `list_active_registry_view` at `mc/bridge/facade_mixins.py:274-276`
  - [ ] Remove unused `import asyncio` at `mc/cli/__init__.py:5`

- [ ] Task 7: Run linter to verify (AC: #10)
  - [ ] `uv run ruff check mc/ --fix`
  - [ ] `uv run ruff format mc/`

## Dev Notes

- The dual-key lookup elimination (Task 5) is the riskiest change. LLM-generated execution plans may arrive in camelCase. Identify all callers of `ExecutionPlan.from_dict()` and ensure data passes through `_convert_keys_to_snake()` before reaching it.
- The ActivityEventType additions are purely additive — no existing code breaks.
- The StrEnum backport removal is safe because `pyproject.toml` already requires `>=3.11`.

### References

- [Source: agent_docs/code_conventions/cross_service_naming.md] — canonical status and event values
- [Source: agent_docs/code_conventions/python.md] — type hint conventions
- [Source: mc/types.py] — all enum definitions and dataclasses
- [Source: mc/bridge/key_conversion.py] — bridge conversion functions
- [Source: dashboard/convex/schema.ts:333-377] — Convex activity event types
- [Source: dashboard/convex/schema.ts:113-124] — Convex task status validator
