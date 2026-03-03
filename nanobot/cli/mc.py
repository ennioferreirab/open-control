"""CLI commands for Mission Control lifecycle management."""

from __future__ import annotations

import asyncio
import os
import re
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

mc_app = typer.Typer(
    help="Mission Control \u2014 multi-agent orchestration dashboard",
    no_args_is_help=True,
)

console = Console()

# PID file location
PID_FILE = Path.home() / ".nanobot" / "mc.pid"


def _find_dashboard_dir() -> Path:
    """Locate the dashboard directory relative to the project root."""
    candidates = [
        Path.cwd() / "dashboard",
        Path(__file__).resolve().parents[2] / "dashboard",
    ]
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "package.json").exists():
            return candidate
    return Path.cwd() / "dashboard"  # Fallback


def _kill_stale_processes() -> None:
    """Kill stale processes from a previous MC session to avoid conflicts."""
    dashboard_dir = str(_find_dashboard_dir())
    # Always-kill patterns (nanobot-specific, safe to match globally)
    patterns = [
        "mc.gateway",
        "-m nanobot gateway",
    ]
    # Dashboard-scoped patterns (only kill if the command references our dashboard)
    dashboard_patterns = [
        "next dev",
        "convex dev",
        "npm-run-all",
    ]
    try:
        result = subprocess.run(
            ["ps", "ax", "-o", "pid,command"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return

    my_pid = os.getpid()
    killed = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        if pid == my_pid:
            continue
        cmd = parts[1]
        should_kill = False
        for pat in patterns:
            if pat in cmd:
                should_kill = True
                break
        if not should_kill:
            for pat in dashboard_patterns:
                if pat in cmd and dashboard_dir in cmd:
                    should_kill = True
                    break
        if should_kill:
            try:
                os.kill(pid, signal.SIGTERM)
                killed.append(pid)
            except OSError:
                pass

    if killed:
        console.print(f"[dim]Cleaned up {len(killed)} stale process(es)[/dim]")
        time.sleep(2)  # Give processes time to shut down gracefully
        # Force-kill any processes that didn't respond to SIGTERM
        for pid in killed:
            try:
                os.kill(pid, 0)  # Check if still alive
                os.kill(pid, signal.SIGKILL)
                console.print(f"[dim]Force-killed unresponsive process {pid}[/dim]")
            except OSError:
                pass  # Process already exited


@mc_app.command()
def start(
    dashboard_dir: str = typer.Option(
        None,
        "--dashboard-dir",
        "-d",
        help="Path to dashboard directory (auto-detected if not specified)",
    ),
):
    """Start Mission Control (dashboard + agent gateway + nanobot channels)."""
    from mc.process_manager import ProcessManager

    resolved_dir = Path(dashboard_dir) if dashboard_dir else _find_dashboard_dir()

    if not resolved_dir.is_dir():
        console.print(f"[red]Dashboard directory not found: {resolved_dir}[/red]")
        console.print("Run from the project root or specify --dashboard-dir")
        raise typer.Exit(1)

    # Check for already-running instance
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            os.kill(old_pid, 0)
            console.print(
                f"[yellow]Mission Control is already running (PID {old_pid}).[/yellow]"
            )
            console.print("Run [bold]nanobot mc down[/bold] first.")
            raise typer.Exit(1)
        except (ValueError, OSError):
            _cleanup_pid_file()

    console.print("[bold]Starting Mission Control...[/bold]")

    # Kill stale processes from previous sessions
    _kill_stale_processes()

    # Write PID file
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    # Show nanobot channel info
    try:
        from nanobot.config.loader import load_config
        config = load_config()
        enabled = []
        if config.channels.telegram.enabled:
            enabled.append("telegram")
        if config.channels.whatsapp.enabled:
            enabled.append("whatsapp")
        if config.channels.discord.enabled:
            enabled.append("discord")
        if config.channels.slack.enabled:
            enabled.append("slack")
        if config.channels.email.enabled:
            enabled.append("email")
        if enabled:
            console.print(f"[green]✓[/green] Nanobot channels: {', '.join(enabled)}")
        else:
            console.print("[yellow]⚠[/yellow] No nanobot channels enabled")
    except Exception:
        pass

    async def _run():
        pm = ProcessManager(dashboard_dir=resolved_dir)
        try:
            await pm.start()
            console.print("[green]Mission Control is running[/green]")
            console.print("  Dashboard: [cyan]http://localhost:3000[/cyan]")
            console.print("  Nanobot:   [cyan]channels + agent gateway[/cyan]")
            await pm.wait()
        finally:
            await pm.stop()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
    finally:
        _cleanup_pid_file()


def _stop_mc() -> None:
    """Send SIGTERM to the running Mission Control process."""
    if not PID_FILE.exists():
        console.print("Mission Control is not running.")
        raise typer.Exit(0)

    try:
        pid = int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        console.print("Mission Control is not running (invalid PID file).")
        _cleanup_pid_file()
        raise typer.Exit(0)

    try:
        os.kill(pid, 0)  # Signal 0 = check existence
    except OSError:
        console.print("Mission Control is not running (stale PID file).")
        _cleanup_pid_file()
        raise typer.Exit(0)

    console.print("[yellow]Stopping Mission Control...[/yellow]")
    os.kill(pid, signal.SIGTERM)
    console.print("[green]Shutdown signal sent.[/green]")


@mc_app.command()
def stop():
    """Stop Mission Control gracefully."""
    _stop_mc()


@mc_app.command()
def down():
    """Bring down Mission Control and all services."""
    _stop_mc()
    _kill_stale_processes()


def _cleanup_pid_file() -> None:
    """Remove the PID file."""
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


@mc_app.command()
def status():
    """Show Mission Control system health overview."""
    # Check if MC is running
    if not PID_FILE.exists():
        console.print(
            "Mission Control is not running. "
            "Start with [bold]nanobot mc start[/bold]"
        )
        raise typer.Exit(0)

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)  # Check process exists
    except (ValueError, OSError):
        console.print(
            "Mission Control is not running (stale PID file). "
            "Start with [bold]nanobot mc start[/bold]"
        )
        _cleanup_pid_file()
        raise typer.Exit(0)

    # MC is running — query Convex
    console.print("[bold green]Mission Control is running[/bold green]\n")

    try:
        bridge = _get_bridge()
    except SystemExit:
        console.print("[yellow]Cannot connect to Convex.[/yellow]")
        raise typer.Exit(1)

    try:
        # Dashboard URL
        console.print("  Dashboard: [cyan]http://localhost:3000[/cyan]")

        # Uptime
        pid_mtime = PID_FILE.stat().st_mtime
        uptime_seconds = int(time.time() - pid_mtime)
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        console.print(f"  Uptime:    {hours}h {minutes}m {seconds}s\n")

        # Agent status
        agents = bridge.query("agents:list") or []
        agent_table = Table(title="Agents")
        agent_table.add_column("Name", style="bold")
        agent_table.add_column("Status")
        agent_table.add_column("Last Active")

        for agent in agents:
            status_val = agent.get("status", "unknown")
            color = _get_agent_status_color(status_val)
            last_active = (agent.get("last_active_at") or "")[:19] or "-"
            agent_table.add_row(
                agent.get("name", "?"),
                f"[{color}]{status_val}[/{color}]",
                last_active,
            )

        if agents:
            console.print(agent_table)
        else:
            console.print("  No agents registered.\n")

        # Task counts by status
        tasks = bridge.query("tasks:list") or []
        status_counts: dict[str, int] = {}
        for task in tasks:
            s = task.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1

        task_table = Table(title="Tasks")
        task_table.add_column("Status", style="bold")
        task_table.add_column("Count", justify="right")

        for s in [
            "inbox",
            "assigned",
            "in_progress",
            "review",
            "done",
            "retrying",
            "crashed",
        ]:
            count = status_counts.get(s, 0)
            if count > 0 or s in ("inbox", "in_progress", "done"):
                color = _get_status_color(s)
                task_table.add_row(f"[{color}]{s}[/{color}]", str(count))

        console.print(task_table)
        console.print(f"\n  Total tasks: {len(tasks)}")

    except Exception as e:
        console.print(f"[red]Error querying system state: {e}[/red]")
    finally:
        bridge.close()


@mc_app.command()
def docs():
    """Show auto-generated API documentation from Convex schema."""
    from rich.markdown import Markdown

    dashboard_dir = _find_dashboard_dir()
    convex_dir = dashboard_dir / "convex"

    if not convex_dir.is_dir():
        console.print("[red]Convex directory not found.[/red]")
        raise typer.Exit(1)

    doc_lines = ["# Mission Control API Reference\n"]

    # Parse schema
    schema_file = convex_dir / "schema.ts"
    if schema_file.exists():
        doc_lines.append("## Tables\n")
        doc_lines.append(_parse_schema_tables(schema_file.read_text()))

    # Parse function files
    for ts_file in sorted(convex_dir.glob("*.ts")):
        if ts_file.name.startswith("_") or ts_file.name == "schema.ts":
            continue
        doc_lines.append(f"\n## {ts_file.stem}\n")
        doc_lines.append(
            _parse_convex_functions(ts_file.read_text(), ts_file.stem)
        )

    md_text = "\n".join(doc_lines)
    console.print(Markdown(md_text))


def _parse_schema_tables(schema_text: str) -> str:
    """Extract table definitions from a Convex schema.ts file."""
    lines = []
    # Match table names: defineTable pattern
    table_matches = re.findall(
        r"(\w+):\s*defineTable\(\{(.*?)\}\)", schema_text, re.DOTALL
    )
    for table_name, body in table_matches:
        lines.append(f"### {table_name}\n")
        # Extract field definitions: fieldName: v.type(...)
        fields = re.findall(r"(\w+):\s*v\.(\w+)\(([^)]*)\)", body)
        if fields:
            lines.append("| Field | Type | Detail |")
            lines.append("|-------|------|--------|")
            for field_name, vtype, detail in fields:
                detail_clean = detail.strip().strip('"').strip("'")
                lines.append(f"| {field_name} | {vtype} | {detail_clean} |")
        lines.append("")

    # Extract indexes
    index_matches = re.findall(
        r'\.index\("(\w+)",\s*\[([^\]]+)\]\)', schema_text
    )
    if index_matches:
        lines.append("### Indexes\n")
        for idx_name, idx_fields in index_matches:
            fields_clean = idx_fields.replace('"', "").strip()
            lines.append(f"- **{idx_name}**: [{fields_clean}]")
        lines.append("")

    return "\n".join(lines)


def _parse_convex_functions(file_text: str, module_name: str) -> str:
    """Extract exported query/mutation names from a Convex function file."""
    lines = []
    # Match exported queries and mutations
    exports = re.findall(
        r"export\s+const\s+(\w+)\s*=\s*(query|mutation|internalQuery|internalMutation)",
        file_text,
    )
    if exports:
        for func_name, func_type in exports:
            lines.append(f"- `{module_name}:{func_name}` ({func_type})")
    else:
        lines.append("_No exported functions found._")
    return "\n".join(lines)


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
    """Guided setup wizard — create a full agent team in one go."""
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

    # ------------------------------------------------------------------
    # Step 1 — Lead Agent
    # ------------------------------------------------------------------
    console.print("[bold]Step 1:[/bold] Lead Agent\n")

    if lead_agent_exists():
        console.print("  lead-agent already exists — [dim]skipping[/dim]")
        plans.append(AgentPlan(
            name="lead-agent",
            role="Lead Agent — Orchestrator",
            yaml_text="",
            source="lead",
            skip=True,
            skip_reason="already exists",
        ))
    else:
        console.print("  Will create [bold]lead-agent[/bold] (orchestrator)")
        plans.append(AgentPlan(
            name="lead-agent",
            role="Lead Agent — Orchestrator",
            yaml_text=build_lead_agent_yaml(),
            source="lead",
        ))
    console.print()

    # ------------------------------------------------------------------
    # Step 2 — Preset Agents
    # ------------------------------------------------------------------
    if not skip_presets:
        console.print("[bold]Step 2:[/bold] Preset Agents\n")
        console.print("  Available presets:")
        for i, p in enumerate(PRESETS, 1):
            exists_tag = " [dim](exists)[/dim]" if agent_exists(p.name) else ""
            console.print(f"    {i}. {p.name} — {p.role}{exists_tag}")
        console.print()

        if yes:
            # Non-interactive: add all presets that don't exist
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
        console.print("[bold]Step 2:[/bold] Preset Agents — [dim]skipped[/dim]\n")

    # ------------------------------------------------------------------
    # Step 3 — Custom Agents
    # ------------------------------------------------------------------
    if not skip_custom:
        console.print("[bold]Step 3:[/bold] Custom Agents\n")

        if yes:
            console.print("  --yes flag set — [dim]skipping custom agents[/dim]")
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

                # Extract name from generated YAML
                parsed = yaml.safe_load(yaml_text)
                agent_name = parsed.get("name", "custom-agent")
                agent_role = parsed.get("role", "Custom Agent")

                console.print(f"  Generated: [bold]{agent_name}[/bold] — {agent_role}")

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
        console.print("[bold]Step 3:[/bold] Custom Agents — [dim]skipped[/dim]\n")

    # ------------------------------------------------------------------
    # Step 4 — Review & Confirm
    # ------------------------------------------------------------------
    console.print("[bold]Step 4:[/bold] Review & Confirm\n")

    to_create = [p for p in plans if not p.skip]
    to_skip = [p for p in plans if p.skip]

    if not to_create:
        console.print("  Nothing to create — all agents already exist or were skipped.")
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

    # Create
    results = create_agents(to_create)

    console.print()
    created = sum(1 for r in results if r.success and not r.error.startswith("skipped"))
    failed = sum(1 for r in results if not r.success)

    for r in results:
        if r.success and r.path:
            console.print(f"  [green]✓[/green] {r.name} → {r.path}")
        elif not r.success:
            console.print(f"  [red]✗[/red] {r.name} — {r.error}")

    console.print(f"\n  [green]{created} agent(s) created.[/green]", end="")
    if failed:
        console.print(f"  [red]{failed} failed.[/red]", end="")
    console.print()

    if created > 0:
        _sync_to_convex()


async def _generate_custom_agent_safe(description: str) -> tuple[str | None, list[str]]:
    """Wrapper around generate_custom_agent that catches provider errors."""
    try:
        from mc.init_wizard import generate_custom_agent
        return await generate_custom_agent(description)
    except SystemExit as exc:
        return None, [str(exc)]
    except Exception as exc:
        return None, [f"Generation failed: {exc}"]


# ============================================================================
# Bridge Helper
# ============================================================================


def _get_bridge():
    """Create a ConvexBridge from environment variables."""
    from mc.bridge import ConvexBridge

    convex_url = os.environ.get("CONVEX_URL")
    if not convex_url:
        env_file = _find_dashboard_dir() / ".env.local"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("NEXT_PUBLIC_CONVEX_URL="):
                    convex_url = line.split("=", 1)[1].strip().strip('"')
                    break

    if not convex_url:
        console.print("[red]CONVEX_URL not set.[/red]")
        console.print(
            "Set CONVEX_URL environment variable or ensure dashboard/.env.local exists."
        )
        raise typer.Exit(1)

    admin_key = os.environ.get("CONVEX_ADMIN_KEY")
    return ConvexBridge(convex_url, admin_key)


def _get_status_color(status: str) -> str:
    """Map task status to Rich color name."""
    return {
        "inbox": "magenta",
        "assigned": "blue",
        "in_progress": "cyan",
        "review": "yellow",
        "done": "green",
        "retrying": "yellow",
        "crashed": "red",
    }.get(status, "white")


def _get_agent_status_color(status: str) -> str:
    """Map agent status to Rich color name."""
    return {"active": "blue", "idle": "dim", "crashed": "red"}.get(status, "white")


# Agents directory
AGENTS_DIR = Path.home() / ".nanobot" / "agents"

_AGENT_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


# ============================================================================
# Task Commands
# ============================================================================

tasks_app = typer.Typer(
    help="Manage Mission Control tasks",
    no_args_is_help=True,
)
mc_app.add_typer(tasks_app, name="tasks")


@tasks_app.command("create")
def tasks_create(
    title: str = typer.Argument(None, help="Task title"),
    description: str = typer.Option(
        None, "--description", "-d", help="Task description"
    ),
    tags: str = typer.Option(None, "--tags", "-t", help="Comma-separated tags"),
):
    """Create a new task."""
    if title is None:
        title = typer.prompt("Task title")

    bridge = _get_bridge()
    try:
        tag_list = (
            [t.strip() for t in tags.split(",") if t.strip()] if tags else None
        )
        args = {"title": title}
        if description:
            args["description"] = description
        if tag_list:
            args["tags"] = tag_list
        bridge.mutation("tasks:create", args)
        console.print(f"[green]Task created:[/green] {title}")
        console.print(f"  Status: inbox")
        console.print(
            f"  Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    finally:
        bridge.close()


@tasks_app.command("list")
def tasks_list():
    """List all tasks."""
    bridge = _get_bridge()
    try:
        tasks = bridge.query("tasks:list")
        if not tasks:
            console.print("No tasks found.")
            return

        status_order = [
            "inbox",
            "assigned",
            "in_progress",
            "review",
            "done",
            "retrying",
            "crashed",
        ]
        tasks.sort(
            key=lambda t: (
                status_order.index(t.get("status", "inbox"))
                if t.get("status", "inbox") in status_order
                else len(status_order)
            )
        )

        table = Table(title="Tasks")
        table.add_column("Status", style="bold")
        table.add_column("Title", max_width=50)
        table.add_column("Agent")
        table.add_column("Created")

        for task in tasks:
            status = task.get("status", "unknown")
            color = _get_status_color(status)
            title_text = task.get("title", "Untitled")
            if len(title_text) > 50:
                title_text = title_text[:47] + "..."
            agent = task.get("assigned_agent") or "-"
            created = (task.get("created_at") or "")[:10]

            table.add_row(
                f"[{color}]{status}[/{color}]",
                title_text,
                agent,
                created,
            )

        console.print(table)
    finally:
        bridge.close()


# ============================================================================
# Agent Commands
# ============================================================================

agents_app = typer.Typer(
    help="Manage Mission Control agents",
    no_args_is_help=True,
)
mc_app.add_typer(agents_app, name="agents")


def _sync_to_convex() -> None:
    """Try to sync local agents and skills to Convex. Silently skip if Convex is unavailable."""
    from mc.gateway import sync_agent_registry, sync_skills

    try:
        bridge = _get_bridge()
    except (SystemExit, Exception):
        # Convex not configured — skip sync silently
        return

    try:
        synced, errors = sync_agent_registry(bridge, AGENTS_DIR)
        if synced:
            console.print(
                f"[dim]Synced {len(synced)} agent(s) to Convex.[/dim]"
            )
        for filename, errs in errors.items():
            for e in errs:
                console.print(f"[yellow]Sync warning ({filename}): {e}[/yellow]")

        # Sync skills alongside agents (Story 8.2)
        try:
            skill_names = sync_skills(bridge)
            if skill_names:
                console.print(
                    f"[dim]Synced {len(skill_names)} skill(s) to Convex.[/dim]"
                )
        except Exception as exc:
            console.print(f"[yellow]Skills sync skipped: {exc}[/yellow]")
    except Exception as exc:
        console.print(f"[yellow]Sync skipped: {exc}[/yellow]")
    finally:
        bridge.close()


@agents_app.command("sync")
def sync_agents():
    """Sync local agent YAML files and skills to Convex."""
    from mc.gateway import sync_agent_registry, sync_skills

    if not AGENTS_DIR.is_dir():
        console.print("No agents directory found. Nothing to sync.")
        raise typer.Exit(0)

    bridge = _get_bridge()
    try:
        synced, errors = sync_agent_registry(bridge, AGENTS_DIR)

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

        # Sync skills (Story 8.2)
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
    from mc.yaml_validator import validate_agent_file

    # Scan agent directories for config.yaml files
    agents_dir = AGENTS_DIR
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
        status_color = _get_agent_status_color(agent.status)
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
    from mc.yaml_validator import validate_agent_file

    console.print("[bold]Create a new agent[/bold]\n")

    # Agent name
    while True:
        name = typer.prompt("Agent name (lowercase alphanumeric + hyphens)")
        name = name.strip().lower()
        if _AGENT_NAME_PATTERN.match(name):
            break
        console.print(
            "[red]Invalid name.[/red] Use lowercase letters, numbers, and hyphens "
            "(e.g., 'my-agent')."
        )

    # Role
    role = typer.prompt("Role (e.g., 'Senior Developer')")

    # Skills
    skills_input = typer.prompt(
        "Skills (comma-separated, or leave empty)", default="", show_default=False
    )
    skills = [s.strip() for s in skills_input.split(",") if s.strip()]

    # System prompt
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

    # Model (optional)
    model_input = typer.prompt(
        "LLM model (optional, press Enter to skip)", default="", show_default=False
    )
    model = model_input.strip() or None

    # Build YAML content
    config_data = {
        "name": name,
        "role": role,
        "prompt": prompt,
        "skills": skills,
    }
    if model:
        config_data["model"] = model

    # Create agent workspace
    agent_dir = AGENTS_DIR / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "memory").mkdir(exist_ok=True)
    (agent_dir / "skills").mkdir(exist_ok=True)

    # Write MEMORY.md
    memory_file = agent_dir / "memory" / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("")

    # Write SOUL.md
    from mc.agent_assist import ensure_soul_md
    ensure_soul_md(agent_dir, name, role)

    # Write config.yaml
    config_path = agent_dir / "config.yaml"
    config_path.write_text(
        yaml.dump(config_data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    # Validate the generated file
    result = validate_agent_file(config_path)
    if isinstance(result, list):
        console.print(f"[red]Validation failed:[/red]")
        for err in result:
            console.print(f"  - {err}")
        # Clean up on failure
        import shutil

        shutil.rmtree(agent_dir)
        raise typer.Exit(1)

    console.print(f"\n[green]Agent '{name}' created at {agent_dir}[/green]")
    _sync_to_convex()


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
    _sync_to_convex()
