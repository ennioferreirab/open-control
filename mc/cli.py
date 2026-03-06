"""CLI commands for Mission Control lifecycle management."""

from __future__ import annotations

import asyncio
import os
import re
import signal
import subprocess
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

mc_app = typer.Typer(
    help="Mission Control \u2014 multi-agent orchestration dashboard",
    no_args_is_help=True,
)

console = Console()

# PID file location
PID_FILE = Path.home() / ".nanobot" / "mc.pid"

# Agents directory (also used by cli_agents via mc.cli.AGENTS_DIR)
AGENTS_DIR = Path.home() / ".nanobot" / "agents"

_AGENT_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


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
    if not admin_key:
        from mc.gateway import _resolve_admin_key

        admin_key = _resolve_admin_key()
    return ConvexBridge(convex_url, admin_key)


# ============================================================================
# Status color helpers (used by status command and by cli_config/cli_agents)
# ============================================================================


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
        "planning": "cyan",
        "ready": "blue",
        "failed": "red",
        "deleted": "dim",
    }.get(status, "white")


def _get_agent_status_color(status: str) -> str:
    """Map agent status to Rich color name."""
    return {"active": "blue", "idle": "dim", "crashed": "red"}.get(status, "white")


# ============================================================================
# Sync helper (used by cli_agents)
# ============================================================================


def _sync_to_convex() -> None:
    """Try to sync local agents and skills to Convex. Silently skip if Convex is unavailable."""
    from mc.gateway import sync_agent_registry, sync_skills

    try:
        bridge = _get_bridge()
    except (SystemExit, Exception):
        # Convex not configured -- skip sync silently
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


# ============================================================================
# Lifecycle Commands
# ============================================================================


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
            console.print(f"[green]\u2713[/green] Nanobot channels: {', '.join(enabled)}")
        else:
            console.print("[yellow]\u26a0[/yellow] No nanobot channels enabled")
    except Exception:
        pass

    # Pre-sync: update config.json from Convex BEFORE nanobot gateway starts.
    try:
        bridge = _get_bridge()
        from mc.gateway import sync_nanobot_default_model

        if sync_nanobot_default_model(bridge):
            console.print("[green]\u2713[/green] Synced nanobot default model from dashboard")
    except Exception:
        pass  # Non-critical; mc.gateway will retry during its own startup

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

    # MC is running -- query Convex
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


# ============================================================================
# Register sub-apps from cli_agents and cli_config
# ============================================================================

from mc.cli_agents import (  # noqa: E402
    agents_app,
    register_init_command,
    register_sessions_command,
)
from mc.cli_config import (  # noqa: E402
    register_docs_command,
    tasks_app,
)

mc_app.add_typer(agents_app, name="agents")
mc_app.add_typer(tasks_app, name="tasks")

# Register top-level commands from sub-modules
register_sessions_command(mc_app)
register_init_command(mc_app)
register_docs_command(mc_app)
