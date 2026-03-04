"""
Tests for ClaudeCodeProvider (mc/cc_provider.py).

Coverage:
- _build_command: model, budget, turns, tools, permission mode, session resume
- _parse_stream: valid NDJSON, malformed lines, empty lines
- _handle_message: result extraction, session_id capture, on_stream callback,
                   string content branch
- execute_task: non-zero exit code, process cancellation
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.cc_provider import ClaudeCodeProvider
from mc.types import AgentData, CCTaskResult, ClaudeCodeOpts, WorkspaceContext


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_agent(
    model: str | None = None,
    cc_opts: ClaudeCodeOpts | None = None,
    backend: str = "claude-code",
) -> AgentData:
    return AgentData(
        name="test-agent",
        display_name="Test Agent",
        role="worker",
        model=model,
        backend=backend,
        claude_code_opts=cc_opts,
    )


def _make_workspace(tmp_path: Path) -> WorkspaceContext:
    mcp_config = tmp_path / ".mcp.json"
    mcp_config.write_text("{}")
    return WorkspaceContext(
        cwd=tmp_path,
        mcp_config=mcp_config,
        claude_md=tmp_path / "CLAUDE.md",
        socket_path=f"/tmp/mc-test-agent.sock",
    )


class _FakeDefaults:
    """Minimal stand-in for ClaudeCodeConfig."""
    default_model = "claude-sonnet-4-6"
    default_max_budget_usd = 5.0
    default_max_turns = 50
    default_permission_mode = "acceptEdits"


# ---------------------------------------------------------------------------
# _build_command
# ---------------------------------------------------------------------------

class TestBuildCommand:
    def test_minimal_command_structure(self, tmp_path):
        """Command always includes -p, --output-format, --cwd, --mcp-config."""
        provider = ClaudeCodeProvider()
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("hello", agent, ctx, None)

        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "hello" in cmd
        assert "--output-format" in cmd
        assert "stream-json" in cmd
        assert "--cwd" in cmd
        assert str(tmp_path) in cmd
        assert "--mcp-config" in cmd
        assert str(ctx.mcp_config) in cmd

    def test_model_from_agent_config(self, tmp_path):
        """Per-agent model is added as --model flag."""
        provider = ClaudeCodeProvider()
        agent = _make_agent(model="claude-opus-4-6")
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("x", agent, ctx, None)

        idx = cmd.index("--model")
        assert cmd[idx + 1] == "claude-opus-4-6"

    def test_model_from_defaults_when_no_agent_model(self, tmp_path):
        """Falls back to defaults.default_model when agent.model is None."""
        provider = ClaudeCodeProvider(defaults=_FakeDefaults())
        agent = _make_agent(model=None)
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("x", agent, ctx, None)

        idx = cmd.index("--model")
        assert cmd[idx + 1] == "claude-sonnet-4-6"

    def test_no_model_flag_when_no_model_anywhere(self, tmp_path):
        """If neither agent nor defaults provide a model, --model is omitted."""
        provider = ClaudeCodeProvider()
        agent = _make_agent(model=None)
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("x", agent, ctx, None)

        assert "--model" not in cmd

    def test_budget_from_agent_opts(self, tmp_path):
        """Per-agent max_budget_usd is used when set."""
        provider = ClaudeCodeProvider(defaults=_FakeDefaults())
        cc = ClaudeCodeOpts(max_budget_usd=2.5)
        agent = _make_agent(cc_opts=cc)
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("x", agent, ctx, None)

        idx = cmd.index("--max-budget-usd")
        assert cmd[idx + 1] == "2.5"

    def test_budget_from_defaults(self, tmp_path):
        """Falls back to defaults.default_max_budget_usd when agent has none."""
        provider = ClaudeCodeProvider(defaults=_FakeDefaults())
        agent = _make_agent()  # no cc_opts
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("x", agent, ctx, None)

        idx = cmd.index("--max-budget-usd")
        assert cmd[idx + 1] == "5.0"

    def test_turns_from_agent_opts(self, tmp_path):
        """Per-agent max_turns is used when set."""
        provider = ClaudeCodeProvider(defaults=_FakeDefaults())
        cc = ClaudeCodeOpts(max_turns=10)
        agent = _make_agent(cc_opts=cc)
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("x", agent, ctx, None)

        idx = cmd.index("--max-turns")
        assert cmd[idx + 1] == "10"

    def test_turns_from_defaults(self, tmp_path):
        """Falls back to defaults.default_max_turns when agent has none."""
        provider = ClaudeCodeProvider(defaults=_FakeDefaults())
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("x", agent, ctx, None)

        idx = cmd.index("--max-turns")
        assert cmd[idx + 1] == "50"

    def test_allowed_tools_one_flag_per_tool(self, tmp_path):
        """Each allowed tool gets its own --allowedTools flag."""
        provider = ClaudeCodeProvider()
        cc = ClaudeCodeOpts(allowed_tools=["Read", "Glob"])
        agent = _make_agent(cc_opts=cc)
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("x", agent, ctx, None)

        # Collect all values following --allowedTools flags
        allowed: list[str] = []
        for i, tok in enumerate(cmd):
            if tok == "--allowedTools" and i + 1 < len(cmd):
                allowed.append(cmd[i + 1])

        assert "Read" in allowed
        assert "Glob" in allowed
        assert "mcp__nanobot__*" in allowed  # always injected

    def test_nanobot_mcp_tool_always_added(self, tmp_path):
        """mcp__nanobot__* is always added even with no agent allowed_tools."""
        provider = ClaudeCodeProvider()
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("x", agent, ctx, None)

        # Find --allowedTools values
        allowed = [cmd[i + 1] for i, t in enumerate(cmd) if t == "--allowedTools"]
        assert "mcp__nanobot__*" in allowed

    def test_disallowed_tools(self, tmp_path):
        """Disallowed tools are forwarded with --disallowedTools."""
        provider = ClaudeCodeProvider()
        cc = ClaudeCodeOpts(disallowed_tools=["Write"])
        agent = _make_agent(cc_opts=cc)
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("x", agent, ctx, None)

        idx = cmd.index("--disallowedTools")
        assert cmd[idx + 1] == "Write"

    def test_session_resume_flag(self, tmp_path):
        """--resume flag is added when session_id is provided."""
        provider = ClaudeCodeProvider()
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("x", agent, ctx, "sess-abc123")

        idx = cmd.index("--resume")
        assert cmd[idx + 1] == "sess-abc123"

    def test_no_resume_when_session_id_none(self, tmp_path):
        """--resume is omitted when session_id is None."""
        provider = ClaudeCodeProvider()
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("x", agent, ctx, None)

        assert "--resume" not in cmd

    def test_permission_mode_from_defaults(self, tmp_path):
        """permission_mode defaults to 'acceptEdits' via _FakeDefaults."""
        provider = ClaudeCodeProvider(defaults=_FakeDefaults())
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("x", agent, ctx, None)

        idx = cmd.index("--permission-mode")
        assert cmd[idx + 1] == "acceptEdits"

    def test_permission_mode_from_agent_opts(self, tmp_path):
        """Per-agent permission_mode overrides the default."""
        provider = ClaudeCodeProvider(defaults=_FakeDefaults())
        cc = ClaudeCodeOpts(permission_mode="bypassPermissions")
        agent = _make_agent(cc_opts=cc)
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("x", agent, ctx, None)

        idx = cmd.index("--permission-mode")
        assert cmd[idx + 1] == "bypassPermissions"


# ---------------------------------------------------------------------------
# _parse_stream
# ---------------------------------------------------------------------------

class TestParseStream:
    """Test the NDJSON stream parser."""

    async def _collect(self, lines: list[bytes]) -> list[dict]:
        """Helper: create a fake proc, feed lines, collect parsed dicts."""
        provider = ClaudeCodeProvider()

        # Build a fake stdout that yields the lines
        async def _fake_iter():
            for line in lines:
                yield line

        fake_proc = MagicMock()
        fake_proc.stdout = _fake_iter()

        results = []
        async for msg in provider._parse_stream(fake_proc):
            results.append(msg)
        return results

    @pytest.mark.asyncio
    async def test_valid_ndjson(self):
        """Parses valid JSON lines correctly."""
        lines = [
            b'{"type":"result","result":"done"}\n',
            b'{"type":"assistant","message":{}}\n',
        ]
        msgs = await self._collect(lines)
        assert len(msgs) == 2
        assert msgs[0]["type"] == "result"
        assert msgs[1]["type"] == "assistant"

    @pytest.mark.asyncio
    async def test_empty_lines_skipped(self):
        """Empty and whitespace-only lines are silently skipped."""
        lines = [b"\n", b"   \n", b'{"type":"result"}\n']
        msgs = await self._collect(lines)
        assert len(msgs) == 1
        assert msgs[0]["type"] == "result"

    @pytest.mark.asyncio
    async def test_malformed_json_skipped_with_warning(self, caplog):
        """Malformed JSON lines are skipped (with a warning)."""
        lines = [b"not-json\n", b'{"type":"result"}\n']
        with caplog.at_level(logging.WARNING, logger="mc.cc_provider"):
            msgs = await self._collect(lines)
        assert len(msgs) == 1
        assert "malformed" in caplog.text.lower() or "Malformed" in caplog.text


# ---------------------------------------------------------------------------
# _handle_message / result extraction
# ---------------------------------------------------------------------------

class TestHandleMessage:
    def test_result_message_extracts_fields(self):
        """type=result populates all CCTaskResult fields."""
        provider = ClaudeCodeProvider()
        result = CCTaskResult(output="", session_id="", cost_usd=0.0, usage={}, is_error=False)
        msg = {
            "type": "result",
            "result": "Task complete",
            "is_error": False,
            "cost_usd": 1.23,
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "session_id": "sess-xyz",
        }
        provider._handle_message(msg, result, None)

        assert result.output == "Task complete"
        assert result.is_error is False
        assert result.cost_usd == 1.23
        assert result.usage == {"input_tokens": 100, "output_tokens": 50}
        assert result.session_id == "sess-xyz"

    def test_result_message_uses_total_cost_usd_field(self):
        """total_cost_usd (spec field name) is preferred over cost_usd."""
        provider = ClaudeCodeProvider()
        result = CCTaskResult(output="", session_id="", cost_usd=0.0, usage={}, is_error=False)
        msg = {
            "type": "result",
            "result": "done",
            "is_error": False,
            "total_cost_usd": 2.50,
        }
        provider._handle_message(msg, result, None)
        assert result.cost_usd == 2.50

    def test_result_message_uses_nested_cost_object(self):
        """Nested cost.total_cost_usd fallback is handled."""
        provider = ClaudeCodeProvider()
        result = CCTaskResult(output="", session_id="", cost_usd=0.0, usage={}, is_error=False)
        msg = {
            "type": "result",
            "result": "done",
            "is_error": False,
            "cost": {"total_cost_usd": 3.75},
        }
        provider._handle_message(msg, result, None)
        assert result.cost_usd == 3.75

    def test_result_message_marks_error(self):
        """type=result with is_error=True marks result.is_error."""
        provider = ClaudeCodeProvider()
        result = CCTaskResult(output="", session_id="", cost_usd=0.0, usage={}, is_error=False)
        msg = {"type": "result", "result": "oops", "is_error": True}
        provider._handle_message(msg, result, None)
        assert result.is_error is True

    def test_session_id_captured_from_any_message(self):
        """session_id is captured from any message type that carries it."""
        provider = ClaudeCodeProvider()
        result = CCTaskResult(output="", session_id="", cost_usd=0.0, usage={}, is_error=False)
        msg = {"type": "system", "session_id": "sess-early"}
        provider._handle_message(msg, result, None)
        assert result.session_id == "sess-early"

    def test_session_id_last_wins(self):
        """Later messages overwrite earlier session_id (last-wins behavior)."""
        provider = ClaudeCodeProvider()
        result = CCTaskResult(output="", session_id="first", cost_usd=0.0, usage={}, is_error=False)
        msg = {"type": "system", "session_id": "second"}
        provider._handle_message(msg, result, None)
        assert result.session_id == "second"

    def test_on_stream_called_with_normalized_text_block(self):
        """on_stream receives normalized {'type': 'text', 'text': ...} dict."""
        provider = ClaudeCodeProvider()
        result = CCTaskResult(output="", session_id="", cost_usd=0.0, usage={}, is_error=False)
        received: list[dict] = []

        msg = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "tool_use", "name": "Bash", "input": {}},
                ]
            },
        }
        provider._handle_message(msg, result, received.append)

        assert len(received) == 2
        assert received[0] == {"type": "text", "text": "Hello"}
        assert received[1] == {"type": "tool_use", "name": "Bash"}

    def test_on_stream_called_with_normalized_tool_use_block(self):
        """on_stream receives normalized {'type': 'tool_use', 'name': ...} dict."""
        provider = ClaudeCodeProvider()
        result = CCTaskResult(output="", session_id="", cost_usd=0.0, usage={}, is_error=False)
        received: list[dict] = []

        msg = {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"path": "/f"}}]},
        }
        provider._handle_message(msg, result, received.append)

        assert len(received) == 1
        assert received[0] == {"type": "tool_use", "name": "Read"}

    def test_on_stream_not_called_when_none(self):
        """No error when on_stream is None for assistant messages."""
        provider = ClaudeCodeProvider()
        result = CCTaskResult(output="", session_id="", cost_usd=0.0, usage={}, is_error=False)
        msg = {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "hi"}]},
        }
        # Should not raise
        provider._handle_message(msg, result, None)

    def test_on_stream_called_for_string_content(self):
        """String content (non-list) is wrapped in a text event for on_stream."""
        provider = ClaudeCodeProvider()
        result = CCTaskResult(output="", session_id="", cost_usd=0.0, usage={}, is_error=False)
        received: list[dict] = []

        msg = {
            "type": "assistant",
            "message": {"content": "plain text string"},
        }
        provider._handle_message(msg, result, received.append)

        assert len(received) == 1
        assert received[0] == {"type": "text", "text": "plain text string"}

    def test_on_stream_not_called_for_empty_string_content(self):
        """Empty string content does NOT trigger on_stream callback."""
        provider = ClaudeCodeProvider()
        result = CCTaskResult(output="", session_id="", cost_usd=0.0, usage={}, is_error=False)
        received: list[dict] = []

        msg = {
            "type": "assistant",
            "message": {"content": ""},
        }
        provider._handle_message(msg, result, received.append)

        assert len(received) == 0

    def test_unknown_message_type_is_ignored(self):
        """Unknown message types do not cause errors."""
        provider = ClaudeCodeProvider()
        result = CCTaskResult(output="", session_id="", cost_usd=0.0, usage={}, is_error=False)
        provider._handle_message({"type": "unknown_future_type", "data": "x"}, result, None)
        assert result.output == ""
        assert result.is_error is False


# ---------------------------------------------------------------------------
# execute_task integration
# ---------------------------------------------------------------------------

class TestExecuteTask:
    """Integration-level tests using mock subprocess."""

    def _make_mock_proc(self, ndjson_lines: list[str], returncode: int = 0) -> MagicMock:
        """Build a mock asyncio.subprocess.Process."""
        async def _stdout_iter():
            for line in ndjson_lines:
                yield (line + "\n").encode()

        async def _read_stderr():
            return b""

        proc = MagicMock()
        proc.stdout = _stdout_iter()
        proc.stderr = AsyncMock()
        proc.stderr.read = _read_stderr
        proc.wait = AsyncMock(return_value=returncode)
        proc.send_signal = MagicMock()
        proc.kill = MagicMock()
        return proc

    @pytest.mark.asyncio
    async def test_successful_execution(self, tmp_path):
        """execute_task returns correct result on success."""
        lines = [
            json.dumps({
                "type": "result",
                "result": "All done",
                "is_error": False,
                "cost_usd": 0.5,
                "usage": {"input_tokens": 10},
                "session_id": "sess-1",
            })
        ]
        proc = self._make_mock_proc(lines, returncode=0)

        provider = ClaudeCodeProvider()
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await provider.execute_task(
                "do stuff", agent, "task-1", ctx
            )

        assert result.output == "All done"
        assert result.is_error is False
        assert result.cost_usd == 0.5
        assert result.session_id == "sess-1"

    @pytest.mark.asyncio
    async def test_nonzero_exit_sets_is_error(self, tmp_path):
        """Non-zero exit with no output sets is_error=True and uses stderr."""
        async def _read_stderr():
            return b"Something went wrong"

        proc = self._make_mock_proc([], returncode=1)
        proc.stderr.read = _read_stderr

        provider = ClaudeCodeProvider()
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await provider.execute_task("oops", agent, "task-2", ctx)

        assert result.is_error is True
        assert "Something went wrong" in result.output

    @pytest.mark.asyncio
    async def test_nonzero_exit_does_not_override_existing_output(self, tmp_path):
        """If output was captured before non-zero exit, is_error stays False."""
        lines = [
            json.dumps({
                "type": "result",
                "result": "partial output",
                "is_error": False,
                "cost_usd": 0.0,
                "usage": {},
                "session_id": "",
            })
        ]

        async def _read_stderr():
            return b"exit error"

        proc = self._make_mock_proc(lines, returncode=1)
        proc.stderr.read = _read_stderr

        provider = ClaudeCodeProvider()
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await provider.execute_task("x", agent, "task-3", ctx)

        # Output was set, so is_error remains as-set by the result message
        assert result.output == "partial output"

    @pytest.mark.asyncio
    async def test_on_stream_callback_invoked(self, tmp_path):
        """on_stream is called for each content block in assistant messages."""
        lines = [
            json.dumps({
                "type": "assistant",
                "message": {
                    "content": [{"type": "text", "text": "thinking..."}]
                },
            }),
            json.dumps({
                "type": "result",
                "result": "done",
                "is_error": False,
                "cost_usd": 0.0,
                "usage": {},
                "session_id": "",
            }),
        ]
        proc = self._make_mock_proc(lines)

        received: list[dict] = []
        provider = ClaudeCodeProvider()
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await provider.execute_task("x", agent, "task-4", ctx, on_stream=received.append)

        assert len(received) == 1
        assert received[0]["text"] == "thinking..."

    @pytest.mark.asyncio
    async def test_session_resume_passed_to_command(self, tmp_path):
        """session_id is forwarded as --resume in the CLI command."""
        proc = self._make_mock_proc([])

        provider = ClaudeCodeProvider()
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)

        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await provider.execute_task(
                "x", agent, "task-5", ctx, session_id="sess-resume"
            )

        call_args = mock_exec.call_args[0]
        cmd = list(call_args)
        idx = cmd.index("--resume")
        assert cmd[idx + 1] == "sess-resume"

    @pytest.mark.asyncio
    async def test_cancellation_kills_process(self, tmp_path):
        """CancelledError causes the process to be killed via _kill_process."""
        # Make stdout hang forever so we can cancel
        async def _hanging_stdout():
            await asyncio.sleep(9999)
            # Unreachable but makes this a proper async generator
            yield b""

        proc = MagicMock()
        proc.stdout = _hanging_stdout()
        proc.stderr = AsyncMock()
        proc.stderr.read = AsyncMock(return_value=b"")
        proc.wait = AsyncMock(return_value=0)
        proc.send_signal = MagicMock()
        proc.kill = MagicMock()

        provider = ClaudeCodeProvider()
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            with patch.object(provider, "_kill_process", new_callable=AsyncMock) as mock_kill:
                with pytest.raises(asyncio.CancelledError):
                    task = asyncio.create_task(
                        provider.execute_task("x", agent, "task-cancel", ctx)
                    )
                    await asyncio.sleep(0)  # let the coroutine start
                    task.cancel()
                    await task

                mock_kill.assert_called_once_with(proc)
