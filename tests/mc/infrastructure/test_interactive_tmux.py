from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, call

from mc.infrastructure.interactive.tmux import TmuxSessionManager


def _completed(
    args: list[str], returncode: int = 0, stdout: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout)


def test_ensure_session_creates_detached_tmux_session_when_missing() -> None:
    runner = MagicMock(
        side_effect=[
            _completed(["tmux", "has-session", "-t", "mc-int-123"], returncode=1),
            _completed(
                [
                    "tmux",
                    "new-session",
                    "-d",
                    "-s",
                    "mc-int-123",
                    "-c",
                    "/tmp/workspace",
                    "claude",
                ]
            ),
        ]
    )
    manager = TmuxSessionManager(run=runner)

    created = manager.ensure_session(
        "mc-int-123",
        cwd="/tmp/workspace",
        command=["claude"],
    )

    assert created is True
    assert runner.call_args_list[0] == call(
        ["tmux", "has-session", "-t", "mc-int-123"],
        capture_output=True,
        text=True,
        check=False,
    )
    args, kwargs = runner.call_args_list[1]
    assert args == (
        [
            "tmux",
            "new-session",
            "-d",
            "-s",
            "mc-int-123",
            "-c",
            "/tmp/workspace",
            "claude",
        ],
    )
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["check"] is False
    assert kwargs["env"]["TERM"] == "xterm-256color"
    assert kwargs["env"]["COLORTERM"] == "truecolor"


def test_ensure_session_merges_provider_env_with_terminal_env() -> None:
    runner = MagicMock(
        side_effect=[
            _completed(["tmux", "has-session", "-t", "mc-int-123"], returncode=1),
            _completed(["tmux", "new-session", "-d", "-s", "mc-int-123"]),
        ]
    )
    manager = TmuxSessionManager(run=runner)

    manager.ensure_session("mc-int-123", command=["codex"], env={"CODEX_HOME": "/tmp/codex-home"})

    _, kwargs = runner.call_args_list[1]
    assert kwargs["env"]["TERM"] == "xterm-256color"
    assert kwargs["env"]["CODEX_HOME"] == "/tmp/codex-home"


def test_ensure_session_reuses_existing_tmux_session() -> None:
    runner = MagicMock(
        side_effect=[_completed(["tmux", "has-session", "-t", "mc-int-123"], returncode=0)]
    )
    manager = TmuxSessionManager(run=runner)

    created = manager.ensure_session("mc-int-123", cwd="/tmp/workspace", command=["claude"])

    assert created is False
    assert runner.call_count == 1


def test_list_sessions_returns_session_names() -> None:
    runner = MagicMock(
        return_value=_completed(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            stdout="mc-int-123\nmc-int-456\n",
        )
    )
    manager = TmuxSessionManager(run=runner)

    sessions = manager.list_sessions()

    assert sessions == ["mc-int-123", "mc-int-456"]


def test_cleanup_orphans_kills_only_untracked_interactive_sessions() -> None:
    runner = MagicMock(
        side_effect=[
            _completed(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                stdout="mc-int-123\nmc-int-456\nother-session\n",
            ),
            _completed(["tmux", "kill-session", "-t", "mc-int-456"]),
        ]
    )
    manager = TmuxSessionManager(run=runner)

    removed = manager.cleanup_orphans(active_session_names={"mc-int-123"})

    assert removed == ["mc-int-456"]
    assert runner.call_args_list[-1] == call(
        ["tmux", "kill-session", "-t", "mc-int-456"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_terminate_session_is_best_effort() -> None:
    runner = MagicMock(
        return_value=_completed(["tmux", "kill-session", "-t", "mc-int-123"], returncode=1)
    )
    manager = TmuxSessionManager(run=runner)

    removed = manager.terminate_session("mc-int-123")

    assert removed is False
    runner.assert_called_once_with(
        ["tmux", "kill-session", "-t", "mc-int-123"],
        capture_output=True,
        text=True,
        check=False,
    )
