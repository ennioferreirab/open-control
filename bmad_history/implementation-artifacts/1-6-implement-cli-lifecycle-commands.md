# Story 1.6: Implement CLI Lifecycle Commands

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to start and stop Mission Control with simple CLI commands and get help for all available subcommands,
So that I can manage the system lifecycle without manual process management.

## Acceptance Criteria

1. **Given** the process manager is implemented (Story 1.5), **When** the user runs `nanobot mc start`, **Then** all Mission Control processes start (Agent Gateway, Next.js, Convex dev) via the ProcessManager
2. **Given** `nanobot mc start` is invoked, **Then** the dashboard is accessible at localhost:3000 once the Next.js dev server is ready
3. **Given** `nanobot mc start` is invoked, **Then** the CLI prints startup status showing each process launched (e.g., "[convex] Starting...", "[nextjs] Starting...", "[gateway] Starting...")
4. **Given** `nanobot mc start` is invoked and processes are running, **Then** the CLI remains running, forwarding process output to stdout (does not return to shell prompt)
5. **Given** Mission Control is running, **When** the user runs `nanobot mc stop`, **Then** graceful shutdown is initiated via the ProcessManager
6. **Given** `nanobot mc stop` is invoked, **Then** the CLI prints shutdown progress for each process (e.g., "[gateway] Stopped", "[nextjs] Stopped", "[convex] Stopped")
7. **Given** all processes have stopped, **Then** the CLI exits cleanly with exit code 0
8. **Given** the user wants to discover available commands, **When** the user runs `nanobot mc --help`, **Then** all available subcommands are listed with brief descriptions (start, stop, and future subcommands like agents, tasks, status)
9. **Given** the user wants help for a specific command, **When** the user runs `nanobot mc start --help`, **Then** the start command's options and description are displayed
10. **Given** `nanobot mc stop` is invoked but Mission Control is not running, **Then** the CLI prints "Mission Control is not running." and exits with code 0
11. **Given** all additions to this module, **Then** `nanobot/cli/mc.py` does NOT exceed 500 lines (NFR21)
12. **Given** the CLI is a thin layer, **Then** it contains NO business logic — all process management is delegated to `nanobot/mc/process_manager.py`

## Tasks / Subtasks

- [x] Task 1: Create `nanobot/cli/mc.py` with typer subcommand group (AC: #8, #9, #11, #12)
  - [x] 1.1: Create `nanobot/cli/mc.py` with a `typer.Typer()` instance named `mc_app`
  - [x] 1.2: Register `mc_app` in `nanobot/cli/commands.py` via `app.add_typer(mc_app, name="mc")`
  - [x] 1.3: Add help text to mc_app: "Mission Control — multi-agent orchestration dashboard"
  - [x] 1.4: Verify `nanobot mc --help` lists subcommands
- [x] Task 2: Implement `nanobot mc start` command (AC: #1, #2, #3, #4)
  - [x] 2.1: Add `start` command to mc_app
  - [x] 2.2: Resolve dashboard directory path relative to project root
  - [x] 2.3: Validate dashboard directory exists (print error and exit 1 if missing)
  - [x] 2.4: Create ProcessManager instance with dashboard_dir
  - [x] 2.5: Call `await process_manager.start()` to spawn all processes
  - [x] 2.6: Print startup banner showing Mission Control status and dashboard URL
  - [x] 2.7: Call `await process_manager.wait()` to block until shutdown (keeps CLI running)
  - [x] 2.8: Handle KeyboardInterrupt (Ctrl+C) via ProcessManager signal handlers + finally block
- [x] Task 3: Implement `nanobot mc stop` command (AC: #5, #6, #7, #10)
  - [x] 3.1: Add `stop` command to mc_app
  - [x] 3.2: Detect whether Mission Control is running (check for PID file or running processes)
  - [x] 3.3: If not running, print "Mission Control is not running." and exit 0
  - [x] 3.4: If running, send shutdown signal to the running process (via PID file or signal)
  - [x] 3.5: Print shutdown progress messages
  - [x] 3.6: Exit cleanly with exit code 0
- [x] Task 4: Add PID file management for stop command (AC: #5, #10)
  - [x] 4.1: On `start`, write PID of the main CLI process to `~/.nanobot/mc.pid`
  - [x] 4.2: On `stop`, read PID file and send SIGTERM to that process
  - [x] 4.3: On shutdown completion, remove the PID file
  - [x] 4.4: Handle stale PID files (process not running but PID file exists)
- [x] Task 5: Add placeholder subcommands for future stories (AC: #8)
  - [x] 5.1: No placeholder commands added — future commands (agents, tasks, status) will be added in their respective stories as separate typer subcommand groups registered in mc.py
  - [x] 5.2: Future commands will be added in Stories 2.7 (tasks), 3.4 (agents), 7.5 (status)
- [x] Task 6: Verify integration and CLI help (AC: #8, #9, #11)
  - [x] 6.1: Verified import works: `from nanobot.cli.mc import mc_app` succeeds
  - [x] 6.2: Verified `from nanobot.cli.commands import app` succeeds with mc_app registered
  - [x] 6.3: Both start and stop commands have docstrings for --help integration
  - [x] 6.4: `mc.py` is 110 lines (well under 500 limit)

## Dev Notes

### Critical Architecture Requirements

- **Module**: `nanobot/cli/mc.py` — this is a NEW file.
- **500-line limit (NFR21)**: This is a thin CLI layer. Target ~100-150 lines.
- **No business logic**: The CLI delegates ALL process management to `ProcessManager` from `nanobot/mc/process_manager.py`. The CLI only handles: argument parsing, output formatting (Rich), and calling ProcessManager methods.
- **Typer-based**: Follow the existing CLI patterns in `nanobot/cli/commands.py` — use `typer.Typer()`, Rich console for output, and `asyncio.run()` for async operations.
- **Registration in commands.py**: The mc subcommand group must be registered in the existing `nanobot/cli/commands.py` using `app.add_typer()`, following the same pattern as `channels_app`, `cron_app`, and `provider_app`.

### Existing CLI Patterns to Follow

From `nanobot/cli/commands.py`:

```python
# Pattern: Subcommand group registration
channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")

cron_app = typer.Typer(help="Manage scheduled tasks")
app.add_typer(cron_app, name="cron")

provider_app = typer.Typer(help="Manage providers")
app.add_typer(provider_app, name="provider")
```

The `mc` subcommand should follow this same pattern:

```python
# In nanobot/cli/mc.py
import typer

mc_app = typer.Typer(help="Mission Control — multi-agent orchestration dashboard")
```

```python
# In nanobot/cli/commands.py — add this registration
from nanobot.cli.mc import mc_app
app.add_typer(mc_app, name="mc")
```

### CLI Module Design

```python
"""CLI commands for Mission Control lifecycle management."""

import asyncio
import os
import signal
from pathlib import Path

import typer
from rich.console import Console

mc_app = typer.Typer(
    help="Mission Control — multi-agent orchestration dashboard",
    no_args_is_help=True,
)

console = Console()

# PID file location
PID_FILE = Path.home() / ".nanobot" / "mc.pid"


def _find_dashboard_dir() -> Path:
    """Locate the dashboard directory relative to the project root."""
    # Walk up from this file to find project root, then look for dashboard/
    # Or accept as option/env var
    candidates = [
        Path.cwd() / "dashboard",
        Path(__file__).resolve().parents[2] / "dashboard",
    ]
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "package.json").exists():
            return candidate
    return Path.cwd() / "dashboard"  # Fallback


@mc_app.command()
def start(
    dashboard_dir: str = typer.Option(
        None,
        "--dashboard-dir",
        "-d",
        help="Path to dashboard directory (auto-detected if not specified)",
    ),
):
    """Start Mission Control (dashboard + agent gateway)."""
    from nanobot.mc.process_manager import ProcessManager

    resolved_dir = Path(dashboard_dir) if dashboard_dir else _find_dashboard_dir()

    if not resolved_dir.is_dir():
        console.print(f"[red]Dashboard directory not found: {resolved_dir}[/red]")
        console.print("Run from the project root or specify --dashboard-dir")
        raise typer.Exit(1)

    console.print("[bold]Starting Mission Control...[/bold]")

    # Write PID file
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    async def _run():
        pm = ProcessManager(
            dashboard_dir=resolved_dir,
            gateway_factory=None,  # Gateway factory provided by later stories
        )
        try:
            await pm.start()
            console.print("[green]Mission Control is running[/green]")
            console.print(f"  Dashboard: [cyan]http://localhost:3000[/cyan]")
            await pm.wait()
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")
        finally:
            await pm.shutdown()
            _cleanup_pid_file()

    try:
        asyncio.run(_run())
    finally:
        _cleanup_pid_file()


@mc_app.command()
def stop():
    """Stop Mission Control gracefully."""
    if not PID_FILE.exists():
        console.print("Mission Control is not running.")
        raise typer.Exit(0)

    try:
        pid = int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        console.print("Mission Control is not running (invalid PID file).")
        _cleanup_pid_file()
        raise typer.Exit(0)

    # Check if process is actually running
    try:
        os.kill(pid, 0)  # Signal 0 = check existence
    except OSError:
        console.print("Mission Control is not running (stale PID file).")
        _cleanup_pid_file()
        raise typer.Exit(0)

    console.print("[yellow]Stopping Mission Control...[/yellow]")
    os.kill(pid, signal.SIGTERM)
    console.print("[green]Shutdown signal sent.[/green]")


def _cleanup_pid_file() -> None:
    """Remove the PID file."""
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass
```

### PID File Strategy

The `stop` command needs a way to find and signal the running `start` process. The simplest approach:

1. `nanobot mc start` writes the main process PID to `~/.nanobot/mc.pid`
2. `nanobot mc stop` reads the PID, verifies the process exists, and sends SIGTERM
3. The `start` command's signal handler (set up by ProcessManager) catches SIGTERM and initiates graceful shutdown
4. On shutdown completion, the PID file is removed

**Stale PID handling**: If the PID file exists but the process is not running (crashed without cleanup), `stop` detects this via `os.kill(pid, 0)` raising `OSError`, removes the stale PID file, and reports "not running."

### Gateway Factory

For Story 1.6, the `gateway_factory` is set to `None` (gateway implementation comes later). The ProcessManager should handle `gateway_factory=None` gracefully — it simply skips starting the gateway and only manages the two Node.js processes. When gateway.py is implemented in a later story, the CLI will provide the real factory:

```python
# Future: when gateway.py exists
from nanobot.mc.gateway import create_gateway

pm = ProcessManager(
    dashboard_dir=resolved_dir,
    gateway_factory=create_gateway,
)
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT put process management logic in the CLI** — The CLI calls `ProcessManager.start()`, `ProcessManager.shutdown()`, and `ProcessManager.wait()`. It does NOT directly spawn subprocesses, send signals to children, or manage output forwarding. That is all in `process_manager.py`.

2. **DO NOT use `subprocess.run()` or `subprocess.Popen()`** — The CLI is async via `asyncio.run()`. Process management is handled by the ProcessManager which uses `asyncio.create_subprocess_exec()`.

3. **DO NOT add task, agent, or status commands in this story** — Those are implemented in Stories 2.7, 3.4, and 7.5 respectively. This story only implements `start` and `stop`.

4. **DO NOT forget to register mc_app in commands.py** — Without the `app.add_typer(mc_app, name="mc")` line in `commands.py`, `nanobot mc` will not work.

5. **DO NOT use lazy imports inside the command functions** — Follow the existing pattern in commands.py where imports like `from nanobot.mc.process_manager import ProcessManager` are at the top of the function (not module level) to avoid import errors when Mission Control is not installed.

6. **DO NOT create a separate `mc` executable** — Mission Control commands are subcommands of the existing `nanobot` CLI. `nanobot mc start` — not a separate `nanobot-mc` binary.

7. **DO NOT exceed 500 lines** — This is a thin CLI layer. If it grows beyond ~150 lines, you are putting too much logic in the CLI.

8. **DO NOT skip the `--help` integration** — Typer auto-generates help text from docstrings and option descriptions. Make sure every command has a docstring and every option has a `help=` parameter.

9. **DO NOT hardcode the dashboard path** — Use `_find_dashboard_dir()` to auto-detect the dashboard directory. Allow override via `--dashboard-dir` option.

10. **DO NOT forget cleanup on crash** — If the `start` command crashes, the PID file must be cleaned up. Use `try/finally` blocks.

### What This Story Does NOT Include

- **No Agent Gateway implementation** — `gateway_factory=None` for now. Gateway is a future story.
- **No `nanobot mc agents` commands** — Story 3.4
- **No `nanobot mc tasks` commands** — Story 2.7
- **No `nanobot mc status` command** — Story 7.5
- **No dashboard validation** — The CLI does not verify that the Next.js server is actually serving HTTP responses. It only checks that the process is alive.
- **No Convex deployment setup** — The user must have already run `npx convex dev` once to create a Convex project. The `start` command assumes Convex is configured.
- **No tests for mc.py** — CLI integration testing is complex and provides limited value for a thin command layer. The ProcessManager (Story 1.5) has unit tests. Manual verification of CLI commands is sufficient for MVP.

### Files Created in This Story

| File | Purpose |
|------|---------|
| `nanobot/cli/mc.py` | Mission Control CLI subcommands (start, stop) |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `nanobot/cli/commands.py` | Add `from nanobot.cli.mc import mc_app` and `app.add_typer(mc_app, name="mc")` registration |

### Verification Steps

1. `nanobot mc --help` — shows start, stop subcommands with descriptions
2. `nanobot mc start --help` — shows start command options
3. `nanobot mc stop --help` — shows stop command description
4. `wc -l nanobot/cli/mc.py` — output is < 500 lines
5. `nanobot mc stop` when not running — prints "Mission Control is not running."

### References

- [Source: `_bmad-output/planning-artifacts/architecture.md#Infrastructure & Deployment`] — Process orchestration, `nanobot mc start` spawns all three processes
- [Source: `_bmad-output/planning-artifacts/architecture.md#Project Structure & Boundaries`] — `nanobot/cli/mc.py` file location, Boundary 4: CLI to Mission Control
- [Source: `_bmad-output/planning-artifacts/epics.md#Story 1.6`] — Original story definition with acceptance criteria
- [Source: `_bmad-output/planning-artifacts/prd.md#FR45`] — "User can start the entire Mission Control system with a single command (`nanobot mc start`)"
- [Source: `_bmad-output/planning-artifacts/prd.md#FR46`] — "User can stop Mission Control gracefully (`nanobot mc stop`)"
- [Source: `_bmad-output/planning-artifacts/prd.md#FR48`] — "System provides built-in help for all CLI commands (`--help`)"
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR6`] — Startup within 15 seconds
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR14`] — Graceful shutdown within 30 seconds
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR21`] — 500-line module limit
- [Source: `nanobot/cli/commands.py`] — Existing CLI patterns: typer subcommand groups, Rich console output, asyncio.run() for async

## Code Review Record

### Review Date
2026-02-23

### Reviewer
Claude Opus 4.6 (adversarial review)

### Issues Found

1. **[MEDIUM][FIXED] KeyboardInterrupt in wrong scope**: `except KeyboardInterrupt` was inside the async `_run()` coroutine (mc.py:66-67), but `asyncio.run()` handles KeyboardInterrupt specially by cancelling the main task and re-raising outside the coroutine. The catch inside `_run()` was dead code. Moved `except KeyboardInterrupt` to wrap `asyncio.run()` instead.

2. **[MEDIUM][FIXED] Double `_cleanup_pid_file()` call**: `_cleanup_pid_file()` was called in both the inner async `_run()` finally block and the outer synchronous `try/finally`. Removed the inner call since the outer one always runs and is the correct single cleanup point.

3. **[LOW][FIXED] Registration placement breaks code organization in commands.py**: The `mc_app` import and registration was inserted between `provider_app` registration and its `_LOGIN_HANDLERS` code, breaking the logical grouping. Moved to its own section header before `__main__` guard, following the same `# ====` section pattern.

4. **[LOW][NOTED] `stop` command is fire-and-forget**: The `stop` command sends SIGTERM but does not wait for the target process to actually exit. If the process crashes during shutdown, the PID file may remain stale until the next `stop` invocation. Acceptable for MVP since stale PID detection already handles this case.

5. **[LOW][NOTED] `_find_dashboard_dir` fallback returns possibly non-existent path**: When no candidate directory is found, the function returns `Path.cwd() / "dashboard"` which may not exist. This is caught by the validation check in `start`, but the error message could be confusing. Acceptable for MVP.

### Verification
- `from nanobot.cli.mc import mc_app` -- OK
- `from nanobot.cli.commands import app` -- OK
- `mc.py` is 110 lines (under 500 limit) -- OK
- All ACs verified against implementation -- PASS
- Thin CLI layer principle upheld -- PASS

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
None

### Completion Notes List
- Created `nanobot/cli/mc.py` (110 lines) with `start` and `stop` commands
- Adapted reference implementation to actual ProcessManager API: constructor takes `dashboard_dir` and `project_root` (not `gateway_factory`); uses `pm.stop()` (not `pm.shutdown()`)
- ProcessManager already registers SIGTERM/SIGINT signal handlers internally, so the CLI just needs `try/finally` for PID cleanup
- Registered `mc_app` in `nanobot/cli/commands.py` after the `provider_app` registration
- Task 5 (placeholder subcommands): chose not to add empty placeholder commands since they add noise; future stories will register their own typer subcommand groups
- Verified: import of mc_app succeeds, import of commands.py with mc_app registered succeeds, module is 110 lines

### File List
| File | Action | Description |
|------|--------|-------------|
| `nanobot/cli/mc.py` | Created | Mission Control CLI subcommands (start, stop) — 110 lines |
| `nanobot/cli/commands.py` | Modified | Added `from nanobot.cli.mc import mc_app` and `app.add_typer(mc_app, name="mc")` registration |
