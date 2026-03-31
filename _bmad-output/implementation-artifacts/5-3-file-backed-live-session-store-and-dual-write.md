# Story 5.3: File-Backed Live Session Store and Dual-Write

Status: ready-for-dev

## Story

As the platform operator,
I want Live events written to a file-backed store while Convex still receives compatibility writes,
so that we can migrate read paths before cutting over the write path.

## Acceptance Criteria

1. Live session metadata is persisted to a dedicated filesystem store.
2. Live events are appended as JSONL with a stable `seq`.
3. Convex still receives the compatibility writes during migration.
4. `interactiveSessions` records lightweight Live metadata fields.
5. Unit tests cover file writes, metadata updates, and dual-write behavior.

## Tasks / Subtasks

- [ ] Task 1: Add live store module
  - [ ] 1.1 Create `mc/contexts/interactive/live_store.py`
  - [ ] 1.2 Implement meta and event append/read helpers

- [ ] Task 2: Wire activity service
  - [ ] 2.1 Update `mc/contexts/interactive/activity_service.py`
  - [ ] 2.2 Write metadata and event files on every append
  - [ ] 2.3 Preserve existing Convex mutation behavior

- [ ] Task 3: Extend Convex metadata
  - [ ] 3.1 Add lightweight fields to `dashboard/convex/schema.ts`
  - [ ] 3.2 Persist them in `dashboard/convex/interactiveSessions.ts`

- [ ] Task 4: Add tests
  - [ ] 4.1 Add `tests/mc/contexts/interactive/test_live_store.py`
  - [ ] 4.2 Extend `tests/mc/contexts/interactive/test_activity_service.py`
  - [ ] 4.3 Extend `dashboard/convex/interactiveSessions.test.ts`

## Expected Files

| File | Change |
|------|--------|
| `mc/contexts/interactive/live_store.py` | New store |
| `mc/contexts/interactive/activity_service.py` | Dual-write |
| `dashboard/convex/schema.ts` | Add lightweight Live fields |
| `dashboard/convex/interactiveSessions.ts` | Persist lightweight Live fields |
| `tests/mc/contexts/interactive/test_live_store.py` | New tests |
| `tests/mc/contexts/interactive/test_activity_service.py` | Update tests |
| `dashboard/convex/interactiveSessions.test.ts` | Update tests |
