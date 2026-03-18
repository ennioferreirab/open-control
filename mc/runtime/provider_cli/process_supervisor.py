"""ProviderProcessSupervisor - launches and manages provider CLI subprocesses."""

from __future__ import annotations

import asyncio
import os
import signal
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Literal

from mc.contexts.provider_cli.types import ProviderProcessHandle


class ProviderProcessSupervisor:
    """Launches provider CLI processes and provides process-level controls.

    The supervisor is intentionally provider-agnostic.  It owns OS-level
    concerns: pid, pgid, stdout/stderr streaming, and signal delivery.
    Provider-specific output parsing is delegated to ProviderCLIParser
    implementations.
    """

    def __init__(self) -> None:
        # Map from mc_session_id -> asyncio.subprocess.Process
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    async def launch(
        self,
        *,
        mc_session_id: str,
        provider: str,
        command: list[str],
        cwd: str,
        env: dict[str, str] | None = None,
        stdin_mode: Literal["pipe", "devnull", "inherit"] = "pipe",
    ) -> ProviderProcessHandle:
        """Launch *command* as a subprocess and return a ProviderProcessHandle.

        Args:
            mc_session_id: Unique MC session identifier.
            provider: Provider name string (e.g. "claude-code", "codex").
            command: Executable and arguments.
            cwd: Working directory for the subprocess.
            env: Optional environment override.  If None, inherits current env.
            stdin_mode: How stdin should be wired for the subprocess.

        Returns:
            A ProviderProcessHandle with pid, pgid, and metadata.
        """
        # Merge with current environment when explicit env is not provided
        effective_env: dict[str, str] | None
        if env is not None:
            # Merge: start from current env and overlay the provided values
            effective_env = {**os.environ, **env}
        else:
            effective_env = None  # inherit from parent

        stdin: int | None
        if stdin_mode == "pipe":
            stdin = asyncio.subprocess.PIPE
        elif stdin_mode == "devnull":
            stdin = asyncio.subprocess.DEVNULL
        elif stdin_mode == "inherit":
            stdin = None
        else:
            raise ValueError(f"Unsupported stdin_mode: {stdin_mode}")

        proc = await asyncio.create_subprocess_exec(
            *command,
            stdin=stdin,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,  # merge stderr into stdout
            cwd=cwd,
            env=effective_env,
            start_new_session=True,  # creates a new process group
        )

        pid = proc.pid
        try:
            pgid = os.getpgid(pid)
        except ProcessLookupError:
            # Process exited extremely quickly (e.g. `echo`).  With
            # start_new_session=True the pgid equals the pid at launch, so
            # use pid as the fallback pgid.
            pgid = pid

        self._processes[mc_session_id] = proc

        return ProviderProcessHandle(
            mc_session_id=mc_session_id,
            provider=provider,
            pid=pid,
            pgid=pgid,
            cwd=cwd,
            command=command,
            started_at=datetime.now(UTC).isoformat(),
        )

    async def stream_output(self, handle: ProviderProcessHandle) -> AsyncIterator[bytes]:
        """Yield raw output chunks from the process identified by *handle*.

        Streams stdout (which includes stderr when launched via :meth:`launch`
        because stderr is merged into stdout via STDOUT redirect).
        """
        proc = self._processes.get(handle.mc_session_id)
        if proc is None or proc.stdout is None:
            return

        while True:
            chunk = await proc.stdout.read(4096)
            if not chunk:
                break
            yield chunk

    def is_alive(self, handle: ProviderProcessHandle) -> bool:
        """Return True if the process for *handle* is still running.

        Returns False when the process has exited or the session is unknown.
        Uses asyncio.subprocess.Process.returncode: None means still running.
        """
        proc = self._processes.get(handle.mc_session_id)
        if proc is None:
            return False
        return proc.returncode is None

    async def wait_for_exit(self, handle: ProviderProcessHandle) -> int | None:
        """Wait for the process to finish and return its exit code."""
        proc = self._processes.get(handle.mc_session_id)
        if proc is None:
            return None
        exit_code = await proc.wait()
        self._processes.pop(handle.mc_session_id, None)
        return exit_code

    async def send_signal(self, handle: ProviderProcessHandle, sig: signal.Signals) -> None:
        """Send *sig* to the process group owned by *handle*.

        Uses the process group (pgid) when available so that child processes
        in the same session also receive the signal.
        """
        pgid = handle.pgid
        if pgid is not None:
            try:
                os.killpg(pgid, sig)
                return
            except ProcessLookupError:
                pass  # process already gone; fall through to pid-based signal

        proc = self._processes.get(handle.mc_session_id)
        if proc is not None:
            try:
                proc.send_signal(sig)
            except ProcessLookupError:
                pass  # process already exited

    async def terminate(self, handle: ProviderProcessHandle) -> None:
        """Send SIGTERM to the process group."""
        await self.send_signal(handle, signal.SIGTERM)

    async def write_stdin(self, handle: ProviderProcessHandle, data: str) -> None:
        """Write raw text to the subprocess stdin and flush it."""
        proc = self._processes.get(handle.mc_session_id)
        if proc is None or proc.stdin is None:
            raise RuntimeError(f"stdin unavailable for provider session '{handle.mc_session_id}'")

        proc.stdin.write(data.encode("utf-8"))
        await proc.stdin.drain()

    async def kill(self, handle: ProviderProcessHandle) -> None:
        """Send SIGKILL to the process group (unconditional termination)."""
        await self.send_signal(handle, signal.SIGKILL)

    async def inspect_process_tree(self, handle: ProviderProcessHandle) -> dict[str, Any]:
        """Return a lightweight snapshot of the process tree rooted at *handle*.

        Attempts to use *psutil* for a richer view; falls back to basic
        pid/pgid information when psutil is not available.
        """
        info: dict[str, Any] = {
            "pid": handle.pid,
            "pgid": handle.pgid,
            "children": [],
        }

        try:
            import psutil  # optional dependency

            try:
                parent = psutil.Process(handle.pid)
                info["status"] = parent.status()
                info["children"] = [
                    {"pid": c.pid, "status": c.status()} for c in parent.children(recursive=True)
                ]
            except psutil.NoSuchProcess:
                info["status"] = "gone"
        except ImportError:
            # psutil not installed; return minimal info
            pass

        return info
