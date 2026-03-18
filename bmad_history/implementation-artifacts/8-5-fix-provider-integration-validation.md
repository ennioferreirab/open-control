# Story 8.5: Fix Provider Integration & Convex Validation

Status: done

## Story

As a **user**,
I want the gateway to properly surface OAuth/provider errors and the Convex activity schema to be properly validated,
So that I get clear actionable errors when the OAuth provider fails and the activity feed data is always valid.

## Problem Statement

Adversarial code review of Story 8.1 found integration and validation issues:

1. **Unvalidated activity eventType**: The `activities:create` Convex mutation accepts `eventType: v.string()` instead of the union type, bypassing schema validation. Invalid event types can be written.
2. **OAuth errors are buried**: When `_make_provider` fails (e.g. expired OAuth token), the error goes through `handle_agent_crash()` and gets buried in the task thread instead of being surfaced as a clear actionable message.
3. **Duplicated provider logic**: `executor.py:_make_provider()` duplicates logic from `nanobot/cli/commands.py:_make_provider()`. Changes to one won't be reflected in the other.
4. **Private SkillsLoader API**: `sync_skills` in gateway.py uses private methods (`_strip_frontmatter`, `_parse_nanobot_metadata`, `_check_requirements`, `_get_missing_requirements`).
5. **Fragile timestamp comparison**: `_write_back_convex_agents` parses ISO timestamps and compares against local file mtime with timezone handling issues.

## Acceptance Criteria

1. **Given** the Python bridge calls `activities:create` with an invalid eventType, **Then** Convex rejects it with a validation error (not silently accepting)
2. **Given** the executor's `_make_provider` raises `AnthropicOAuthExpired`, **Then** the task thread gets a clear system message with the login command AND a `system_error` activity event is created
3. **Given** any provider configuration error in the gateway, **Then** the error message includes the specific action the user needs to take (e.g. "Run: nanobot provider login anthropic-oauth")
4. **Given** a new LLM provider is added to the CLI, **Then** the gateway executor uses the same provider resolution logic (shared code, not duplicated)
5. **Given** `sync_skills` is called, **Then** it uses only public APIs from SkillsLoader (no private `_` methods)
6. **Given** `_write_back_convex_agents` compares timestamps, **Then** both sides use UTC-aware datetime objects for correct comparison

## Tasks / Subtasks

- [x] Task 1: Fix `activities:create` eventType validation (AC: #1)
  - [x] 1.1: In `dashboard/convex/activities.ts:create`, change `eventType: v.string()` to `eventType: v.union(v.literal("task_created"), v.literal("task_assigned"), ...)` matching the full union type from schema.ts
  - [x] 1.2: Remove the `as` type cast on the eventType (it was masking the validation bypass)
  - [x] 1.3: Add `v.literal("bulk_clear_done")` and `v.literal("agent_config_updated")` to the union if not already in schema.ts activities eventType

- [x] Task 2: Surface OAuth/provider errors prominently (AC: #2, #3)
  - [x] 2.1: In `executor.py:_execute_task()`, catch provider-specific exceptions (`AnthropicOAuthExpired`, `ProviderError`) BEFORE the general except block
  - [x] 2.2: For provider errors, write a system message with clear instructions: "Provider error: {message}. Action: {specific_action}"
  - [x] 2.3: Create a `system_error` activity event with the provider error details so it appears in the dashboard activity feed (not just buried in thread)
  - [x] 2.4: Log the error prominently to stdout with `logger.error` including the action command

- [x] Task 3: Extract shared provider factory (AC: #4)
  - [x] 3.1: Create `nanobot/mc/provider_factory.py` with a `create_provider(model: str | None = None) -> tuple[Any, str]` function
  - [x] 3.2: Move the provider resolution logic from `executor.py:_make_provider()` into the new module
  - [x] 3.3: Update `executor.py` to import from `provider_factory.py` instead of having inline logic
  - [x] 3.4: Update `nanobot/cli/commands.py` to also import from `provider_factory.py` (remove its local `_make_provider`)
  - [x] 3.5: Ensure the factory handles all provider types: anthropic_oauth, openai_codex, custom, litellm (default)

- [x] Task 4: Replace private SkillsLoader API usage (AC: #5)
  - [x] 4.1: In `gateway.py:sync_skills()`, replace `loader._strip_frontmatter(raw_content)` with `loader.get_skill_body(name)`
  - [x] 4.2: Replace `loader._parse_nanobot_metadata()` and `loader._check_requirements()` with `loader.is_skill_available(name)` and `loader.get_missing_requirements(name)`
  - [x] 4.3: Added public methods to SkillsLoader: `get_skill_body()`, `is_skill_available()`, `get_missing_requirements()`, `get_nanobot_metadata()`
  - [x] 4.4: Updated `nanobot/agent/skills.py` with the new public methods

- [x] Task 5: Fix fragile timestamp comparison (AC: #6)
  - [x] 5.1: Extracted `_parse_utc_timestamp()` helper in gateway.py; both Convex `lastActiveAt` and local mtime use UTC-aware datetime objects
  - [x] 5.2: Handle edge cases: missing timezone info (naive -> UTC), `Z` suffix, `+00:00` suffix, non-string/None input
  - [x] 5.3: If timestamp parsing fails, skip the write-back for that agent with a warning log (don't crash)

- [x] Task 6: Update/add tests
  - [x] 6.1: Convex schema validation is enforced by the `v.union()` type on the mutation arg (runtime validated by Convex)
  - [x] 6.2: 6 tests for provider error surfacing (system messages, activity events, no auto-retry, task crash, OAuth login command, cleanup)
  - [x] 6.3: 8 tests for provider factory (all provider types, model override, import failure, ProviderError attributes)
  - [x] 6.4: 7 tests for SkillsLoader public API (get_skill_body, is_skill_available, get_missing_requirements, no private calls)
  - [x] 6.5: 10 tests for timestamp handling (_parse_utc_timestamp edge cases, write-back comparison)

## Dev Notes

### Critical Architecture Requirements

- **Single integration point**: ALL Convex access goes through `ConvexBridge`.
- **Provider factory location**: `nanobot/mc/provider_factory.py` -- importable from both `executor.py` and `cli/commands.py` without circular imports.
- **SkillsLoader**: The existing SkillsLoader in `nanobot/agent/skills.py` may need public method additions. Be careful with the `nanobot.agent` package import chain (heavy deps).

### Key File References

| Component | File | What to change |
|-----------|------|----------------|
| Activities mutation | `dashboard/convex/activities.ts:4-40` | Fix eventType validation |
| Activities schema | `dashboard/convex/schema.ts:72-100` | Reference for valid eventType values |
| Executor task execution | `nanobot/mc/executor.py:227-297` | Add provider error handling |
| Provider factory (new) | `nanobot/mc/provider_factory.py` | Extract from executor.py |
| Executor _make_provider | `nanobot/mc/executor.py:34-74` | Replace with factory import |
| CLI _make_provider | `nanobot/cli/commands.py` | Replace with factory import |
| Skills sync | `nanobot/mc/gateway.py:201-287` | Replace private API usage |
| SkillsLoader | `nanobot/agent/skills.py` | Add public methods if needed |
| Write-back timestamps | `nanobot/mc/gateway.py:83-127` | Fix timezone handling |
| Tests | `tests/mc/test_gateway.py` | Update and add tests |

## File List

| File | Action | Description |
|------|--------|-------------|
| `dashboard/convex/activities.ts` | Modified | Changed `eventType: v.string()` to `v.union(v.literal(...))` matching schema; removed `as` type cast |
| `nanobot/mc/provider_factory.py` | Created | Shared provider factory with `create_provider()` and `ProviderError` |
| `nanobot/mc/executor.py` | Modified | Delegated `_make_provider` to factory; added `_handle_provider_error`, `_PROVIDER_ERRORS`, `_provider_error_action` |
| `nanobot/cli/commands.py` | Modified | Replaced local `_make_provider` with delegation to `provider_factory.create_provider()` |
| `nanobot/mc/gateway.py` | Modified | Added `_parse_utc_timestamp()` helper; replaced private SkillsLoader calls with public API; compacted to stay under 500 lines |
| `nanobot/agent/skills.py` | Modified | Added public methods: `get_skill_body()`, `is_skill_available()`, `get_missing_requirements()`, `get_nanobot_metadata()` |
| `nanobot/mc/types.py` | Modified | Added missing enum values: `TASK_DELETED`, `TASK_RESTORED`, `BULK_CLEAR_DONE` to `ActivityEventType` |
| `tests/mc/test_provider_factory.py` | Created | 8 tests for provider factory (all provider types, import failure, attributes) |
| `tests/mc/test_story_8_5.py` | Created | 26 tests for provider error surfacing, SkillsLoader public API, timestamp handling |

## Change Log

| Date | Change |
|------|--------|
| 2026-02-23 | Task 1: Fixed `activities:create` to use `v.union(v.literal(...))` instead of `v.string()` for eventType validation; removed `as` type cast; added `agent_config_updated`, `agent_activated`, `agent_deactivated` to the union |
| 2026-02-23 | Task 3: Created `nanobot/mc/provider_factory.py` with shared `create_provider()` and `ProviderError`; updated both `executor.py` and `cli/commands.py` to delegate to factory |
| 2026-02-23 | Task 2: Added `_handle_provider_error()` to `TaskExecutor` that catches `ProviderError` and `AnthropicOAuthExpired` separately from general errors; writes system message with action, creates `system_error` activity, transitions to crashed without auto-retry |
| 2026-02-23 | Task 4: Added public methods to SkillsLoader (`get_skill_body`, `is_skill_available`, `get_missing_requirements`, `get_nanobot_metadata`); updated `sync_skills` in gateway.py to use only public API |
| 2026-02-23 | Task 5: Extracted `_parse_utc_timestamp()` helper that handles Z suffix, +00:00 offset, naive timestamps (assumed UTC), and invalid input (returns None); updated `_write_back_convex_agents` to use it with proper logging on parse failure |
| 2026-02-23 | Task 6: Added 34 new tests across 2 test files covering all acceptance criteria; all 89 MC tests pass |
| 2026-02-23 | Bonus: Added `TASK_DELETED`, `TASK_RESTORED`, `BULK_CLEAR_DONE` to Python `ActivityEventType` enum to match Convex schema |
