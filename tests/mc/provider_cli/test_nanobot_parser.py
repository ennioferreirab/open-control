"""Tests for the Nanobot runtime-owned provider CLI parser."""

from __future__ import annotations

import signal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from mc.contexts.provider_cli.parser import ProviderCLIParser
from mc.contexts.provider_cli.providers.nanobot import NanobotCLIParser
from mc.contexts.provider_cli.types import (
    ParsedCliEvent,
    ProviderProcessHandle,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_handle(mc_session_id: str = "mc-session-123") -> ProviderProcessHandle:
    return ProviderProcessHandle(
        mc_session_id=mc_session_id,
        provider="mc",
        pid=12345,
        pgid=12345,
        cwd="/tmp/agents/my-agent",
        command=["python", "-m", "mc.runtime.nanobot_interactive_session"],
        started_at=datetime.now(timezone.utc).isoformat(),
    )


def _make_supervisor() -> MagicMock:
    sup = MagicMock()
    sup.launch = AsyncMock()
    sup.inspect_process_tree = AsyncMock()
    sup.send_signal = AsyncMock()
    sup.terminate = AsyncMock()
    return sup


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


def test_nanobot_parser_satisfies_protocol() -> None:
    parser = NanobotCLIParser()
    assert isinstance(parser, ProviderCLIParser)


def test_provider_name_is_mc() -> None:
    parser = NanobotCLIParser()
    assert parser.provider_name == "mc"


# ---------------------------------------------------------------------------
# start_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_session_delegates_to_supervisor() -> None:
    sup = _make_supervisor()
    sup.launch.return_value = _make_handle()
    parser = NanobotCLIParser(supervisor=sup)

    handle = await parser.start_session(
        mc_session_id="mc-session-123",
        command=["python", "-m", "mc.runtime.nanobot_interactive_session"],
        cwd="/tmp/agents/my-agent",
        env={"MC_INTERACTIVE_SESSION_ID": "mc-session-123"},
    )

    sup.launch.assert_awaited_once_with(
        mc_session_id="mc-session-123",
        provider="mc",
        command=["python", "-m", "mc.runtime.nanobot_interactive_session"],
        cwd="/tmp/agents/my-agent",
        env={"MC_INTERACTIVE_SESSION_ID": "mc-session-123"},
    )
    assert handle.provider == "mc"


# ---------------------------------------------------------------------------
# discover_session — runtime-owned mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_session_returns_runtime_owned_mode() -> None:
    parser = NanobotCLIParser()
    snapshot = await parser.discover_session(_make_handle())
    assert snapshot.mode == "runtime-owned"


@pytest.mark.asyncio
async def test_discover_session_supports_resume_is_false() -> None:
    parser = NanobotCLIParser()
    snapshot = await parser.discover_session(_make_handle())
    assert snapshot.supports_resume is False


@pytest.mark.asyncio
async def test_discover_session_supports_interrupt_is_true() -> None:
    parser = NanobotCLIParser()
    snapshot = await parser.discover_session(_make_handle())
    assert snapshot.supports_interrupt is True


@pytest.mark.asyncio
async def test_discover_session_supports_stop_is_true() -> None:
    parser = NanobotCLIParser()
    snapshot = await parser.discover_session(_make_handle())
    assert snapshot.supports_stop is True


@pytest.mark.asyncio
async def test_discover_session_uses_mc_session_id_as_fallback() -> None:
    parser = NanobotCLIParser()
    snapshot = await parser.discover_session(_make_handle("mc-session-abc"))
    assert snapshot.provider_session_id == "mc-session-abc"


@pytest.mark.asyncio
async def test_discover_session_uses_extracted_session_key() -> None:
    parser = NanobotCLIParser()
    parser.parse_output(b"MC_INTERACTIVE_SESSION_ID=mc:session-key-001\n")
    snapshot = await parser.discover_session(_make_handle("mc-session-xyz"))
    assert snapshot.provider_session_id == "mc:session-key-001"


# ---------------------------------------------------------------------------
# parse_output
# ---------------------------------------------------------------------------


def test_parse_output_returns_parsed_cli_events() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(b"Hello from Nanobot\n")
    assert isinstance(events, list)
    for e in events:
        assert isinstance(e, ParsedCliEvent)


def test_parse_output_session_key_extraction() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(b"MC_INTERACTIVE_SESSION_ID=mc:abc-123\n")
    discovered = [e for e in events if e.kind == "session_discovered"]
    assert len(discovered) == 1
    assert discovered[0].provider_session_id == "mc:abc-123"
    assert discovered[0].metadata.get("session_key") == "mc:abc-123"


def test_parse_output_session_ready() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(b"[nanobot-live] Session ready. Type /exit to close Live.\n")
    assert any(e.kind == "session_ready" for e in events)


def test_parse_output_turn_started() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(b"[nanobot-live] Nanobot interactive turn started.\n")
    assert any(e.kind == "turn_started" for e in events)


def test_parse_output_turn_completed() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(b"[nanobot-live] Nanobot interactive turn completed.\n")
    assert any(e.kind == "turn_completed" for e in events)


def test_parse_output_session_stopped() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(b"[nanobot-live] Nanobot Live session ended.\n")
    assert any(e.kind == "session_stopped" for e in events)


def test_parse_output_progress_lines() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(b"[progress] Running analysis...\n")
    output_events = [e for e in events if e.kind == "output"]
    assert any(e.metadata.get("source") == "progress" for e in output_events)
    assert any("Running analysis" in (e.text or "") for e in output_events)


def test_parse_output_tool_lines() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(b"[tool] Executing shell command\n")
    output_events = [e for e in events if e.kind == "output"]
    assert any(e.metadata.get("source") == "tool" for e in output_events)


def test_parse_output_subagent_spawned() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(b"Spawning subagent for task-456\n")
    assert any(e.kind == "subagent_spawned" for e in events)


def test_parse_output_generic_lines_become_output() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(b"Some generic nanobot output\n")
    assert all(e.kind == "output" for e in events)


def test_parse_output_error_traceback() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(b"Traceback (most recent call last):\n")
    assert any(e.kind == "error" for e in events)


def test_parse_output_attaches_session_id_after_discovery() -> None:
    parser = NanobotCLIParser()
    parser.parse_output(b"MC_INTERACTIVE_SESSION_ID=mc:key-007\n")
    events = parser.parse_output(b"[progress] Working...\n")
    for e in events:
        assert e.provider_session_id == "mc:key-007"


def test_parse_output_empty_returns_empty() -> None:
    parser = NanobotCLIParser()
    assert parser.parse_output(b"") == []


def test_parse_output_multiple_lines() -> None:
    parser = NanobotCLIParser()
    events = parser.parse_output(b"[progress] Step 1\n[progress] Step 2\n[progress] Step 3\n")
    assert len(events) == 3
    for e in events:
        assert e.kind == "output"
        assert e.metadata.get("source") == "progress"


# ---------------------------------------------------------------------------
# interrupt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_interrupt_sends_sigint_via_supervisor() -> None:
    sup = _make_supervisor()
    parser = NanobotCLIParser(supervisor=sup)
    handle = _make_handle()
    await parser.interrupt(handle)
    sup.send_signal.assert_awaited_once_with(handle, signal.SIGINT)


# ---------------------------------------------------------------------------
# resume — not supported
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_raises_not_implemented_error() -> None:
    parser = NanobotCLIParser()
    with pytest.raises(NotImplementedError, match="runtime-owned"):
        await parser.resume(_make_handle(), "Continue with plan B")


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_calls_supervisor_terminate() -> None:
    sup = _make_supervisor()
    parser = NanobotCLIParser(supervisor=sup)
    handle = _make_handle()
    await parser.stop(handle)
    sup.terminate.assert_awaited_once_with(handle)


# ---------------------------------------------------------------------------
# inspect_process_tree
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inspect_process_tree_delegates_to_supervisor() -> None:
    sup = _make_supervisor()
    sup.inspect_process_tree.return_value = {
        "pid": 12345,
        "pgid": 12345,
        "children": [],
    }
    parser = NanobotCLIParser(supervisor=sup)
    handle = _make_handle()
    result = await parser.inspect_process_tree(handle)
    sup.inspect_process_tree.assert_awaited_once_with(handle)
    assert result["pid"] == 12345
