"""Tests for CodexCLIParser."""

from __future__ import annotations

import signal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mc.contexts.provider_cli.parser import ProviderCLIParser
from mc.contexts.provider_cli.providers.codex import CodexCLIParser
from mc.contexts.provider_cli.types import (
    ParsedCliEvent,
    ProviderProcessHandle,
    ProviderSessionSnapshot,
)


def _make_handle(
    mc_session_id: str = "mc-session-1",
    pid: int = 12345,
    pgid: int = 12345,
) -> ProviderProcessHandle:
    return ProviderProcessHandle(
        mc_session_id=mc_session_id,
        provider="codex",
        pid=pid,
        pgid=pgid,
        cwd="/tmp/agent-workspace",
        command=["codex", "--sandbox", "workspace-write"],
        started_at="2024-01-01T00:00:00Z",
    )


def _make_supervisor() -> MagicMock:
    supervisor = MagicMock()
    supervisor.launch = AsyncMock()
    supervisor.send_signal = AsyncMock()
    supervisor.terminate = AsyncMock()
    supervisor.kill = AsyncMock()
    supervisor.inspect_process_tree = AsyncMock(return_value={"pid": 12345, "children": []})
    return supervisor


class TestCodexCLIParserProtocol:
    def test_parser_is_instance_of_protocol(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        assert isinstance(parser, ProviderCLIParser)

    def test_provider_name_is_codex(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        assert parser.provider_name == "codex"

    def test_has_all_required_protocol_methods(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        assert hasattr(parser, "provider_name")
        assert callable(parser.parse_output)
        assert callable(parser.start_session)
        assert callable(parser.discover_session)
        assert callable(parser.inspect_process_tree)
        assert callable(parser.interrupt)
        assert callable(parser.resume)
        assert callable(parser.stop)


class TestCodexCLIParserStartSession:
    @pytest.mark.asyncio
    async def test_start_session_delegates_to_supervisor(self) -> None:
        supervisor = _make_supervisor()
        expected_handle = _make_handle()
        supervisor.launch.return_value = expected_handle

        parser = CodexCLIParser(supervisor=supervisor)
        handle = await parser.start_session(
            mc_session_id="mc-session-1",
            command=["codex", "--sandbox", "workspace-write"],
            cwd="/tmp/agent-workspace",
        )

        supervisor.launch.assert_awaited_once_with(
            mc_session_id="mc-session-1",
            provider="codex",
            command=["codex", "--sandbox", "workspace-write"],
            cwd="/tmp/agent-workspace",
            env=None,
        )
        assert handle is expected_handle

    @pytest.mark.asyncio
    async def test_start_session_passes_env(self) -> None:
        supervisor = _make_supervisor()
        supervisor.launch.return_value = _make_handle()

        parser = CodexCLIParser(supervisor=supervisor)
        await parser.start_session(
            mc_session_id="mc-session-1",
            command=["codex"],
            cwd="/tmp",
            env={"MY_VAR": "value"},
        )

        supervisor.launch.assert_awaited_once()
        call_kwargs = supervisor.launch.call_args.kwargs
        assert call_kwargs["env"] == {"MY_VAR": "value"}


class TestCodexCLIParserParseOutput:
    def test_plain_text_returns_output_event(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        events = parser.parse_output(b"Hello, how can I help?\n")
        output_events = [e for e in events if e.kind == "output"]
        assert len(output_events) == 1
        assert "Hello, how can I help?" in (output_events[0].text or "")

    def test_returns_list_of_parsed_cli_events(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        events = parser.parse_output(b"some output text")
        assert isinstance(events, list)
        assert all(isinstance(e, ParsedCliEvent) for e in events)

    def test_empty_bytes_returns_empty_list(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        assert parser.parse_output(b"") == []

    def test_detects_session_id(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        events = parser.parse_output(b"Session: abc-123-def-456\nStarting task...\n")
        session_events = [e for e in events if e.kind == "session_discovered"]
        assert len(session_events) >= 1
        assert session_events[0].provider_session_id == "abc-123-def-456"

    def test_detects_approval_request(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        events = parser.parse_output(b"Approval required: execute shell command `ls -la`\n")
        approval_events = [e for e in events if e.kind == "approval_requested"]
        assert len(approval_events) >= 1

    def test_detects_error_output(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        events = parser.parse_output(b"Error: something went wrong\n")
        assert len(events) >= 1
        kinds = {e.kind for e in events}
        assert kinds & {"output", "error"}

    def test_handles_multiline_output(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        events = parser.parse_output(b"Line 1\nLine 2\nLine 3\n")
        output_events = [e for e in events if e.kind == "output"]
        assert len(output_events) == 3


class TestCodexCLIParserDiscoverSession:
    @pytest.mark.asyncio
    async def test_returns_provider_session_snapshot(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        snapshot = await parser.discover_session(_make_handle())
        assert isinstance(snapshot, ProviderSessionSnapshot)

    @pytest.mark.asyncio
    async def test_preserves_mc_session_id(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        snapshot = await parser.discover_session(_make_handle(mc_session_id="my-session-42"))
        assert snapshot.mc_session_id == "my-session-42"

    @pytest.mark.asyncio
    async def test_mode_is_provider_native(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        snapshot = await parser.discover_session(_make_handle())
        assert snapshot.mode == "provider-native"

    @pytest.mark.asyncio
    async def test_uses_cached_session_id(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        parser.parse_output(b"Session: provider-session-xyz\n")
        snapshot = await parser.discover_session(_make_handle())
        assert snapshot.provider_session_id == "provider-session-xyz"

    @pytest.mark.asyncio
    async def test_provider_session_id_none_before_discovery(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        snapshot = await parser.discover_session(_make_handle())
        assert snapshot.provider_session_id is None


class TestCodexCLIParserCapabilities:
    @pytest.mark.asyncio
    async def test_supports_resume(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        snapshot = await parser.discover_session(_make_handle())
        assert snapshot.supports_resume is True

    @pytest.mark.asyncio
    async def test_supports_interrupt(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        snapshot = await parser.discover_session(_make_handle())
        assert snapshot.supports_interrupt is True

    @pytest.mark.asyncio
    async def test_supports_stop(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        snapshot = await parser.discover_session(_make_handle())
        assert snapshot.supports_stop is True


class TestCodexCLIParserInterrupt:
    @pytest.mark.asyncio
    async def test_sends_sigint_via_supervisor(self) -> None:
        supervisor = _make_supervisor()
        parser = CodexCLIParser(supervisor=supervisor)
        handle = _make_handle()
        await parser.interrupt(handle)
        supervisor.send_signal.assert_awaited_once_with(handle, signal.SIGINT)


class TestCodexCLIParserStop:
    @pytest.mark.asyncio
    async def test_delegates_to_supervisor_terminate(self) -> None:
        supervisor = _make_supervisor()
        parser = CodexCLIParser(supervisor=supervisor)
        handle = _make_handle()
        await parser.stop(handle)
        supervisor.terminate.assert_awaited_once_with(handle)


class TestCodexCLIParserResume:
    @pytest.mark.asyncio
    async def test_resume_is_awaitable(self) -> None:
        parser = CodexCLIParser(supervisor=_make_supervisor())
        await parser.resume(_make_handle(), "continue please")


class TestCodexCLIParserInspectProcessTree:
    @pytest.mark.asyncio
    async def test_delegates_to_supervisor(self) -> None:
        supervisor = _make_supervisor()
        expected: dict[str, Any] = {"pid": 12345, "pgid": 12345, "children": []}
        supervisor.inspect_process_tree.return_value = expected

        parser = CodexCLIParser(supervisor=supervisor)
        handle = _make_handle()
        result = await parser.inspect_process_tree(handle)

        supervisor.inspect_process_tree.assert_awaited_once_with(handle)
        assert result == expected
