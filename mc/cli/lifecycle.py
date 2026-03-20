"""Lifecycle and status commands for Open Control."""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import time
from pathlib import Path

import typer
from rich.table import Table


def _kill_stale_processes() -> None:
    """Kill stale processes from a previous MC session to avoid conflicts."""
    import mc.cli as _cli

    dashboard_dir = str(_cli._find_dashboard_dir())
    patterns = [
        "mc.runtime.gateway",
        "-m nanobot gateway",
    ]
    dashboard_patterns = [
        "next dev",
        "convex dev",
        "npm-run-all",
    ]
    try:
        result = subprocess.run(
            ["ps", "ax", "-o", "pid,command"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return

    my_pid = os.getpid()
    killed: list[int] = []
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
        should_kill = any(pat in cmd for pat in patterns)
        if not should_kill:
            should_kill = any(pat in cmd and dashboard_dir in cmd for pat in dashboard_patterns)
        if should_kill:
            try:
                os.kill(pid, signal.SIGTERM)
                killed.append(pid)
            except OSError:
                pass

    if killed:
        _cli.console.print(f"[dim]Cleaned up {len(killed)} stale process(es)[/dim]")
        time.sleep(2)
        for pid in killed:
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
                _cli.console.print(f"[dim]Force-killed unresponsive process {pid}[/dim]")
            except OSError:
                pass


def _stop_mc() -> None:
    """Send SIGTERM to the running Open Control process."""
    import mc.cli as _cli

    if not _cli.PID_FILE.exists():
        _cli.console.print("Open Control is not running.")
        raise typer.Exit(0)

    try:
        pid = int(_cli.PID_FILE.read_text().strip())
    except (ValueError, OSError):
        _cli.console.print("Open Control is not running (invalid PID file).")
        _cli._cleanup_pid_file()
        raise typer.Exit(0) from None

    try:
        os.kill(pid, 0)
    except OSError:
        _cli.console.print("Open Control is not running (stale PID file).")
        _cli._cleanup_pid_file()
        raise typer.Exit(0) from None

    _cli.console.print("[yellow]Stopping Open Control...[/yellow]")
    os.kill(pid, signal.SIGTERM)
    _cli.console.print("[green]Shutdown signal sent.[/green]")


def register_lifecycle_commands(mc_app: typer.Typer) -> None:
    """Register lifecycle commands on the main mc_app."""

    @mc_app.command()
    def start(
        dashboard_dir: str = typer.Option(
            None,
            "--dashboard-dir",
            "-d",
            help="Path to dashboard directory (auto-detected if not specified)",
        ),
        local: bool = typer.Option(
            False,
            "--local",
            help="Use a local Convex deployment explicitly (default behavior).",
        ),
        cloud: bool = typer.Option(
            False,
            "--cloud",
            help="Use the hosted Convex development deployment instead of local.",
        ),
    ):
        """Start Open Control (dashboard + agent gateway + nanobot channels)."""
        import mc.cli as _cli
        from mc.cli.process_manager import ProcessManager

        if local and cloud:
            _cli.console.print("[red]Choose only one of --local or --cloud.[/red]")
            raise typer.Exit(1)

        resolved_dir = Path(dashboard_dir) if dashboard_dir else _cli._find_dashboard_dir()
        convex_mode = "cloud" if cloud else "local"

        if not resolved_dir.is_dir():
            _cli.console.print(f"[red]Dashboard directory not found: {resolved_dir}[/red]")
            _cli.console.print("Run from the project root or specify --dashboard-dir")
            raise typer.Exit(1)

        if _cli.PID_FILE.exists():
            try:
                old_pid = int(_cli.PID_FILE.read_text().strip())
                os.kill(old_pid, 0)
                _cli.console.print(
                    f"[yellow]Open Control is already running (PID {old_pid}).[/yellow]"
                )
                _cli.console.print("Run [bold]open-control mc down[/bold] first.")
                raise typer.Exit(1)
            except (ValueError, OSError):
                _cli._cleanup_pid_file()

        _cli.console.print("[bold]Starting Open Control...[/bold]")
        _kill_stale_processes()

        _cli.PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        _cli.PID_FILE.write_text(str(os.getpid()))

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
                _cli.console.print(f"[green]✓[/green] Nanobot channels: {', '.join(enabled)}")
            else:
                _cli.console.print("[yellow]⚠[/yellow] No nanobot channels enabled")
        except Exception:
            pass

        if convex_mode == "cloud":
            try:
                bridge = _cli._get_bridge()
                from mc.infrastructure.agent_bootstrap import sync_nanobot_default_model

                if sync_nanobot_default_model(bridge):
                    _cli.console.print(
                        "[green]✓[/green] Synced nanobot default model from dashboard"
                    )
            except Exception:
                pass

        async def _run():
            pm = ProcessManager(dashboard_dir=resolved_dir, convex_mode=convex_mode)
            try:
                await pm.start()
                _cli.console.print("[green]Open Control is running[/green]")
                _cli.console.print("  Dashboard: [cyan]http://localhost:3000[/cyan]")
                _cli.console.print(f"  Convex:    [cyan]{convex_mode}[/cyan]")
                _cli.console.print("  Nanobot:   [cyan]channels + agent gateway[/cyan]")
                await pm.wait()
            finally:
                await pm.stop()

        try:
            asyncio.run(_run())
        except KeyboardInterrupt:
            _cli.console.print("\n[yellow]Shutting down...[/yellow]")
        finally:
            _cli._cleanup_pid_file()

    @mc_app.command()
    def stop():
        """Stop Open Control gracefully."""
        _stop_mc()

    @mc_app.command()
    def down():
        """Bring down Open Control and all services."""
        _stop_mc()
        _kill_stale_processes()

    @mc_app.command()
    def status():
        """Show Open Control system health overview."""
        import mc.cli as _cli

        if not _cli.PID_FILE.exists():
            _cli.console.print(
                "Open Control is not running. Start with [bold]open-control mc start[/bold]"
            )
            raise typer.Exit(0)

        try:
            pid = int(_cli.PID_FILE.read_text().strip())
            os.kill(pid, 0)
        except (ValueError, OSError):
            _cli.console.print(
                "Open Control is not running (stale PID file). "
                "Start with [bold]open-control mc start[/bold]"
            )
            _cli._cleanup_pid_file()
            raise typer.Exit(0) from None

        _cli.console.print("[bold green]Open Control is running[/bold green]\n")

        try:
            bridge = _cli._get_bridge()
        except SystemExit:
            _cli.console.print("[yellow]Cannot connect to Convex.[/yellow]")
            raise typer.Exit(1) from None

        try:
            _cli.console.print("  Dashboard: [cyan]http://localhost:3000[/cyan]")
            pid_mtime = _cli.PID_FILE.stat().st_mtime
            uptime_seconds = int(time.time() - pid_mtime)
            hours, remainder = divmod(uptime_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            _cli.console.print(f"  Uptime:    {hours}h {minutes}m {seconds}s\n")

            agents = bridge.query("agents:list") or []
            agent_table = Table(title="Agents")
            agent_table.add_column("Name", style="bold")
            agent_table.add_column("Status")
            agent_table.add_column("Last Active")

            for agent in agents:
                status_val = agent.get("status", "unknown")
                color = _cli._get_agent_status_color(status_val)
                last_active = (agent.get("last_active_at") or "")[:19] or "-"
                agent_table.add_row(
                    agent.get("name", "?"),
                    f"[{color}]{status_val}[/{color}]",
                    last_active,
                )

            if agents:
                _cli.console.print(agent_table)
            else:
                _cli.console.print("  No agents registered.\n")

            tasks = bridge.query("tasks:list") or []
            status_counts: dict[str, int] = {}
            for task in tasks:
                status_name = task.get("status", "unknown")
                status_counts[status_name] = status_counts.get(status_name, 0) + 1

            task_table = Table(title="Tasks")
            task_table.add_column("Status", style="bold")
            task_table.add_column("Count", justify="right")

            for status_name in [
                "inbox",
                "assigned",
                "in_progress",
                "review",
                "done",
                "retrying",
                "crashed",
            ]:
                count = status_counts.get(status_name, 0)
                if count > 0 or status_name in ("inbox", "in_progress", "done"):
                    color = _cli._get_status_color(status_name)
                    task_table.add_row(f"[{color}]{status_name}[/{color}]", str(count))

            _cli.console.print(task_table)
            _cli.console.print(f"\n  Total tasks: {len(tasks)}")
        except Exception as exc:
            _cli.console.print(f"[red]Error querying system state: {exc}[/red]")
        finally:
            bridge.close()
