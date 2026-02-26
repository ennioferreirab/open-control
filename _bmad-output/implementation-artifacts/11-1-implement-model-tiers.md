# Story 11.1: Implement Model Tier System

Status: ready-for-dev

## Story

As an **admin**,
I want to configure model tiers (standard low/medium/high + reasoning low/medium/high) that map to connected models,
so that changing a tier updates all agents using it without needing to reconfigure each agent individually.

## Acceptance Criteria

### AC1: Settings-Based Tier Storage

**Given** the existing `settings` table (key-value store with `by_key` index)
**When** the model tier system is initialized
**Then** the key `"model_tiers"` stores a JSON string with 6 tier mappings:
```json
{
  "standard-low": "anthropic/claude-haiku-3-5",
  "standard-medium": "anthropic/claude-sonnet-4-6",
  "standard-high": "anthropic/claude-opus-4-6",
  "reasoning-low": null,
  "reasoning-medium": null,
  "reasoning-high": null
}
```
**And** the key `"connected_models"` stores a JSON array of available model identifiers
**And** reasoning tiers can be `null` (meaning "not available")
**And** standard tiers must always map to a non-null model string

### AC2: Tier Reference Helpers in types.py

**Given** an agent model string
**When** the string starts with `"tier:"` (e.g., `"tier:standard-high"`)
**Then** `is_tier_reference(model)` returns `True`
**And** `extract_tier_name(model)` returns the tier name (e.g., `"standard-high"`)
**When** the string does NOT start with `"tier:"` (e.g., `"anthropic/claude-opus-4-6"`)
**Then** `is_tier_reference(model)` returns `False`
**And** `extract_tier_name(model)` returns `None`

### AC3: TierResolver with Cached Lookups

**Given** the `TierResolver` class in `nanobot/mc/tier_resolver.py`
**When** `resolve_model(model_string)` is called with a tier reference like `"tier:standard-high"`
**Then** it fetches the `"model_tiers"` setting from Convex via `settings:get`
**And** returns the resolved model string (e.g., `"anthropic/claude-opus-4-6"`)
**And** results are cached for 60 seconds to avoid repeated Convex queries
**When** called with a non-tier string (e.g., `"anthropic/claude-opus-4-6"`)
**Then** it returns the string unchanged (pass-through)
**When** called with a tier reference that maps to `null`
**Then** it raises a `ValueError` with a descriptive message

### AC4: Gateway Startup Sync

**Given** the gateway starts up and calls `main()`
**When** agent registry sync completes
**Then** the gateway syncs connected models to `settings:set("connected_models", ...)` using the models discovered from the provider configuration
**And** if no `"model_tiers"` setting exists, seeds default tiers using `settings:set`
**And** existing tier mappings are NOT overwritten on subsequent startups

### AC5: Executor and Dispatcher Tier Resolution

**Given** an agent has `model: "tier:standard-high"` in its configuration
**When** `executor.py` calls `_make_provider(agent_model)` or `step_dispatcher.py` calls `_run_step_agent(agent_model=...)`
**Then** the tier reference is resolved to the actual model string BEFORE passing to `create_provider()`
**And** provider creation uses the resolved model (e.g., `"anthropic/claude-opus-4-6"`)
**And** if tier resolution fails (null tier, missing setting), the error is surfaced clearly in the task thread

### AC6: Frontend Model Tier Settings Panel

**Given** the dashboard settings area
**When** the admin opens the Model Tiers configuration
**Then** a `ModelTierSettings.tsx` panel displays 6 rows (one per tier)
**And** each row shows the tier name and a `<Select>` dropdown populated by the `"connected_models"` setting
**And** reasoning tiers include a "None (not available)" option that maps to `null`
**And** standard tiers do NOT include the "None" option
**And** saving updates the `"model_tiers"` setting via `settings:set`
**And** the panel shows a loading state while fetching settings and a success indicator after saving

## Tasks / Subtasks

- [ ] **Task 1: Add tier reference helpers to types.py** (AC: #2)
  - [ ] 1.1 Add `TIER_PREFIX = "tier:"` constant at module level in `nanobot/mc/types.py`
  - [ ] 1.2 Add `VALID_TIER_NAMES` frozenset: `{"standard-low", "standard-medium", "standard-high", "reasoning-low", "reasoning-medium", "reasoning-high"}`
  - [ ] 1.3 Implement `is_tier_reference(model: str | None) -> bool` — returns `True` if model is not None and starts with `"tier:"`
  - [ ] 1.4 Implement `extract_tier_name(model: str) -> str | None` — strips prefix and returns tier name if valid, else `None`
  - [ ] 1.5 Add unit tests in `tests/mc/test_types.py` for both helpers covering: valid tier refs, non-tier strings, None, empty string, invalid tier names

- [ ] **Task 2: Create TierResolver class** (AC: #3)
  - [ ] 2.1 Create `nanobot/mc/tier_resolver.py` with class `TierResolver`
  - [ ] 2.2 Constructor takes a `ConvexBridge` instance and stores it as `self._bridge`
  - [ ] 2.3 Add `_cache: dict[str, str | None]` and `_cache_time: float` attributes, initialized to empty dict and `0.0`
  - [ ] 2.4 Add `CACHE_TTL = 60.0` class constant
  - [ ] 2.5 Implement `_refresh_cache()` — calls `self._bridge.query("settings:get", {"key": "model_tiers"})`, parses JSON string into dict, updates `_cache` and `_cache_time` to `time.monotonic()`
  - [ ] 2.6 Implement `resolve_model(model: str | None) -> str | None`:
    - If model is None or empty, return None (let caller fall back to default)
    - If not `is_tier_reference(model)`, return model unchanged (pass-through for custom models)
    - Extract tier name via `extract_tier_name(model)`
    - If cache is stale (`time.monotonic() - _cache_time > CACHE_TTL`), call `_refresh_cache()`
    - Look up tier name in `_cache`; if mapped to a non-null string, return it
    - If mapped to `null`, raise `ValueError(f"Tier '{tier_name}' is not configured (set to null)")`
    - If tier name not found in cache, raise `ValueError(f"Unknown tier: '{tier_name}'")`
  - [ ] 2.7 Implement `invalidate_cache()` method — sets `_cache_time = 0.0` to force refresh on next call
  - [ ] 2.8 Add unit tests in `tests/mc/test_tier_resolver.py` covering: pass-through, valid tier resolution, null tier error, unknown tier error, cache TTL behavior

- [ ] **Task 3: Integrate tier resolution into executor.py** (AC: #5)
  - [ ] 3.1 At the top of `executor.py`, add `from nanobot.mc.tier_resolver import TierResolver` (lazy import inside `_execute_task` to avoid circular deps if needed)
  - [ ] 3.2 Add `_tier_resolver: TierResolver | None` attribute to `TaskExecutor.__init__`, initialized lazily
  - [ ] 3.3 In `_execute_task()`, after `agent_prompt, agent_model, agent_skills = self._load_agent_config(agent_name)` (line ~703), add tier resolution block:
    ```python
    if agent_model and is_tier_reference(agent_model):
        try:
            agent_model = self._get_tier_resolver().resolve_model(agent_model)
            logger.info("[executor] Resolved tier for agent '%s': %s", agent_name, agent_model)
        except ValueError as exc:
            logger.error("[executor] Tier resolution failed for '%s': %s", agent_name, exc)
            # Surface error in task thread and crash task
            await self._handle_tier_error(task_id, title, agent_name, exc)
            return
    ```
  - [ ] 3.4 Add `_get_tier_resolver()` lazy initializer method that creates `TierResolver(self._bridge)` on first call
  - [ ] 3.5 Add `_handle_tier_error()` async method that writes a system message to the task thread explaining the tier resolution failure and transitions task to crashed
  - [ ] 3.6 Import `is_tier_reference` from `nanobot.mc.types` in the existing import block

- [ ] **Task 4: Integrate tier resolution into step_dispatcher.py** (AC: #5)
  - [ ] 4.1 In `_execute_step()`, after `agent_prompt, agent_model, agent_skills = _load_agent_config(agent_name)` (line ~335), add tier resolution:
    ```python
    if agent_model and is_tier_reference(agent_model):
        from nanobot.mc.tier_resolver import TierResolver
        resolver = TierResolver(self._bridge)
        agent_model = resolver.resolve_model(agent_model)
    ```
  - [ ] 4.2 Wrap tier resolution in try/except to catch `ValueError` and surface in step crash message
  - [ ] 4.3 Import `is_tier_reference` from `nanobot.mc.types` in the existing import block at the top of the file

- [ ] **Task 5: Gateway startup — sync connected models and seed default tiers** (AC: #4)
  - [ ] 5.1 In `gateway.py` `main()`, after agent registry sync and skills sync, add connected models sync:
    ```python
    # Sync connected models list and seed default tiers (Epic 11)
    try:
        _sync_model_tiers(bridge)
        logger.info("[gateway] Model tiers synced")
    except Exception:
        logger.exception("[gateway] Model tiers sync failed")
    ```
  - [ ] 5.2 Implement `_sync_model_tiers(bridge: ConvexBridge)` function:
    - Read available models from provider config via `load_config().agents.defaults.model` and any additional models list
    - Call `bridge.mutation("settings:set", {"key": "connected_models", "value": json.dumps(models_list)})`
    - Query `bridge.query("settings:get", {"key": "model_tiers"})` — if None, seed default tiers
    - Default tiers: `{"standard-low": "anthropic/claude-haiku-3-5", "standard-medium": "anthropic/claude-sonnet-4-6", "standard-high": "anthropic/claude-opus-4-6", "reasoning-low": null, "reasoning-medium": null, "reasoning-high": null}`
    - Call `bridge.mutation("settings:set", {"key": "model_tiers", "value": json.dumps(default_tiers)})`
  - [ ] 5.3 Keep idempotent: do NOT overwrite existing `model_tiers` if already set

- [ ] **Task 6: Build ModelTierSettings.tsx frontend component** (AC: #6)
  - [ ] 6.1 Create `dashboard/components/ModelTierSettings.tsx`
  - [ ] 6.2 Use `useQuery(api.settings.get, { key: "model_tiers" })` to fetch current tier mappings
  - [ ] 6.3 Use `useQuery(api.settings.get, { key: "connected_models" })` to fetch available models list
  - [ ] 6.4 Parse both JSON strings — `model_tiers` into `Record<string, string | null>`, `connected_models` into `string[]`
  - [ ] 6.5 Render 6 rows, each with:
    - Tier label (formatted, e.g., "Standard Low", "Reasoning High")
    - `<Select>` dropdown populated with connected_models options
    - For reasoning tiers: include "None (not available)" option that sets value to null
    - For standard tiers: no null option
  - [ ] 6.6 Add local state for edited tiers, dirty detection, and save handler
  - [ ] 6.7 Save handler calls `useMutation(api.settings.set)` with `{ key: "model_tiers", value: JSON.stringify(editedTiers) }`
  - [ ] 6.8 Show loading skeleton while queries are pending, success toast/indicator on save
  - [ ] 6.9 Use existing shadcn/ui components: `Select`, `SelectTrigger`, `SelectValue`, `SelectContent`, `SelectItem`, `Button`, `Separator`

- [ ] **Task 7: Integrate ModelTierSettings into Settings area** (AC: #6)
  - [ ] 7.1 Import `ModelTierSettings` in the settings page or config modal (check existing settings UI location — likely near `dashboard/components/` or `dashboard/app/`)
  - [ ] 7.2 Add a "Model Tiers" section/tab in the settings sidebar or modal
  - [ ] 7.3 Ensure the panel is only visible to admin users (consistent with existing settings access patterns)

## Dev Notes

### Architecture Patterns

- **Settings table reuse**: The `settings` table at `dashboard/convex/settings.ts` already provides `get`, `set`, and `list` operations with a `by_key` index. Both `model_tiers` and `connected_models` are stored as JSON-serialized strings under their respective keys. No schema changes needed.

- **Tier reference format**: The convention `"tier:standard-high"` is chosen to be unambiguous — real model strings always contain a `/` (e.g., `"anthropic/claude-sonnet-4-6"`), so there is zero collision risk between tier references and direct model strings.

- **Cache strategy**: The 60-second TTL cache in `TierResolver` avoids hammering Convex on every step execution while keeping tier changes responsive. The `invalidate_cache()` method allows forced refresh when settings are updated.

- **Pass-through design**: `TierResolver.resolve_model()` returns non-tier strings unchanged. This means code that already works with direct model strings continues to work without modification. Only strings with the `"tier:"` prefix trigger resolution.

### Code to Reuse

- `dashboard/convex/settings.ts` — `get` query and `set` mutation are already implemented and tested
- `nanobot/mc/provider_factory.py` — `create_provider(model)` already accepts model strings; tier resolution happens BEFORE this call
- `nanobot/mc/executor.py` lines 702-703 — `_load_agent_config()` returns `(prompt, model, skills)` where model may now be a tier reference
- `nanobot/mc/step_dispatcher.py` line 335 — same `_load_agent_config()` pattern

### Common Mistakes to Avoid

- Do NOT modify the Convex schema — settings table already supports arbitrary key-value pairs
- Do NOT resolve tiers inside `_load_agent_config()` — it does not have access to the bridge. Resolution must happen in `_execute_task()` / `_execute_step()` where the bridge is available.
- Do NOT cache the TierResolver instance across the module — it needs the bridge instance. Create it in `TaskExecutor.__init__()` or lazily in `_execute_task()`.
- Remember `settings:get` returns the raw `value` string (or null), not a parsed object. Always `json.loads()` the result.
- Use `uv run python` not `python3`. Use `uv run pytest` for tests.

### Project Structure Notes

- Python backend: `nanobot/mc/` (types, gateway, executor, step_dispatcher, new tier_resolver)
- Frontend: `dashboard/components/` (new ModelTierSettings.tsx)
- Convex: `dashboard/convex/settings.ts` (reuse, no changes)
- Tests: `tests/mc/` (new test_types.py additions, new test_tier_resolver.py)

### References

- `dashboard/convex/settings.ts` — settings table queries/mutations
- `dashboard/convex/schema.ts` — settings table schema (key: string, value: string, index by_key)
- `nanobot/mc/types.py` — shared types module where tier helpers go
- `nanobot/mc/gateway.py` — gateway startup (`main()` function, line ~925)
- `nanobot/mc/executor.py` — `_execute_task()` method, `_load_agent_config()` call at line ~703
- `nanobot/mc/step_dispatcher.py` — `_execute_step()` method, `_load_agent_config()` call at line ~335
- `nanobot/mc/provider_factory.py` — `create_provider(model)` function

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
