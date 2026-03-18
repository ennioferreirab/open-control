"""Tests for the Nanobot runtime-owned provider CLI parser."""

from __future__ import annotations

import signal
from unittest.mock import patch

import pytest

from mc.contexts.provider_cli.providers.nanobot import NanobotCLIParser
from mc.contexts.provider_cli.types import (
    ProviderProcessHandle,
)


def _make_handle(*, pid: int = 11111, pgid: int = 11110) -> ProviderProcessHandle:
    return ProviderProcessHandle(
        mc_session_id="mc-session-1",
        provider="nanobot",
        pid=pid,
        pgid=pgid,
        cwd="/tmp",
        command=["nanobot", "run"],
        started_at="2026-03-14T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Type/protocol contract
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# discover_session: runtime-owned metadata
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_session_returns_runtime_owned_snapshot() -> None:
    parser = NanobotCLIParser()
    handle = _make_handle()
    snap = await parser.discover_session(handle)
    assert snap.mode == "runtime-owned"
    assert snap.supports_resume is False
    assert snap.supports_interrupt is True
    assert snap.supports_stop is True
    assert snap.mc_session_id == "mc-session-1"
    assert snap.provider_session_id is None


# ---------------------------------------------------------------------------
# parse_output: plain-text and structured events
# ---------------------------------------------------------------------------


def test_parse_output_plain_text_produces_output_event() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(b"Some progress text")
    assert len(events) == 1
    assert events[0].kind == "output"
    assert events[0].text == "Some progress text"


def test_parse_output_progress_prefix() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(b"[progress] Working...")
    assert len(events) == 1
    assert events[0].kind == "progress"


def test_parse_output_tool_prefix() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(b"[tool] Running shell command")
    assert len(events) == 1
    assert events[0].kind == "tool"


def test_parse_output_session_ready() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(b"[nanobot-live] Session ready. Type /exit to close Live.")
    assert len(events) == 1
    assert events[0].kind == "session_ready"


def test_parse_output_session_failed() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(b"[nanobot-live] RuntimeError: exploded")
    assert len(events) == 1
    assert events[0].kind == "session_failed"


def test_parse_output_empty_returns_empty() -> None:
    parser = NanobotCLIParser()
    assert parser.parse_output(b"") == []


def test_parse_output_whitespace_only_returns_empty() -> None:
    parser = NanobotCLIParser()
    assert parser.parse_output(b"   \n   ") == []


# ---------------------------------------------------------------------------
# interrupt: SIGINT on process group
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_interrupt_sends_sigint_to_process_group() -> None:
    parser = NanobotCLIParser()
    handle = _make_handle(pid=11111, pgid=11110)
    with patch("os.killpg") as mock_killpg:
        await parser.interrupt(handle)
        mock_killpg.assert_called_once_with(11110, signal.SIGINT)


@pytest.mark.asyncio
async def test_interrupt_falls_back_to_pid_when_pgid_is_zero() -> None:
    parser = NanobotCLIParser()
    handle = _make_handle(pid=22222, pgid=0)
    with patch("os.kill") as mock_kill:
        await parser.interrupt(handle)
        mock_kill.assert_called_once_with(22222, signal.SIGINT)


# ---------------------------------------------------------------------------
# stop: SIGTERM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_sends_sigterm_to_process_group() -> None:
    parser = NanobotCLIParser()
    handle = _make_handle(pid=33333, pgid=33332)
    with patch("os.killpg") as mock_killpg:
        await parser.stop(handle)
        mock_killpg.assert_called_once_with(33332, signal.SIGTERM)


@pytest.mark.asyncio
async def test_stop_falls_back_to_pid_when_pgid_is_zero() -> None:
    parser = NanobotCLIParser()
    handle = _make_handle(pid=44444, pgid=0)
    with patch("os.kill") as mock_kill:
        await parser.stop(handle)
        mock_kill.assert_called_once_with(44444, signal.SIGTERM)


# ---------------------------------------------------------------------------
# resume: not supported
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_raises_not_supported_error() -> None:
    parser = NanobotCLIParser()
    handle = _make_handle()
    with pytest.raises(NotImplementedError, match="runtime-owned"):
        await parser.resume(handle, "some message")
