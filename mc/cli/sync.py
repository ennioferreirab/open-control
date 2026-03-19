"""CLI command: nanobot mc sync — full platform sync."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

console = Console()


def register_sync_command(mc_app: typer.Typer) -> None:
    """Register the top-level ``nanobot mc sync`` command."""

    @mc_app.command()
    def sync() -> None:
        """Sync agents, skills, models, and settings to Convex.

        Runs the same sync sequence as gateway startup, without starting the
        runtime. Useful after editing agent YAML, creating skills, or changing
        model configuration.
        """
        from mc.cli import _get_bridge
        from mc.infrastructure.config import AGENTS_DIR

        bridge = _get_bridge()
        try:
            _run_sync(bridge, AGENTS_DIR)
        finally:
            bridge.close()


def _run_sync(bridge, agents_dir: Path) -> None:
    """Execute the full sync sequence with Rich output."""
    from mc.contexts.agents.sync import AgentSyncService
    from mc.infrastructure.agent_bootstrap import (
        _distribute_builtin_skills,
        sync_nanobot_default_model,
    )

    sync_service = AgentSyncService(bridge=bridge, agents_dir=agents_dir)

    totals = {"ok": 0, "warn": 0, "fail": 0}

    # 1. Agent registry
    _header("Agents")
    if agents_dir.is_dir():
        try:
            synced, errors = sync_service.sync_agent_registry()
            for agent in synced:
                console.print(f"  [green]✓[/green] {agent.name} ({agent.role})")
            for filename, errs in errors.items():
                for e in errs:
                    console.print(f"  [red]✗[/red] {filename}: {e}")
            totals["ok"] += len(synced)
            totals["fail"] += len(errors)
        except Exception as exc:
            _fail("Agent sync failed", exc, totals)
    else:
        console.print("  [dim]No agents directory found — skipped[/dim]")

    # 2. Nanobot default model
    _header("Default model")
    try:
        updated = sync_nanobot_default_model(bridge)
        if updated:
            console.print("  [green]✓[/green] Updated from Convex")
        else:
            console.print("  [dim]—[/dim] Already up to date")
        totals["ok"] += 1
    except Exception as exc:
        _fail("Default model sync failed", exc, totals)

    # 3. Distribute builtin skills
    _header("Skill distribution")
    try:
        from nanobot.config.loader import load_config as _lc

        from mc.skills import MC_SKILLS_DIR

        ws = _lc().workspace_path
        project_root = Path(__file__).resolve().parents[2]
        vendor_dir = project_root / "vendor" / "nanobot" / "nanobot" / "skills"
        _distribute_builtin_skills(ws / "skills", vendor_dir, MC_SKILLS_DIR)
        console.print("  [green]✓[/green] Builtin skills distributed to workspace")
        totals["ok"] += 1
    except Exception as exc:
        _fail("Skill distribution failed", exc, totals)

    # 4. Skills sync
    _header("Skills")
    try:
        skill_names = sync_service.sync_skills()
        console.print(f"  [green]✓[/green] {len(skill_names)} skill(s) synced")
        totals["ok"] += 1
    except Exception as exc:
        _fail("Skills sync failed", exc, totals)

    # 5. Model tiers
    _header("Model tiers")
    try:
        sync_service.sync_model_tiers()
        console.print("  [green]✓[/green] Connected models and tiers synced")
        totals["ok"] += 1
    except Exception as exc:
        _fail("Model tiers sync failed", exc, totals)

    # 6. Embedding model
    _header("Embedding model")
    try:
        sync_service.sync_embedding_model()
        console.print("  [green]✓[/green] Embedding model synced")
        totals["ok"] += 1
    except Exception as exc:
        _fail("Embedding model sync failed", exc, totals)

    # 7. Memory backup
    _header("Memory backup")
    try:
        from mc.infrastructure.agent_bootstrap import _backup_agent_memory

        count = _backup_agent_memory(bridge, agents_dir)
        console.print(f"  [green]✓[/green] {count} agent(s) backed up")
        totals["ok"] += 1
    except Exception as exc:
        _fail("Memory backup failed", exc, totals)

    # 8. Default board
    _header("Default board")
    try:
        bridge.ensure_default_board()
        console.print("  [green]✓[/green] Default board ensured")
        totals["ok"] += 1
    except Exception as exc:
        _fail("Default board failed", exc, totals)

    # 9. Orphaned task cleanup (pre-production: delete tasks without boardId)
    _header("Orphaned task cleanup")
    try:
        from mc.infrastructure.agent_bootstrap import cleanup_orphaned_tasks

        deleted = cleanup_orphaned_tasks(bridge)
        if deleted:
            console.print(f"  [green]✓[/green] Deleted {deleted} orphaned task(s) without boardId")
        else:
            console.print("  [dim]—[/dim] No orphaned tasks found")
        totals["ok"] += 1
    except Exception as exc:
        _fail("Orphaned task cleanup failed", exc, totals)

    # Summary
    console.print()
    parts = [f"[green]{totals['ok']} ok[/green]"]
    if totals["warn"]:
        parts.append(f"[yellow]{totals['warn']} warnings[/yellow]")
    if totals["fail"]:
        parts.append(f"[red]{totals['fail']} failed[/red]")
    console.print(f"Sync complete: {', '.join(parts)}")

    if totals["fail"]:
        raise typer.Exit(1)


def _header(label: str) -> None:
    console.print(f"\n[bold]{label}[/bold]")


def _fail(msg: str, exc: Exception, totals: dict) -> None:
    console.print(f"  [red]✗[/red] {msg}: {exc}")
    totals["fail"] += 1
