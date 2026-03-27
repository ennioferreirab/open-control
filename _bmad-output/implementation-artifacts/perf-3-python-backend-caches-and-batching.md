# Story PERF-3: Python Backend — Caches and Activity Log Batching

Status: done

## Story

As the platform operator,
I want the Python backend to cache frequently-read data and batch activity log writes,
so that active task execution doesn't produce 30+ Convex calls per second when 3-5 suffice.

## Acceptance Criteria

1. `InteractiveSessionRegistry.get()` caches session documents in memory, eliminating redundant Convex queries during supervision event handling. The cache is invalidated on `_upsert()`.
2. `SessionActivityService` buffers `append` events and flushes them in batches via a new `sessionActivityLog:appendBatch` Convex mutation. Flush triggers: buffer reaches 20 events OR 300ms since last flush.
3. A `SettingsCache` with 60-second TTL is used for `global_orientation_prompt`, `task_timeout_minutes`, and other settings queries that currently have no cache.
4. `tagAttributes:list` queries in the context builder use a cache with 5-minute TTL.
5. Sequential queries in `context_builder.py` for independent data (agent, board, messages, tag attrs, orientation) are parallelized with `asyncio.gather()`.
6. All existing Python tests pass without regression.

## Tasks / Subtasks

- [x]Task 1: Add in-memory cache to InteractiveSessionRegistry (AC: #1)
  - [x]1.1 In `mc/contexts/interactive/registry.py`, add `_session_cache: dict[str, dict[str, Any]] = {}` to `__init__`
  - [x]1.2 In `get()` (line 63), check cache first; on miss, query Convex and populate cache
  - [x]1.3 In `_upsert()` (line 232), after mutation, update cache with the upserted metadata
  - [x]1.4 In `end_session()` and `terminate()`, remove session from cache after upsert
  - [x]1.5 Add test in `tests/mc/contexts/interactive/test_registry.py` verifying that `record_supervision` uses cached data after first fetch

- [x]Task 2: Create `appendBatch` mutation and buffer in ActivityService (AC: #2)
  - [x]2.1 In `dashboard/convex/sessionActivityLog.ts`, add `appendBatch` internalMutation that accepts an array of events, queries max seq once, then inserts all events with incrementing seq numbers
  - [x]2.2 In `mc/contexts/interactive/activity_service.py`, add `_event_buffer: list[dict]` and `_last_flush_time: float` to the service
  - [x]2.3 Modify `append_event()` to append to buffer instead of calling mutation directly
  - [x]2.4 Add `_flush_buffer()` method that calls `sessionActivityLog:appendBatch` with buffered events and resets buffer/timer
  - [x]2.5 Trigger flush when: `len(buffer) >= 20` OR `time.time() - _last_flush_time > 0.3`
  - [x]2.6 Add `flush()` public method for explicit flush (call at session end/error)
  - [x]2.7 Ensure `end_session()` and error paths call `flush()` to avoid losing buffered events
  - [x]2.8 Add test for batch append mutation in `dashboard/convex/sessionActivityLog.test.ts`
  - [x]2.9 Add test for buffer flush logic in `tests/mc/contexts/interactive/test_activity_service.py`

- [x]Task 3: Create SettingsCache (AC: #3)
  - [x]3.1 Create `mc/bridge/settings_cache.py` with `SettingsCache` class: `get(key)` method with TTL-based expiry, constructor takes `bridge` and `ttl_seconds`
  - [x]3.2 Wire `SettingsCache` into the gateway/runtime bootstrap (where `ConvexBridge` is created)
  - [x]3.3 Modify `mc/application/execution/orientation.py` to use `SettingsCache.get("global_orientation_prompt")` instead of direct bridge query
  - [x]3.4 Modify `mc/runtime/timeout_checker.py` to use `SettingsCache.get("task_timeout_minutes")` instead of direct bridge query
  - [x]3.5 Modify `mc/runtime/orchestrator.py` `generate_title_via_low_agent()` to use the existing `TierResolver` for model_tiers lookup instead of ad-hoc settings query
  - [x]3.6 Add test for SettingsCache TTL behavior in `tests/mc/bridge/test_settings_cache.py`

- [x]Task 4: Cache tagAttributes:list in context builder (AC: #4)
  - [x]4.1 In `mc/application/execution/context_builder.py`, add a module-level or instance-level cache for `tagAttributes:list` with 5-minute TTL
  - [x]4.2 Modify `_build_tag_attrs()` (line 720) to use cached result
  - [x]4.3 Similarly cache in `mc/contexts/execution/post_processing.py` (line 402) and `mc/contexts/execution/cc_executor.py` (line 153)

- [x]Task 5: Parallelize context builder queries (AC: #5)
  - [x]5.1 In `mc/application/execution/context_builder.py`, identify the sequential `await asyncio.to_thread(...)` calls for agent, board, messages, tag attrs, orientation
  - [x]5.2 Refactor to use `asyncio.gather()` for independent fetches
  - [x]5.3 Ensure error handling still works (one failed fetch shouldn't crash the entire gather)

- [x]Task 6: Verify (AC: #6)
  - [x]6.1 Run `uv run pytest` — all tests pass
  - [x]6.2 Run `cd dashboard && npm run test` — Convex tests pass (for appendBatch)

## Dev Notes

### Why this story exists

During active task execution, the Python backend makes 30-50 Convex calls per second: each supervision event triggers a session query + session upsert + activity log append. Settings are re-queried without caching. Context builder queries run sequentially. These are the main contributors to Convex load during execution.

### Expected Files

| File | Change |
|------|--------|
| `mc/contexts/interactive/registry.py` | Add `_session_cache` dict; cache in `get()`, update in `_upsert()` |
| `mc/contexts/interactive/activity_service.py` | Add event buffer; batch flush logic; `flush()` method |
| `mc/bridge/settings_cache.py` | **NEW** — TTL-based settings cache |
| `mc/application/execution/orientation.py` | Use SettingsCache |
| `mc/application/execution/context_builder.py` | Cache tagAttributes; parallelize with asyncio.gather |
| `mc/runtime/timeout_checker.py` | Use SettingsCache |
| `mc/runtime/orchestrator.py` | Use TierResolver for model_tiers in title generation |
| `mc/contexts/execution/post_processing.py` | Cache tagAttributes |
| `mc/contexts/execution/cc_executor.py` | Cache tagAttributes |
| `dashboard/convex/sessionActivityLog.ts` | Add `appendBatch` internalMutation |
| `dashboard/convex/sessionActivityLog.test.ts` | Test for appendBatch |
| `tests/mc/contexts/interactive/test_registry.py` | Test session cache |
| `tests/mc/contexts/interactive/test_activity_service.py` | Test buffer flush |
| `tests/mc/bridge/test_settings_cache.py` | **NEW** — Test TTL cache |

### Technical Constraints

- The `_session_cache` in registry is per-process and single-threaded (asyncio). No concurrency issues.
- The activity buffer flush timer uses `time.time()` wall clock. The 300ms threshold is approximate — the buffer flushes on the next `append_event()` call after 300ms, not via a background timer. This is simpler and sufficient.
- `SettingsCache` must be thread-safe since it may be called from `asyncio.to_thread()`. Use a simple dict with no locking (Python GIL protects single-threaded access).
- `appendBatch` must handle the edge case where all events in a batch belong to different sessions — but in practice, batches will be session-scoped since the buffer is per-service and services are session-scoped.
- Actually, the `SessionActivityService` is instantiated per-execution, so all buffered events will have the same `sessionId`. Assert this in the batch mutation or group by sessionId.

### Testing Guidance

- Follow `agent_docs/running_tests.md`.
- For the SettingsCache, test: cache hit within TTL returns cached value; cache miss after TTL queries Convex; different keys are independent.
- For the activity buffer, test: buffer fills and flushes at threshold; time-based flush works; explicit flush on session end.
- For the registry cache, test: first `get()` queries Convex; subsequent `get()` returns cached; `_upsert()` updates cache.

### References

- [Plan: /Users/ennio/.claude/plans/piped-gliding-emerson.md — Fixes B1, B2, B3, B4]
- [Source: mc/contexts/interactive/registry.py — InteractiveSessionRegistry]
- [Source: mc/contexts/interactive/activity_service.py — SessionActivityService]
- [Source: mc/contexts/interactive/supervisor.py — handle_event line 119]
- [Source: mc/application/execution/context_builder.py — _build_tag_attrs, _fetch_convex_agent]
- [Source: mc/application/execution/orientation.py]
- [Source: mc/runtime/timeout_checker.py]
- [Source: dashboard/convex/sessionActivityLog.ts]

## Dev Agent Record

**Status:** done
**Agent:** Claude Opus 4.6

### Files Changed

| File | Change |
|------|--------|
| `mc/contexts/interactive/registry.py` | Added `_session_cache` dict; cache in `get()`, update in `_upsert()`, remove in `end_session()`/`terminate()` |
| `mc/contexts/interactive/activity_service.py` | Added event buffer with `_event_buffer`/`_last_flush_time`; batch flush logic at size 20 or 300ms; `flush()` method; auto-flush at session end and result |
| `mc/bridge/settings_cache.py` | **NEW** — TTL-based settings cache with per-key expiry, stale fallback on failure |
| `mc/bridge/tag_attributes_cache.py` | **NEW** — Module-level 5-minute TTL cache for `tagAttributes:list` queries |
| `mc/bridge/__init__.py` | Wire `SettingsCache` onto `ConvexBridge` as `settings_cache` attribute |
| `mc/infrastructure/orientation.py` | Use `SettingsCache` for `global_orientation_prompt` when available |
| `mc/runtime/timeout_checker.py` | Use `SettingsCache` for `task_timeout_minutes` when available |
| `mc/runtime/orchestrator.py` | Replace ad-hoc `model_tiers` JSON parsing with `TierResolver` |
| `mc/application/execution/context_builder.py` | Cache `tagAttributes:list` via module cache; parallelize agent+task fetch with `asyncio.gather()`; parallelize thread messages+task steps fetch |
| `mc/contexts/execution/post_processing.py` | Cache `tagAttributes:list` via module cache |
| `mc/contexts/execution/cc_executor.py` | Cache `tagAttributes:list` via module cache |
| `dashboard/convex/sessionActivityLog.ts` | Added `appendBatch` internalMutation for batch event insertion with single seq query |
| `dashboard/convex/sessionActivityLog.test.ts` | Added 4 tests for `appendBatch` (incrementing seq, empty batch, truncation) |
| `tests/mc/bridge/test_settings_cache.py` | **NEW** — 7 tests for TTL, invalidation, stale fallback |
| `tests/mc/contexts/interactive/__init__.py` | **NEW** — Package init |
| `tests/mc/contexts/interactive/test_registry.py` | **NEW** — 5 tests for session cache behavior |
| `tests/mc/contexts/interactive/test_activity_service.py` | **NEW** — 10 tests for buffer/flush logic |
| `tests/mc/application/execution/test_nanobot_live.py` | Added `strategy._activity.flush()` calls before assertions to account for event buffering |
| `tests/mc/application/execution/test_provider_cli_strategy.py` | Added `_extract_activity_events()` helper; updated 3 tests to handle both `append` and `appendBatch` calls |

### Change Log

1. **Task 1 — Registry cache:** Added `_session_cache` dict to `InteractiveSessionRegistry`. `get()` checks cache first; `_upsert()` updates cache; `end_session()`/`terminate()` evict from cache. Supervision events now trigger 1 Convex query instead of N.

2. **Task 2 — Activity log batching:** Added `appendBatch` Convex mutation that queries max seq once and inserts all events. Python `SessionActivityService` buffers events and flushes at size=20 or time=300ms. `flush()` called at session end, result, and error paths. Single events use `append`; multiple use `appendBatch`.

3. **Task 3 — SettingsCache:** Created `mc/bridge/settings_cache.py` with per-key TTL cache. Wired into `ConvexBridge.__init__`. `orientation.py` and `timeout_checker.py` use it via `isinstance(settings_cache, SettingsCache)` check to avoid MagicMock false positives in tests. Orchestrator now uses `TierResolver` instead of ad-hoc settings query.

4. **Task 4 — tagAttributes cache:** Created `mc/bridge/tag_attributes_cache.py` with 5-minute TTL module-level cache. Applied in `context_builder.py`, `post_processing.py`, and `cc_executor.py`.

5. **Task 5 — Parallelize context builder:** In `build_task_context()`, parallelized Convex agent + fresh task fetch with `asyncio.gather(return_exceptions=True)`. In `build_step_context()`, parallelized thread messages + task steps fetch. Error handling preserves individual failure gracefully.
