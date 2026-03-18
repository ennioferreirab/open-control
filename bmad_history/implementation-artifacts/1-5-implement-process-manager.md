# Story 1.5: Implement Process Manager

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want a process manager that spawns and monitors all Mission Control subprocesses,
So that the system can be started and stopped reliably as a coordinated unit.

## Acceptance Criteria

1. **Given** the bridge and dashboard project exist (Stories 1.1-1.4), **When** the process manager is invoked to start, **Then** it spawns 3 child processes: Agent Gateway (Python AsyncIO main loop), Next.js dev server (`npm run dev` in `dashboard/`), and Convex dev server (`npx convex dev` in `dashboard/`)
2. **Given** the process manager starts all 3 processes, **Then** all 3 processes start within 15 seconds (NFR6)
3. **Given** all processes are running, **Then** the process manager monitors child process health and detects crashes (non-zero exit codes or unexpected termination)
4. **Given** child processes produce output, **Then** stdout/stderr from all child processes are captured and forwarded to the main process stdout with a prefix identifying the source process (e.g., `[next.js]`, `[convex]`, `[gateway]`)
5. **Given** the process manager receives a shutdown signal (SIGTERM, SIGINT, or programmatic stop), **When** graceful shutdown is initiated, **Then** all child processes receive termination signals in reverse startup order (gateway first, then Next.js, then Convex)
6. **Given** graceful shutdown is initiated, **Then** the process manager waits up to 30 seconds for all processes to exit (NFR14)
7. **Given** a child process does not exit within the 30-second timeout, **Then** it is force-killed (SIGKILL)
8. **Given** graceful shutdown completes, **Then** all task state in Convex is preserved (no in-flight mutations lost — the gateway flushes pending bridge operations before exiting)
9. **Given** the process manager is created, **Then** the module is at `nanobot/mc/process_manager.py` and does NOT exceed 500 lines (NFR21)
10. **Given** the process manager is created, **Then** unit tests exist in `nanobot/mc/test_process_manager.py`
11. **Given** a child process crashes during normal operation, **Then** the process manager logs the crash with the process name and exit code, and reports it to the caller (does NOT auto-restart — crash handling is a caller concern)

## Tasks / Subtasks

- [x] Task 1: Create the ProcessManager class (AC: #1, #9)
  - [x] 1.1: Create `nanobot/mc/process_manager.py` with `ProcessManager` class
  - [x] 1.2: Define `__init__` with `dashboard_dir` parameter (path to `dashboard/` directory)
  - [x] 1.3: Define process configuration for all 3 child processes as a data structure (command, args, working directory, label)
  - [x] 1.4: Verify module stays under 500 lines (363 lines)
- [x] Task 2: Implement startup logic (AC: #1, #2, #4)
  - [x] 2.1: Implement `start()` async method that spawns all 3 child processes in order
  - [x] 2.2: Start Convex dev server first (backend must be ready for Next.js and gateway)
  - [x] 2.3: Start Next.js dev server second
  - [x] 2.4: Start Agent Gateway last (depends on Convex being available)
  - [x] 2.5: Capture stdout/stderr from each child process and forward to main stdout with `[process-name]` prefix
  - [x] 2.6: Implement startup timeout — if any process fails to start within 15 seconds, abort all and raise error
  - [x] 2.7: Log startup progress for each process: "Starting [name]...", "Started [name] (PID: xxx)"
- [x] Task 3: Implement health monitoring (AC: #3, #11)
  - [x] 3.1: Implement `_monitor()` async method that watches all child processes for unexpected termination
  - [x] 3.2: Detect process crashes via non-zero exit codes or unexpected termination
  - [x] 3.3: On crash detection, log the process name, PID, and exit code
  - [x] 3.4: Invoke an optional `on_crash` callback provided by the caller (does NOT auto-restart)
  - [x] 3.5: If one process crashes, optionally trigger shutdown of remaining processes (configurable behavior)
- [x] Task 4: Implement graceful shutdown (AC: #5, #6, #7, #8)
  - [x] 4.1: Implement `stop()` async method for graceful shutdown
  - [x] 4.2: Send SIGTERM to processes in reverse startup order: gateway first, Next.js second, Convex last
  - [x] 4.3: Wait up to 30 seconds total for all processes to exit
  - [x] 4.4: Force-kill (SIGKILL) any process that hasn't exited after the timeout
  - [x] 4.5: Register signal handlers (SIGTERM, SIGINT) that trigger `stop()` when the main process receives them
  - [x] 4.6: Log shutdown progress: "Stopping [name] (PID: xxx)...", "Stopped [name]", or "Force-killed [name]"
  - [x] 4.7: Return a summary of shutdown results (which processes stopped cleanly vs. force-killed)
- [x] Task 5: Write unit tests (AC: #10)
  - [x] 5.1: Create `nanobot/mc/test_process_manager.py`
  - [x] 5.2: Test startup spawns 3 processes in correct order
  - [x] 5.3: Test stdout forwarding with process name prefix
  - [x] 5.4: Test graceful shutdown sends signals in reverse order
  - [x] 5.5: Test force-kill after timeout
  - [x] 5.6: Test crash detection invokes callback
  - [x] 5.7: Test startup timeout failure aborts all processes

## Dev Notes

### Critical Architecture Requirements

- **3 child processes**: The process manager spawns exactly 3 processes. No more, no less for MVP.
- **Startup order matters**: Convex dev server must start first (it serves the backend functions). Next.js starts second (it needs `NEXT_PUBLIC_CONVEX_URL`). Agent Gateway starts last (it needs Convex to be available for bridge connections).
- **Shutdown order is reverse of startup**: Gateway stops first (so it can flush pending bridge operations to Convex before Convex goes down). Next.js stops second. Convex stops last.
- **No auto-restart**: The process manager detects crashes but does NOT auto-restart processes. The caller (CLI or gateway) decides what to do. Auto-restart of agents is a different concern handled by the gateway (Story 7.1).
- **AsyncIO-based**: The process manager uses `asyncio.create_subprocess_exec()` for subprocess management. This integrates naturally with the nanobot AsyncIO runtime.
- **500-line limit (NFR21)**: The module must stay under 500 lines. The process manager should be straightforward — subprocess spawning, monitoring, and shutdown.
- **Agent Gateway is a placeholder for now**: In this story, the "Agent Gateway" process is a placeholder (e.g., a simple Python script that starts an event loop). The actual gateway logic is implemented in later stories. The process manager just needs to know how to start it.

### Process Definitions

| # | Process | Command | Working Directory | Label | Startup Order |
|---|---------|---------|-------------------|-------|---------------|
| 1 | Convex dev server | `npx convex dev` | `dashboard/` | `convex` | First |
| 2 | Next.js dev server | `npm run dev` | `dashboard/` | `next.js` | Second |
| 3 | Agent Gateway | `python -m nanobot.mc.gateway` | project root | `gateway` | Third (last) |

**Shutdown order**: Reverse — gateway first, next.js second, convex last.

### ProcessManager Class Design

```python
"""
ProcessManager — Spawns and manages Mission Control subprocesses.

Manages 3 child processes:
1. Convex dev server (npx convex dev)
2. Next.js dev server (npm run dev)
3. Agent Gateway (python -m nanobot.mc.gateway)
"""

import asyncio
import logging
import signal
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class ProcessConfig:
    """Configuration for a managed child process."""
    label: str
    command: str
    args: list[str]
    cwd: str
    env: dict[str, str] | None = None  # Additional env vars (merged with os.environ)


@dataclass
class ManagedProcess:
    """A running child process with its configuration."""
    config: ProcessConfig
    process: asyncio.subprocess.Process
    output_task: asyncio.Task | None = None  # Task reading stdout/stderr


# Constants
STARTUP_TIMEOUT_SECONDS = 15  # NFR6
SHUTDOWN_TIMEOUT_SECONDS = 30  # NFR14


class ProcessManager:
    """Manages Mission Control child processes."""

    def __init__(
        self,
        dashboard_dir: str | Path,
        project_root: str | Path | None = None,
        on_crash: Callable[[str, int], Awaitable[None]] | None = None,
    ):
        """
        Initialize the process manager.

        Args:
            dashboard_dir: Absolute path to the dashboard/ directory
            project_root: Absolute path to the nanobot project root (defaults to dashboard_dir parent)
            on_crash: Optional async callback(process_label, exit_code) called when a child crashes
        """
        ...

    async def start(self) -> None:
        """
        Start all 3 child processes in order.

        Raises:
            RuntimeError: If any process fails to start within STARTUP_TIMEOUT_SECONDS
        """
        ...

    async def stop(self) -> dict[str, str]:
        """
        Gracefully stop all child processes in reverse startup order.

        Returns:
            Dict mapping process label to shutdown result:
            "stopped" (clean exit) or "killed" (force-killed after timeout)
        """
        ...

    async def wait(self) -> None:
        """
        Wait for all processes to exit (used after start to keep main process alive).
        Returns when any process exits unexpectedly or stop() is called.
        """
        ...

    @property
    def is_running(self) -> bool:
        """True if all managed processes are still running."""
        ...

    def _get_process_configs(self) -> list[ProcessConfig]:
        """Return the 3 process configurations in startup order."""
        ...
```

### Subprocess Spawning Pattern

```python
async def _spawn_process(self, config: ProcessConfig) -> ManagedProcess:
    """
    Spawn a single child process.

    Args:
        config: Process configuration

    Returns:
        ManagedProcess instance with running process
    """
    logger.info(f"[MC] Starting {config.label}...")

    process = await asyncio.create_subprocess_exec(
        config.command,
        *config.args,
        cwd=config.cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,  # Merge stderr into stdout
        env={**os.environ, **(config.env or {})},
    )

    logger.info(f"[MC] Started {config.label} (PID: {process.pid})")

    # Start background task to forward output
    output_task = asyncio.create_task(
        self._forward_output(config.label, process)
    )

    return ManagedProcess(
        config=config,
        process=process,
        output_task=output_task,
    )
```

### Output Forwarding Pattern

Each child process's stdout/stderr is read line by line and forwarded to the main process's stdout with a label prefix. This provides a unified log view.

```python
async def _forward_output(self, label: str, process: asyncio.subprocess.Process) -> None:
    """
    Read and forward child process output to main stdout.

    Args:
        label: Process label for prefixing (e.g., "convex", "next.js", "gateway")
        process: The child process to read from
    """
    assert process.stdout is not None
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        decoded = line.decode("utf-8", errors="replace").rstrip()
        if decoded:
            logger.info(f"[{label}] {decoded}")
```

### Graceful Shutdown Pattern

```python
async def _stop_process(
    self,
    managed: ManagedProcess,
    timeout: float,
) -> str:
    """
    Stop a single child process gracefully.

    Args:
        managed: The managed process to stop
        timeout: Seconds to wait before force-killing

    Returns:
        "stopped" if clean exit, "killed" if force-killed
    """
    label = managed.config.label
    process = managed.process

    if process.returncode is not None:
        # Already exited
        return "stopped"

    logger.info(f"[MC] Stopping {label} (PID: {process.pid})...")

    # Send SIGTERM
    try:
        process.terminate()
    except ProcessLookupError:
        return "stopped"

    # Wait for clean exit
    try:
        await asyncio.wait_for(process.wait(), timeout=timeout)
        logger.info(f"[MC] Stopped {label} (exit code: {process.returncode})")
        return "stopped"
    except asyncio.TimeoutError:
        # Force kill
        logger.warning(f"[MC] Force-killing {label} (PID: {process.pid}) after {timeout}s timeout")
        try:
            process.kill()
            await process.wait()
        except ProcessLookupError:
            pass
        return "killed"
```

### Signal Handler Registration

The process manager registers signal handlers so that Ctrl+C (SIGINT) and SIGTERM trigger graceful shutdown.

```python
def _register_signal_handlers(self) -> None:
    """Register signal handlers for graceful shutdown."""
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(self._handle_signal(s)),
        )

async def _handle_signal(self, sig: signal.Signals) -> None:
    """Handle shutdown signal."""
    logger.info(f"[MC] Received {sig.name}, initiating graceful shutdown...")
    await self.stop()
```

### Health Monitoring Pattern

```python
async def _monitor(self) -> None:
    """
    Monitor all child processes for unexpected termination.
    Runs as a background task after startup.
    """
    while self._running:
        for managed in self._processes:
            process = managed.process
            if process.returncode is not None and self._running:
                # Process exited unexpectedly
                label = managed.config.label
                exit_code = process.returncode
                logger.error(
                    f"[MC] Process {label} (PID: {process.pid}) crashed with exit code {exit_code}"
                )
                if self._on_crash:
                    await self._on_crash(label, exit_code)
                return  # Exit monitoring — caller decides next step

        await asyncio.sleep(1)  # Check every second
```

### Startup Order and Dependencies

The startup order is critical because of inter-process dependencies:

```
1. Convex dev server (npx convex dev)
   - Must start first — serves the backend functions and reactive queries
   - The dashboard and gateway both need Convex to be running
   - Outputs "Convex functions ready" when backend is synced

2. Next.js dev server (npm run dev)
   - Starts second — needs NEXT_PUBLIC_CONVEX_URL to be set
   - The Convex dev server must have synced before Next.js can connect
   - Outputs "Ready on http://localhost:3000" when ready

3. Agent Gateway (python -m nanobot.mc.gateway)
   - Starts last — needs Convex to be available for bridge connections
   - Creates ConvexBridge instance which connects to the running Convex deployment
   - In this story, the gateway module is a minimal placeholder
```

**Startup readiness**: For MVP, the process manager uses a simple time-based approach — start each process and give it a brief moment to initialize. A more sophisticated approach (watching stdout for readiness messages) can be added later if needed. The 15-second overall timeout (NFR6) ensures the system doesn't hang.

### Agent Gateway Placeholder

The Agent Gateway module (`nanobot/mc/gateway.py`) does not exist yet. For this story, the process manager needs something to start as the third process. Create a minimal placeholder:

```python
# nanobot/mc/gateway.py — Minimal placeholder for Story 1.5
"""
Agent Gateway — connects nanobot agents to Convex via the bridge.

This is a placeholder. Full implementation starts in later stories.
"""

import asyncio
import logging
import signal

logger = logging.getLogger(__name__)


async def main() -> None:
    """Gateway main loop — placeholder."""
    logger.info("[gateway] Agent Gateway started (placeholder)")

    # Wait until interrupted
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()
    logger.info("[gateway] Agent Gateway stopping...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
```

This placeholder:
- Can be started with `python -m nanobot.mc.gateway`
- Runs indefinitely until receiving SIGTERM/SIGINT
- Exits cleanly on signal
- Will be replaced with actual gateway logic in later stories

### Existing nanobot Patterns (Brownfield Context)

The existing nanobot codebase uses:
- **`typer`** for CLI (`nanobot/cli/commands.py`)
- **`rich`** for console output (Console, Table, Markdown)
- **`asyncio`** for the agent runtime
- **`logging`** module for log output
- **`signal`** handlers for graceful shutdown

The process manager follows these same patterns. It does NOT introduce new dependencies — only uses standard library `asyncio` and `signal` modules.

### Platform Considerations

- **macOS/Linux**: `process.terminate()` sends SIGTERM. `process.kill()` sends SIGKILL. Signal handlers use `loop.add_signal_handler()`.
- **Windows**: Not a target for MVP (architecture specifies macOS/Linux localhost deployment). If Windows support is needed later, signal handling would need adaptation.
- **`npx` and `npm` commands**: These are assumed to be available on the system PATH. The process manager does not install Node.js dependencies.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT use `subprocess.Popen` for async processes** — Use `asyncio.create_subprocess_exec()` which integrates with the AsyncIO event loop. `subprocess.Popen` blocks the event loop.

2. **DO NOT auto-restart crashed processes** — The process manager reports crashes. The caller (CLI command or future gateway) decides whether to restart. Auto-restart logic for agents is in Story 7.1.

3. **DO NOT start processes in parallel** — Start them sequentially in the specified order. Convex must be running before Next.js, and both must be running before the gateway.

4. **DO NOT forget to forward child process output** — Without output forwarding, the user cannot see what the child processes are doing. Each line must be prefixed with the process label.

5. **DO NOT merge stdout and stderr into separate streams** — Use `stderr=asyncio.subprocess.STDOUT` to merge them into a single stream. This simplifies output forwarding and ensures all output is interleaved correctly.

6. **DO NOT block the event loop during shutdown** — Use `asyncio.wait_for()` with timeout for waiting on process exit, not `process.wait()` with no timeout.

7. **DO NOT send SIGKILL immediately** — Always try SIGTERM first and wait for clean exit. Only force-kill after the 30-second timeout. This gives processes time to flush state.

8. **DO NOT forget to clean up background tasks** — The output forwarding tasks (`_forward_output`) must be cancelled or awaited during shutdown to prevent warnings about pending tasks.

9. **DO NOT use `os.kill()` directly** — Use the `process.terminate()` and `process.kill()` methods on the `asyncio.subprocess.Process` object. They handle platform differences.

10. **DO NOT hardcode paths** — The `dashboard_dir` and `project_root` are passed as constructor parameters. The process manager resolves commands relative to these paths.

11. **DO NOT create the gateway module with actual business logic** — This story creates a minimal placeholder. The real gateway implementation is in later stories.

12. **DO NOT exceed 500 lines** — The process manager should be ~250-350 lines including the class, all methods, and helpers. If it approaches 500, the design is too complex.

### Test Strategy

Tests go in `nanobot/mc/test_process_manager.py` (co-located with source).

**Testing approach**: Since the process manager spawns real subprocesses, tests should mock `asyncio.create_subprocess_exec` to avoid actually starting Node.js/Convex servers. Tests verify:

1. **Correct spawn order** — Processes are started in the correct sequence
2. **Output forwarding** — Child stdout is forwarded with labels
3. **Shutdown order** — Processes are terminated in reverse order
4. **Force-kill on timeout** — Process.kill() is called after timeout
5. **Crash detection** — Callback is invoked when a process exits unexpectedly
6. **Startup timeout** — Error is raised if startup takes too long

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_startup_order():
    """Processes start in correct order: convex, next.js, gateway."""
    spawn_order = []

    async def mock_create_subprocess(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("program", "")
        spawn_order.append(cmd)
        mock_proc = AsyncMock()
        mock_proc.pid = 12345
        mock_proc.returncode = None
        mock_proc.stdout = AsyncMock()
        mock_proc.stdout.readline = AsyncMock(return_value=b"")
        mock_proc.wait = AsyncMock()
        mock_proc.terminate = MagicMock()
        mock_proc.kill = MagicMock()
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=mock_create_subprocess):
        pm = ProcessManager("/path/to/dashboard")
        await pm.start()

        assert len(spawn_order) == 3
        assert "npx" in spawn_order[0]    # Convex first
        assert "npm" in spawn_order[1]    # Next.js second
        assert "python" in spawn_order[2]  # Gateway third


@pytest.mark.asyncio
async def test_shutdown_reverse_order():
    """Processes are terminated in reverse startup order."""
    terminate_order = []
    # ... mock processes, track terminate() call order
    # Assert: gateway terminated first, next.js second, convex last


@pytest.mark.asyncio
async def test_force_kill_after_timeout():
    """Process that doesn't exit within timeout is force-killed."""
    # Mock process.wait() to raise TimeoutError
    # Assert process.kill() is called


@pytest.mark.asyncio
async def test_crash_callback():
    """on_crash callback is invoked when process exits unexpectedly."""
    callback = AsyncMock()
    # Mock process to exit with non-zero code
    # Assert callback was called with (label, exit_code)
```

### What This Story Does NOT Include

- **No CLI commands** — `nanobot mc start` and `nanobot mc stop` are implemented in Story 1.6. This story only creates the ProcessManager class that the CLI calls.
- **No actual Agent Gateway logic** — Only a minimal placeholder (`gateway.py`) that can be started and stopped. Real gateway logic comes in later stories.
- **No Convex deployment setup** — The process manager assumes `npx convex dev` is already configured (Story 1.1 sets up the Convex project).
- **No process auto-restart** — Crash detection reports to the caller. Auto-restart of agents is Story 7.1.
- **No Windows support** — Signal handling assumes Unix (macOS/Linux).

### Files Created in This Story

| File | Purpose |
|------|---------|
| `nanobot/mc/process_manager.py` | ProcessManager class — spawns, monitors, and stops 3 child processes |
| `nanobot/mc/gateway.py` | Minimal Agent Gateway placeholder (can be started/stopped) |
| `nanobot/mc/test_process_manager.py` | Unit tests for ProcessManager |

### Files Modified in This Story

None. This story only creates new files.

### Verification Steps

1. `from nanobot.mc.process_manager import ProcessManager` — imports successfully
2. `python -m nanobot.mc.gateway` — starts and waits, exits cleanly on Ctrl+C
3. `python -m pytest nanobot/mc/test_process_manager.py -v` — all tests pass
4. `wc -l nanobot/mc/process_manager.py` — output is < 500 lines
5. Manual smoke test (optional): instantiate `ProcessManager`, call `start()`, verify all 3 processes spawn, call `stop()`, verify clean shutdown

### References

- [Source: `_bmad-output/planning-artifacts/architecture.md#Infrastructure & Deployment`] — Process orchestration table: 3 processes, their roles and lifecycle
- [Source: `_bmad-output/planning-artifacts/architecture.md#Project Structure & Boundaries`] — `process_manager.py` location, directory structure
- [Source: `_bmad-output/planning-artifacts/epics.md#Story 1.5`] — Original story definition with acceptance criteria
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR6`] — "nanobot mc start launches the full system within 15 seconds"
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR14`] — "Graceful shutdown completes within 30 seconds, preserving all task state in Convex"
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR21`] — 500-line module limit
- [Source: `_bmad-output/implementation-artifacts/1-3-build-asyncio-convex-bridge-core.md`] — AsyncIO integration strategy, synchronous bridge + asyncio.to_thread pattern
- [Source: `_bmad-output/implementation-artifacts/1-4-add-bridge-retry-logic-and-dual-logging.md`] — Bridge retry ensures in-flight mutations complete before shutdown
- [Source: `nanobot/cli/commands.py`] — Existing CLI patterns: typer, rich, asyncio, signal handling

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
None

### Completion Notes List
- All 11 unit tests pass (pytest)
- Module is 363 lines (under 500-line NFR21 limit)
- Used `from __future__ import annotations` for Python 3.9 compatibility (dict[str, str] | None syntax)
- Used `asyncio.wait_for()` instead of `asyncio.timeout()` for Python 3.9 compatibility
- Gateway placeholder starts and exits cleanly on signal

### File List
- `nanobot/mc/gateway.py` — Minimal Agent Gateway placeholder (asyncio event loop, exits on SIGTERM/SIGINT)
- `nanobot/mc/process_manager.py` — ProcessManager class (378 lines): ProcessConfig, ManagedProcess dataclasses, start/stop/wait/monitor lifecycle
- `nanobot/mc/test_process_manager.py` — 11 unit tests covering startup order, shutdown order, force-kill, crash callback, timeout, output forwarding, is_running, double-start, immediate-exit

### Code Review Record

**Reviewer**: Claude Opus 4.6 (adversarial review)
**Date**: 2026-02-23
**Result**: PASS (all issues fixed)

#### Issues Found and Fixed

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 1 | HIGH | `_monitor` reported exit code 0 as a "crash" — AC #11 specifies "non-zero exit codes" but code only checked `returncode is not None` | Added conditional: non-zero exits log as `error` (crash), zero exits log as `warning` (unexpected exit). Both still invoke `on_crash` callback since any unexpected exit is noteworthy. |
| 2 | MEDIUM | `wait()` after `kill()` in `_stop_process` had no timeout — could hang forever on zombie processes | Added `asyncio.wait_for(..., timeout=5.0)` wrapper around post-SIGKILL wait, with error logging if it times out. |
| 3 | MEDIUM | `_stopping` flag was never reset if `stop()` raised an exception, making ProcessManager permanently un-stoppable | Wrapped `stop()` body in try/finally to ensure `_stopping = False` always runs. |
| 4 | MEDIUM | `test_output_forwarding` shared a single iterator across all 3 mock processes — only first process got real output, test was weaker than it appeared | Fixed to use `call_count` tracking so only the first process (convex) gets custom output lines; added assertion for "second line" to strengthen coverage. |
| 5 | LOW | Signal handlers registered in `start()` are never unregistered in `stop()` | Accepted for MVP — ProcessManager is used once per process lifetime. Noted for future improvement. |
| 6 | LOW | `test_force_kill_after_timeout` has fragile mock interaction with `AsyncMock` + cancellation | Accepted — test passes correctly and validates the right behavior despite internal fragility. |

All 11 tests pass after fixes. Module is 378 lines (under 500-line NFR21 limit).
