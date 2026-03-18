# Story 10.1: Lock Down Terminal Session Mutations

## Story

**As a** system operator,
**I want** all terminal session write operations to be internal-only (not callable from the browser),
**so that** no unauthenticated client can modify terminal session state directly.

## Status

review

## Acceptance Criteria

1. `upsert`, `registerTerminal`, and `disconnectTerminal` in `terminalSessions.ts` are converted from `mutation()` to `internalMutation()` and are no longer callable from the browser.
2. `sendInput`, `get`, and `listSessions` remain as public `mutation()`/`query()` (browser-callable).
3. `terminal_bridge.py` no longer contains a hardcoded Convex URL constant (`_DEFAULT_CONVEX_URL`).
4. `terminal_bridge.py` exits with a clear error message if `--convex-url` / `$CONVEX_URL` is not set.
5. `terminal_bridge.py` exits with a clear error message if `--admin-key` / `$CONVEX_ADMIN_KEY` is not set.
6. All existing Python tests pass after the changes.

## Tasks / Subtasks

- [x] Task 1: Convert write mutations to internalMutation in terminalSessions.ts
  - [x] 1.1 Add `internalMutation` to the import from `./_generated/server`
  - [x] 1.2 Change `upsert` from `mutation({...})` to `internalMutation({...})`
  - [x] 1.3 Change `registerTerminal` from `mutation({...})` to `internalMutation({...})`
  - [x] 1.4 Change `disconnectTerminal` from `mutation({...})` to `internalMutation({...})`
  - [x] 1.5 Verify `sendInput`, `get`, `listSessions` are unchanged

- [x] Task 2: Remove hardcoded Convex URL from terminal_bridge.py
  - [x] 2.1 Remove `_DEFAULT_CONVEX_URL` constant
  - [x] 2.2 Change `--convex-url` default to `os.environ.get("CONVEX_URL")` (no fallback)
  - [x] 2.3 Add startup check: if `args.convex_url` is None, print error and `sys.exit(1)`

- [x] Task 3: Add admin key startup check to terminal_bridge.py
  - [x] 3.1 Add startup check: if `args.admin_key` is None, print error and `sys.exit(1)`

## Dev Notes

- Only modify `terminalSessions.ts` and `terminal_bridge.py`
- The import line becomes: `import { mutation, query, internalMutation } from "./_generated/server";`
- `internalMutation` is a Convex built-in — no new package needed
- The function body/args/handler stay IDENTICAL — only the wrapper changes
- Python test suite: `uv run pytest tests/mc/ -v`
- No new tests are needed for the TypeScript changes (Convex type system enforces the constraint)

## Dev Agent Record

### Implementation Plan

1. Modify `dashboard/convex/terminalSessions.ts`: add `internalMutation` to import, convert 3 mutations
2. Modify `terminal_bridge.py`: remove hardcoded URL constant, add URL and admin key startup checks
3. Run `uv run pytest tests/mc/ -v` to verify no regressions

### Completion Notes

- Task 1: Added `internalMutation` to the import and converted `upsert`, `registerTerminal`, `disconnectTerminal` to use `internalMutation()`. `sendInput`, `get`, and `listSessions` remain unchanged as public APIs.
- Task 2: Removed `_DEFAULT_CONVEX_URL` constant. Changed `--convex-url` default to `os.environ.get("CONVEX_URL")` with no hardcoded fallback. Added startup check that exits with error if URL is not provided.
- Task 3: Added startup check that exits with error if `admin_key` is not provided.
- All Python tests pass: `uv run pytest tests/mc/ -v`

## File List

- `dashboard/convex/terminalSessions.ts`
- `terminal_bridge.py`

## Change Log

- 2026-03-01: Implemented Story 10.1 — converted 3 terminal session mutations to internalMutation, removed hardcoded Convex URL from terminal_bridge.py, added startup checks for URL and admin key.
