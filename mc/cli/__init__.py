"""CLI commands for Open Control lifecycle management."""

from __future__ import annotations

import os
import re
from pathlib import Path

import typer
from rich.console import Console

from mc.infrastructure.config import AGENTS_DIR

mc_app = typer.Typer(
    help="Open Control - multi-agent orchestration dashboard",
    no_args_is_help=True,
)

console = Console()
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
    return Path.cwd() / "dashboard"


def _cleanup_pid_file() -> None:
    """Remove the PID file."""
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


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
        console.print("Set CONVEX_URL environment variable or ensure dashboard/.env.local exists.")
        raise typer.Exit(1)

    admin_key = os.environ.get("CONVEX_ADMIN_KEY")
    if not admin_key:
        from mc.infrastructure.config import _resolve_admin_key

        admin_key = _resolve_admin_key()
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
        "ready": "blue",
        "failed": "red",
        "deleted": "dim",
    }.get(status, "white")


def _get_agent_status_color(status: str) -> str:
    """Map agent status to Rich color name."""
    return {"active": "blue", "idle": "dim", "crashed": "red"}.get(status, "white")


def _sync_to_convex() -> None:
    """Try to sync local agents and skills to Convex. Silently skip if unavailable."""
    from mc.infrastructure.agent_bootstrap import sync_agent_registry, sync_skills

    try:
        bridge = _get_bridge()
    except (SystemExit, Exception):
        return

    try:
        synced, errors = sync_agent_registry(bridge, AGENTS_DIR)
        if synced:
            console.print(f"[dim]Synced {len(synced)} agent(s) to Convex.[/dim]")
        for filename, errs in errors.items():
            for err in errs:
                console.print(f"[yellow]Sync warning ({filename}): {err}[/yellow]")

        try:
            skill_names = sync_skills(bridge)
            if skill_names:
                console.print(f"[dim]Synced {len(skill_names)} skill(s) to Convex.[/dim]")
        except Exception as exc:
            console.print(f"[yellow]Skills sync skipped: {exc}[/yellow]")
    except Exception as exc:
        console.print(f"[yellow]Sync skipped: {exc}[/yellow]")
    finally:
        bridge.close()


_AGENT_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

from mc.cli.agents import agents_app, register_init_command, register_sessions_command  # noqa: E402
from mc.cli.lifecycle import register_lifecycle_commands  # noqa: E402
from mc.cli.schema_docs import register_docs_command  # noqa: E402
from mc.cli.sync import register_sync_command  # noqa: E402
from mc.cli.tasks import tasks_app  # noqa: E402

mc_app.add_typer(tasks_app, name="tasks")
mc_app.add_typer(agents_app, name="agents")
register_lifecycle_commands(mc_app)
register_docs_command(mc_app)
register_sessions_command(mc_app)
register_init_command(mc_app)
register_sync_command(mc_app)
