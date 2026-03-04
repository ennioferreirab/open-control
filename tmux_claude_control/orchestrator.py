"""
orchestrator.py — Multi-session orchestrator for Claude Code instances.

Manages multiple ClaudeController workers, each in its own tmux session.
Enables parallel task dispatch, result collection, and coordinated shutdown.
"""

import time
import threading
from dataclasses import dataclass, field
from .claude_controller import ClaudeController, Response, ClaudeError


# ── WorkerResult ──────────────────────────────────────────────────────────────

@dataclass
class WorkerResult:
    """Result from a dispatched task."""
    worker_name: str
    response: Response | None
    error: str = ""
    duration: float = 0.0


# ── Orchestrator ──────────────────────────────────────────────────────────────

class Orchestrator:
    """Manages multiple Claude Code sessions for parallel task execution."""

    def __init__(self, prefix: str = "orch") -> None:
        self.prefix = prefix
        self.workers: dict[str, ClaudeController] = {}

    def spawn_worker(self, name: str, cwd: str = ".", timeout: float = 30.0) -> ClaudeController:
        """
        Create a new Claude Code worker in its own tmux session.

        Session name: f"{self.prefix}-{name}"
        Calls controller.launch() and waits for idle.
        """
        session_name = f"{self.prefix}-{name}"
        ctrl = ClaudeController(session_name=session_name, cwd=cwd)
        ctrl.launch(dangerous_skip=True, timeout=timeout)
        self.workers[name] = ctrl
        return ctrl

    def dispatch_task(self, worker_name: str, prompt: str, timeout: float = 120.0) -> Response:
        """Send a prompt to a specific worker and wait for response."""
        ctrl = self.workers[worker_name]
        return ctrl.send_prompt(prompt, timeout=timeout)

    def dispatch_parallel(
        self,
        tasks: dict[str, str],
        timeout: float = 120.0,
    ) -> dict[str, WorkerResult]:
        """
        Send different prompts to different workers in parallel.

        tasks: {worker_name: prompt_text}
        Returns: {worker_name: WorkerResult}

        Uses threading to send all prompts simultaneously, then collects results.
        """
        results: dict[str, WorkerResult] = {}
        threads: list[threading.Thread] = []
        lock = threading.Lock()

        def _run(name: str, prompt: str) -> None:
            start = time.monotonic()
            try:
                resp = self.dispatch_task(name, prompt, timeout=timeout)
                with lock:
                    results[name] = WorkerResult(
                        worker_name=name,
                        response=resp,
                        duration=time.monotonic() - start,
                    )
            except Exception as e:
                with lock:
                    results[name] = WorkerResult(
                        worker_name=name,
                        response=None,
                        error=str(e),
                        duration=time.monotonic() - start,
                    )

        for name, prompt in tasks.items():
            t = threading.Thread(target=_run, args=(name, prompt))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=timeout + 10)

        return results

    def wait_all_idle(self, timeout: float = 60.0) -> dict[str, bool]:
        """Wait for all workers to be in idle state."""
        results: dict[str, bool] = {}
        for name, ctrl in self.workers.items():
            try:
                ctrl.wait_for_idle(timeout=timeout)
                results[name] = True
            except Exception:
                results[name] = False
        return results

    def get_worker(self, name: str) -> ClaudeController:
        """Get a specific worker by name."""
        return self.workers[name]

    def list_workers(self) -> list[str]:
        """List all worker names."""
        return list(self.workers.keys())

    def shutdown_worker(self, name: str) -> None:
        """Gracefully shutdown a specific worker."""
        if name in self.workers:
            self.workers[name].exit_gracefully()
            del self.workers[name]

    def shutdown_all(self) -> None:
        """Gracefully shutdown all workers."""
        for name in list(self.workers.keys()):
            try:
                self.workers[name].exit_gracefully()
            except Exception:
                self.workers[name].kill()
            del self.workers[name]

    def kill_all(self) -> None:
        """Forcefully kill all workers (emergency cleanup)."""
        for name in list(self.workers.keys()):
            try:
                self.workers[name].kill()
            except Exception:
                pass
            del self.workers[name]

