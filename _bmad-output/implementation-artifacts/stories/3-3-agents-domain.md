# Story 3-3: Migrate agents domain paths

## Story
As a developer, I need all agent directory resolution to go through `get_agents_dir()` so agent storage location is consistent when `OPEN_CONTROL_HOME` is set.

## Status: ready

## Acceptance Criteria
- [ ] All 6 files below use `get_agents_dir()` instead of `Path.home() / ".nanobot" / "agents"`
- [ ] No remaining hardcoded `.nanobot/agents` in Python source (excluding vendor/, tests/, docs/)
- [ ] `make validate` passes

## Tasks
- [ ] `mc/cli/init_wizard.py:28` — `AGENTS_DIR = Path.home() / ".nanobot" / "agents"` → `AGENTS_DIR = get_agents_dir()`
- [ ] `mc/cli/agents.py:336` — `Path.home() / ".nanobot" / "agents" / agent_name` → `get_agents_dir() / agent_name`
- [ ] `mc/cli/agent_assist.py:201` — `Path.home() / ".nanobot" / "agents" / name` → `get_agents_dir() / name`
- [ ] `mc/contexts/conversation/mentions/handler.py:47` — `Path.home() / ".nanobot" / "agents"` → `get_agents_dir()`
- [ ] `mc/infrastructure/boards.py:37` — `Path.home() / ".nanobot" / "agents" / agent_name` → `get_agents_dir() / agent_name`
- [ ] `mc/contexts/agents/spec_migration.py:263` — `default=Path.home() / ".nanobot" / "agents"` → `default=get_agents_dir()`

## File List
- `mc/cli/init_wizard.py`
- `mc/cli/agents.py`
- `mc/cli/agent_assist.py`
- `mc/contexts/conversation/mentions/handler.py`
- `mc/infrastructure/boards.py`
- `mc/contexts/agents/spec_migration.py`

## Dev Notes
- Import: `from mc.infrastructure.runtime_home import get_agents_dir`
- `boards.py:123,170` also reference `.nanobot/agents` but inside `get_board_workspace_path()` return values — check if those are separate board workspace paths or agent paths. Line 123: `Path.home() / ".nanobot" / "agents" / agent_name / "memory"` → `get_agents_dir() / agent_name / "memory"`
- `boards.py:170`: `Path.home() / ".nanobot" / "agents" / agent_name / "memory" / "MEMORY.md"` → `get_agents_dir() / agent_name / "memory" / "MEMORY.md"`
- `boards.py:210`: `Path.home() / ".nanobot" / "boards"` → this is boards domain, use `get_boards_dir()` (story 3-5 handles boards)
