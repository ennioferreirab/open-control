"""Task commands for Mission Control CLI."""

from __future__ import annotations

import json as _json

import typer
from rich.table import Table

tasks_app = typer.Typer(
    help="Manage Mission Control tasks",
    no_args_is_help=True,
)


@tasks_app.command("create")
def tasks_create(
    title: str = typer.Argument(None, help="Task title"),
    description: str = typer.Option(None, "--description", "-d", help="Task description"),
    tags: str = typer.Option(None, "--tags", "-t", help="Comma-separated tags"),
    trust_level: str = typer.Option(
        None,
        "--trust-level",
        help="Trust level: autonomous|agent_reviewed|human_approved",
    ),
    supervision_mode: str = typer.Option(
        None,
        "--supervision-mode",
        help="Supervision mode: autonomous|supervised",
    ),
    manual: bool = typer.Option(False, "--manual", help="Mark task as manually managed"),
    agent: str = typer.Option(None, "--agent", help="Agent name to assign"),
    source: str = typer.Option(None, "--source", help="Source agent name"),
):
    """Create a new task."""
    import mc.cli as _cli

    if title is None:
        title = typer.prompt("Task title")
    if not title or not title.strip():
        _cli.console.print("[red]Task title cannot be empty[/red]")
        raise typer.Exit(1)

    bridge = _cli._get_bridge()
    try:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
        args: dict[str, object] = {"title": title}
        if description:
            args["description"] = description
        if tag_list:
            args["tags"] = tag_list
        if trust_level:
            args["trust_level"] = trust_level
        if supervision_mode:
            args["supervision_mode"] = supervision_mode
        if manual:
            args["is_manual"] = True
        if agent:
            args["assigned_agent"] = agent
        if source:
            args["source_agent"] = source
        try:
            result = bridge.mutation("tasks:create", args)
        except Exception as exc:
            _cli.console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1) from None
        task_id = result if isinstance(result, str) else (result or {}).get("id", "")
        _cli.console.print(f"[green]Task created:[/green] {title}")
        if task_id:
            _cli.console.print(f"  ID: {task_id}")
        if manual:
            _cli.console.print("  Type: manual (human task)")
        if trust_level:
            _cli.console.print(f"  Trust: {trust_level}")
        if agent:
            _cli.console.print(f"  Agent: {agent}")
    finally:
        bridge.close()


@tasks_app.command("list")
def tasks_list(
    status: str = typer.Option(None, "--status", "-s", help="Filter by status"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all tasks."""
    import mc.cli as _cli

    bridge = _cli._get_bridge()
    try:
        tasks = (
            bridge.query("tasks:listByStatus", {"status": status})
            if status
            else bridge.query("tasks:list")
        )
        if not tasks:
            _cli.console.print("No tasks found.")
            return

        if output_json:
            _cli.console.print(_json.dumps(tasks, indent=2, default=str))
            return

        status_order = ["inbox", "assigned", "in_progress", "review", "done", "retrying", "crashed"]
        tasks.sort(
            key=lambda task: (
                status_order.index(task.get("status", "inbox"))
                if task.get("status", "inbox") in status_order
                else len(status_order)
            )
        )

        table = Table(title="Tasks")
        table.add_column("ID", style="dim")
        table.add_column("Status", style="bold")
        table.add_column("Title", max_width=50)
        table.add_column("Agent")
        table.add_column("Created")

        for task in tasks:
            task_id = task.get("id", "")
            status_val = task.get("status", "unknown")
            color = _cli._get_status_color(status_val)
            title_text = task.get("title", "Untitled")
            if len(title_text) > 50:
                title_text = title_text[:47] + "..."
            agent = task.get("assigned_agent") or "-"
            created = (task.get("created_at") or "")[:10]
            table.add_row(
                task_id,
                f"[{color}]{status_val}[/{color}]",
                title_text,
                agent,
                created,
            )

        _cli.console.print(table)
    finally:
        bridge.close()


@tasks_app.command("get")
def tasks_get(
    task_id: str = typer.Argument(..., help="Task ID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show details of a task plus last 10 thread messages."""
    import mc.cli as _cli

    bridge = _cli._get_bridge()
    try:
        task = bridge.query("tasks:getById", {"task_id": task_id})
        if not task:
            _cli.console.print(f"[red]Task not found:[/red] {task_id}")
            raise typer.Exit(1)
        messages = bridge.query("messages:listByTask", {"task_id": task_id}) or []
        messages = messages[-10:]

        if output_json:
            _cli.console.print(
                _json.dumps({"task": task, "messages": messages}, indent=2, default=str)
            )
            return

        _cli.console.print(f"\n[bold]Task:[/bold] {task.get('title', 'Untitled')}")
        _cli.console.print(f"  [dim]ID:[/dim]           {task_id}")
        _cli.console.print(f"  [dim]Status:[/dim]        {task.get('status', '-')}")
        _cli.console.print(f"  [dim]Agent:[/dim]         {task.get('assigned_agent') or '-'}")
        _cli.console.print(f"  [dim]Trust Level:[/dim]   {task.get('trust_level') or '-'}")
        _cli.console.print(f"  [dim]Supervision:[/dim]   {task.get('supervision_mode') or '-'}")
        _cli.console.print(f"  [dim]Manual:[/dim]        {task.get('is_manual', False)}")
        _cli.console.print(f"  [dim]Created:[/dim]       {(task.get('created_at') or '')[:19]}")
        _cli.console.print(f"  [dim]Updated:[/dim]       {(task.get('updated_at') or '')[:19]}")
        tags = task.get("tags") or []
        _cli.console.print(f"  [dim]Tags:[/dim]          {', '.join(tags) if tags else '-'}")
        description_text = task.get("description") or ""
        if description_text:
            _cli.console.print("\n[bold]Description:[/bold]")
            _cli.console.print(f"  {description_text}")

        if messages:
            _cli.console.print(f"\n[bold]Last {len(messages)} messages:[/bold]")
            for message in messages:
                author = message.get("author_name") or message.get("author_type") or "?"
                content = message.get("content") or ""
                timestamp = (message.get("timestamp") or message.get("created_at") or "")[:19]
                _cli.console.print(f"  [{timestamp}] [cyan]{author}[/cyan]: {content[:120]}")
    finally:
        bridge.close()


def _task_mutation_command(
    mutation_name: str,
    success_message: str,
    args: dict[str, object],
) -> None:
    import mc.cli as _cli

    bridge = _cli._get_bridge()
    try:
        try:
            bridge.mutation(mutation_name, args)
            _cli.console.print(success_message)
        except Exception as exc:
            _cli.console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1) from None
    finally:
        bridge.close()


@tasks_app.command("update-status")
def tasks_update_status(
    task_id: str = typer.Argument(..., help="Task ID"),
    status: str = typer.Argument(..., help="New status"),
    agent: str = typer.Option(None, "--agent", help="Agent name"),
):
    """Update the status of a task."""
    args: dict[str, object] = {"task_id": task_id, "status": status}
    if agent:
        args["agent_name"] = agent
    _task_mutation_command(
        "tasks:updateStatus", f"[green]Status updated:[/green] {task_id} → {status}", args
    )


@tasks_app.command("send-message")
def tasks_send_message(
    task_id: str = typer.Argument(..., help="Task ID"),
    content: str = typer.Argument(..., help="Message content"),
    author: str = typer.Option("User", "--author", help="Author name"),
):
    """Post a comment message to a task thread."""
    _task_mutation_command(
        "messages:postComment",
        f"[green]Message sent to task:[/green] {task_id}",
        {"task_id": task_id, "content": content, "author_name": author},
    )


@tasks_app.command("delete")
def tasks_delete(task_id: str = typer.Argument(..., help="Task ID")):
    """Soft-delete a task."""
    _task_mutation_command(
        "tasks:softDelete", f"[green]Task deleted:[/green] {task_id}", {"task_id": task_id}
    )


@tasks_app.command("restore")
def tasks_restore(
    task_id: str = typer.Argument(..., help="Task ID"),
    mode: str = typer.Option("previous", "--mode", help="Restore mode: previous|beginning"),
):
    """Restore a soft-deleted task."""
    _task_mutation_command(
        "tasks:restore",
        f"[green]Task restored:[/green] {task_id} (mode: {mode})",
        {"task_id": task_id, "mode": mode},
    )


@tasks_app.command("approve")
def tasks_approve(
    task_id: str = typer.Argument(..., help="Task ID"),
    user: str = typer.Option("User", "--user", help="Approving user name"),
):
    """Approve a task that is awaiting human approval."""
    _task_mutation_command(
        "tasks:approve",
        f"[green]Task approved:[/green] {task_id}",
        {"task_id": task_id, "user_name": user},
    )


@tasks_app.command("deny")
def tasks_deny(
    task_id: str = typer.Argument(..., help="Task ID"),
    feedback: str = typer.Argument(..., help="Denial feedback"),
    user: str = typer.Option("User", "--user", help="Denying user name"),
):
    """Deny a task that is awaiting human approval."""
    _task_mutation_command(
        "tasks:deny",
        f"[yellow]Task denied:[/yellow] {task_id}",
        {"task_id": task_id, "feedback": feedback, "user_name": user},
    )


@tasks_app.command("pause")
def tasks_pause(task_id: str = typer.Argument(..., help="Task ID")):
    """Pause a running task."""
    _task_mutation_command(
        "tasks:pauseTask", f"[green]Task paused:[/green] {task_id}", {"task_id": task_id}
    )


@tasks_app.command("resume")
def tasks_resume(task_id: str = typer.Argument(..., help="Task ID")):
    """Resume a paused task."""
    _task_mutation_command(
        "tasks:resumeTask", f"[green]Task resumed:[/green] {task_id}", {"task_id": task_id}
    )


@tasks_app.command("update-title")
def tasks_update_title(
    task_id: str = typer.Argument(..., help="Task ID"),
    title: str = typer.Argument(..., help="New title"),
):
    """Update the title of a task."""
    _task_mutation_command(
        "tasks:updateTitle",
        f"[green]Title updated:[/green] {task_id} → {title}",
        {"task_id": task_id, "title": title},
    )


@tasks_app.command("update-description")
def tasks_update_description(
    task_id: str = typer.Argument(..., help="Task ID"),
    description: str = typer.Argument(..., help="New description"),
):
    """Update the description of a task."""
    _task_mutation_command(
        "tasks:updateDescription",
        f"[green]Description updated:[/green] {task_id}",
        {"task_id": task_id, "description": description},
    )


@tasks_app.command("update-tags")
def tasks_update_tags(
    task_id: str = typer.Argument(..., help="Task ID"),
    tags: str = typer.Argument(..., help="Comma-separated tags"),
):
    """Update the tags of a task (comma-separated)."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    _task_mutation_command(
        "tasks:updateTags",
        f"[green]Tags updated:[/green] {task_id} → {tag_list}",
        {"task_id": task_id, "tags": tag_list},
    )


@tasks_app.command("manual-move")
def tasks_manual_move(
    task_id: str = typer.Argument(..., help="Task ID"),
    status: str = typer.Argument(..., help="Target status"),
):
    """Manually move a task to a specific status."""
    _task_mutation_command(
        "tasks:manualMove",
        f"[green]Task moved:[/green] {task_id} → {status}",
        {"task_id": task_id, "new_status": status},
    )
