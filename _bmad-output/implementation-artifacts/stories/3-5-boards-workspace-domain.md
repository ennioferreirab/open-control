# Story 3-5: Migrate boards and workspace domain paths

## Story
As a developer, I need all board and workspace directory resolution to go through `get_boards_dir()` and `get_workspace_dir()` so multi-board setups and skill storage work consistently when `OPEN_CONTROL_HOME` is set.

## Status: ready

## Acceptance Criteria
- [ ] All files below use centralized functions instead of hardcoded paths
- [ ] No remaining hardcoded `.nanobot/boards` or `.nanobot/workspace` in Python source (excluding vendor/, tests/, docs/)
- [ ] `make validate` passes

## Tasks
### Boards
- [ ] `mc/infrastructure/agent_bootstrap.py:264` — `Path.home() / ".nanobot" / "boards"` → `get_boards_dir()`
- [ ] `mc/infrastructure/boards.py:79` — `Path.home() / ".nanobot" / "boards" / board_name / "agents" / agent_name` → `get_boards_dir() / board_name / "agents" / agent_name`
- [ ] `mc/infrastructure/boards.py:210` — `Path.home() / ".nanobot" / "boards"` → `get_boards_dir()`
- [ ] `mc/artifacts/service.py:14` — `Path.home() / ".nanobot"` → `get_runtime_home()`

### Workspace
- [ ] `mc/infrastructure/agent_bootstrap.py:147` — `Path.home() / ".nanobot" / "workspace"` → `get_workspace_dir()`
- [ ] `mc/infrastructure/agent_bootstrap.py:349` — same pattern
- [ ] `mc/contexts/execution/agent_runner.py:128` — `Path.home() / ".nanobot" / "agents" / agent_name` → `get_agents_dir() / agent_name` (agents, not workspace)
- [ ] `mc/contexts/execution/agent_runner.py:130` — `Path.home() / ".nanobot" / "workspace" / "skills"` → `get_workspace_dir() / "skills"`
- [ ] `mc/contexts/execution/cc_executor.py:578` — `Path.home() / ".nanobot" / "workspace" / "HEARTBEAT.md"` → `get_workspace_dir() / "HEARTBEAT.md"`
- [ ] `mc/contexts/execution/completion_reporting.py:31` — same heartbeat pattern

## File List
- `mc/infrastructure/agent_bootstrap.py`
- `mc/infrastructure/boards.py`
- `mc/artifacts/service.py`
- `mc/contexts/execution/agent_runner.py`
- `mc/contexts/execution/cc_executor.py`
- `mc/contexts/execution/completion_reporting.py`

## Dev Notes
- `agent_bootstrap.py` has multiple domains (boards, workspace, memory_settings) — this story only handles boards and workspace lines. Memory settings is story 3-6.
- `agent_runner.py:128` uses agents path, not workspace — use `get_agents_dir()` there
- Import what you need: `from mc.infrastructure.runtime_home import get_boards_dir, get_workspace_dir, get_agents_dir, get_runtime_home`
- `cc_executor.py:87,108` are tasks domain (story 3-4) — only touch line 578 here
