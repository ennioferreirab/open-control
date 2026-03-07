"""CLI commands for agent management (sessions, sync, list, create, assist, init)."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

console = Console()

_AGENT_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

agents_app = typer.Typer(
    help="Manage Mission Control agents",
    no_args_is_help=True,
)


def register_sessions_command(mc_app: typer.Typer) -> None:
    """Register the sessions command on the main mc_app."""
    @mc_app.command()
    def sessions():
        """List active Claude Code agent sessions."""
        from mc.cli import _get_bridge

        bridge = _get_bridge()
        try:
            all_settings = bridge.query("settings:list") or []
            cc_sessions = [
                s for s in all_settings
                if isinstance(s.get("key"), str)
                and s["key"].startswith("cc_session:")
                and s.get("value")
            ]

            if not cc_sessions:
                console.print("No active CC sessions found.")
                return

            table = Table(title="Claude Code Sessions")
            table.add_column("Agent", style="bold")
            table.add_column("Task ID")
            table.add_column("Session ID")
            regular_sessions = []
            latest_sessions = []
            for entry in cc_sessions:
                key = entry.get("key", "")
                parts = key.split(":", 2)
                if len(parts) == 3:
                    _, agent_name_part, task_id_part = parts
                    if task_id_part == "latest":
                        latest_sessions.append(entry)
                    else:
                        regular_sessions.append(entry)

            for entry in sorted(regular_sessions, key=lambda x: x.get("key", "")):
                key = entry.get("key", "")
                value = entry.get("value", "")
                parts = key.split(":", 2)
                agent_col = parts[1] if len(parts) > 1 else key
                task_col = parts[2] if len(parts) > 2 else ""
                session_col = value[:40] + "..." if len(value) > 40 else value
                table.add_row(agent_col, task_col, session_col)

            for entry in sorted(latest_sessions, key=lambda x: x.get("key", "")):
                key = entry.get("key", "")
                value = entry.get("value", "")
                parts = key.split(":", 2)
                agent_col = parts[1] if len(parts) > 1 else key
                session_col = value[:40] + "..." if len(value) > 40 else value
                table.add_row(agent_col, "[dim]:latest[/dim]", session_col)

            console.print(table)
            console.print(f"\n  Total: {len(regular_sessions)} task session(s), {len(latest_sessions)} latest pointer(s)")
        finally:
            bridge.close()


@agents_app.command("sync")
def sync_agents():
    """Sync local agent YAML files and skills to Convex."""
    import mc.cli as _cli
    from mc.infrastructure.agent_bootstrap import sync_agent_registry, sync_skills

    if not _cli.AGENTS_DIR.is_dir():
        console.print("No agents directory found. Nothing to sync.")
        raise typer.Exit(0)

    bridge = _cli._get_bridge()
    try:
        synced, errors = sync_agent_registry(bridge, _cli.AGENTS_DIR)

        if synced:
            table = Table(title="Synced Agents")
            table.add_column("Name", style="bold")
            table.add_column("Role")
            table.add_column("Model")
            for agent in synced:
                table.add_row(agent.name, agent.role, agent.model or "-")
            console.print(table)
        else:
            console.print("No valid agents found to sync.")

        for filename, errs in errors.items():
            console.print(f"[red]Invalid: {filename}[/red]")
            for e in errs:
                console.print(f"  - {e}")

        console.print(
            f"\n[green]{len(synced)} synced[/green]"
            + (f", [red]{len(errors)} failed[/red]" if errors else "")
        )
        try:
            skill_names = sync_skills(bridge)
            console.print(f"[green]{len(skill_names)} skill(s) synced[/green]")
        except Exception as exc:
            console.print(f"[yellow]Skills sync failed: {exc}[/yellow]")
    finally:
        bridge.close()


@agents_app.command("list")
def list_agents():
    """List all registered agents."""
    import mc.cli as _cli
    from mc.yaml_validator import validate_agent_file

    agents_dir = _cli.AGENTS_DIR
    valid_agents = []

    if agents_dir.is_dir():
        for child in sorted(agents_dir.iterdir()):
            config_file = child / "config.yaml"
            if child.is_dir() and config_file.is_file():
                result = validate_agent_file(config_file)
                if not isinstance(result, list):
                    valid_agents.append(result)

    if not valid_agents:
        console.print(
            "No agents found. Create one with `nanobot mc agents create`"
        )
        return

    table = Table(title="Registered Agents")
    table.add_column("Name", style="bold")
    table.add_column("Role")
    table.add_column("Status")
    table.add_column("Model")
    table.add_column("Skills")

    for agent in valid_agents:
        status_color = _cli._get_agent_status_color(agent.status)
        table.add_row(
            agent.name,
            agent.role,
            f"[{status_color}]{agent.status}[/{status_color}]",
            agent.model or "-",
            ", ".join(agent.skills) if agent.skills else "-",
        )

    console.print(table)


@agents_app.command("create")
def create_agent():
    """Create a new agent via interactive prompts."""
    import mc.cli as _cli
    from mc.yaml_validator import validate_agent_file

    console.print("[bold]Create a new agent[/bold]\n")
    while True:
        name = typer.prompt("Agent name (lowercase alphanumeric + hyphens)")
        name = name.strip().lower()
        if _AGENT_NAME_PATTERN.match(name):
            break
        console.print(
            "[red]Invalid name.[/red] Use lowercase letters, numbers, and hyphens "
            "(e.g., 'my-agent')."
        )
    role = typer.prompt("Role (e.g., 'Senior Developer')")
    skills_input = typer.prompt(
        "Skills (comma-separated, or leave empty)", default="", show_default=False
    )
    skills = [s.strip() for s in skills_input.split(",") if s.strip()]
    console.print("System prompt (enter your prompt, finish with an empty line):")
    prompt_lines = []
    while True:
        line = typer.prompt("", default="", show_default=False)
        if not line:
            break
        prompt_lines.append(line)
    prompt = "\n".join(prompt_lines)
    if not prompt.strip():
        prompt = typer.prompt("System prompt cannot be empty. Enter a prompt")
    model_input = typer.prompt(
        "LLM model (optional, press Enter to skip)", default="", show_default=False
    )
    model = model_input.strip() or None
    config_data = {
        "name": name,
        "role": role,
        "prompt": prompt,
        "skills": skills,
    }
    if model:
        config_data["model"] = model
    agent_dir = _cli.AGENTS_DIR / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "memory").mkdir(exist_ok=True)
    (agent_dir / "skills").mkdir(exist_ok=True)
    memory_file = agent_dir / "memory" / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("")
    from mc.agent_assist import ensure_soul_md
    ensure_soul_md(agent_dir, name, role)
    config_path = agent_dir / "config.yaml"
    config_path.write_text(
        yaml.dump(config_data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    result = validate_agent_file(config_path)
    if isinstance(result, list):
        console.print(f"[red]Validation failed:[/red]")
        for err in result:
            console.print(f"  - {err}")
        import shutil
        shutil.rmtree(agent_dir)
        raise typer.Exit(1)

    console.print(f"\n[green]Agent '{name}' created at {agent_dir}[/green]")
    _cli._sync_to_convex()


@agents_app.command("assist")
def assist_agent():
    """Create an agent from a natural language description (LLM-assisted)."""
    from rich.syntax import Syntax
    from mc.agent_assist import (
        build_llm_provider, create_agent_workspace,
        extract_yaml_from_response, generate_agent_yaml, validate_yaml_content,
    )

    console.print("[bold]Agent-Assisted Creation[/bold]\n")
    description = typer.prompt("Describe the agent you want to create")
    if not description.strip():
        console.print("[red]Description cannot be empty.[/red]")
        raise typer.Exit(1)

    provider = build_llm_provider()
    max_iterations = 3
    feedback: str | None = None

    for iteration in range(max_iterations):
        console.print("\nGenerating agent configuration...")
        raw = asyncio.run(generate_agent_yaml(provider, description, feedback=feedback))
        if not raw.strip():
            console.print("[red]LLM returned an empty response. Try again.[/red]")
            raise typer.Exit(1)

        yaml_text = extract_yaml_from_response(raw)
        parsed, errors = validate_yaml_content(yaml_text)

        if errors:
            console.print("\n[red]Validation errors:[/red]")
            for e in errors:
                console.print(f"  - {e}")
            if iteration < max_iterations - 1:
                console.print("\nRetrying with validation feedback...")
                feedback = "; ".join(errors)
                continue
            console.print("\n[red]Maximum retries reached.[/red]")
            raise typer.Exit(1)

        console.print()
        console.print(Syntax(yaml_text, "yaml", theme="monokai", line_numbers=False))
        console.print()

        choice = typer.prompt(
            "Save this configuration? [Y/n/edit]", default="Y", show_default=False
        ).strip().lower()

        if choice in ("y", ""):
            _save_assisted_agent(parsed["name"], yaml_text, create_agent_workspace)
            return
        elif choice == "n":
            console.print("Cancelled. No files were created.")
            raise typer.Exit(0)
        elif choice == "edit":
            if iteration >= max_iterations - 1:
                console.print("[yellow]Maximum feedback iterations reached.[/yellow]")
                if typer.prompt("Save current config? [Y/n]", default="Y").strip().lower() in ("y", ""):
                    _save_assisted_agent(parsed["name"], yaml_text, create_agent_workspace)
                else:
                    console.print("Cancelled.")
                return
            feedback = typer.prompt("What would you like to change?")
            if not feedback.strip():
                console.print("No feedback provided. Cancelled.")
                raise typer.Exit(0)
        else:
            console.print(f"[yellow]Unknown choice '{choice}'. Cancelled.[/yellow]")
            raise typer.Exit(0)


def _save_assisted_agent(agent_name, yaml_text, create_fn):
    """Save an assisted-generated agent, checking for overwrites."""
    import mc.cli as _cli
    from mc.yaml_validator import validate_agent_file

    agent_dir = Path.home() / ".nanobot" / "agents" / agent_name
    if agent_dir.exists():
        if not typer.confirm(f"Agent '{agent_name}' already exists. Overwrite?", default=False):
            console.print("Cancelled.")
            raise typer.Exit(0)

    config_path = create_fn(agent_name, yaml_text)
    result = validate_agent_file(config_path)
    if isinstance(result, list):
        console.print("[red]Saved file failed validation:[/red]")
        for err in result:
            console.print(f"  - {err}")
        raise typer.Exit(1)
    console.print(f"\n[green]Agent '{agent_name}' created at {config_path}[/green]")
    _cli._sync_to_convex()


def register_init_command(mc_app: typer.Typer) -> None:
    """Register the init wizard command on the main mc_app."""
    @mc_app.command()
    def init(
        skip_presets: bool = typer.Option(
            False, "--skip-presets", help="Skip preset agent selection"
        ),
        skip_custom: bool = typer.Option(
            False, "--skip-custom", help="Skip custom agent creation"
        ),
        yes: bool = typer.Option(
            False, "--yes", "-y", help="Auto-confirm (non-interactive)"
        ),
    ):
        """Guided setup wizard -- create a full agent team in one go."""
        import mc.cli as _cli
        from rich.rule import Rule

        from mc.init_wizard import (
            PRESETS,
            AgentPlan,
            agent_exists,
            build_lead_agent_yaml,
            build_preset_yaml,
            create_agents,
            lead_agent_exists,
        )

        plans: list[AgentPlan] = []
        console.print()
        console.print(Rule("[bold]Mission Control Setup Wizard[/bold]"))
        console.print()
        console.print("[bold]Step 1:[/bold] Lead Agent\n")

        if lead_agent_exists():
            console.print("  lead-agent already exists -- [dim]skipping[/dim]")
            plans.append(AgentPlan(
                name="lead-agent",
                role="Lead Agent -- Orchestrator",
                yaml_text="",
                source="lead",
                skip=True,
                skip_reason="already exists",
            ))
        else:
            console.print("  Will create [bold]lead-agent[/bold] (orchestrator)")
            plans.append(AgentPlan(
                name="lead-agent",
                role="Lead Agent -- Orchestrator",
                yaml_text=build_lead_agent_yaml(),
                source="lead",
            ))
        console.print()
        if not skip_presets:
            console.print("[bold]Step 2:[/bold] Preset Agents\n")
            console.print("  Available presets:")
            for i, p in enumerate(PRESETS, 1):
                exists_tag = " [dim](exists)[/dim]" if agent_exists(p.name) else ""
                console.print(f"    {i}. {p.name} -- {p.role}{exists_tag}")
            console.print()

            if yes:
                for p in PRESETS:
                    if agent_exists(p.name):
                        plans.append(AgentPlan(
                            name=p.name, role=p.role, yaml_text="",
                            source="preset", skip=True,
                            skip_reason="already exists",
                        ))
                    else:
                        plans.append(AgentPlan(
                            name=p.name, role=p.role,
                            yaml_text=build_preset_yaml(p), source="preset",
                        ))
            else:
                raw = typer.prompt(
                    "  Select presets (comma-separated numbers, 'all', or 'none')",
                    default="all",
                )
                raw = raw.strip().lower()

                if raw == "none":
                    selected_presets = []
                elif raw == "all":
                    selected_presets = list(PRESETS)
                else:
                    indices = []
                    for part in raw.split(","):
                        part = part.strip()
                        if part.isdigit():
                            idx = int(part) - 1
                            if 0 <= idx < len(PRESETS):
                                indices.append(idx)
                    selected_presets = [PRESETS[i] for i in sorted(set(indices))]

                for p in selected_presets:
                    if agent_exists(p.name):
                        if typer.confirm(
                            f"  Agent '{p.name}' already exists. Overwrite?",
                            default=False,
                        ):
                            plans.append(AgentPlan(
                                name=p.name, role=p.role,
                                yaml_text=build_preset_yaml(p), source="preset",
                            ))
                        else:
                            plans.append(AgentPlan(
                                name=p.name, role=p.role, yaml_text="",
                                source="preset", skip=True,
                                skip_reason="user declined overwrite",
                            ))
                    else:
                        plans.append(AgentPlan(
                            name=p.name, role=p.role,
                            yaml_text=build_preset_yaml(p), source="preset",
                        ))
            console.print()
        else:
            console.print("[bold]Step 2:[/bold] Preset Agents -- [dim]skipped[/dim]\n")
        if not skip_custom:
            console.print("[bold]Step 3:[/bold] Custom Agents\n")

            if yes:
                console.print("  --yes flag set -- [dim]skipping custom agents[/dim]")
            else:
                console.print(
                    "  Describe agents in plain English. "
                    "Leave blank when done."
                )
                while True:
                    description = typer.prompt(
                        "\n  Agent description (blank to finish)",
                        default="",
                        show_default=False,
                    )
                    if not description.strip():
                        break

                    console.print("  Generating agent configuration...")
                    yaml_text, errors = asyncio.run(
                        _generate_custom_agent_safe(description)
                    )
                    if errors:
                        console.print(f"  [red]Error:[/red] {'; '.join(errors)}")
                        continue

                    parsed = yaml.safe_load(yaml_text)
                    agent_name = parsed.get("name", "custom-agent")
                    agent_role = parsed.get("role", "Custom Agent")

                    console.print(f"  Generated: [bold]{agent_name}[/bold] -- {agent_role}")

                    if agent_exists(agent_name):
                        if not typer.confirm(
                            f"  Agent '{agent_name}' already exists. Overwrite?",
                            default=False,
                        ):
                            console.print("  Skipped.")
                            continue

                    plans.append(AgentPlan(
                        name=agent_name,
                        role=agent_role,
                        yaml_text=yaml_text,
                        source="custom",
                    ))
            console.print()
        else:
            console.print("[bold]Step 3:[/bold] Custom Agents -- [dim]skipped[/dim]\n")
        console.print("[bold]Step 4:[/bold] Review & Confirm\n")

        to_create = [p for p in plans if not p.skip]
        to_skip = [p for p in plans if p.skip]

        if not to_create:
            console.print("  Nothing to create -- all agents already exist or were skipped.")
            raise typer.Exit(0)

        table = Table(title="Agents to Create")
        table.add_column("Name", style="bold")
        table.add_column("Role")
        table.add_column("Source")
        for p in to_create:
            table.add_row(p.name, p.role, p.source)
        console.print(table)

        if to_skip:
            console.print(f"\n  [dim]Skipping {len(to_skip)} agent(s): "
                           f"{', '.join(p.name for p in to_skip)}[/dim]")

        console.print()

        if not yes:
            if not typer.confirm("  Proceed?", default=True):
                console.print("  Cancelled.")
                raise typer.Exit(0)

        results = create_agents(to_create)

        console.print()
        created = sum(1 for r in results if r.success and not r.error.startswith("skipped"))
        failed = sum(1 for r in results if not r.success)

        for r in results:
            if r.success and r.path:
                console.print(f"  [green]\u2713[/green] {r.name} \u2192 {r.path}")
            elif not r.success:
                console.print(f"  [red]\u2717[/red] {r.name} -- {r.error}")

        console.print(f"\n  [green]{created} agent(s) created.[/green]", end="")
        if failed:
            console.print(f"  [red]{failed} failed.[/red]", end="")
        console.print()

        if created > 0:
            _cli._sync_to_convex()


async def _generate_custom_agent_safe(description: str) -> tuple[str | None, list[str]]:
    """Wrapper around generate_custom_agent that catches provider errors."""
    try:
        from mc.init_wizard import generate_custom_agent
        return await generate_custom_agent(description)
    except SystemExit as exc:
        return None, [str(exc)]
    except Exception as exc:
        return None, [f"Generation failed: {exc}"]
