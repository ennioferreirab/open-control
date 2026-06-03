# Phase 9 — Re-home configuration into mc

Back to [overview.md](overview.md).

## Goal

Replace `nanobot.config` with an mc-owned config so nothing in `mc/` calls `nanobot.config.loader.load_config`. Parse once at the boundary, trust the typed object inside (the **boundary-discipline** principle).

## Changes

- New `mc/infrastructure/config_schema.py` (or extend the existing [mc/infrastructure/config.py](../../../mc/infrastructure/config.py)) with an mc-owned `Config` model carrying only the ~8 fields `mc/` actually reads (from the investigation): `agents.defaults.model`, `agents.models`, `workspace_path`, `providers.<name>` (`api_key`, `api_base`, `extra_headers`), the `claude_code` block, `tools.web.search.api_key`, `channels.telegram.token`. Drop nanobot's dozens of unused channel/session fields (the **subtract-before-you-add** principle).
- A single `load_config()` reading the same on-disk file. Collapse the duplicated runtime-home resolution: `mc/infrastructure/runtime_home.py` becomes the one source of truth, replacing nanobot's `get_data_path()`.
- Migrate the ~12 `load_config` call sites (investigation lists them) to the mc-owned function and delete the `nanobot.config` imports, including the `TYPE_CHECKING` annotations in [mc/infrastructure/secrets.py](../../../mc/infrastructure/secrets.py).
- **Runtime home is renamed to `~/.open-control`** (decided). This phase lands the rename across `mc/` and `dashboard/lib/runtimeHome.ts` and drops the `~/.nanobot` default. The `NANOBOT_HOME` env fallback is removed in Phase 11. This is a breaking change for local dev; existing `~/.nanobot` data must be moved by the operator (a one-line mv, noted in the PR).
- Port the provider registry as pure data into mc if `secrets.py` still needs env-key resolution after the Factory deletion; otherwise delete that need with the Factory.

## Data structures

- mc-owned `Config` — a Pydantic model, ~8 fields, camelCase aliasing preserved for the on-disk file. The contract a replacement must satisfy, decided once.

## Verification

**Static.** `make check`; `uv run pytest`. Grep proves zero `nanobot.config` references in `mc/`.

**Runtime.** `make start` reads config from disk and the stack boots: gateway, a task, memory, and skill distribution all resolve their config. Capture in the PR.
