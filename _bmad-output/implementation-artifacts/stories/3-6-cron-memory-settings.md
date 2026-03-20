# Story 3-6: Migrate cron store and memory settings paths

## Story
As a developer, I need cron job storage and memory settings to use centralized runtime paths so scheduled jobs and agent memory configuration work correctly with `OPEN_CONTROL_HOME`.

## Status: ready

## Acceptance Criteria
- [ ] All files below use `get_runtime_path()` instead of hardcoded paths
- [ ] No remaining hardcoded `.nanobot/cron` or `.nanobot/memory_settings` in Python source (excluding vendor/, tests/, docs/)
- [ ] `make validate` passes

## Tasks
### Cron
- [ ] `mc/runtime/gateway.py:130` — `Path.home() / ".nanobot" / "cron" / "jobs.json"` → `get_runtime_path("cron", "jobs.json")`

### Memory settings
- [ ] `mc/memory/store.py:50` — `Path.home() / ".nanobot" / "memory_settings.json"` → `get_runtime_path("memory_settings.json")`
- [ ] `mc/infrastructure/agent_bootstrap.py:622` — `Path.home() / ".nanobot" / "memory_settings.json"` → `get_runtime_path("memory_settings.json")`
- [ ] `mc/contexts/agents/sync.py:351` — `Path.home() / ".nanobot" / "memory_settings.json"` → `get_runtime_path("memory_settings.json")`

## File List
- `mc/runtime/gateway.py`
- `mc/memory/store.py`
- `mc/infrastructure/agent_bootstrap.py`
- `mc/contexts/agents/sync.py`

## Dev Notes
- Import: `from mc.infrastructure.runtime_home import get_runtime_path`
- `agent_bootstrap.py` is also modified by story 3-5 (boards/workspace) — these stories MUST NOT run in parallel or must be in the same wave with clear non-overlapping line ranges. Story 3-5 touches lines 147, 264, 349. This story touches line 622. No overlap.
- `sync.py:82` has a docstring `~/.nanobot/agents` — leave as-is (informational)
