"""
ProcessManager — Spawns and manages Mission Control subprocesses.

Manages 4 child processes:
1. Convex dev server (npm run dev:backend)
2. Next.js dev server (npm run dev:frontend)
3. Agent Gateway (python -m mc.runtime.gateway)
4. Nanobot Gateway — channels/Telegram (python -m nanobot gateway)
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


@dataclass
class ProcessConfig:
    """Configuration for a managed child process."""

    label: str
    command: str
    args: list[str]
    cwd: str
    env: dict[str, str] | None = None
    critical: bool = True  # If False, crash won't bring down other processes
    restart_on_crash: bool = False  # If True, auto-restart on unexpected exit


@dataclass
class ManagedProcess:
    """A running child process with its configuration."""

    config: ProcessConfig
    process: asyncio.subprocess.Process
    output_task: asyncio.Task | None = None


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
            project_root: Absolute path to the nanobot project root
                          (defaults to dashboard_dir parent)
            on_crash: Optional async callback(process_label, exit_code)
                      called when a child crashes
        """
        self._dashboard_dir = str(dashboard_dir)
        self._project_root = (
            str(project_root) if project_root else str(Path(self._dashboard_dir).parent)
        )
        self._on_crash = on_crash
        self._processes: list[ManagedProcess] = []
        self._running = False
        self._monitor_task: asyncio.Task | None = None
        self._stopping = False

    async def start(self) -> None:
        """
        Start all child processes in order.

        Raises:
            RuntimeError: If any process fails to start within
                          STARTUP_TIMEOUT_SECONDS
        """
        if self._running:
            raise RuntimeError("ProcessManager is already running")

        configs = self._get_process_configs()

        try:
            await asyncio.wait_for(self._start_all(configs), timeout=STARTUP_TIMEOUT_SECONDS)
        except (asyncio.TimeoutError, RuntimeError) as exc:
            logger.error(f"[MC] Startup failed: {exc}")
            # Abort: stop any processes that did start
            await self.stop()
            raise RuntimeError(f"Startup failed within {STARTUP_TIMEOUT_SECONDS}s: {exc}") from exc

        self._running = True
        self._register_signal_handlers()
        self._monitor_task = asyncio.create_task(self._monitor())
        logger.info("[MC] All processes started successfully")

    async def stop(self) -> dict[str, str]:
        """
        Gracefully stop all child processes in reverse startup order.

        Returns:
            Dict mapping process label to shutdown result:
            "stopped" (clean exit) or "killed" (force-killed after timeout)
        """
        if self._stopping:
            return {}

        self._stopping = True
        self._running = False

        try:
            # Cancel the monitor task
            if self._monitor_task and not self._monitor_task.done():
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass

            results: dict[str, str] = {}

            # Calculate per-process timeout
            num_processes = len(self._processes)
            per_process_timeout = (
                SHUTDOWN_TIMEOUT_SECONDS / num_processes if num_processes else 30.0
            )

            # Stop in reverse startup order
            for managed in reversed(self._processes):
                result = await self._stop_process(managed, per_process_timeout)
                results[managed.config.label] = result

                # Cancel the output forwarding task
                if managed.output_task and not managed.output_task.done():
                    managed.output_task.cancel()
                    try:
                        await managed.output_task
                    except asyncio.CancelledError:
                        pass

            self._processes.clear()
            logger.info(f"[MC] Shutdown complete: {results}")
            return results
        finally:
            self._stopping = False

    async def wait(self) -> None:
        """
        Wait for critical processes to exit. Returns when any critical
        process exits unexpectedly or stop() is called.
        Non-critical processes crashing won't bring down MC.
        """
        if not self._processes:
            return

        # Only wait on critical processes
        critical = [
            m for m in self._processes if m.config.critical and m.process.returncode is None
        ]
        if not critical:
            return

        wait_tasks = [asyncio.create_task(managed.process.wait()) for managed in critical]
        if wait_tasks:
            await asyncio.wait(wait_tasks, return_when=asyncio.FIRST_COMPLETED)

            # Clean up remaining wait tasks
            for task in wait_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

    @property
    def is_running(self) -> bool:
        """True if all managed processes are still running."""
        if not self._processes or not self._running:
            return False
        return all(managed.process.returncode is None for managed in self._processes)

    async def _start_all(self, configs: list[ProcessConfig]) -> None:
        """Spawn all processes sequentially."""
        for config in configs:
            managed = await self._spawn_process(config)
            self._processes.append(managed)
            # Brief pause to let the process initialize
            await asyncio.sleep(0.1)
            # Check it didn't immediately crash
            if managed.process.returncode is not None:
                raise RuntimeError(
                    f"{config.label} exited immediately with code {managed.process.returncode}"
                )

    def _get_venv_python(self) -> str:
        """Return venv Python if available, otherwise sys.executable."""
        venv_python = Path(self._project_root) / ".venv" / "bin" / "python3"
        if venv_python.exists():
            return str(venv_python)
        return sys.executable

    def _get_process_configs(self) -> list[ProcessConfig]:
        """Return the process configurations in startup order.

        Start Convex and Next separately so frontend boot is not blocked by
        ``predev`` hooks attached to ``npm run dev``.
        """
        venv_python = self._get_venv_python()
        return [
            ProcessConfig(
                label="convex",
                command="npm",
                args=["run", "dev:backend"],
                cwd=self._dashboard_dir,
                env={"NODE_OPTIONS": "--max-old-space-size=1536"},
                critical=False,
                restart_on_crash=True,
            ),
            ProcessConfig(
                label="dashboard",
                command="npm",
                args=["run", "dev:frontend"],
                cwd=self._dashboard_dir,
                env={"NODE_OPTIONS": "--max-old-space-size=1536"},
                critical=False,
                restart_on_crash=True,
            ),
            ProcessConfig(
                label="gateway",
                command=sys.executable,
                args=["-m", "mc.runtime.gateway"],
                cwd=self._project_root,
            ),
            ProcessConfig(
                label="nanobot",
                command=venv_python,
                args=["-m", "nanobot", "gateway"],
                cwd=self._project_root,
                critical=False,
            ),
        ]

    async def _spawn_process(self, config: ProcessConfig) -> ManagedProcess:
        """
        Spawn a single child process.

        Args:
            config: Process configuration

        Returns:
            ManagedProcess instance with running process
        """
        logger.info(f"[MC] Starting {config.label}...")

        env = {**os.environ, **(config.env or {})}
        process = await asyncio.create_subprocess_exec(
            config.command,
            *config.args,
            cwd=config.cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )

        logger.info(f"[MC] Started {config.label} (PID: {process.pid})")

        output_task = asyncio.create_task(self._forward_output(config.label, process))

        return ManagedProcess(
            config=config,
            process=process,
            output_task=output_task,
        )

    async def _forward_output(self, label: str, process: asyncio.subprocess.Process) -> None:
        """
        Read and forward child process output to stderr (visible to user).

        Args:
            label: Process label for prefixing
            process: The child process to read from
        """
        assert process.stdout is not None
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            decoded = line.decode("utf-8", errors="replace").rstrip()
            if decoded:
                print(f"[{label}] {decoded}", file=sys.stderr, flush=True)

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
            return "stopped"

        logger.info(f"[MC] Stopping {label} (PID: {process.pid})...")

        try:
            process.terminate()
        except ProcessLookupError:
            return "stopped"

        try:
            await asyncio.wait_for(process.wait(), timeout=timeout)
            logger.info(f"[MC] Stopped {label} (exit code: {process.returncode})")
            return "stopped"
        except asyncio.TimeoutError:
            logger.warning(
                f"[MC] Force-killing {label} (PID: {process.pid}) after {timeout}s timeout"
            )
            try:
                process.kill()
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except ProcessLookupError:
                pass
            except asyncio.TimeoutError:
                logger.error(
                    f"[MC] Process {label} (PID: {process.pid}) did not exit after SIGKILL"
                )
            return "killed"

    async def _monitor(self) -> None:
        """
        Monitor all child processes for unexpected termination.
        Runs as a background task after startup.
        Processes with restart_on_crash=True are restarted automatically.
        """
        while self._running:
            for i, managed in enumerate(self._processes):
                process = managed.process
                if process.returncode is not None and self._running:
                    label = managed.config.label
                    exit_code = process.returncode
                    if exit_code != 0:
                        logger.error(
                            f"[MC] Process {label} (PID: {process.pid}) "
                            f"crashed with exit code {exit_code}"
                        )
                    else:
                        logger.warning(
                            f"[MC] Process {label} (PID: {process.pid}) "
                            f"exited unexpectedly with code 0"
                        )

                    if managed.config.restart_on_crash:
                        logger.info(f"[MC] Restarting {label}...")
                        try:
                            restarted = await self._spawn_process(managed.config)
                            self._processes[i] = restarted
                            logger.info(f"[MC] Restarted {label} (PID: {restarted.process.pid})")
                        except Exception as exc:
                            logger.error(f"[MC] Failed to restart {label}: {exc}")
                        continue

                    if managed.config.critical:
                        if self._on_crash:
                            await self._on_crash(label, exit_code)
                        return
            await asyncio.sleep(1)

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
