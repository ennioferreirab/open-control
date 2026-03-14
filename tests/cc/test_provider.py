"""
Tests for ClaudeCodeProvider (claude_code/provider.py).

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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from claude_code.provider import ClaudeCodeProvider
from claude_code.types import CCTaskResult, ClaudeCodeOpts, WorkspaceContext

from mc.types import AgentData

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
        socket_path="/tmp/mc-test-agent.sock",
    )


def _write_nanobot_config(home: Path, data: dict) -> None:
    config_path = home / ".nanobot" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(data), encoding="utf-8")


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
        """Command always includes -p, --output-format, --mcp-config (cwd via subprocess)."""
        provider = ClaudeCodeProvider()
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("hello", agent, ctx, None)

        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "hello" in cmd
        assert "--output-format" in cmd
        assert "stream-json" in cmd
        assert "--cwd" not in cmd  # cwd is set via subprocess cwd= param, not CLI flag
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
        assert "mcp__mc__*" in allowed  # always injected

    def test_mc_mcp_tool_always_added(self, tmp_path):
        """mcp__mc__* is always added even with no agent allowed_tools."""
        provider = ClaudeCodeProvider()
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("x", agent, ctx, None)

        # Find --allowedTools values
        allowed = [cmd[i + 1] for i, t in enumerate(cmd) if t == "--allowedTools"]
        assert "mcp__mc__*" in allowed

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

    def test_cc_prefix_stripped_from_model(self, tmp_path):
        """Model with cc/ prefix should have the prefix stripped."""
        provider = ClaudeCodeProvider()
        agent = _make_agent(model="cc/claude-sonnet-4-6")
        ctx = _make_workspace(tmp_path)
        cmd = provider._build_command("hello", agent, ctx, None)
        model_idx = cmd.index("--model")
        assert cmd[model_idx + 1] == "claude-sonnet-4-6"

    def test_unknown_model_warns(self, tmp_path, caplog):
        """Unknown model emits a warning but command is still built."""
        provider = ClaudeCodeProvider()
        agent = _make_agent(model="claude-opus-6")
        ctx = _make_workspace(tmp_path)
        with caplog.at_level(logging.WARNING, logger="claude_code.provider"):
            cmd = provider._build_command("x", agent, ctx, None)
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "claude-opus-6"
        assert "claude-opus-6" in caplog.text
        assert "not in known models" in caplog.text

    def test_known_model_no_warning(self, tmp_path, caplog):
        """Known model does not emit a warning."""
        provider = ClaudeCodeProvider()
        agent = _make_agent(model="claude-sonnet-4-6")
        ctx = _make_workspace(tmp_path)
        with caplog.at_level(logging.WARNING, logger="claude_code.provider"):
            cmd = provider._build_command("x", agent, ctx, None)
        assert "--model" in cmd
        assert "not in known models" not in caplog.text


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
        with caplog.at_level(logging.WARNING, logger="claude_code.provider"):
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

    def test_stream_event_error_sets_is_error(self):
        """stream_event with error type captures error details."""
        provider = ClaudeCodeProvider()
        result = CCTaskResult(output="", session_id="", cost_usd=0.0, usage={}, is_error=False)
        msg = {
            "type": "stream_event",
            "event": {
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "Model does not exist",
                },
            },
        }
        provider._handle_message(msg, result, None)
        assert result.is_error is True
        assert result.error_type == "invalid_request_error"
        assert result.error_message == "Model does not exist"
        assert result.output  # non-empty

    def test_stream_event_non_error_ignored(self):
        """stream_event with non-error type does not modify result."""
        provider = ClaudeCodeProvider()
        result = CCTaskResult(output="", session_id="", cost_usd=0.0, usage={}, is_error=False)
        msg = {
            "type": "stream_event",
            "event": {"type": "content_block_start"},
        }
        provider._handle_message(msg, result, None)
        assert result.is_error is False
        assert result.output == ""

    def test_result_error_with_error_dict(self):
        """result with is_error=True and error dict synthesizes output."""
        provider = ClaudeCodeProvider()
        result = CCTaskResult(output="", session_id="", cost_usd=0.0, usage={}, is_error=False)
        msg = {
            "type": "result",
            "result": "",
            "is_error": True,
            "error": {"type": "auth_error", "message": "Invalid API key"},
        }
        provider._handle_message(msg, result, None)
        assert result.is_error is True
        assert result.error_type == "auth_error"
        assert result.error_message == "Invalid API key"
        assert result.output  # synthesized from error dict

    def test_result_error_preserves_existing_output(self):
        """result with is_error=True keeps result text but still captures error details."""
        provider = ClaudeCodeProvider()
        result = CCTaskResult(output="", session_id="", cost_usd=0.0, usage={}, is_error=False)
        msg = {
            "type": "result",
            "result": "Some output",
            "is_error": True,
            "error": {"type": "x", "message": "y"},
        }
        provider._handle_message(msg, result, None)
        assert result.output == "Some output"
        assert result.error_type == "x"
        assert result.error_message == "y"

    def test_result_error_no_details_fallback(self):
        """result with is_error=True but no error key uses fallback output."""
        provider = ClaudeCodeProvider()
        result = CCTaskResult(output="", session_id="", cost_usd=0.0, usage={}, is_error=False)
        msg = {
            "type": "result",
            "result": "",
            "is_error": True,
        }
        provider._handle_message(msg, result, None)
        assert result.is_error is True
        assert result.output == "Unknown error (no details in result message)"


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
            json.dumps(
                {
                    "type": "result",
                    "result": "All done",
                    "is_error": False,
                    "cost_usd": 0.5,
                    "usage": {"input_tokens": 10},
                    "session_id": "sess-1",
                }
            )
        ]
        proc = self._make_mock_proc(lines, returncode=0)

        provider = ClaudeCodeProvider()
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await provider.execute_task("do stuff", agent, "task-1", ctx)

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
            json.dumps(
                {
                    "type": "result",
                    "result": "partial output",
                    "is_error": False,
                    "cost_usd": 0.0,
                    "usage": {},
                    "session_id": "",
                }
            )
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
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "text", "text": "thinking..."}]},
                }
            ),
            json.dumps(
                {
                    "type": "result",
                    "result": "done",
                    "is_error": False,
                    "cost_usd": 0.0,
                    "usage": {},
                    "session_id": "",
                }
            ),
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
            await provider.execute_task("x", agent, "task-5", ctx, session_id="sess-resume")

        call_args = mock_exec.call_args[0]
        cmd = list(call_args)
        idx = cmd.index("--resume")
        assert cmd[idx + 1] == "sess-resume"

    @pytest.mark.asyncio
    async def test_execute_task_passes_resolved_secret_env_to_subprocess(
        self, tmp_path, monkeypatch
    ):
        """Subprocess env includes API keys resolved from env/config."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("OPENAI_API_KEY", "openai-from-env")
        _write_nanobot_config(
            tmp_path,
            {
                "providers": {
                    "anthropic": {"apiKey": "anthropic-from-config"},
                    "openai": {"apiKey": "openai-from-config"},
                },
                "tools": {
                    "web": {
                        "search": {"apiKey": "brave-from-config"},
                    }
                },
            },
        )
        proc = self._make_mock_proc([])

        provider = ClaudeCodeProvider()
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)

        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await provider.execute_task("x", agent, "task-env", ctx)

        env = mock_exec.call_args.kwargs["env"]
        assert env["ANTHROPIC_API_KEY"] == "anthropic-from-config"
        assert env["OPENAI_API_KEY"] == "openai-from-env"
        assert env["BRAVE_API_KEY"] == "brave-from-config"

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

    @pytest.mark.asyncio
    async def test_stream_error_then_result_error(self, tmp_path):
        """Stream error followed by result error preserves stream error details."""
        lines = [
            json.dumps(
                {
                    "type": "stream_event",
                    "event": {
                        "type": "error",
                        "error": {
                            "type": "invalid_request_error",
                            "message": "Model does not exist",
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "type": "result",
                    "result": "",
                    "is_error": True,
                    "error": {"type": "invalid_request_error", "message": "Model does not exist"},
                }
            ),
        ]
        proc = self._make_mock_proc(lines, returncode=1)

        provider = ClaudeCodeProvider()
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await provider.execute_task("x", agent, "task-err", ctx)

        assert result.is_error is True
        assert result.error_type == "invalid_request_error"
        assert result.error_message == "Model does not exist"
        assert result.output  # non-empty

    @pytest.mark.asyncio
    async def test_stream_error_without_result_message(self, tmp_path):
        """Stream error with no result message preserves error info."""
        lines = [
            json.dumps(
                {
                    "type": "stream_event",
                    "event": {
                        "type": "error",
                        "error": {
                            "type": "overloaded_error",
                            "message": "Server is overloaded",
                        },
                    },
                }
            ),
        ]

        async def _read_stderr():
            return b"Process exited unexpectedly"

        proc = self._make_mock_proc(lines, returncode=1)
        proc.stderr.read = _read_stderr

        provider = ClaudeCodeProvider()
        agent = _make_agent()
        ctx = _make_workspace(tmp_path)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await provider.execute_task("x", agent, "task-no-result", ctx)

        assert result.is_error is True
        assert result.error_type == "overloaded_error"
        assert result.error_message == "Server is overloaded"
        assert "overloaded_error" in result.output


# ---------------------------------------------------------------------------
# AnthropicOAuthProvider — thinking temperature contract
# ---------------------------------------------------------------------------


class TestAnthropicThinkingTemperature:
    """Lock Anthropic thinking payload temperature behavior (AC #1, #2).

    Adaptive thinking and budgeted thinking both require temperature=1.0.
    Non-thinking requests must keep the caller-supplied temperature.
    """

    def _make_fake_response(self) -> tuple[str, list, str, dict, str | None]:
        return ("response text", [], "stop", {"total_tokens": 10}, None)

    @pytest.mark.asyncio
    async def test_adaptive_thinking_forces_temperature_1(self) -> None:
        """Adaptive thinking requests (claude-*-4-6 models) must set temperature=1.0."""
        from nanobot.providers.anthropic_oauth_provider import AnthropicOAuthProvider

        provider = AnthropicOAuthProvider(
            default_model="anthropic-oauth/claude-sonnet-4-6-20250514"
        )
        messages = [{"role": "user", "content": "hello"}]

        captured_bodies: list[dict] = []

        async def _fake_request(headers: dict, body: dict) -> tuple:
            captured_bodies.append(body)
            return ("ok", [], "stop", {"total_tokens": 5}, None)

        with (
            patch(
                "nanobot.providers.anthropic_oauth_provider.get_anthropic_token",
                return_value="tok",
            ),
            patch(
                "nanobot.providers.anthropic_oauth_provider._request_anthropic",
                new=_fake_request,
            ),
        ):
            await provider.chat(
                messages,
                model="claude-sonnet-4-6-20250514",
                temperature=0.5,
                reasoning_level="medium",
            )

        assert len(captured_bodies) == 1
        body = captured_bodies[0]
        assert body.get("thinking", {}).get("type") == "adaptive", (
            "adaptive model should produce thinking.type=adaptive"
        )
        assert body["temperature"] == 1.0, (
            f"adaptive thinking must force temperature=1.0, got {body['temperature']}"
        )

    @pytest.mark.asyncio
    async def test_budgeted_thinking_forces_temperature_1(self) -> None:
        """Budgeted (enabled) thinking requests must set temperature=1.0."""
        from nanobot.providers.anthropic_oauth_provider import AnthropicOAuthProvider

        provider = AnthropicOAuthProvider(
            default_model="anthropic-oauth/claude-sonnet-3-5-20241022"
        )
        messages = [{"role": "user", "content": "hello"}]

        captured_bodies: list[dict] = []

        async def _fake_request(headers: dict, body: dict) -> tuple:
            captured_bodies.append(body)
            return ("ok", [], "stop", {"total_tokens": 5}, None)

        with (
            patch(
                "nanobot.providers.anthropic_oauth_provider.get_anthropic_token",
                return_value="tok",
            ),
            patch(
                "nanobot.providers.anthropic_oauth_provider._request_anthropic",
                new=_fake_request,
            ),
        ):
            await provider.chat(
                messages,
                model="claude-sonnet-3-5-20241022",
                temperature=0.3,
                reasoning_level="medium",
            )

        assert len(captured_bodies) == 1
        body = captured_bodies[0]
        assert body.get("thinking", {}).get("type") == "enabled", (
            "non-adaptive model should produce thinking.type=enabled"
        )
        assert body["temperature"] == 1.0, (
            f"budgeted thinking must force temperature=1.0, got {body['temperature']}"
        )

    @pytest.mark.asyncio
    async def test_non_thinking_keeps_caller_temperature(self) -> None:
        """Non-thinking requests must keep the caller-supplied temperature unchanged."""
        from nanobot.providers.anthropic_oauth_provider import AnthropicOAuthProvider

        provider = AnthropicOAuthProvider(
            default_model="anthropic-oauth/claude-sonnet-4-6-20250514"
        )
        messages = [{"role": "user", "content": "hello"}]

        captured_bodies: list[dict] = []

        async def _fake_request(headers: dict, body: dict) -> tuple:
            captured_bodies.append(body)
            return ("ok", [], "stop", {"total_tokens": 5}, None)

        with (
            patch(
                "nanobot.providers.anthropic_oauth_provider.get_anthropic_token",
                return_value="tok",
            ),
            patch(
                "nanobot.providers.anthropic_oauth_provider._request_anthropic",
                new=_fake_request,
            ),
        ):
            await provider.chat(
                messages,
                model="claude-sonnet-4-6-20250514",
                temperature=0.42,
                # no reasoning_level — non-thinking path
            )

        assert len(captured_bodies) == 1
        body = captured_bodies[0]
        assert "thinking" not in body, "non-thinking request should not include thinking key"
        assert body["temperature"] == 0.42, (
            f"non-thinking request must preserve caller temperature, got {body['temperature']}"
        )
