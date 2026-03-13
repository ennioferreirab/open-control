"""tmux lifecycle helpers for interactive TUI sessions."""

from __future__ import annotations

import os
import subprocess
from typing import Callable

from mc.infrastructure.interactive.terminal_env import build_interactive_terminal_env

RunResult = subprocess.CompletedProcess[str]
RunCommand = Callable[..., RunResult]


class TmuxSessionManager:
    """Create, inspect, and clean up reconnectable tmux sessions."""

    def __init__(self, *, run: RunCommand = subprocess.run) -> None:
        self._run = run

    def ensure_session(
        self,
        session_name: str,
        *,
        cwd: str | None = None,
        command: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> bool:
        """Ensure a detached session exists. Returns True when newly created."""

        if self._has_session(session_name):
            return False

        cmd = ["tmux", "new-session", "-d", "-s", session_name]
        if cwd is not None:
            cmd.extend(["-c", cwd])
        if command:
            cmd.extend(command)

        base_env = dict(os.environ)
        if env:
            base_env.update(env)

        result = self._run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            env=build_interactive_terminal_env(base_env=base_env),
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to create tmux session {session_name}: {result.stderr or result.stdout}"
            )
        return True

    def has_session(self, session_name: str) -> bool:
        """Return True when the named tmux session exists."""

        return self._has_session(session_name)

    def list_sessions(self) -> list[str]:
        result = self._run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line.strip()]

    def terminate_session(self, session_name: str) -> bool:
        result = self._run(
            ["tmux", "kill-session", "-t", session_name],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0

    def send_keys(self, session_name: str, text: str) -> bool:
        result = self._run(
            ["tmux", "send-keys", "-t", session_name, "-l", text, "Enter"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0

    def cleanup_orphans(self, *, active_session_names: set[str]) -> list[str]:
        removed: list[str] = []
        for session_name in self.list_sessions():
            if not session_name.startswith("mc-int-"):
                continue
            if session_name in active_session_names:
                continue
            if self.terminate_session(session_name):
                removed.append(session_name)
        return removed

    def _has_session(self, session_name: str) -> bool:
        result = self._run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
