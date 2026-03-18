# Story 2.7: Implement CLI Task Commands

Status: done

## Story

As a **user**,
I want to create and list tasks from the terminal,
So that I can manage tasks without opening the dashboard.

## Acceptance Criteria

1. **Given** Mission Control is running, **When** the user runs `nanobot mc tasks create "Research AI trends"`, **Then** a new task is created in Convex with title "Research AI trends", status "inbox", trust level "autonomous"
2. **Given** a task is created via CLI, **Then** a `task_created` activity event is written
3. **Given** a task is created via CLI, **Then** the CLI prints confirmation: task title, status, and created timestamp
4. **Given** a task is created via CLI, **Then** the new task appears on the dashboard Kanban board in real-time (NFR18)
5. **Given** the user runs `nanobot mc tasks create` without a title argument, **Then** the CLI prompts for a task title interactively
6. **Given** tasks exist in Convex, **When** the user runs `nanobot mc tasks list`, **Then** all tasks are displayed in a formatted table: ID, title (truncated), status, assigned agent, created date
7. **Given** tasks are listed, **Then** tasks are grouped or sorted by status
8. **Given** tasks are listed, **Then** results return within 2 seconds (NFR5)
9. **Given** no tasks exist, **When** the user runs `nanobot mc tasks list`, **Then** the CLI prints: "No tasks found."
10. **And** CLI task commands are added to `nanobot/cli/mc.py`
11. **And** task commands call bridge methods — no direct Convex SDK usage in CLI
12. **And** `nanobot mc tasks --help` shows available subcommands with descriptions

## Tasks / Subtasks

- [x] Task 1: Create the `tasks` Typer subgroup in `nanobot/cli/mc.py` (AC: #10, #12)
  - [x] 1.1: Add a `tasks_app = typer.Typer(help="Manage tasks")` subgroup
  - [x] 1.2: Register it with `mc_app.add_typer(tasks_app, name="tasks")`
  - [x] 1.3: Verify `nanobot mc tasks --help` shows the subcommands

- [x] Task 2: Implement `tasks create` command (AC: #1, #2, #3, #4, #5, #11)
  - [x] 2.1: Add `create` command to `tasks_app` accepting optional `title` argument
  - [x] 2.2: If no title argument, use `typer.prompt("Task title")` for interactive input
  - [x] 2.3: Accept optional `--description` / `-d` option
  - [x] 2.4: Accept optional `--tags` / `-t` option (comma-separated string, parsed to list)
  - [x] 2.5: Create a `ConvexBridge` instance using environment variables (`CONVEX_URL`, `CONVEX_ADMIN_KEY`)
  - [x] 2.6: Call `bridge.mutation("tasks:create", {...})` with title, description, tags
  - [x] 2.7: Print confirmation using `rich.console.Console`: task title, status ("inbox"), created timestamp
  - [x] 2.8: Close the bridge connection after the call

- [x] Task 3: Implement `tasks list` command (AC: #6, #7, #8, #9, #11)
  - [x] 3.1: Add `list` command to `tasks_app`
  - [x] 3.2: Create a `ConvexBridge` instance
  - [x] 3.3: Call `bridge.query("tasks:list")` to fetch all tasks
  - [x] 3.4: If no tasks, print "No tasks found." and exit
  - [x] 3.5: Sort tasks by status (using a defined status order: inbox, assigned, in_progress, review, done, retrying, crashed)
  - [x] 3.6: Display tasks in a `rich.table.Table` with columns: Status, Title (truncated to 50 chars), Agent, Created
  - [x] 3.7: Apply status-based color to the status column (violet=inbox, blue=assigned/in_progress, amber=review, green=done, red=crashed)
  - [x] 3.8: Close the bridge connection after the call

- [x] Task 4: Create bridge connection helper (AC: #11)
  - [x] 4.1: Create a helper function `_get_bridge()` in `nanobot/cli/mc.py` that reads `CONVEX_URL` and optional `CONVEX_ADMIN_KEY` from environment variables
  - [x] 4.2: Raise a clear error if `CONVEX_URL` is not set: "CONVEX_URL environment variable is required. Set it to your Convex deployment URL."
  - [x] 4.3: Return a configured `ConvexBridge` instance

- [x] Task 5: Add Convex tasks:create mutation support for bridge calls (AC: #11)
  - [x] 5.1: Verify the Convex `tasks:create` mutation (from Story 2.2) works when called from the Python bridge
  - [x] 5.2: Verify the bridge's snake_case to camelCase conversion works for task creation args
  - [x] 5.3: Verify the bridge's camelCase to snake_case conversion works for query results

- [x] Task 6: Write integration notes (AC: #4)
  - [x] 6.1: Document in the story that CLI-created tasks appear on the dashboard in real-time because both CLI and dashboard read/write to the same Convex state (NFR18)
  - [x] 6.2: No additional code is needed for this — Convex's reactive queries handle it automatically

- [x] Task 7: Write tests
  - [x] 7.1: Create `nanobot/mc/test_cli_tasks.py` or add to `nanobot/cli/test_mc.py`
  - [x] 7.2: Test `tasks create` with title argument creates a task via bridge
  - [x] 7.3: Test `tasks list` formats output correctly
  - [x] 7.4: Test `tasks list` with no tasks shows "No tasks found."
  - [x] 7.5: Test bridge connection helper raises error when CONVEX_URL is not set

## Dev Notes

### Critical Architecture Requirements

- **CLI calls bridge, bridge calls Convex**: The CLI MUST NOT import the `convex` Python SDK directly. It creates a `ConvexBridge` instance and calls bridge methods. The bridge handles connection, retry, and case conversion. This is Boundary 4 from the architecture.
- **Same Convex state**: CLI and dashboard operate on the same Convex database. A task created via CLI appears on the dashboard immediately (NFR18). No synchronization code is needed — Convex's reactive queries handle this automatically.
- **Bridge is synchronous**: The `ConvexBridge` class uses the synchronous `ConvexClient` from the Python SDK. CLI commands can call `bridge.query()` and `bridge.mutation()` directly without asyncio.
- **Environment variables**: The bridge needs `CONVEX_URL` (the Convex deployment URL) to connect. Optionally, `CONVEX_ADMIN_KEY` for admin-level access. These should be read from environment variables, or from `.env.local` in the dashboard directory.

### CLI Command Structure

```
nanobot mc tasks --help          # Shows: create, list
nanobot mc tasks create          # Interactive prompt for title
nanobot mc tasks create "title"  # Creates task with given title
nanobot mc tasks create "title" -d "description" -t "tag1,tag2"
nanobot mc tasks list            # Shows all tasks in a table
```

### Typer Subgroup Pattern

```python
# In nanobot/cli/mc.py

tasks_app = typer.Typer(
    help="Manage Mission Control tasks",
    no_args_is_help=True,
)
mc_app.add_typer(tasks_app, name="tasks")


@tasks_app.command("create")
def tasks_create(
    title: str = typer.Argument(None, help="Task title"),
    description: str = typer.Option(None, "--description", "-d", help="Task description"),
    tags: str = typer.Option(None, "--tags", "-t", help="Comma-separated tags"),
):
    """Create a new task."""
    if title is None:
        title = typer.prompt("Task title")

    bridge = _get_bridge()
    try:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
        result = bridge.mutation("tasks:create", {
            "title": title,
            "description": description,
            "tags": tag_list,
        })
        console.print(f"[green]Task created:[/green] {title}")
        console.print(f"  Status: inbox")
        console.print(f"  Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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

        # Sort by status order
        status_order = ["inbox", "assigned", "in_progress", "review", "done", "retrying", "crashed"]
        tasks.sort(key=lambda t: status_order.index(t.get("status", "inbox")))

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
            agent = task.get("assigned_agent", "-")
            created = task.get("created_at", "")[:10]  # Date only

            table.add_row(
                f"[{color}]{status}[/{color}]",
                title_text,
                agent,
                created,
            )

        console.print(table)
    finally:
        bridge.close()
```

### Bridge Connection Helper

```python
def _get_bridge():
    """Create a ConvexBridge from environment variables."""
    from nanobot.mc.bridge import ConvexBridge

    convex_url = os.environ.get("CONVEX_URL")
    if not convex_url:
        # Try to read from dashboard/.env.local
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
    return ConvexBridge(convex_url, admin_key)
```

### Status Color Mapping for Rich Output

```python
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
```

### Existing CLI Patterns (from `nanobot/cli/mc.py`)

The existing `mc.py` file already:
- Imports `typer` and `rich.console.Console`
- Has `mc_app = typer.Typer(...)`
- Has `start` and `stop` commands
- Uses `PID_FILE` for process management
- Uses `_find_dashboard_dir()` to locate the dashboard directory

New task commands are added to the same file as a Typer subgroup.

### Bridge snake_case Conversion Notes

The bridge automatically converts keys:
- **Outgoing (Python -> Convex)**: `snake_case` keys become `camelCase`
  - `{"title": "foo", "trust_level": "autonomous"}` -> `{"title": "foo", "trustLevel": "autonomous"}`
- **Incoming (Convex -> Python)**: `camelCase` keys become `snake_case`
  - `{"assignedAgent": "bot", "createdAt": "..."}` -> `{"assigned_agent": "bot", "created_at": "..."}`

This means CLI code works with `snake_case` keys, and the bridge handles the conversion at the boundary.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT import `convex` in the CLI module** — The CLI must use `ConvexBridge` exclusively. The bridge is the ONLY module that imports the `convex` Python SDK (Boundary 1).

2. **DO NOT use asyncio for CLI commands** — The `ConvexBridge` uses the synchronous `ConvexClient`. CLI commands call `bridge.query()` and `bridge.mutation()` directly. No `async def`, no `asyncio.run()`.

3. **DO NOT forget to close the bridge** — Use `try/finally` to ensure `bridge.close()` is called after each command. An unclosed bridge keeps a connection open.

4. **DO NOT hardcode the Convex URL** — Read from `CONVEX_URL` environment variable or from `dashboard/.env.local`. Never hardcode deployment URLs.

5. **DO NOT pass camelCase keys to the bridge** — The bridge expects snake_case keys from the Python side and converts them to camelCase for Convex. Pass `"trust_level"`, not `"trustLevel"`. BUT: simple field names that are the same in both cases (like `"title"`, `"description"`, `"tags"`) don't need conversion.

6. **DO NOT truncate task IDs in the list output** — Convex `_id` values are long strings. For the table display, either omit the ID column entirely or truncate it. The status + title is usually sufficient to identify tasks.

7. **DO NOT create a separate `tasks.py` CLI module** — All task commands live in `nanobot/cli/mc.py` as a Typer subgroup. The 500-line limit (NFR21) applies, but the CLI module should be well under that.

8. **DO NOT add task editing or deletion commands** — This story covers `create` and `list` only. Status updates are done via the state machine (Story 2.4), not direct CLI commands.

9. **DO NOT use `print()` for output** — Use `rich.console.Console` and `rich.table.Table` for formatted, colorized output. This matches the existing nanobot CLI patterns.

10. **DO NOT forget the `no_args_is_help=True` on the tasks Typer** — Without this, running `nanobot mc tasks` with no subcommand would do nothing instead of showing help.

### What This Story Does NOT Include

- **No task status update from CLI** — Tasks are created and listed. Status changes happen via agents (bridge) or dashboard (mutations). A `tasks update` command could be added later.
- **No task deletion** — Tasks are never deleted in the MVP. They move through the state machine to "done" or "crashed".
- **No task filtering** — `tasks list` shows ALL tasks. Filtering by status, agent, or date could be added later.
- **No agent assignment from CLI** — Tasks created via CLI default to unassigned (Lead Agent routing). Agent assignment from CLI is a future enhancement.
- **No interactive task creation wizard** — The CLI uses simple argument + options. The progressive disclosure wizard (trust level, reviewers) is dashboard-only.

### Files Created in This Story

*No new files — commands are added to existing files.*

### Files Modified in This Story

| File | Changes |
|------|---------|
| `nanobot/cli/mc.py` | Add `tasks_app` Typer subgroup with `create` and `list` commands, `_get_bridge()` helper, `_get_status_color()` helper |

### Verification Steps

1. Set `CONVEX_URL` environment variable to the Convex deployment URL
2. `nanobot mc tasks --help` — Shows "create" and "list" subcommands
3. `nanobot mc tasks create "Research AI trends"` — Prints confirmation with title, status, timestamp
4. Verify task appears in Convex dashboard `tasks` table
5. Verify task appears on the dashboard Kanban board in the Inbox column (NFR18)
6. Verify `activities` table has a `task_created` event
7. `nanobot mc tasks create` (no argument) — Prompts for task title interactively
8. `nanobot mc tasks create "Test" -d "A test task" -t "tag1,tag2"` — Creates task with description and tags
9. `nanobot mc tasks list` — Displays formatted table with tasks sorted by status
10. Delete all tasks from Convex dashboard, then `nanobot mc tasks list` — Shows "No tasks found."
11. `wc -l nanobot/cli/mc.py` — Under 500 lines

### References

- [Source: `_bmad-output/planning-artifacts/architecture.md#Project Structure & Boundaries`] — Boundary 4: CLI calls mc/ package functions, no business logic in CLI
- [Source: `_bmad-output/planning-artifacts/architecture.md#API & Communication Patterns`] — CLI -> Convex via Python SDK queries
- [Source: `_bmad-output/planning-artifacts/epics.md#Story 2.7`] — Original story definition with acceptance criteria
- [Source: `_bmad-output/planning-artifacts/prd.md#FR8`] — Create task from CLI
- [Source: `_bmad-output/planning-artifacts/prd.md#FR9`] — List tasks from CLI
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR5`] — CLI commands return within 2 seconds
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR18`] — CLI and dashboard operate on same Convex state
- [Source: `nanobot/cli/mc.py`] — Existing CLI module with start/stop commands, typer/rich patterns
- [Source: `nanobot/mc/bridge.py`] — ConvexBridge class with query/mutation methods and case conversion

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References
- All 28 tests in `nanobot/mc/test_cli_tasks.py` pass
- No regressions in existing bridge tests (67 pass) or state machine tests (52 pass)
- 11 pre-existing failures in `test_process_manager.py` (async mark issues, unrelated)

### Completion Notes List
- Added `tasks_app` Typer subgroup with `no_args_is_help=True` to `mc_app`
- `tasks create` accepts optional title argument, prompts if missing, supports `-d` and `-t` options
- `tasks list` fetches via `bridge.query("tasks:list")`, sorts by status order, displays Rich table with colored status
- `_get_bridge()` reads `CONVEX_URL` from env or `dashboard/.env.local`, raises clear error if not found
- `_get_status_color()` maps task statuses to Rich colors
- Bridge is always closed in `finally` blocks
- CLI never imports `convex` SDK directly (Boundary 4)
- Real-time dashboard sync is automatic via shared Convex state (NFR18)
- Integration note: CLI-created tasks appear on dashboard Kanban in real-time with zero additional code

### File List
| File | Action |
|------|--------|
| `nanobot/cli/mc.py` | Modified: added `_get_bridge()`, `_get_status_color()`, `tasks_app` with `create` and `list` commands |
| `nanobot/mc/test_cli_tasks.py` | Created: 28 unit tests covering status colors, bridge helper, create, list, and help |
