"""CLI commands for task management and configuration (docs, tasks CRUD)."""

from __future__ import annotations

import re

import typer
from rich.console import Console
from rich.table import Table

console = Console()

tasks_app = typer.Typer(
    help="Manage Mission Control tasks",
    no_args_is_help=True,
)


def register_docs_command(mc_app: typer.Typer) -> None:
    """Register the docs command on the main mc_app."""
    @mc_app.command()
    def docs():
        """Show auto-generated API documentation from Convex schema."""
        from rich.markdown import Markdown
        from mc.cli import _find_dashboard_dir

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
    table_matches = re.findall(
        r"(\w+):\s*defineTable\(\{(.*?)\}\)", schema_text, re.DOTALL
    )
    for table_name, body in table_matches:
        lines.append(f"### {table_name}\n")
        fields = re.findall(r"(\w+):\s*v\.(\w+)\(([^)]*)\)", body)
        if fields:
            lines.append("| Field | Type | Detail |")
            lines.append("|-------|------|--------|")
            for field_name, vtype, detail in fields:
                detail_clean = detail.strip().strip('"').strip("'")
                lines.append(f"| {field_name} | {vtype} | {detail_clean} |")
        lines.append("")

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


# ============================================================================
# Task Commands
# ============================================================================


@tasks_app.command("create")
def tasks_create(
    title: str = typer.Argument(None, help="Task title"),
    description: str = typer.Option(
        None, "--description", "-d", help="Task description"
    ),
    tags: str = typer.Option(None, "--tags", "-t", help="Comma-separated tags"),
    trust_level: str = typer.Option(
        None,
        "--trust-level",
        help="Trust level: autonomous|human_approved",
    ),
    supervision_mode: str = typer.Option(
        None,
        "--supervision-mode",
        help="Supervision mode: autonomous|supervised",
    ),
    manual: bool = typer.Option(
        False,
        "--manual",
        help="Mark task as manually managed",
    ),
    agent: str = typer.Option(None, "--agent", help="Agent name to assign"),
    source: str = typer.Option(None, "--source", help="Source agent name"),
):
    """Create a new task."""
    import mc.cli as _cli

    if title is None:
        title = typer.prompt("Task title")
    if not title or not title.strip():
        console.print("[red]Task title cannot be empty[/red]")
        raise typer.Exit(1)

    bridge = _cli._get_bridge()
    try:
        tag_list = (
            [t.strip() for t in tags.split(",") if t.strip()] if tags else None
        )
        args: dict = {"title": title}
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
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
        task_id = result if isinstance(result, str) else (result or {}).get("id", "")
        console.print(f"[green]Task created:[/green] {title}")
        if task_id:
            console.print(f"  ID: {task_id}")
        if manual:
            console.print("  Type: manual (human task)")
        if trust_level:
            console.print(f"  Trust: {trust_level}")
        if agent:
            console.print(f"  Agent: {agent}")
    finally:
        bridge.close()


@tasks_app.command("list")
def tasks_list(
    status: str = typer.Option(None, "--status", "-s", help="Filter by status"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all tasks."""
    import json as _json
    import mc.cli as _cli

    bridge = _cli._get_bridge()
    try:
        if status:
            tasks = bridge.query("tasks:listByStatus", {"status": status})
        else:
            tasks = bridge.query("tasks:list")
        if not tasks:
            console.print("No tasks found.")
            return

        if output_json:
            console.print(_json.dumps(tasks, indent=2, default=str))
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

        console.print(table)
    finally:
        bridge.close()


@tasks_app.command("get")
def tasks_get(
    task_id: str = typer.Argument(..., help="Task ID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show details of a task plus last 10 thread messages."""
    import json as _json
    import mc.cli as _cli

    bridge = _cli._get_bridge()
    try:
        task = bridge.query("tasks:getById", {"task_id": task_id})
        if not task:
            console.print(f"[red]Task not found:[/red] {task_id}")
            raise typer.Exit(1)

        messages = bridge.query("messages:listByTask", {"task_id": task_id}) or []
        messages = messages[-10:]

        if output_json:
            console.print(_json.dumps({"task": task, "messages": messages}, indent=2, default=str))
            return

        console.print(f"\n[bold]Task:[/bold] {task.get('title', 'Untitled')}")
        console.print(f"  [dim]ID:[/dim]           {task_id}")
        console.print(f"  [dim]Status:[/dim]        {task.get('status', '-')}")
        console.print(f"  [dim]Agent:[/dim]         {task.get('assigned_agent') or '-'}")
        console.print(f"  [dim]Trust Level:[/dim]   {task.get('trust_level') or '-'}")
        console.print(f"  [dim]Supervision:[/dim]   {task.get('supervision_mode') or '-'}")
        console.print(f"  [dim]Manual:[/dim]        {task.get('is_manual', False)}")
        console.print(f"  [dim]Created:[/dim]       {(task.get('created_at') or '')[:19]}")
        console.print(f"  [dim]Updated:[/dim]       {(task.get('updated_at') or '')[:19]}")
        tags = task.get("tags") or []
        console.print(f"  [dim]Tags:[/dim]          {', '.join(tags) if tags else '-'}")
        description = task.get("description") or ""
        if description:
            console.print(f"\n[bold]Description:[/bold]")
            console.print(f"  {description}")

        if messages:
            console.print(f"\n[bold]Last {len(messages)} messages:[/bold]")
            for msg in messages:
                author = msg.get("author_name") or msg.get("author_type") or "?"
                content = msg.get("content") or ""
                ts = (msg.get("timestamp") or msg.get("created_at") or "")[:19]
                console.print(f"  [{ts}] [cyan]{author}[/cyan]: {content[:120]}")
    finally:
        bridge.close()


@tasks_app.command("update-status")
def tasks_update_status(
    task_id: str = typer.Argument(..., help="Task ID"),
    status: str = typer.Argument(..., help="New status"),
    agent: str = typer.Option(None, "--agent", help="Agent name"),
):
    """Update the status of a task."""
    import mc.cli as _cli

    bridge = _cli._get_bridge()
    try:
        args: dict = {"task_id": task_id, "status": status}
        if agent:
            args["agent_name"] = agent
        try:
            bridge.mutation("tasks:updateStatus", args)
            console.print(f"[green]Status updated:[/green] {task_id} \u2192 {status}")
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
    finally:
        bridge.close()


@tasks_app.command("send-message")
def tasks_send_message(
    task_id: str = typer.Argument(..., help="Task ID"),
    content: str = typer.Argument(..., help="Message content"),
    author: str = typer.Option("User", "--author", help="Author name"),
):
    """Post a comment message to a task thread."""
    import mc.cli as _cli

    bridge = _cli._get_bridge()
    try:
        args: dict = {
            "task_id": task_id,
            "content": content,
            "author_name": author,
        }
        try:
            bridge.mutation("messages:postComment", args)
            console.print(f"[green]Message sent to task:[/green] {task_id}")
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
    finally:
        bridge.close()


@tasks_app.command("delete")
def tasks_delete(
    task_id: str = typer.Argument(..., help="Task ID"),
):
    """Soft-delete a task."""
    import mc.cli as _cli

    bridge = _cli._get_bridge()
    try:
        try:
            bridge.mutation("tasks:softDelete", {"task_id": task_id})
            console.print(f"[green]Task deleted:[/green] {task_id}")
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
    finally:
        bridge.close()


@tasks_app.command("restore")
def tasks_restore(
    task_id: str = typer.Argument(..., help="Task ID"),
    mode: str = typer.Option("previous", "--mode", help="Restore mode: previous|beginning"),
):
    """Restore a soft-deleted task."""
    import mc.cli as _cli

    bridge = _cli._get_bridge()
    try:
        args: dict = {"task_id": task_id, "mode": mode}
        try:
            bridge.mutation("tasks:restore", args)
            console.print(f"[green]Task restored:[/green] {task_id} (mode: {mode})")
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
    finally:
        bridge.close()


@tasks_app.command("approve")
def tasks_approve(
    task_id: str = typer.Argument(..., help="Task ID"),
    user: str = typer.Option("User", "--user", help="Approving user name"),
):
    """Approve a task that is awaiting human approval."""
    import mc.cli as _cli

    bridge = _cli._get_bridge()
    try:
        args: dict = {"task_id": task_id, "user_name": user}
        try:
            bridge.mutation("tasks:approve", args)
            console.print(f"[green]Task approved:[/green] {task_id}")
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
    finally:
        bridge.close()


@tasks_app.command("deny")
def tasks_deny(
    task_id: str = typer.Argument(..., help="Task ID"),
    feedback: str = typer.Argument(..., help="Denial feedback"),
    user: str = typer.Option("User", "--user", help="Denying user name"),
):
    """Deny a task that is awaiting human approval."""
    import mc.cli as _cli

    bridge = _cli._get_bridge()
    try:
        args: dict = {"task_id": task_id, "feedback": feedback, "user_name": user}
        try:
            bridge.mutation("tasks:deny", args)
            console.print(f"[yellow]Task denied:[/yellow] {task_id}")
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
    finally:
        bridge.close()


@tasks_app.command("pause")
def tasks_pause(
    task_id: str = typer.Argument(..., help="Task ID"),
):
    """Pause a running task."""
    import mc.cli as _cli

    bridge = _cli._get_bridge()
    try:
        try:
            bridge.mutation("tasks:pauseTask", {"task_id": task_id})
            console.print(f"[green]Task paused:[/green] {task_id}")
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
    finally:
        bridge.close()


@tasks_app.command("resume")
def tasks_resume(
    task_id: str = typer.Argument(..., help="Task ID"),
):
    """Resume a paused task."""
    import mc.cli as _cli

    bridge = _cli._get_bridge()
    try:
        try:
            bridge.mutation("tasks:resumeTask", {"task_id": task_id})
            console.print(f"[green]Task resumed:[/green] {task_id}")
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
    finally:
        bridge.close()


@tasks_app.command("update-title")
def tasks_update_title(
    task_id: str = typer.Argument(..., help="Task ID"),
    title: str = typer.Argument(..., help="New title"),
):
    """Update the title of a task."""
    import mc.cli as _cli

    bridge = _cli._get_bridge()
    try:
        args: dict = {"task_id": task_id, "title": title}
        try:
            bridge.mutation("tasks:updateTitle", args)
            console.print(f"[green]Title updated:[/green] {task_id} \u2192 {title}")
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
    finally:
        bridge.close()


@tasks_app.command("update-description")
def tasks_update_description(
    task_id: str = typer.Argument(..., help="Task ID"),
    description: str = typer.Argument(..., help="New description"),
):
    """Update the description of a task."""
    import mc.cli as _cli

    bridge = _cli._get_bridge()
    try:
        args: dict = {"task_id": task_id, "description": description}
        try:
            bridge.mutation("tasks:updateDescription", args)
            console.print(f"[green]Description updated:[/green] {task_id}")
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
    finally:
        bridge.close()


@tasks_app.command("update-tags")
def tasks_update_tags(
    task_id: str = typer.Argument(..., help="Task ID"),
    tags: str = typer.Argument(..., help="Comma-separated tags"),
):
    """Update the tags of a task (comma-separated)."""
    import mc.cli as _cli

    bridge = _cli._get_bridge()
    try:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        args: dict = {"task_id": task_id, "tags": tag_list}
        try:
            bridge.mutation("tasks:updateTags", args)
            console.print(f"[green]Tags updated:[/green] {task_id} \u2192 {tag_list}")
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
    finally:
        bridge.close()


@tasks_app.command("manual-move")
def tasks_manual_move(
    task_id: str = typer.Argument(..., help="Task ID"),
    status: str = typer.Argument(..., help="Target status"),
):
    """Manually move a task to a specific status."""
    import mc.cli as _cli

    bridge = _cli._get_bridge()
    try:
        args: dict = {"task_id": task_id, "new_status": status}
        try:
            bridge.mutation("tasks:manualMove", args)
            console.print(f"[green]Task moved:[/green] {task_id} \u2192 {status}")
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
    finally:
        bridge.close()
