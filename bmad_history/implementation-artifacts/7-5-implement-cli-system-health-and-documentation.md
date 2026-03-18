# Story 7.5: Implement CLI System Health & Documentation

Status: done

## Story

As a **user**,
I want to check system health from the terminal and access auto-generated API documentation,
So that I can monitor Mission Control and reference the API without opening the dashboard.

## Acceptance Criteria

1. **Given** Mission Control is running, **When** the user runs `nanobot mc status` (FR44), **Then** the CLI displays: number of running agents and their statuses, number of tasks by state, system uptime, Convex connection status, dashboard URL
2. **Given** Mission Control is running, **Then** the status results return within 2 seconds (NFR5)
3. **Given** Mission Control is not running, **When** the user runs `nanobot mc status`, **Then** the CLI prints: "Mission Control is not running. Start with `nanobot mc start`"
4. **Given** the Convex schema is defined, **When** API documentation is generated (FR47), **Then** documentation is auto-generated from Convex schema and function definitions
5. **Given** the user runs `nanobot mc docs`, **Then** the auto-generated documentation is displayed or a reference to the docs file is shown
6. **And** the data privacy notice is documented in README regarding sensitive data transiting through Convex cloud (NFR20)
7. **And** CLI status command is added to `nanobot/cli/mc.py`
8. **And** unit tests exist for the status command logic

## Tasks / Subtasks

- [ ] Task 1: Implement `nanobot mc status` command (AC: #1, #2, #3, #7)
  - [ ] 1.1: Add a `status` command to `mc_app` in `nanobot/cli/mc.py`
  - [ ] 1.2: Check if Mission Control is running by verifying the PID file (`~/.nanobot/mc.pid`) and process existence
  - [ ] 1.3: If not running, print: "Mission Control is not running. Start with `nanobot mc start`" and exit
  - [ ] 1.4: If running, connect to Convex via `_get_bridge()` and query system state
  - [ ] 1.5: Query `agents:list` to get agent count and statuses
  - [ ] 1.6: Query `tasks:list` to get task count by status
  - [ ] 1.7: Read PID file creation time for approximate uptime
  - [ ] 1.8: Display results using Rich formatting (panels, tables)
  - [ ] 1.9: Handle connection failures gracefully (Convex unreachable)

- [ ] Task 2: Implement status display formatting (AC: #1)
  - [ ] 2.1: Use Rich `Panel` for the status overview header
  - [ ] 2.2: Display system status: "Running" (green) or "Degraded" (yellow) based on Convex connectivity
  - [ ] 2.3: Display dashboard URL: `http://localhost:3000`
  - [ ] 2.4: Display uptime from PID file creation time
  - [ ] 2.5: Use Rich `Table` for agent status breakdown (name, status, last active)
  - [ ] 2.6: Use Rich `Table` for task counts by status (inbox: N, assigned: N, in_progress: N, review: N, done: N, crashed: N)
  - [ ] 2.7: Show total task count as a summary line

- [ ] Task 3: Implement `nanobot mc docs` command (AC: #4, #5)
  - [ ] 3.1: Add a `docs` command to `mc_app` in `nanobot/cli/mc.py`
  - [ ] 3.2: Generate API documentation from the Convex schema and function definitions
  - [ ] 3.3: Option A: Read `dashboard/convex/schema.ts` and all function files, parse exports, and display a formatted summary
  - [ ] 3.4: Option B: Generate a static markdown file (`docs/api-reference.md`) during build and display its path
  - [ ] 3.5: Display the docs in the terminal using Rich Markdown or provide a file path
  - [ ] 3.6: Include table names, fields, types, indexes, and available queries/mutations

- [ ] Task 4: Add data privacy notice to README (AC: #6)
  - [ ] 4.1: Add a "Data Privacy" section to the project README (or `docs/DATA-PRIVACY.md`)
  - [ ] 4.2: Document that task data, agent messages, and activity logs transit through Convex cloud servers
  - [ ] 4.3: Advise users handling sensitive data (financial, email, calendar) to review Convex's privacy policy
  - [ ] 4.4: Note that `MC_ACCESS_TOKEN` protects dashboard access but does not encrypt data in transit to Convex
  - [ ] 4.5: Suggest self-hosted alternatives for highly sensitive deployments (post-MVP)

- [ ] Task 5: Write unit tests (AC: #8)
  - [ ] 5.1: Create `nanobot/mc/test_cli_status.py` (or add to existing test file)
  - [ ] 5.2: Test status command when MC is not running (no PID file)
  - [ ] 5.3: Test status command when MC is running — mock bridge queries
  - [ ] 5.4: Test status display includes agent counts and task counts
  - [ ] 5.5: Test graceful handling when Convex is unreachable

## Dev Notes

### Critical Architecture Requirements

- **Status command queries live Convex state**: The `mc status` command connects to Convex (same as `mc tasks list`) and queries real-time data. It is a read-only operation.
- **PID file is the process indicator**: The existing PID file (`~/.nanobot/mc.pid`) is used to determine if MC is running. The status command checks both file existence and process liveness.
- **Bridge is the only Convex interface**: The status command reuses the existing `_get_bridge()` helper from `mc.py` to connect to Convex. No direct SDK usage.
- **Rich CLI output**: All MC CLI commands use Rich for formatting. Status output should match the existing style (tables, colored status text).

### Status Command Pattern

```python
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
        console.print(f"  Dashboard: [cyan]http://localhost:3000[/cyan]")

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

        for s in ["inbox", "assigned", "in_progress", "review", "done", "retrying", "crashed"]:
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
```

### Docs Command Pattern

For MVP, a lightweight approach that reads Convex function exports:

```python
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
        doc_lines.append(_parse_convex_functions(ts_file.read_text(), ts_file.stem))

    md_text = "\n".join(doc_lines)
    console.print(Markdown(md_text))
```

The `_parse_schema_tables` and `_parse_convex_functions` functions use regex to extract table definitions and exported query/mutation names from TypeScript files. This is a lightweight approach — no TypeScript AST parsing needed for MVP.

### Data Privacy Notice Pattern

```markdown
## Data Privacy

Mission Control uses [Convex](https://convex.dev) as its real-time backend.
All task data, agent messages, activity logs, and settings are stored on Convex's
cloud infrastructure.

### What data transits through Convex

- Task titles, descriptions, and status history
- Inter-agent messages and review feedback
- Agent configuration metadata (names, roles, skills)
- Activity events and system logs
- Dashboard settings (timeouts, default model)

### Security considerations

- **Dashboard access**: Set `MC_ACCESS_TOKEN` in your `.env.local` to require
  authentication for the dashboard. Without this, the dashboard is open to anyone
  on the network.
- **Convex transport**: Data is encrypted in transit (HTTPS/WSS) between your
  machine and Convex servers. See [Convex Security](https://docs.convex.dev/production/security)
  for details.
- **Sensitive data**: If your agents process sensitive information (financial records,
  personal emails, calendar data), be aware that this data will be stored on Convex's
  infrastructure. Review Convex's [Privacy Policy](https://www.convex.dev/privacy)
  before handling regulated data.

### For sensitive deployments

For deployments handling highly sensitive data, consider:
- Using Convex's self-hosted option (when available)
- Implementing data sanitization in agent prompts to avoid storing raw sensitive content
- Reviewing your organization's data residency requirements against Convex's infrastructure
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT make the status command start MC** — `mc status` is read-only. If MC is not running, it prints a message and exits. It does NOT start the system.

2. **DO NOT poll or stream in the status command** — Status is a one-shot query. Run once, display results, exit. No `--watch` mode for MVP.

3. **DO NOT parse TypeScript with a full AST parser** — For the docs command, simple regex extraction of `export const` query/mutation names is sufficient. No `ts-morph` or similar dependency.

4. **DO NOT skip the PID file check** — The status command must check both PID file existence AND process liveness (via `os.kill(pid, 0)`). A stale PID file means MC crashed.

5. **DO NOT import new heavy dependencies** — Use Rich (already a dependency) for formatting. No new CLI dependencies needed.

6. **DO NOT forget to close the bridge** — The status command creates a bridge, queries Convex, and must close the bridge before exiting. Use try/finally.

7. **DO NOT add the privacy notice to a separate website** — The privacy notice belongs in the project README or a local docs file. It must be visible to anyone who clones the repo.

8. **DO NOT make the docs command require MC to be running** — Docs are generated from static files (schema.ts, function files). MC does not need to be running.

### What This Story Does NOT Include

- **Real-time monitoring dashboard** — The CLI status is a snapshot, not a live monitor
- **Health check API endpoint** — No HTTP health check for MVP
- **Alerting or notifications** — No email/Slack alerts for system health
- **Performance metrics** — No CPU/memory monitoring
- **OpenAPI spec generation** — Convex does not use REST; docs are schema-based

### Files Created in This Story

| File | Purpose |
|------|---------|
| (status and docs commands added to existing `mc.py`) | CLI commands |
| `nanobot/mc/test_cli_status.py` | Unit tests for status command |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `nanobot/cli/mc.py` | Add `status` and `docs` commands |
| `README.md` (or `docs/DATA-PRIVACY.md`) | Add data privacy notice (NFR20) |

### Verification Steps

1. Stop MC if running — run `nanobot mc status` — verify "not running" message
2. Start MC — run `nanobot mc status` — verify agent counts, task counts, uptime display
3. Verify status returns within 2 seconds (NFR5)
4. Create some tasks and agents — run status again — verify counts update
5. Run `nanobot mc docs` — verify schema tables and functions are displayed
6. Check README for data privacy notice section
7. Run `pytest nanobot/mc/test_cli_status.py` — all tests pass

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 7.5`] — Original story definition
- [Source: `_bmad-output/planning-artifacts/prd.md#FR44`] — CLI system health overview
- [Source: `_bmad-output/planning-artifacts/prd.md#FR47`] — Auto-generated API documentation
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR5`] — CLI response < 2 seconds
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR20`] — Data privacy notice
- [Source: `nanobot/cli/mc.py`] — Existing CLI module to extend
- [Source: `nanobot/mc/bridge.py`] — Bridge for Convex queries
- [Source: `dashboard/convex/schema.ts`] — Schema for docs generation

## Dev Agent Record

### Agent Model Used
claude-opus-4-6

### Debug Log References
All 17 new tests pass. All 60 CLI tests pass with no regressions. Import verified.

### Completion Notes List
- Added `status` command: checks PID file + process liveness, queries Convex for agents/tasks, displays Rich-formatted output with uptime, agent table, task counts
- Added `docs` command: parses Convex schema.ts and function files via regex, renders Markdown API reference in terminal
- Added helper functions `_parse_schema_tables` and `_parse_convex_functions` for lightweight TS parsing
- Added `import time` for uptime calculation
- Added Data Privacy section to README.md (NFR20)
- Created 17 unit tests covering: not-running state, stale PID, running state with agents/tasks, bridge close, error handling, docs command with schema/functions

### File List
| File | Action |
|------|--------|
| `nanobot/cli/mc.py` | Modified - added `status`, `docs` commands + helper functions |
| `nanobot/mc/test_cli_status.py` | Created - 17 unit tests |
| `README.md` | Modified - added Data Privacy section |
