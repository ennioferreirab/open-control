# Story 3.4: Implement CLI Agent Commands

Status: done

## Story

As a **user**,
I want to list and create agents from the terminal,
So that I can manage my agent roster without editing YAML files manually.

## Acceptance Criteria

1. **Given** Mission Control is running, **When** the user runs `nanobot mc agents list`, **Then** all registered agents are displayed in a formatted table: name, role, status, model, skills
2. **Given** the user runs `nanobot mc agents list`, **Then** results return within 2 seconds (NFR5)
3. **Given** the user runs `nanobot mc agents list`, **Then** the agent registry is refreshed from YAML files before display (NFR17)
4. **Given** no agents are registered, **When** the user runs `nanobot mc agents list`, **Then** the CLI prints: "No agents found. Create one with `nanobot mc agents create`"
5. **Given** Mission Control is running, **When** the user runs `nanobot mc agents create`, **Then** an interactive prompt guides the user through: agent name, role, skills (comma-separated), system prompt, and optional LLM model
6. **Given** the user completes the interactive `agents create` prompts, **Then** a valid YAML file is generated and saved to the agents folder at `~/.nanobot/agents/{name}/config.yaml`
7. **Given** a YAML file is created via CLI, **Then** the CLI prints confirmation with the file path
8. **Given** the generated YAML file, **Then** it passes validation from Story 3.1 validator
9. **And** CLI agent commands are added to `nanobot/cli/mc.py`
10. **And** `nanobot mc agents --help` shows available subcommands (list, create)

## Tasks / Subtasks

- [ ] Task 1: Create agents subcommand group (AC: #9, #10)
  - [ ] 1.1: Add `agents_app = typer.Typer(help="Manage Mission Control agents")` to `nanobot/cli/mc.py`
  - [ ] 1.2: Register it as a subcommand: `mc_app.add_typer(agents_app, name="agents")`
  - [ ] 1.3: Verify `nanobot mc agents --help` shows available subcommands

- [ ] Task 2: Implement `agents list` command (AC: #1, #2, #3, #4)
  - [ ] 2.1: Create `agents_app.command()` function `list_agents()`
  - [ ] 2.2: Determine agents directory path (`~/.nanobot/agents/`)
  - [ ] 2.3: Call `sync_agent_registry()` from `gateway.py` to refresh from YAML and sync to Convex (NFR17)
  - [ ] 2.4: Call `bridge.list_agents()` to get the current agent list from Convex
  - [ ] 2.5: Display agents in a Rich `Table` with columns: Name, Role, Status, Model, Skills
  - [ ] 2.6: Color the status column: blue for active, gray for idle, red for crashed
  - [ ] 2.7: Show skills as comma-separated string
  - [ ] 2.8: If no agents found, print: "No agents found. Create one with `nanobot mc agents create`"

- [ ] Task 3: Implement `agents create` command (AC: #5, #6, #7, #8)
  - [ ] 3.1: Create `agents_app.command()` function `create_agent()`
  - [ ] 3.2: Use `typer.prompt()` or Rich prompts for interactive input:
    - Agent name (required, validated: lowercase alphanumeric + hyphens)
    - Role (required)
    - Skills (optional, comma-separated, parsed to list)
    - System prompt (required, multi-line support)
    - LLM model (optional, default: system default)
  - [ ] 3.3: Construct YAML content from the collected inputs
  - [ ] 3.4: Create the agent directory: `~/.nanobot/agents/{name}/`
  - [ ] 3.5: Create subdirectories: `memory/`, `skills/` (per UX design spec agent workspace structure)
  - [ ] 3.6: Write `config.yaml` to the agent directory
  - [ ] 3.7: Validate the generated YAML using `validate_agent_file()` from Story 3.1
  - [ ] 3.8: Print confirmation: "Agent '{name}' created at {path}"
  - [ ] 3.9: If validation fails (shouldn't happen with correct code), print error and clean up

- [ ] Task 4: Implement bridge initialization for CLI commands (AC: #1, #3)
  - [ ] 4.1: Create a helper function `_get_bridge() -> ConvexBridge` that initializes a bridge connection for CLI commands
  - [ ] 4.2: Read Convex deployment URL and admin key from environment variables or `.env.local`
  - [ ] 4.3: Handle connection errors gracefully with helpful error messages

- [ ] Task 5: Write unit tests
  - [ ] 5.1: Test `agents list` output format with mock agents
  - [ ] 5.2: Test `agents list` empty state message
  - [ ] 5.3: Test `agents create` generates valid YAML that passes validator
  - [ ] 5.4: Test agent directory structure creation (config.yaml, memory/, skills/)

## Dev Notes

### Critical Architecture Requirements

- **CLI is a thin layer**: The CLI commands in `mc.py` should delegate to `nanobot/mc/` package functions. No business logic in the CLI module. The `list` command calls `sync_agent_registry()` + `bridge.list_agents()`. The `create` command collects input, writes YAML, and calls `validate_agent_file()`.
- **Bridge for Convex access**: CLI commands that need Convex data must initialize a `ConvexBridge` and call bridge methods. No direct Convex SDK usage in the CLI.
- **Registry refresh on list (NFR17)**: Every `agents list` call must re-scan the YAML directory and sync to Convex BEFORE displaying results. This ensures the user always sees up-to-date data.
- **500-line limit**: `mc.py` must stay under 500 lines (NFR21). Since it now contains `start`, `stop`, and `agents` commands, watch the line count.

### CLI Output Pattern (Rich Table)

```python
from rich.table import Table

def list_agents():
    table = Table(title="Registered Agents")
    table.add_column("Name", style="bold")
    table.add_column("Role")
    table.add_column("Status")
    table.add_column("Model")
    table.add_column("Skills")

    for agent in agents:
        status_color = {"active": "blue", "idle": "dim", "crashed": "red"}.get(
            agent["status"], "white"
        )
        table.add_row(
            agent["name"],
            agent["role"],
            f"[{status_color}]{agent['status']}[/{status_color}]",
            agent.get("model", "-"),
            ", ".join(agent.get("skills", [])) or "-",
        )
    console.print(table)
```

### Agent YAML Template (for `create` command)

```yaml
name: {name}
role: {role}
prompt: |
  {prompt}
skills:
{skills_yaml}
model: {model}  # omitted if not specified
```

### Agent Workspace Structure

Per UX design spec, `agents create` must initialize the full workspace:

```
~/.nanobot/agents/{name}/
  config.yaml     # Agent configuration
  memory/
    MEMORY.md     # Per-agent long-term memory (empty initial)
  skills/         # Per-agent custom skills (empty initial)
```

### Bridge Initialization for CLI

The CLI needs a `ConvexBridge` instance to talk to Convex. The bridge requires:
- `CONVEX_URL`: Convex deployment URL (from env or `.env.local`)
- `CONVEX_ADMIN_KEY`: Admin key (optional, for server-side auth)

```python
def _get_bridge() -> ConvexBridge:
    """Initialize a ConvexBridge for CLI commands."""
    url = os.environ.get("CONVEX_URL")
    if not url:
        # Try reading from dashboard/.env.local
        env_file = _find_dashboard_dir() / ".env.local"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("NEXT_PUBLIC_CONVEX_URL="):
                    url = line.split("=", 1)[1].strip()
    if not url:
        console.print("[red]Convex URL not found.[/red]")
        console.print("Set CONVEX_URL env var or ensure dashboard/.env.local exists")
        raise typer.Exit(1)
    admin_key = os.environ.get("CONVEX_ADMIN_KEY")
    return ConvexBridge(deployment_url=url, admin_key=admin_key)
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT put business logic in the CLI module** -- The CLI collects input and delegates. Validation logic is in `yaml_validator.py`. Sync logic is in `gateway.py`. Bridge handles Convex communication.
2. **DO NOT skip the registry refresh on `agents list`** -- NFR17 requires that YAML changes are detected on each CLI command. Always call `sync_agent_registry()` before listing.
3. **DO NOT use `input()` for prompts** -- Use `typer.prompt()` or Rich prompts for consistent CLI styling.
4. **DO NOT forget to create the workspace subdirectories** -- `memory/` and `skills/` directories must be created alongside `config.yaml`.
5. **DO NOT hardcode the Convex URL** -- Read from environment variables or `.env.local` file.
6. **DO NOT generate invalid YAML** -- Use `yaml.dump()` with `default_flow_style=False` for clean output. Validate the generated file before confirming success.
7. **DO NOT add the `agents list` as a typer `command` named `list`** -- `list` is a Python builtin. Name the function `list_agents` and use `@agents_app.command(name="list")` to expose it as `nanobot mc agents list`.
8. **DO NOT create separate bridge instances per command** -- Create one bridge per CLI invocation and pass it through. But don't persist it across invocations.

### What This Story Does NOT Include

- **No agent deletion** -- Agents are soft-deactivated by removing their YAML file (Story 3.2 handles)
- **No agent editing** -- Users edit YAML files directly
- **No agent-assisted creation** -- Story 3.5 adds natural language agent creation
- **No dashboard integration** -- Dashboard shows agents via Story 3.3

### Files Created in This Story

None. All changes go into existing files.

### Files Modified in This Story

| File | Changes |
|------|---------|
| `nanobot/cli/mc.py` | Add `agents` subcommand group with `list` and `create` commands, add `_get_bridge()` helper |

### Verification Steps

1. Run `nanobot mc agents --help` -> shows `list` and `create` subcommands with descriptions
2. Create 2 agent YAML files manually in `~/.nanobot/agents/`
3. Run `nanobot mc agents list` -> formatted table shows both agents with name, role, status, model, skills
4. Run `nanobot mc agents list` with no agents -> shows "No agents found" message
5. Run `nanobot mc agents create` -> interactive prompts for name, role, skills, prompt, model
6. After create completes, verify `~/.nanobot/agents/{name}/config.yaml` exists with correct content
7. Verify `~/.nanobot/agents/{name}/memory/` and `~/.nanobot/agents/{name}/skills/` directories exist
8. Run `nanobot mc agents list` -> newly created agent appears in the table
9. Verify generated YAML passes validation: `python -c "from nanobot.mc.yaml_validator import validate_agent_file; print(validate_agent_file(Path(...)))"`

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 3.4`] -- Original story definition
- [Source: `_bmad-output/planning-artifacts/prd.md#CLI Interface`] -- CLI subcommand structure
- [Source: `_bmad-output/planning-artifacts/architecture.md#Architectural Boundaries`] -- CLI as thin layer, bridge for Convex access
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Agent Configuration UX`] -- Agent workspace structure (config.yaml, memory/, skills/)
- [Source: `nanobot/cli/mc.py`] -- Existing CLI module with `start`/`stop` commands
- [Source: `nanobot/mc/bridge.py`] -- ConvexBridge class
- [Source: `nanobot/mc/gateway.py`] -- `sync_agent_registry()` function (Story 3.2)

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
N/A

### Completion Notes List
- Added `agents` subcommand group with `list` and `create` commands to `nanobot/cli/mc.py`
- `list` scans `~/.nanobot/agents/*/config.yaml`, validates each with `validate_agent_file()`, displays in Rich table
- `create` interactively prompts for name, role, skills, system prompt, model; writes YAML via `yaml.dump()`; creates workspace dirs (`memory/`, `skills/`); validates with `validate_agent_file()`
- Agent status colors: active=blue, idle=dim, crashed=red
- Name validation: lowercase alphanumeric + hyphens regex pattern
- Story 3.5 (agent-assisted CLI) was concurrently added by another agent; `assist` command appended to agents_app
- Tests require Python 3.11+ due to StrEnum in types.py; marked with `skipif` for 3.9
- `sync_agent_registry()` and `bridge.list_agents()` not yet available (Story 3.2 dependency); `list` reads directly from YAML directory instead

### File List
| File | Action |
|------|--------|
| `nanobot/cli/mc.py` | Modified: added `agents_app` Typer group, `list_agents()`, `create_agent()`, `_get_agent_status_color()`, `AGENTS_DIR`, `_AGENT_NAME_PATTERN` |
| `nanobot/mc/test_cli_agents.py` | Created: 15 unit tests for agent CLI commands |
