# Story 3-4: Migrate tasks domain paths

## Story
As a developer, I need all task directory resolution to go through `get_tasks_dir()` so task file storage is consistent when `OPEN_CONTROL_HOME` is set.

## Status: ready

## Acceptance Criteria
- [ ] All 8 files below use `get_tasks_dir()` instead of `Path.home() / ".nanobot" / "tasks"`
- [ ] No remaining hardcoded `.nanobot/tasks` in Python source (excluding vendor/, tests/, docs/)
- [ ] `make validate` passes

## Tasks
- [ ] `mc/application/execution/file_enricher.py` — lines 71, 195, 202: replace all 3 occurrences
- [ ] `mc/application/execution/artifact_collector.py` — lines 38, 65: replace both
- [ ] `mc/application/execution/thread_journal_service.py:51` — replace default value
- [ ] `mc/contexts/execution/cc_executor.py` — lines 87, 108: replace both
- [ ] `mc/contexts/execution/post_processing.py` — lines 38, 64, 117, 347, 366: replace all 5
- [ ] `mc/contexts/execution/output_artifacts.py` — lines 25, 41, 87: replace all 3
- [ ] `mc/bridge/repositories/tasks.py` — lines 277, 313, 399: replace all 3
- [ ] `mc/contexts/interactive/activity_service.py:28` — replace 1

## File List
- `mc/application/execution/file_enricher.py`
- `mc/application/execution/artifact_collector.py`
- `mc/application/execution/thread_journal_service.py`
- `mc/contexts/execution/cc_executor.py`
- `mc/contexts/execution/post_processing.py`
- `mc/contexts/execution/output_artifacts.py`
- `mc/bridge/repositories/tasks.py`
- `mc/contexts/interactive/activity_service.py`

## Dev Notes
- Import: `from mc.infrastructure.runtime_home import get_tasks_dir`
- Pattern: `Path.home() / ".nanobot" / "tasks" / safe_id / "output"` → `get_tasks_dir() / safe_id / "output"`
- `post_processing.py:282` has an error message string `~/.nanobot/config.json` — leave as-is (user-facing help, covered by story 3-2 for the actual path)
- This is the highest-volume story (~22 line replacements). Mechanical but verify each one.
