# Story 5.2: Dedicated Live Storage Root and Runtime Contract

Status: ready-for-dev

## Story

As the platform operator,
I want Live transcripts stored under a dedicated filesystem root,
so that deleting the live volume removes only Live history and not task/workspace data.

## Acceptance Criteria

1. `OPEN_CONTROL_LIVE_HOME` is supported in Python and TypeScript.
2. The default live root is `<runtime_home>/live-sessions`.
3. Docker compose mounts `/live-workspace` separately for `mc` and `mc-test`.
4. Runtime-home tests cover the new live path helper.
5. Architecture and scaling docs explain the separate live root.

## Tasks / Subtasks

- [ ] Task 1: Add live path helpers
  - [ ] 1.1 Add `get_live_home()` in `mc/infrastructure/runtime_home.py`
  - [ ] 1.2 Add `getLiveHome()`/`getLivePath()` in `dashboard/lib/runtimeHome.ts`

- [ ] Task 2: Wire compose mounts
  - [ ] 2.1 Mount `./dev_live:/live-workspace` for `mc`
  - [ ] 2.2 Mount `./dev_live_test:/live-workspace` for `mc-test`
  - [ ] 2.3 Set `OPEN_CONTROL_LIVE_HOME=/live-workspace` in both services

- [ ] Task 3: Update contracts and tests
  - [ ] 3.1 Extend `tests/mc/infrastructure/test_runtime_home.py`
  - [ ] 3.2 Update `agent_docs/service_architecture.md`
  - [ ] 3.3 Update `agent_docs/service_communication_patterns.md`
  - [ ] 3.4 Update `agent_docs/scaling_decisions.md`

## Expected Files

| File | Change |
|------|--------|
| `mc/infrastructure/runtime_home.py` | Add live root helper |
| `dashboard/lib/runtimeHome.ts` | Add live root helper |
| `docker-compose.yml` | Separate live mount/env |
| `docker-compose.override.yml` | Separate live mount/env |
| `tests/mc/infrastructure/test_runtime_home.py` | Live helper tests |
| `agent_docs/service_architecture.md` | Document live filesystem root |
| `agent_docs/service_communication_patterns.md` | Document live file API path |
| `agent_docs/scaling_decisions.md` | Update scaling decision for file-backed live |
