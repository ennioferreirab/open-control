from __future__ import annotations

import struct
import termios
from unittest.mock import MagicMock

from mc.infrastructure.interactive.pty import (
    AttachedTerminal,
    TerminalSize,
    resize_terminal,
    spawn_tmux_attach_pty,
)


def test_spawn_tmux_attach_pty_opens_a_reconnectable_terminal(monkeypatch) -> None:
    popen = MagicMock()
    monkeypatch.setattr("mc.infrastructure.interactive.pty.os.openpty", lambda: (10, 11))
    monkeypatch.setattr("mc.infrastructure.interactive.pty.os.close", MagicMock())
    resize = MagicMock()
    monkeypatch.setattr("mc.infrastructure.interactive.pty.resize_terminal", resize)
    popen_factory = MagicMock(return_value=popen)
    monkeypatch.setattr("mc.infrastructure.interactive.pty.subprocess.Popen", popen_factory)

    attached = spawn_tmux_attach_pty("mc-int-123", size=TerminalSize(columns=120, rows=40))

    assert attached.master_fd == 10
    assert attached.process is popen
    resize.assert_called_once_with(11, TerminalSize(columns=120, rows=40))
    popen_factory.assert_called_once()
    _, kwargs = popen_factory.call_args
    assert popen_factory.call_args.args == (["tmux", "attach-session", "-t", "mc-int-123"],)
    assert kwargs["stdin"] == 11
    assert kwargs["stdout"] == 11
    assert kwargs["stderr"] == 11
    assert kwargs["close_fds"] is True
    assert kwargs["start_new_session"] is True
    assert kwargs["env"]["TERM"] == "xterm-256color"
    assert kwargs["env"]["COLORTERM"] == "truecolor"


def test_resize_terminal_updates_pty_window_size(monkeypatch) -> None:
    ioctl = MagicMock()
    monkeypatch.setattr("mc.infrastructure.interactive.pty.fcntl.ioctl", ioctl)

    resize_terminal(10, TerminalSize(columns=120, rows=40))

    ioctl.assert_called_once_with(
        10,
        termios.TIOCSWINSZ,
        struct.pack("HHHH", 40, 120, 0, 0),
    )


def test_attached_terminal_close_terminates_process_and_closes_master_fd(monkeypatch) -> None:
    close_fd = MagicMock()
    monkeypatch.setattr("mc.infrastructure.interactive.pty.os.close", close_fd)
    process = MagicMock()
    process.poll.return_value = None
    attached = AttachedTerminal(master_fd=10, process=process)

    attached.close()

    process.terminate.assert_called_once_with()
    close_fd.assert_called_once_with(10)
