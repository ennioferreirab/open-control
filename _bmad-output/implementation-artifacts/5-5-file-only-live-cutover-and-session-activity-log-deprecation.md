# Story 5.5: File-Only Live Cutover and SessionActivityLog Deprecation

Status: ready-for-dev

## Story

As the platform operator,
I want the Live write path to stop sending transcript bytes to Convex,
so that Live depends only on file-backed storage after cutover.

## Acceptance Criteria

1. `activity_service.py` stops writing `sessionActivityLog:append` and `appendBatch`.
2. `sessionActivityLog.ts` remains only as legacy compatibility surface.
3. Docs state that Live transcript bytes are file-backed.
4. The cutover is verified by tests and/or a smoke run showing no new Live bytes in Convex.

## Tasks / Subtasks

- [ ] Task 1: Cut over writes
  - [ ] 1.1 Remove Convex transcript writes from `mc/contexts/interactive/activity_service.py`

- [ ] Task 2: Deprecate Convex live log
  - [ ] 2.1 Keep `dashboard/convex/sessionActivityLog.ts` for legacy reads only
  - [ ] 2.2 Update structural docs

## Expected Files

| File | Change |
|------|--------|
| `mc/contexts/interactive/activity_service.py` | Stop transcript Convex writes |
| `dashboard/convex/sessionActivityLog.ts` | Legacy read compatibility |
| `agent_docs/database_schema.md` | Deprecation note |
| `agent_docs/service_communication_patterns.md` | Deprecation note |
| `agent_docs/scaling_decisions.md` | Update file-backed live decision |
