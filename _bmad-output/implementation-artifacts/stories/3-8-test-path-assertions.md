# Story 3-8: Update test path assertions for runtime home

## Story
As a developer, I need tests to mock the runtime home resolution correctly so they don't break when the hardcoded paths are removed from source files, and so the env var override behavior is tested.

## Status: ready

## Acceptance Criteria
- [ ] Tests that assert `"/home/test/.nanobot/..."` paths still pass (the default resolves to `.nanobot`)
- [ ] New test in `tests/mc/infrastructure/test_runtime_home.py` covering: OPEN_CONTROL_HOME set, NANOBOT_HOME set, both set (OPEN_CONTROL_HOME wins), neither set (defaults to .nanobot)
- [ ] Dashboard test files that hardcode `.nanobot` paths are updated to use a helper or remain valid (since the default IS .nanobot)
- [ ] `make validate` passes

## Tasks
- [ ] Create `tests/mc/infrastructure/test_runtime_home.py` with test cases:
  - `test_default_resolves_to_nanobot` — neither env var set → `~/.nanobot`
  - `test_open_control_home_override` — `OPEN_CONTROL_HOME=/custom` → `/custom`
  - `test_nanobot_home_override` — `NANOBOT_HOME=/legacy` → `/legacy`
  - `test_open_control_home_takes_precedence` — both set → uses `OPEN_CONTROL_HOME`
  - `test_helper_functions` — `get_agents_dir()`, `get_tasks_dir()` etc. return correct subpaths
- [ ] Review existing test files for broken assumptions:
  - `tests/mc/infrastructure/test_config.py` — may mock `Path.home()`
  - `tests/mc/infrastructure/test_runtime_context.py` — uses `get_agents_dir`
  - `tests/mc/test_cli_lifecycle.py` — PID file path
  - `tests/mc/test_cli_status.py` — PID file path
  - `dashboard/app/api/cron/route.test.ts` — asserts `/home/test/.nanobot/cron/jobs.json`
  - `dashboard/app/api/cron/[jobId]/route.test.ts` — same
  - `dashboard/app/api/settings/global-orientation-default/route.test.ts` — asserts `.nanobot` path
  - `dashboard/app/api/agents/[agentName]/config/route.test.ts` — asserts `.nanobot` path

## File List
- `tests/mc/infrastructure/test_runtime_home.py` (NEW)
- `tests/mc/infrastructure/test_config.py` (review)
- `tests/mc/test_cli_lifecycle.py` (review)
- `tests/mc/test_cli_status.py` (review)
- `dashboard/app/api/cron/route.test.ts` (review)
- `dashboard/app/api/cron/[jobId]/route.test.ts` (review)

## Dev Notes
- Python tests: use `monkeypatch.setenv` / `monkeypatch.delenv` to test env var combinations
- IMPORTANT: `runtime_home.py` caches the result after story 3-1. Tests MUST clear the cache between test cases. Import and reset `_resolved = None` or provide a `_reset_cache()` test helper.
- Dashboard tests that assert `.nanobot` paths are still correct since the default IS `.nanobot` — they only need updating if the route code changes to use `getRuntimePath` (which it will in story 3-7). The mock should patch `getRuntimePath` instead of `homedir`.
- Read `agent_docs/running_tests.md` before writing tests.
