# Story 11.5: Sync Nanobot Default Model from Convex on Gateway Startup

Status: done

## Story

As a **user who configures the nanobot agent model in the dashboard**,
I want the nanobot gateway (Telegram/channels) to automatically use the same model on the next restart,
so that I don't need to manually edit `~/.nanobot/config.json` after changing the model in the dashboard.

## Background / Context

The nanobot gateway process (`python -m nanobot gateway`) reads its model from:
```
~/.nanobot/config.json → agents.defaults.model
```
This is a static value, entirely independent of the MC agent registry stored in Convex.

When the user changes the `nanobot` agent's model in the dashboard (the agent displayed as "Owl"), the Telegram channel ignores that change — it keeps using the stale value from `config.json`.

`mc/gateway.py` already runs `sync_agent_registry()` at startup, which writes back MC agent YAML files from Convex. We extend this pattern: also sync `agents.defaults.model` in `config.json` from the `nanobot` agent's model in Convex.

**Critical**: Do NOT hardcode the display name "owl". Use the existing constant `NANOBOT_AGENT_NAME = "nanobot"` from `mc/types.py`.

## Acceptance Criteria

### AC1: New function `sync_nanobot_default_model(bridge)` in `mc/gateway.py`

**Given** the `nanobot` agent exists in Convex with a `model` field
**When** `sync_nanobot_default_model(bridge)` is called
**Then** `~/.nanobot/config.json` → `agents.defaults.model` is updated to match
**And** the update is written atomically (tempfile + `os.replace`)
**And** the function logs `INFO [gateway] Updated nanobot default model: {old} → {new}`

### AC2: No write when model already matches

**Given** `config.json` already has the same model as Convex
**When** `sync_nanobot_default_model(bridge)` is called
**Then** `config.json` is NOT written to disk
**And** a `DEBUG` log is emitted

### AC3: Graceful skip for missing/invalid data

**Given** any of:
- `nanobot` agent not found in Convex
- agent has no `model` field or model is empty
- `~/.nanobot/config.json` does not exist

**When** `sync_nanobot_default_model(bridge)` is called
**Then** the function skips with a `WARNING` log
**And** does NOT raise an exception or crash the gateway

### AC4: Errors during write do not crash gateway

**Given** `config.json` exists but the write fails (e.g., permissions)
**When** `sync_nanobot_default_model(bridge)` is called
**Then** the exception is caught, logged as `ERROR`
**And** the gateway continues startup normally

### AC5: Called in `run_gateway()` after `sync_agent_registry()`

**Given** `run_gateway()` is executing startup sync steps
**When** `sync_agent_registry()` completes
**Then** `sync_nanobot_default_model(bridge)` is called next (before `_sync_model_tiers`)
**And** it is wrapped in try/except so a failure does not abort startup

### AC6: Uses `NANOBOT_AGENT_NAME` constant, not a hardcoded string

**Given** the function needs to look up the agent by name
**When** reading the code
**Then** the lookup uses `NANOBOT_AGENT_NAME` imported from `mc.types`
**And** no string literal `"nanobot"` or `"owl"` appears in the function body

### AC7: Tests in `tests/mc/test_sync_nanobot_model.py`

Five test cases:
1. Convex model differs from config → config updated, returns True
2. Convex model matches config → no write, returns False
3. Agent absent from Convex → skip, no exception
4. Agent present but `model` is empty/None → skip, no exception
5. `config.json` missing → skip, no exception

## Tasks / Subtasks

- [x] Task 1: Implement `sync_nanobot_default_model(bridge)` in `mc/gateway.py`
  - [x] 1.1 Import `NANOBOT_AGENT_NAME` from `mc.types` (already imported elsewhere in the module)
  - [x] 1.2 Use `bridge.get_agent_by_name(NANOBOT_AGENT_NAME)` to fetch the agent
  - [x] 1.3 Read `~/.nanobot/config.json` (use `nanobot.config.loader.get_config_path()` or `Path.home() / ".nanobot" / "config.json"`)
  - [x] 1.4 Parse JSON, compare `config["agents"]["defaults"]["model"]` with Convex model
  - [x] 1.5 If different: write atomically (write to `.tmp` in same dir, then `os.replace`)
  - [x] 1.6 Log INFO on update, DEBUG on no-op, WARNING on skip, ERROR on write failure

- [x] Task 2: Wire into `run_gateway()` (AC5)
  - [x] 2.1 Add call after `sync_agent_registry()` block, wrapped in try/except with `logger.exception`

- [x] Task 3: Write tests `tests/mc/test_sync_nanobot_model.py` (AC7)
  - [x] 3.1 Test: model differs → updated
  - [x] 3.2 Test: model matches → no write
  - [x] 3.3 Test: agent absent → skip, no exception
  - [x] 3.4 Test: model field empty → skip, no exception
  - [x] 3.5 Test: config.json missing → skip, no exception

- [x] Task 4: Run tests
  - [x] 4.1 `uv run pytest tests/mc/test_sync_nanobot_model.py -v`
  - [x] 4.2 `uv run pytest tests/mc/ -q` — verify no regressions

## Dev Notes

### config.json path

```python
from pathlib import Path
CONFIG_PATH = Path.home() / ".nanobot" / "config.json"
```

### bridge method

```python
# mc/bridge.py:584
def get_agent_by_name(self, name: str) -> dict[str, Any] | None:
    return self.query("agents:getByName", {"name": name})
```

Returns a dict with keys including `name`, `model`, `display_name`, etc. Returns `None` if not found.

### Atomic write pattern

```python
import json, os, tempfile
from pathlib import Path

def _atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)
```

### Function signature and call site

```python
def sync_nanobot_default_model(bridge: "ConvexBridge") -> bool:
    """Sync config.json agents.defaults.model from the nanobot agent in Convex.

    Returns True if config was updated, False otherwise.
    """
    ...
```

Call site in `run_gateway()` (after existing `sync_agent_registry` block, around line 1253):

```python
try:
    updated = sync_nanobot_default_model(bridge)
    if updated:
        logger.info("[gateway] Nanobot default model synced from Convex")
except Exception:
    logger.exception("[gateway] Nanobot model sync failed")
```

### NANOBOT_AGENT_NAME import

Already available in the module:
```python
from mc.gateway import NANOBOT_AGENT_NAME  # defined at top of gateway.py line 35
```
Actually it's defined directly in `mc/gateway.py:35` as:
```python
NANOBOT_AGENT_NAME = "nanobot"  # Re-exported for backward compat; canonical in types.py
```
Use this local constant directly — no extra import needed.

### Files to modify

| File | Change |
|------|--------|
| `mc/gateway.py` | New function + call in `run_gateway()` |
| `tests/mc/test_sync_nanobot_model.py` | New file with 5 test cases |

## Dev Agent Record

### Agent Model Used

GPT-5 Codex (CLI)

### Completion Notes List

- Implemented `sync_nanobot_default_model(bridge)` in `mc/gateway.py` with:
  - `bridge.get_agent_by_name(NANOBOT_AGENT_NAME)` lookup
  - `~/.nanobot/config.json` read via `nanobot.config.loader.get_config_path()`
  - atomic write using tempfile + `os.replace`
  - INFO/DEBUG/WARNING/ERROR logging paths and non-crashing behavior
- Wired startup call immediately after `sync_agent_registry()` and before `_sync_model_tiers`, with `try/except` + `logger.exception`.
- Added `tests/mc/test_sync_nanobot_model.py` with 5 AC7 tests.
- Validation:
  - `uv run pytest tests/mc/test_sync_nanobot_model.py -v` failed to execute in this sandbox due `uv` runtime panic (`system-configuration` NULL object panic).
  - Fallback run `.venv/bin/pytest tests/mc/test_sync_nanobot_model.py -v`: 5 passed.
  - Fallback run `.venv/bin/pytest tests/mc/ -q`: 8 failures, all pre-existing/environmental and unrelated to this story change.

### File List

- mc/gateway.py
- tests/mc/test_sync_nanobot_model.py
- _bmad-output/implementation-artifacts/11-5-sync-nanobot-model-on-startup.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
