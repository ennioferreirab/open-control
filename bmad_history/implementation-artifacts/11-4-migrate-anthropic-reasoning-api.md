# Story 11.4: Migrate Anthropic Reasoning API to `output_config.effort`

Status: done

## Story

As a **developer using nanobot with Claude Opus 4.6 or Sonnet 4.6**,
I want the reasoning parameters to use Anthropic's current `output_config.effort` + adaptive thinking API instead of the deprecated `thinking.budget_tokens`,
so that reasoning depth is controlled correctly on new models and the implementation stays aligned with the official Anthropic API.

## Background / Context

The nanobot providers currently use the deprecated approach for reasoning on Claude models:
```json
{"thinking": {"type": "enabled", "budget_tokens": 1024 | 8000 | 16000}}
```

Anthropic has introduced a new API for Claude Opus 4.6 and Sonnet 4.6:
```json
{"output_config": {"effort": "low|medium|high|max"}, "thinking": {"type": "adaptive"}}
```

Key changes:
- `budget_tokens` is **deprecated** on Opus 4.6 and Sonnet 4.6 (will be removed in a future release)
- `thinking.adaptive` lets Claude decide if/how much to think based on problem complexity
- `effort` levels map directly to the 4-bar indicator in Claude's UI: `low / medium / high / max`
- `max` effort is **only valid on Opus 4.6** — other models must use `"high"` instead
- Adaptive thinking does **not** require `temperature: 1.0` (unlike manual `budget_tokens` mode)
- The `effort` parameter is GA — no extra beta header required

The internal nanobot level names (`low / medium / max`) and the upstream param `reasoning_effort` (`low / medium / high`) both need to map correctly to the new API.

## Acceptance Criteria

### AC1: AnthropicOAuthProvider uses `output_config.effort` for new models

**Given** `anthropic_oauth_provider.py` builds the request body
**When** `reasoning_level` or `reasoning_effort` is set AND the model is `claude-opus-4-6` or `claude-sonnet-4-6`
**Then** the body includes:
```json
{"output_config": {"effort": "<mapped_effort>"}, "thinking": {"type": "adaptive"}}
```
**And** `temperature` is NOT forced to `1.0` (adaptive thinking does not require it)
**And** the old `thinking.budget_tokens` block is NOT added

### AC2: Older Claude models keep the `budget_tokens` approach

**Given** the model is NOT `claude-opus-4-6` or `claude-sonnet-4-6` (e.g., `claude-opus-4-5`, `claude-sonnet-3-5`)
**When** `reasoning_level` or `reasoning_effort` is set in `anthropic_oauth_provider.py`
**Then** the body still uses `{"thinking": {"type": "enabled", "budget_tokens": N}}` with the existing `low=1024 / medium=8000 / max=16000` mapping
**And** `temperature` is set to `1.0` (manual thinking mode still requires it)

### AC3: `max` effort is clamped to `"high"` on non-Opus-4.6 models

**Given** `reasoning_level` is `"max"` and the model is NOT `claude-opus-4-6`
**When** the request body is built in `anthropic_oauth_provider.py`
**Then** `effort` is set to `"high"` (not `"max"`, which would cause an API error)

### AC4: Level mapping is correct across all cases

The effective effort string sent to the API must follow this table:

| Input (`reasoning_level` or `reasoning_effort`) | Model | Sent as |
|---|---|---|
| `"low"` | any new Claude (4-6) | `effort: "low"` |
| `"medium"` | any new Claude (4-6) | `effort: "medium"` |
| `"max"` | `claude-opus-4-6` only | `effort: "max"` |
| `"max"` | Sonnet 4.6 or older | `effort: "high"` |
| `"high"` (upstream param) | any new Claude (4-6) | `effort: "high"` |
| any value | older Claude models | `budget_tokens` path (AC2) |

### AC5: LiteLLMProvider updated for new Claude models

**Given** `litellm_provider.py` builds `kwargs` for `acompletion()`
**When** the model is `claude-opus-4-6` or `claude-sonnet-4-6` AND a reasoning level is set
**Then** the `thinking={"type": "enabled", "budget_tokens": N}` block is replaced by the new approach

> **Note for dev agent:** LiteLLM may expose the `output_config.effort` param differently (e.g., via a top-level `effort` param or a dict). Consult the LiteLLM Anthropic docs at runtime to determine the correct kwarg name. If LiteLLM does not yet support `output_config.effort`, pass it via `extra_body={"output_config": {"effort": effort}}` and `thinking={"type": "adaptive"}`. Either way, `temperature: 1.0` must NOT be forced for adaptive mode.

### AC6: Reasoning params are logged before each API call

**Given** the provider is about to call the Anthropic API
**When** reasoning is active (`reasoning_level` or `reasoning_effort` is set)
**Then** a `logger.debug()` line is emitted showing the exact params being sent, e.g.:
```
reasoning → effort=medium (adaptive) [model=claude-opus-4-6]
```
or for old models:
```
reasoning → budget_tokens=8000 [model=claude-opus-4-5]
```

### AC7: PATCHES.md updated

**Given** `anthropic_oauth_provider.py` and/or `litellm_provider.py` are modified
**When** the story is complete
**Then** `PATCHES.md` is updated to document the reasoning API migration in the relevant file entries

## Tasks / Subtasks

- [x] Task 1: Migrate `anthropic_oauth_provider.py` (AC1, AC2, AC3, AC4, AC6)
  - [x] 1.1 Add helper to detect new-gen models: `_is_adaptive_model(model: str) -> bool` — checks for `"4-6"` in model string
  - [x] 1.2 Update `_REASONING_BUDGET_TOKENS` section — keep for fallback path
  - [x] 1.3 When `reasoning_level` set AND `_is_adaptive_model`: build `output_config.effort` + `thinking.adaptive` block; do NOT force temperature
  - [x] 1.4 When `reasoning_level` set AND NOT `_is_adaptive_model`: keep existing `budget_tokens` path (no change)
  - [x] 1.5 Add `logger.debug()` line before request with the effective params (AC6)

- [x] Task 2: Migrate `litellm_provider.py` (AC5, AC6)
  - [x] 2.1 Add same `_is_adaptive_model()` check (or import from shared util)
  - [x] 2.2 For new-gen Claude: replace `kwargs["thinking"] = {"type": "enabled", "budget_tokens": N}` with new approach (check LiteLLM docs for exact kwarg)
  - [x] 2.3 Keep budget_tokens path for older Claude models unchanged
  - [x] 2.4 Add `logger.debug()` with effective params before `acompletion()` call

- [x] Task 3: Update PATCHES.md (AC7)
  - [x] 3.1 Add entry under `anthropic_oauth_provider.py` section describing the reasoning API migration
  - [x] 3.2 Add entry under `litellm_provider.py` section

- [ ] Task 4: Run tests
  - [ ] 4.1 `uv run pytest tests/` — verify no regressions
  - [ ] 4.2 Manual smoke test: call agent with `reasoning_level: medium` on Opus 4.6 model and verify log shows `effort=medium (adaptive)`

## Dev Notes

### Files to modify

| File | Change |
|------|--------|
| `vendor/nanobot/nanobot/providers/anthropic_oauth_provider.py` | New-gen model detection, effort API path, logging |
| `vendor/nanobot/nanobot/providers/litellm_provider.py` | Same, via LiteLLM kwargs |
| `PATCHES.md` | Document both provider changes |

### Model detection

New-gen models needing the effort API: `claude-opus-4-6`, `claude-sonnet-4-6`.
Simple check: `"4-6" in model.lower()` (matches `claude-opus-4-6`, `claude-sonnet-4-6`, and any future 4.6 variants).
If model has a prefix (`anthropic-oauth/`, `anthropic/`) it must be stripped before checking.

The `_strip_prefix()` function already exists in `anthropic_oauth_provider.py:124`.

### Anthropic API structure for new-gen models

```python
body["output_config"] = {"effort": effort}          # "low", "medium", "high", or "max"
body["thinking"] = {"type": "adaptive"}              # Claude decides whether/how much to think
# Do NOT set body["temperature"] = 1.0 for adaptive mode
```

`max` effort is only valid for `claude-opus-4-6`. For all other models: clamp `"max"` → `"high"`.

### Reasoning level mapping

```python
EFFORT_MAP = {
    "low": "low",
    "medium": "medium",
    "high": "high",      # upstream param passthrough
    "max": "max",        # will be clamped to "high" for non-Opus-4.6
}

def _map_effort(level: str, model: str) -> str:
    effort = EFFORT_MAP.get(level, "medium")
    if effort == "max" and "opus-4-6" not in model.lower():
        effort = "high"
    return effort
```

### LiteLLM notes

LiteLLM may support the Anthropic effort API via one of:
- `effort="medium"` top-level kwarg (if LiteLLM maps it to `output_config.effort`)
- `extra_body={"output_config": {"effort": "medium"}}` (passthrough to Anthropic)
- `thinking={"type": "adaptive"}` may also be a supported kwarg already

Check `docs.litellm.ai/docs/providers/anthropic_effort` at implementation time to confirm exact kwargs before coding.

### PATCHES.md convention

This project maintains `PATCHES.md` to track all vendor modifications. Follow existing formatting:
- Add bullet points under each file's section
- Reference the feature/reason for the change
- [Source: PATCHES.md]

### No impact on agent config

The `reasoning_level` and `reasoning_effort` params flow from agent config → `AgentLoop.__init__()` → `provider.chat()`. No changes needed in `loop.py`, `provider_factory.py`, or config schema. This story is purely provider-level.

### Previous story intelligence

Recent commits context:
- `a252dd7` — Added INFO log for model name on each LLM call (in `loop.py:232`); this story adds DEBUG logs inside the providers themselves for the actual params sent
- `d2569f7` — Removed reasoning selector from tier model; reasoning config is per-agent not per-tier

### References

- [Source: vendor/nanobot/nanobot/providers/anthropic_oauth_provider.py] — current deprecated implementation
- [Source: vendor/nanobot/nanobot/providers/litellm_provider.py#L246-L270] — Claude reasoning path
- [Source: PATCHES.md] — patch documentation conventions
- Anthropic effort API: `platform.claude.com/docs/en/build-with-claude/effort`
- LiteLLM Anthropic effort: `docs.litellm.ai/docs/providers/anthropic_effort`

## Dev Agent Record

### Agent Model Used

GPT-5 (Codex)

### Debug Log References

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest` failed due uv runtime panic in sandboxed environment:
  - `system-configuration-0.6.1/src/dynamic_store.rs: Attempted to create a NULL object`
  - `uv/src/lib.rs: Tokio executor failed, was there a panic?`
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -V` reproduces the same panic, indicating an environment/tooling issue with `uv run` execution in this sandbox.

### Completion Notes List

- Implemented adaptive reasoning API migration in `AnthropicOAuthProvider` for Claude 4.6 models (`output_config.effort` + `thinking.type=adaptive`), while preserving legacy `thinking.budget_tokens` for older Claude models.
- Added effort mapping with `max -> high` clamping for non-Opus-4.6 models in both Anthropic providers.
- Added debug logging of effective reasoning params before provider API calls for adaptive and legacy reasoning paths.
- Updated LiteLLM Claude reasoning path to use native `output_config` + adaptive thinking for 4.6 models (per current LiteLLM Anthropic effort docs).
- Updated `PATCHES.md` entries for both provider files to document the reasoning API migration.
- `uv run` execution is currently blocked in this environment by a reproducible uv runtime panic; full pytest and manual smoke validation remain pending.
- Story and sprint status were transitioned `ready-for-dev -> in-progress -> review` for story `11-4` with testing blocker documented.

### File List

- vendor/nanobot/nanobot/providers/anthropic_oauth_provider.py
- vendor/nanobot/nanobot/providers/litellm_provider.py
- PATCHES.md
- tests/mc/test_reasoning_e2e.py
- tests/mc/test_model_tier_reasoning.py
- _bmad-output/implementation-artifacts/11-4-migrate-anthropic-reasoning-api.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
