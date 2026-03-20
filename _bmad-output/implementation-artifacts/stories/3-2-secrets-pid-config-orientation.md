# Story 3-2: Migrate secrets, PID, config, and orientation paths

## Story
As a developer, I need the most security-critical paths (secrets, PID, config) to use the centralized runtime home so that `OPEN_CONTROL_HOME` works consistently for authentication and process management.

## Status: ready

## Acceptance Criteria
- [ ] `mc/infrastructure/secrets.py` uses `get_secrets_path()` instead of hardcoded path
- [ ] `mc/cli/__init__.py` PID_FILE uses `get_runtime_path("mc.pid")`
- [ ] `mc/memory/providers.py` config path uses `get_config_path()`
- [ ] `mc/infrastructure/orientation.py` uses `get_runtime_path("mc", "agent-orientation.md")`
- [ ] `make validate` passes

## Tasks
- [ ] `mc/infrastructure/secrets.py:14` — replace `Path.home() / ".nanobot" / "secrets.json"` with `get_secrets_path()`; add import
- [ ] `mc/infrastructure/secrets.py:18,23` — update docstrings to say "runtime home" instead of `~/.nanobot`
- [ ] `mc/cli/__init__.py:20` — replace `Path.home() / ".nanobot" / "mc.pid"` with `get_runtime_path("mc.pid")`; add import
- [ ] `mc/memory/providers.py:93` — replace `Path.home() / ".nanobot" / "config.json"` with `get_config_path()`; add import
- [ ] `mc/infrastructure/orientation.py:71` — replace `Path.home() / ".nanobot" / "mc" / "agent-orientation.md"` with `get_runtime_path("mc", "agent-orientation.md")`; add import

## File List
- `mc/infrastructure/secrets.py`
- `mc/cli/__init__.py`
- `mc/memory/providers.py`
- `mc/infrastructure/orientation.py`

## Dev Notes
- Import `from mc.infrastructure.runtime_home import get_secrets_path, get_config_path, get_runtime_path`
- Each file needs its own specific import — don't import everything
- `secrets.py` docstrings reference `~/.nanobot/secrets.json` — update to say "the configured runtime home"
