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


def _jsonl(data: dict | str) -> bytes:
    """Encode a dict or string as a JSONL line (JSON + trailing newline)."""
    if isinstance(data, dict):
        return (json.dumps(data) + "\n").encode()
    return (data + "\n").encode()


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
    )
    events = parser.parse_output(_jsonl(line))
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
    )
    events = parser.parse_output(_jsonl(line))
    sid_events = [e for e in events if e.kind == "session_id"]
    assert sid_events
    assert sid_events[0].provider_session_id == "abc-123-session"


def test_parse_output_returns_result_event_for_result_message() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps({"type": "result", "subtype": "success", "result": "Task complete"})
    events = parser.parse_output(_jsonl(line))
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
    )
    events = parser.parse_output(_jsonl(line))
    tool_events = [e for e in events if e.kind == "tool_use"]
    assert tool_events
    assert "Bash" in tool_events[0].text


def test_parse_output_returns_ask_user_requested_for_nanobot_mcp_tool() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tu_ask_001",
                        "name": "mcp__nanobot__ask_user",
                        "input": {"question": "What does Easy do?"},
                    }
                ],
                "role": "assistant",
            },
        }
    )
    events = parser.parse_output(_jsonl(line))
    ask_events = [e for e in events if e.kind == "ask_user_requested"]
    assert ask_events
    assert "What does Easy do?" in (ask_events[0].text or "")


def test_parse_output_handles_plain_text_line() -> None:
    parser = ClaudeCodeCLIParser()
    events = parser.parse_output(b"Some plain text output from Claude\n")
    text_events = [e for e in events if e.kind == "text"]
    assert text_events
    assert "Some plain text output from Claude" in text_events[0].text


def test_parse_output_returns_error_event_for_error_result() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps({"type": "result", "subtype": "error_max_turns"})
    events = parser.parse_output(_jsonl(line))
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
    events = parser.parse_output(b'{"type": "broken\n')
    assert len(events) == 1
    assert events[0].kind == "text"


def test_parse_output_buffers_partial_json_without_newline() -> None:
    """A JSON fragment without trailing newline is buffered, not emitted."""
    parser = ClaudeCodeCLIParser()
    events = parser.parse_output(b'{"type": "broken')
    assert events == [], "Partial line without newline should be buffered"


def test_parse_output_emits_hook_response_as_system_event() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps(
        {
            "type": "system",
            "subtype": "hook_response",
            "hook_name": "SessionStart:startup",
            "hook_event": "SessionStart",
            "output": '{"hookSpecificOutput": {"additionalContext": "huge"}}',
        }
    )
    events = parser.parse_output(_jsonl(line))
    assert len(events) == 1
    assert events[0].kind == "system_event"
    assert "SessionStart:startup" in (events[0].text or "")
    meta = events[0].metadata or {}
    assert meta["source_type"] == "system"
    assert meta["source_subtype"] == "hook_response"


def test_parse_output_ignores_user_tool_result_messages() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps(
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_123",
                        "content": "verbose output that should stay internal",
                    }
                ],
            },
        }
    )
    events = parser.parse_output(_jsonl(line))
    assert events == []


def test_parse_output_ignores_thinking_only_assistant_messages() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps(
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "thinking", "thinking": "internal reasoning"}],
            },
        }
    )
    events = parser.parse_output(_jsonl(line))
    assert events == []


# ---------------------------------------------------------------------------
# Session ID discovery
# ---------------------------------------------------------------------------


def test_session_id_discovery_updates_internal_state() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps({"type": "system", "subtype": "init", "session_id": "sess-xyz-789"})
    parser.parse_output(_jsonl(line))
    assert parser.discovered_session_id == "sess-xyz-789"


def test_session_id_not_overwritten_by_non_init_messages() -> None:
    parser = ClaudeCodeCLIParser()
    init = json.dumps({"type": "system", "subtype": "init", "session_id": "original-sid"})
    parser.parse_output(_jsonl(init))

    other = json.dumps(
        {
            "type": "assistant",
            "message": {"content": [], "role": "assistant"},
        }
    )
    parser.parse_output(_jsonl(other))

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
    init = json.dumps({"type": "system", "subtype": "init", "session_id": "disco-id-001"})
    parser.parse_output(_jsonl(init))
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
    assert supervisor.launch.call_args.kwargs["stdin_mode"] == "devnull"
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
    assert call_kwargs["stdin_mode"] == "devnull"
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


# ---------------------------------------------------------------------------
# Canonical Live metadata (Story 2.1)
# ---------------------------------------------------------------------------


def test_system_init_emits_canonical_metadata() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps({"type": "system", "subtype": "init", "session_id": "sid-001"})
    events = parser.parse_output(_jsonl(line))
    sid_events = [e for e in events if e.kind == "session_id"]
    assert sid_events
    meta = sid_events[0].metadata or {}
    assert meta["source_type"] == "system"
    assert meta["source_subtype"] == "init"


def test_assistant_text_emits_canonical_metadata() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps(
        {
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "Hello"}],
                "role": "assistant",
            },
        }
    )
    events = parser.parse_output(_jsonl(line))
    text_events = [e for e in events if e.kind == "text"]
    assert text_events
    meta = text_events[0].metadata or {}
    assert meta["source_type"] == "assistant"
    assert meta["source_subtype"] == "text"


def test_tool_use_emits_canonical_metadata() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tu_001",
                        "name": "Read",
                        "input": {"path": "/tmp/file.txt"},
                    }
                ],
                "role": "assistant",
            },
        }
    )
    events = parser.parse_output(_jsonl(line))
    tool_events = [e for e in events if e.kind == "tool_use"]
    assert tool_events
    meta = tool_events[0].metadata or {}
    assert meta["source_type"] == "tool_use"
    assert meta["source_subtype"] == "Read"


def test_result_success_emits_canonical_metadata() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps({"type": "result", "subtype": "success", "result": "Done"})
    events = parser.parse_output(_jsonl(line))
    result_events = [e for e in events if e.kind == "result"]
    assert result_events
    meta = result_events[0].metadata or {}
    assert meta["source_type"] == "result"
    assert meta["source_subtype"] == "success"


def test_result_error_emits_canonical_metadata() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps({"type": "result", "subtype": "error_max_turns"})
    events = parser.parse_output(_jsonl(line))
    error_events = [e for e in events if e.kind == "error"]
    assert error_events
    meta = error_events[0].metadata or {}
    assert meta["source_type"] == "result"
    assert meta["source_subtype"] == "error"


def test_ask_user_emits_canonical_metadata() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tu_ask",
                        "name": "mcp__mc__ask_user",
                        "input": {"question": "Proceed?"},
                    }
                ],
                "role": "assistant",
            },
        }
    )
    events = parser.parse_output(_jsonl(line))
    ask_events = [e for e in events if e.kind == "ask_user_requested"]
    assert ask_events
    meta = ask_events[0].metadata or {}
    assert meta["source_type"] == "tool_use"
    assert meta["source_subtype"] == "ask_user"


def test_truncate_large_values_preserves_structure() -> None:
    """Large string values in raw_json are truncated per-key, keeping JSON valid."""
    from mc.contexts.provider_cli.providers.claude_code import _truncate_large_values

    data = {
        "type": "system",
        "short": "ok",
        "huge": "x" * 20000,
        "nested": {"also_huge": "y" * 20000, "small": "fine"},
        "list": ["z" * 20000, "short"],
    }
    result = _truncate_large_values(data, max_len=100)

    assert result["type"] == "system"
    assert result["short"] == "ok"
    assert len(result["huge"]) < 200
    assert "truncated" in result["huge"]
    assert "20000 chars" in result["huge"]
    assert len(result["nested"]["also_huge"]) < 200
    assert result["nested"]["small"] == "fine"
    assert len(result["list"][0]) < 200
    assert result["list"][1] == "short"

    # Result must be valid JSON
    serialized = json.dumps(result)
    json.loads(serialized)


def test_unknown_type_emits_source_type_in_metadata() -> None:
    parser = ClaudeCodeCLIParser()
    line = json.dumps({"type": "future_type", "data": "something"})
    events = parser.parse_output(_jsonl(line))
    assert events
    meta = events[0].metadata or {}
    assert meta["source_type"] == "future_type"


# ---------------------------------------------------------------------------
# Line buffering — JSON split across TCP chunks
# ---------------------------------------------------------------------------


def test_parse_output_buffers_incomplete_json_across_chunks() -> None:
    """A single large JSON line split across two chunks should produce one event."""
    parser = ClaudeCodeCLIParser()
    # Build a realistic large assistant message (>200 chars) that would be
    # split across TCP chunks in practice.
    full_json = json.dumps(
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "This is a longer response from the assistant that exceeds "
                        "the minimum buffer threshold to simulate a real TCP chunk split "
                        "scenario in production.",
                    }
                ],
            },
        }
    )
    assert len(full_json) > 200, "Test data must exceed buffer threshold"
    mid = len(full_json) // 2

    # First chunk: partial JSON, no newline
    chunk1 = full_json[:mid].encode()
    events1 = parser.parse_output(chunk1)
    assert events1 == [], "Partial JSON should not produce events yet"

    # Second chunk: rest of JSON + newline
    chunk2 = (full_json[mid:] + "\n").encode()
    events2 = parser.parse_output(chunk2)
    text_events = [e for e in events2 if e.kind == "text"]
    assert len(text_events) == 1
    assert "longer response" in (text_events[0].text or "")


def test_parse_output_buffers_multiple_partial_chunks() -> None:
    """Large JSON split across three chunks should still produce one event."""
    parser = ClaudeCodeCLIParser()
    full_json = json.dumps(
        {
            "type": "system",
            "subtype": "init",
            "session_id": "abc-123",
            "tools": [
                {"name": "Read", "description": "Read a file from disk"},
                {"name": "Write", "description": "Write a file to disk"},
                {"name": "Bash", "description": "Run a shell command"},
                {"name": "Grep", "description": "Search file contents"},
            ],
        }
    )
    assert len(full_json) > 200, "Test data must exceed buffer threshold"
    third = len(full_json) // 3

    events1 = parser.parse_output(full_json[:third].encode())
    assert events1 == []

    events2 = parser.parse_output(full_json[third : 2 * third].encode())
    assert events2 == []

    events3 = parser.parse_output((full_json[2 * third :] + "\n").encode())
    sid_events = [e for e in events3 if e.kind == "session_id"]
    assert len(sid_events) == 1
    assert sid_events[0].provider_session_id == "abc-123"


def test_parse_output_complete_lines_not_buffered() -> None:
    """Lines ending with newline are parsed immediately, not buffered."""
    parser = ClaudeCodeCLIParser()
    line = json.dumps({"type": "result", "subtype": "success", "result": "OK"}) + "\n"
    events = parser.parse_output(line.encode())
    assert len([e for e in events if e.kind == "result"]) == 1


def test_parse_output_mixed_complete_and_partial() -> None:
    """A chunk with a complete line + partial line: complete parsed, partial buffered."""
    parser = ClaudeCodeCLIParser()
    complete = json.dumps({"type": "result", "subtype": "success", "result": "First"})
    partial_start = '{"type": "assistant", "message": {"content": [{"type": "text"'

    chunk1 = (complete + "\n" + partial_start).encode()
    events1 = parser.parse_output(chunk1)
    assert len([e for e in events1 if e.kind == "result"]) == 1

    # Finish the partial line
    partial_end = ', "text": "Hello"}]}}\n'
    events2 = parser.parse_output(partial_end.encode())
    text_events = [e for e in events2 if e.kind == "text"]
    assert len(text_events) == 1
    assert "Hello" in (text_events[0].text or "")
