"""Tests for the Claude Code provider CLI parser."""

from __future__ import annotations

import json
import signal
from unittest.mock import AsyncMock, MagicMock

import pytest

from mc.contexts.provider_cli.parser import ProviderCLIParser
from mc.contexts.provider_cli.providers.claude_code import ClaudeCodeCLIParser
from mc.contexts.provider_cli.types import (
    ProviderProcessHandle,
    ProviderSessionSnapshot,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_handle(
    mc_session_id: str = "mc-session-001",
    pid: int = 12345,
    pgid: int = 12344,
) -> ProviderProcessHandle:
    return ProviderProcessHandle(
        mc_session_id=mc_session_id,
        provider="claude-code",
        pid=pid,
        pgid=pgid,
        cwd="/tmp/workspace",
        command=["claude", "--output-format", "stream-json"],
        started_at="2024-01-01T00:00:00Z",
    )


def _make_supervisor() -> MagicMock:
    sup = MagicMock()
    sup.launch = AsyncMock()
    sup.stream_output = AsyncMock()
    sup.wait_for_exit = AsyncMock()
    sup.send_signal = AsyncMock()
    sup.terminate = AsyncMock()
    sup.kill = AsyncMock()
    sup.inspect_process_tree = AsyncMock(return_value={"pid": 12345, "children": []})
    return sup


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_claude_code_parser_satisfies_provider_cli_parser_protocol() -> None:
    parser = ClaudeCodeCLIParser()
    assert isinstance(parser, ProviderCLIParser)


# ---------------------------------------------------------------------------
# provider_name
# ---------------------------------------------------------------------------


def test_provider_name_is_claude_code() -> None:
    parser = ClaudeCodeCLIParser()
    assert parser.provider_name == "claude-code"


# ---------------------------------------------------------------------------
# parse_output — JSONL structured output
# ---------------------------------------------------------------------------


def test_parse_output_returns_text_event_for_assistant_message() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps(
        {
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "Hello from Claude"}],
                "role": "assistant",
            },
        }
    ).encode()
    events = parser.parse_output(line)
    text_events = [e for e in events if e.kind == "text"]
    assert text_events
    assert "Hello from Claude" in text_events[0].text


def test_parse_output_returns_session_id_event_for_system_init() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps(
        {
            "type": "system",
            "subtype": "init",
            "session_id": "abc-123-session",
        }
    ).encode()
    events = parser.parse_output(line)
    sid_events = [e for e in events if e.kind == "session_id"]
    assert sid_events
    assert sid_events[0].provider_session_id == "abc-123-session"


def test_parse_output_returns_result_event_for_result_message() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps({"type": "result", "subtype": "success", "result": "Task complete"}).encode()
    events = parser.parse_output(line)
    result_events = [e for e in events if e.kind == "result"]
    assert result_events
    assert "Task complete" in result_events[0].text


def test_parse_output_returns_tool_use_event() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tu_001",
                        "name": "Bash",
                        "input": {"command": "ls -la"},
                    }
                ],
                "role": "assistant",
            },
        }
    ).encode()
    events = parser.parse_output(line)
    tool_events = [e for e in events if e.kind == "tool_use"]
    assert tool_events
    assert "Bash" in tool_events[0].text


def test_parse_output_handles_plain_text_line() -> None:
    parser = ClaudeCodeCLIParser()
    events = parser.parse_output(b"Some plain text output from Claude")
    text_events = [e for e in events if e.kind == "text"]
    assert text_events
    assert "Some plain text output from Claude" in text_events[0].text


def test_parse_output_returns_error_event_for_error_result() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps({"type": "result", "subtype": "error_max_turns"}).encode()
    events = parser.parse_output(line)
    error_events = [e for e in events if e.kind == "error"]
    assert error_events


def test_parse_output_returns_empty_list_for_empty_input() -> None:
    parser = ClaudeCodeCLIParser()
    assert parser.parse_output(b"") == []


def test_parse_output_returns_empty_list_for_whitespace() -> None:
    parser = ClaudeCodeCLIParser()
    assert parser.parse_output(b"   \n  ") == []


def test_parse_output_handles_malformed_json() -> None:
    parser = ClaudeCodeCLIParser()
    events = parser.parse_output(b'{"type": "broken')
    assert len(events) == 1
    assert events[0].kind == "text"


# ---------------------------------------------------------------------------
# Session ID discovery
# ---------------------------------------------------------------------------


def test_session_id_discovery_updates_internal_state() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps({"type": "system", "subtype": "init", "session_id": "sess-xyz-789"}).encode()
    parser.parse_output(line)
    assert parser.discovered_session_id == "sess-xyz-789"


def test_session_id_not_overwritten_by_non_init_messages() -> None:
    parser = ClaudeCodeCLIParser()
    init = json.dumps({"type": "system", "subtype": "init", "session_id": "original-sid"}).encode()
    parser.parse_output(init)

    other = json.dumps(
        {
            "type": "assistant",
            "message": {"content": [], "role": "assistant"},
        }
    ).encode()
    parser.parse_output(other)

    assert parser.discovered_session_id == "original-sid"


# ---------------------------------------------------------------------------
# discover_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_session_returns_provider_native_snapshot() -> None:
    parser = ClaudeCodeCLIParser()
    handle = _make_handle()
    snapshot = await parser.discover_session(handle)
    assert isinstance(snapshot, ProviderSessionSnapshot)
    assert snapshot.mc_session_id == handle.mc_session_id
    assert snapshot.mode == "provider-native"


@pytest.mark.asyncio
async def test_discover_session_includes_discovered_session_id() -> None:
    parser = ClaudeCodeCLIParser()
    init = json.dumps({"type": "system", "subtype": "init", "session_id": "disco-id-001"}).encode()
    parser.parse_output(init)
    snapshot = await parser.discover_session(_make_handle())
    assert snapshot.provider_session_id == "disco-id-001"


@pytest.mark.asyncio
async def test_discover_session_provider_session_id_none_before_discovery() -> None:
    parser = ClaudeCodeCLIParser()
    snapshot = await parser.discover_session(_make_handle())
    assert snapshot.provider_session_id is None


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_supports_resume() -> None:
    parser = ClaudeCodeCLIParser()
    snapshot = await parser.discover_session(_make_handle())
    assert snapshot.supports_resume is True


@pytest.mark.asyncio
async def test_supports_interrupt() -> None:
    parser = ClaudeCodeCLIParser()
    snapshot = await parser.discover_session(_make_handle())
    assert snapshot.supports_interrupt is True


@pytest.mark.asyncio
async def test_supports_stop() -> None:
    parser = ClaudeCodeCLIParser()
    snapshot = await parser.discover_session(_make_handle())
    assert snapshot.supports_stop is True


# ---------------------------------------------------------------------------
# inspect_process_tree
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inspect_process_tree_delegates_to_supervisor() -> None:
    supervisor = _make_supervisor()
    expected_tree = {"pid": 12345, "children": [{"pid": 12346}]}
    supervisor.inspect_process_tree.return_value = expected_tree

    parser = ClaudeCodeCLIParser(supervisor=supervisor)
    handle = _make_handle()
    result = await parser.inspect_process_tree(handle)

    supervisor.inspect_process_tree.assert_awaited_once_with(handle)
    assert result == expected_tree


# ---------------------------------------------------------------------------
# interrupt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_interrupt_sends_sigint_via_supervisor() -> None:
    supervisor = _make_supervisor()
    parser = ClaudeCodeCLIParser(supervisor=supervisor)
    handle = _make_handle()
    await parser.interrupt(handle)
    supervisor.send_signal.assert_awaited_once_with(handle, signal.SIGINT)


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_sends_sigterm_via_supervisor() -> None:
    supervisor = _make_supervisor()
    parser = ClaudeCodeCLIParser(supervisor=supervisor)
    handle = _make_handle()
    await parser.stop(handle)
    supervisor.terminate.assert_awaited_once_with(handle)


# ---------------------------------------------------------------------------
# start_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_session_launches_via_supervisor() -> None:
    supervisor = _make_supervisor()
    mock_handle = _make_handle()
    supervisor.launch.return_value = mock_handle

    parser = ClaudeCodeCLIParser(supervisor=supervisor)
    result = await parser.start_session(
        mc_session_id="mc-session-001",
        command=["claude", "--output-format", "stream-json"],
        cwd="/tmp/workspace",
    )

    supervisor.launch.assert_awaited_once()
    assert result == mock_handle


# ---------------------------------------------------------------------------
# resume
# ---------------------------------------------------------------------------


def test_resume_builds_command_with_resume_flag() -> None:
    parser = ClaudeCodeCLIParser()
    cmd = parser.resume(
        mc_session_id="mc-001",
        provider_session_id="sess-abc",
        command_prefix=["claude", "--output-format", "stream-json"],
        cwd="/tmp/workspace",
    )
    assert cmd == [
        "claude",
        "--output-format",
        "stream-json",
        "--resume",
        "sess-abc",
    ]


# ---------------------------------------------------------------------------
# start_session delegation (Story 28-9)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_session_passes_command_to_supervisor() -> None:
    """start_session must delegate the full command to supervisor.launch()."""
    supervisor = _make_supervisor()
    mock_handle = _make_handle()
    supervisor.launch.return_value = mock_handle

    parser = ClaudeCodeCLIParser(supervisor=supervisor)
    command = ["claude", "--output-format", "stream-json", "--print", "--prompt", "Do the work"]
    result = await parser.start_session(
        mc_session_id="mc-session-prompt",
        command=command,
        cwd="/tmp/workspace",
    )

    call_kwargs = supervisor.launch.call_args.kwargs
    assert call_kwargs["command"] == command
    assert call_kwargs["mc_session_id"] == "mc-session-prompt"
    assert call_kwargs["cwd"] == "/tmp/workspace"
    assert result == mock_handle


@pytest.mark.asyncio
async def test_start_session_includes_bootstrap_prompt_in_command() -> None:
    """The bootstrap prompt passed in the command must reach the supervisor unchanged."""
    supervisor = _make_supervisor()
    mock_handle = _make_handle()
    supervisor.launch.return_value = mock_handle

    parser = ClaudeCodeCLIParser(supervisor=supervisor)
    bootstrap_prompt = "Bootstrap: implement the authentication module."
    command = ["claude", "--output-format", "stream-json", "--print", "--prompt", bootstrap_prompt]

    await parser.start_session(
        mc_session_id="mc-bootstrap-test",
        command=command,
        cwd="/tmp/workspace",
    )

    call_kwargs = supervisor.launch.call_args.kwargs
    launched_command = call_kwargs["command"]
    assert "--prompt" in launched_command
    prompt_idx = launched_command.index("--prompt")
    assert launched_command[prompt_idx + 1] == bootstrap_prompt
