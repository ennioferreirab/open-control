"""PTY helpers for attaching browser clients to tmux-backed sessions."""

from __future__ import annotations

import fcntl
import os
import struct
import subprocess
import termios
from dataclasses import dataclass

from mc.infrastructure.interactive.terminal_env import build_interactive_terminal_env


@dataclass(frozen=True)
class TerminalSize:
    """Terminal dimensions in character cells."""

    columns: int
    rows: int


@dataclass
class AttachedTerminal:
    """PTY-backed tmux attachment owned by the interactive runtime."""

    master_fd: int
    process: subprocess.Popen[bytes]

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
        os.close(self.master_fd)


def resize_terminal(fd: int, size: TerminalSize) -> None:
    """Resize a PTY file descriptor."""

    fcntl.ioctl(
        fd,
        termios.TIOCSWINSZ,
        struct.pack("HHHH", size.rows, size.columns, 0, 0),
    )


def spawn_tmux_attach_pty(
    session_name: str,
    *,
    size: TerminalSize,
) -> AttachedTerminal:
    """Attach to an existing tmux session through a fresh PTY."""

    master_fd, slave_fd = os.openpty()
    resize_terminal(slave_fd, size)
    process = subprocess.Popen(
        ["tmux", "attach-session", "-t", session_name],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        start_new_session=True,
        env=build_interactive_terminal_env(),
    )
    os.close(slave_fd)
    return AttachedTerminal(master_fd=master_fd, process=process)
