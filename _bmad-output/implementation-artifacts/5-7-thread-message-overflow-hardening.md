# Story 5.7: Thread Message Overflow Hardening

Status: ready-for-dev

## Story

As the platform operator,
I want large task-thread message content to use the same overflow protection as Live,
so that Convex string limits do not become a hidden failure mode.

## Acceptance Criteria

1. `messages.py` uses `safe_string_for_convex()` for all content writes.
2. Overflow files are stored under the task overflow directory.
3. Existing message behavior remains compatible.
4. Tests cover the overflow path and the normal path.

## Tasks / Subtasks

- [ ] Task 1: Apply overflow protection
  - [ ] 1.1 Update `mc/bridge/repositories/messages.py`

- [ ] Task 2: Add tests
  - [ ] 2.1 Update `tests/mc/bridge/test_repositories.py`
  - [ ] 2.2 Update `tests/mc/test_bridge.py`

## Expected Files

| File | Change |
|------|--------|
| `mc/bridge/repositories/messages.py` | Apply overflow protection |
| `tests/mc/bridge/test_repositories.py` | Update tests |
| `tests/mc/test_bridge.py` | Update tests |
