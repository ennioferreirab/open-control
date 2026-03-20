# Runtime Home Migration — Implementation Plan

## Context

The Open Control rebrand introduced `mc/infrastructure/runtime_home.py` (Python) and `dashboard/lib/runtimeHome.ts` (TypeScript) to centralize runtime home resolution with env var support (`OPEN_CONTROL_HOME` → `NANOBOT_HOME` → `~/.nanobot`). Only 2 of ~27 Python files and 3 of ~7 TS routes were migrated. The rest still hardcode `Path.home() / ".nanobot"`, making the env var broken in practice.

## Goal

Complete the migration so ALL runtime path construction goes through the centralized modules. Add logging to the fallback chain. Fix secrets.py (security-relevant). Update tests.

## Scope

- **42 hardcoded occurrences** across ~25 Python files and ~4 TypeScript files
- **0 new features** — pure mechanical refactor
- **Tests must stay green** — `make validate` must pass after each story

## Architecture Decision

- Python: use specific helpers (`get_agents_dir()`, `get_tasks_dir()`) when they exist, `get_runtime_path("sub", "path")` for ad-hoc paths (cron, PID, memory_settings, orientation)
- TypeScript: use `getRuntimePath(...)` for all paths (no need for dedicated wrappers — the generic function is sufficient)
- Docstrings and user-facing help text: update `~/.nanobot` references to `~/.nanobot (or $OPEN_CONTROL_HOME)` where it helps the user, leave internal comments unchanged
- `runtime_home.py`: add INFO-level log on first call so operators know which home was resolved

## Stories

| Story | Domain | Files | Lines changed (est.) |
|-------|--------|-------|---------------------|
| 3-1 | runtime_home logging + validation | 2 (Python + TS) | ~15 |
| 3-2 | secrets, PID, config, orientation | 5 Python files | ~20 |
| 3-3 | agents domain | 6 Python files | ~15 |
| 3-4 | tasks domain | 8 Python files | ~30 |
| 3-5 | boards + workspace domain | 6 Python files | ~15 |
| 3-6 | cron + memory settings | 4 Python + 2 TS files | ~15 |
| 3-7 | dashboard cron + skills routes | 4 TS files | ~10 |
| 3-8 | test path assertions | ~8 test files | ~20 |

## Waves

### Wave 1 — Foundation (parallel: 3-1, 3-2)
Stories 3-1 and 3-2 fix the silent fallback and the most critical hardcoded paths (secrets, PID). Must land first since later stories depend on the logging behavior.

### Wave 2 — Bulk Python migration (parallel: 3-3, 3-4, 3-5, 3-6)
Four stories, each touching an independent domain. All can run in parallel — no shared files.

### Wave 3 — Dashboard + tests (parallel: 3-7, 3-8)
Dashboard route migration and test updates. Depends on Wave 2 being merged so tests reflect the new paths.

## Validation

After each wave: `make validate` (lint + typecheck + tests).
After Wave 3: `make docker-test` to verify the full stack starts correctly.
