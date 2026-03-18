# Story 10.3: Harden Python Startup to Require Admin Key

Status: ready-for-dev

## Story

As the system operator,
I want the Python gateway to require `CONVEX_ADMIN_KEY` at startup and the ConvexBridge to warn when no admin key is provided,
so that misconfigured deployments fail fast with clear error messages instead of producing cryptic runtime errors.

## Acceptance Criteria

1. **AC 8:** Given `gateway.py` is started without `CONVEX_ADMIN_KEY`, then it logs an error and exits before attempting agent/skill sync.

2. **AC 10:** Given all changes are deployed, `npx convex dev` deploys without TypeScript or schema errors.

3. **AC (bridge warning):** Given `ConvexBridge` is instantiated without an admin key, then a warning is logged indicating internal mutations will fail.

## Tasks / Subtasks

- [ ] Task 11: Make `CONVEX_ADMIN_KEY` required in `gateway.py` (AC: 8)
  - [ ] 11.1 In `nanobot/mc/gateway.py`, after the `convex_url` check (around line 1157-1162), add a check:
    ```python
    admin_key = os.environ.get("CONVEX_ADMIN_KEY")
    if not admin_key:
        logger.error(
            "[gateway] Cannot start: CONVEX_ADMIN_KEY not set. "
            "Set CONVEX_ADMIN_KEY env var for server-side auth."
        )
        return
    ```
  - [ ] 11.2 Move the existing `admin_key = os.environ.get("CONVEX_ADMIN_KEY")` (line 1164) into this check block to avoid duplication

- [ ] Task 12: Add warning log in `bridge.py` when no admin key (AC: bridge warning)
  - [ ] 12.1 In `nanobot/mc/bridge.py`, in `ConvexBridge.__init__` (around line 67-78), after the existing `if admin_key:` block, add:
    ```python
    else:
        logger.warning(
            "ConvexBridge initialized WITHOUT admin key — "
            "internal mutations will fail. Set CONVEX_ADMIN_KEY."
        )
    ```

## Dev Notes

### Critical Context

This is **Phase 3 (Medium Priority)** of Convex Security Hardening. A defense-in-depth measure. After Phases 1-2 convert mutations to `internalMutation`, the gateway and bridge MUST use admin auth. This phase ensures fast failure with clear errors when the key is missing.

**Prerequisites**: Stories 10-1 and 10-2 must be deployed first. After those conversions, the gateway cannot function without admin auth.

### Codebase Patterns

- **Gateway `main()` function**: `nanobot/mc/gateway.py` around line 1152-1165 — currently reads `CONVEX_ADMIN_KEY` from env and passes to `ConvexBridge`. No validation that it's set. The convex_url check pattern already exists (lines 1157-1162) — replicate the same pattern for admin_key.

- **ConvexBridge logging**: `nanobot/mc/bridge.py` uses `logger` from the module. The `__init__` method already has a conditional `if admin_key:` block. Add an `else:` branch with a warning.

- **Logger usage**: Both files use `loguru.logger` — import is already present. Use `logger.error()` for gateway (fatal) and `logger.warning()` for bridge (non-fatal, defense-in-depth).

### Files to Modify

| File | What Changes |
|------|-------------|
| `nanobot/mc/gateway.py` | Add admin_key required check after convex_url check |
| `nanobot/mc/bridge.py` | Add warning log when no admin key provided |

### Testing

- `uv run pytest tests/mc/ -v` — all existing tests must pass
- Manual: start gateway without `CONVEX_ADMIN_KEY` → should log error and exit
- Manual: start gateway with `CONVEX_ADMIN_KEY` → should work normally

### Project Structure Notes

- `nanobot/mc/gateway.py` is the main entry point for Mission Control
- `nanobot/mc/bridge.py` is the shared Convex client wrapper used by both gateway and terminal_bridge
- The bridge warning is defense-in-depth — the gateway check should catch missing keys first

### References

- [Source: _bmad-output/implementation-artifacts/tech-spec-convex-security-hardening.md#Phase 3]
- [Source: nanobot/mc/gateway.py:1152-1165] — main() function with convex_url and admin_key
- [Source: nanobot/mc/bridge.py:67-78] — ConvexBridge.__init__

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
