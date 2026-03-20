# Story 3-1: Add logging and validation to runtime_home

## Story
As a platform operator, I need to know which runtime home was resolved at startup, so I can debug configuration issues without reading source code.

## Status: ready

## Acceptance Criteria
- [ ] `get_runtime_home()` logs at INFO level on first call: "Runtime home resolved to: /path (source: OPEN_CONTROL_HOME | NANOBOT_HOME | default)"
- [ ] Log fires only once (cache the result after first resolution)
- [ ] TypeScript `getRuntimeHome()` logs equivalently via `console.info` on first call
- [ ] `make validate` passes

## Tasks
- [ ] **Python `mc/infrastructure/runtime_home.py`**
  - Add module-level `_resolved: Path | None = None` cache
  - On first call, resolve env vars, log source, cache result
  - Subsequent calls return cached value
- [ ] **TypeScript `dashboard/lib/runtimeHome.ts`**
  - Add module-level `let _resolved: string | undefined` cache
  - Log on first call: `console.info("[runtime-home] Resolved to: ...")`

## File List
- `mc/infrastructure/runtime_home.py`
- `dashboard/lib/runtimeHome.ts`

## Dev Notes
- Do NOT add directory existence checks — the directory may be created later by the process
- Use standard `logging.getLogger(__name__)` for Python
- Keep the fallback chain behavior identical, just add observability
