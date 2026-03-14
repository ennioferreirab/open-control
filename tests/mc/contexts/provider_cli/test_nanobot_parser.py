"""Tests for the Nanobot runtime-owned provider CLI parser."""

from __future__ import annotations

import signal
from unittest.mock import patch

import pytest

from mc.contexts.provider_cli.parser import ProviderCLIParser
from mc.contexts.provider_cli.providers.nanobot import NanobotCLIParser
from mc.contexts.provider_cli.types import (
    ParsedCliEvent,
    ProviderProcessHandle,
    ProviderSessionSnapshot,
)

# ---------------------------------------------------------------------------
# Type/protocol contract
# ---------------------------------------------------------------------------


def test_nanobot_parser_implements_provider_cli_parser_protocol() -> None:
    """NanobotCLIParser satisfies the ProviderCLIParser structural protocol."""
    parser = NanobotCLIParser()
    assert isinstance(parser, ProviderCLIParser)


def test_parsed_cli_event_carries_required_fields() -> None:
    event = ParsedCliEvent(kind="output", content="hello", session_key="sk-1")
    assert event.kind == "output"
    assert event.content == "hello"
    assert event.session_key == "sk-1"
    assert event.metadata == {}


def test_parsed_cli_event_metadata_defaults_to_empty_dict() -> None:
    event = ParsedCliEvent(kind="turn_started", content="", session_key="sk-1")
    assert event.metadata == {}


def test_provider_process_handle_carries_pid_and_pgid() -> None:
    handle = ProviderProcessHandle(pid=12345, pgid=12344, session_key="sk-1")
    assert handle.pid == 12345
    assert handle.pgid == 12344
    assert handle.session_key == "sk-1"


def test_provider_session_snapshot_runtime_owned_mode() -> None:
    snap = ProviderSessionSnapshot(
        session_key="sk-1",
        mode="runtime-owned",
        supports_resume=False,
        provider="mc",
    )
    assert snap.mode == "runtime-owned"
    assert snap.supports_resume is False
    assert snap.provider == "mc"
    assert snap.provider_session_id is None


# ---------------------------------------------------------------------------
# discover_session: runtime-owned metadata
# ---------------------------------------------------------------------------


def test_discover_session_returns_runtime_owned_snapshot() -> None:
    parser = NanobotCLIParser()
    snap = parser.discover_session(session_key="sk-abc")
    assert snap.mode == "runtime-owned"
    assert snap.supports_resume is False
    assert snap.provider == "mc"
    assert snap.session_key == "sk-abc"
    assert snap.provider_session_id is None


def test_discover_session_passes_subagent_metadata_when_provided() -> None:
    subagent_meta = {"subagent_id": "sub-1", "child_pid": 9999}
    parser = NanobotCLIParser()
    snap = parser.discover_session(session_key="sk-abc", subagent_metadata=subagent_meta)
    assert snap.metadata.get("subagent_id") == "sub-1"
    assert snap.metadata.get("child_pid") == 9999


# ---------------------------------------------------------------------------
# parse_output: plain-text and structured events
# ---------------------------------------------------------------------------


def test_parse_output_plain_text_line_produces_output_event() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output("Some progress text", session_key="sk-1")
    assert len(events) == 1
    assert events[0].kind == "output"
    assert events[0].content == "Some progress text"
    assert events[0].session_key == "sk-1"


def test_parse_output_progress_prefix_produces_progress_event() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output("[progress] Working...", session_key="sk-1")
    assert len(events) == 1
    assert events[0].kind == "progress"


def test_parse_output_tool_prefix_produces_tool_event() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output("[tool] Running shell command", session_key="sk-1")
    assert len(events) == 1
    assert events[0].kind == "tool"


def test_parse_output_session_ready_produces_session_ready_event() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(
        "[nanobot-live] Session ready. Type /exit to close Live.", session_key="sk-1"
    )
    assert len(events) == 1
    assert events[0].kind == "session_ready"


def test_parse_output_session_failed_produces_session_failed_event() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output("[nanobot-live] RuntimeError: exploded", session_key="sk-1")
    assert len(events) == 1
    assert events[0].kind == "session_failed"


def test_parse_output_empty_string_returns_empty_list() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output("", session_key="sk-1")
    assert events == []


def test_parse_output_whitespace_only_returns_empty_list() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output("   \n   ", session_key="sk-1")
    assert events == []


# ---------------------------------------------------------------------------
# interrupt: maps to SIGINT on process group
# ---------------------------------------------------------------------------


def test_interrupt_sends_sigint_to_process_group() -> None:
    parser = NanobotCLIParser()
    handle = ProviderProcessHandle(pid=11111, pgid=11110, session_key="sk-1")
    with patch("os.killpg") as mock_killpg:
        parser.interrupt(handle)
        mock_killpg.assert_called_once_with(11110, signal.SIGINT)


def test_interrupt_falls_back_to_pid_when_pgid_is_zero() -> None:
    """When pgid is 0 (unknown), fall back to interrupting the pid directly."""
    parser = NanobotCLIParser()
    handle = ProviderProcessHandle(pid=22222, pgid=0, session_key="sk-1")
    with patch("os.kill") as mock_kill:
        parser.interrupt(handle)
        mock_kill.assert_called_once_with(22222, signal.SIGINT)


# ---------------------------------------------------------------------------
# stop: sends SIGTERM
# ---------------------------------------------------------------------------


def test_stop_sends_sigterm_to_process_group() -> None:
    parser = NanobotCLIParser()
    handle = ProviderProcessHandle(pid=33333, pgid=33332, session_key="sk-1")
    with patch("os.killpg") as mock_killpg:
        parser.stop(handle)
        mock_killpg.assert_called_once_with(33332, signal.SIGTERM)


def test_stop_falls_back_to_pid_when_pgid_is_zero() -> None:
    parser = NanobotCLIParser()
    handle = ProviderProcessHandle(pid=44444, pgid=0, session_key="sk-1")
    with patch("os.kill") as mock_kill:
        parser.stop(handle)
        mock_kill.assert_called_once_with(44444, signal.SIGTERM)


# ---------------------------------------------------------------------------
# resume: not supported for runtime-owned sessions
# ---------------------------------------------------------------------------


def test_resume_raises_not_supported_error() -> None:
    parser = NanobotCLIParser()
    handle = ProviderProcessHandle(pid=55555, pgid=55554, session_key="sk-1")
    with pytest.raises(NotImplementedError, match="runtime-owned"):
        parser.resume(handle, resume_id=None)


# ---------------------------------------------------------------------------
# Session continuity: uses MC-owned session_key, not a provider resume id
# ---------------------------------------------------------------------------


def test_snapshot_has_no_provider_native_session_id() -> None:
    """Nanobot uses MC-owned continuity - no external provider session id."""
    parser = NanobotCLIParser()
    snap = parser.discover_session(session_key="sk-continuity-test")
    assert snap.provider_session_id is None


def test_snapshot_mode_is_runtime_owned_not_provider_native() -> None:
    parser = NanobotCLIParser()
    snap = parser.discover_session(session_key="sk-continuity-test")
    assert snap.mode == "runtime-owned"
    assert snap.mode != "provider-native"
