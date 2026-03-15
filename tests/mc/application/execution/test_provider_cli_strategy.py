"""Tests for the ProviderCliRunnerStrategy."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from mc.application.execution.request import (
    EntityType,
    ErrorCategory,
    ExecutionRequest,
    RunnerType,
)
from mc.application.execution.strategies.provider_cli import ProviderCliRunnerStrategy
from mc.contexts.provider_cli.registry import ProviderSessionRegistry
from mc.contexts.provider_cli.types import ParsedCliEvent, ProviderProcessHandle

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(
    task_id: str = "task-001",
    agent_name: str = "dev",
    title: str = "Do the work",
    description: str | None = None,
    runner_type: RunnerType = RunnerType.PROVIDER_CLI,
) -> ExecutionRequest:
    return ExecutionRequest(
        entity_type=EntityType.STEP,
        entity_id="step-001",
        task_id=task_id,
        agent_name=agent_name,
        title=title,
        description=description,
        runner_type=runner_type,
    )


def _make_handle(mc_session_id: str = "mc-001") -> ProviderProcessHandle:
    return ProviderProcessHandle(
        mc_session_id=mc_session_id,
        provider="claude-code",
        pid=12345,
        pgid=12344,
        cwd="/tmp/workspace",
        command=["claude", "--output-format", "stream-json"],
        started_at="2024-01-01T00:00:00Z",
    )


def _make_parser(handle: ProviderProcessHandle | None = None) -> MagicMock:
    parser = MagicMock()
    parser.provider_name = "claude-code"
    parser.parse_output = MagicMock(return_value=[])
    parser.start_session = AsyncMock(return_value=handle or _make_handle())
    parser.stop = AsyncMock()
    parser.interrupt = AsyncMock()
    return parser


# ---------------------------------------------------------------------------
# RunnerType.PROVIDER_CLI is accessible
# ---------------------------------------------------------------------------


def test_runner_type_provider_cli_exists() -> None:
    assert RunnerType.PROVIDER_CLI == "provider-cli"


# ---------------------------------------------------------------------------
# Strategy delegates to parser
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strategy_calls_parser_start_session() -> None:
    handle = _make_handle()
    parser = _make_parser(handle)
    registry = ProviderSessionRegistry()

    result_events = [
        ParsedCliEvent(kind="result", text="Done"),
    ]
    parser.parse_output.return_value = result_events

    async def fake_stream(h: ProviderProcessHandle):
        yield json.dumps({"type": "result", "subtype": "success", "result": "Done"}).encode()

    supervisor = MagicMock()
    supervisor.stream_output = fake_stream
    supervisor.wait_for_exit = AsyncMock(return_value=0)

    strategy = ProviderCliRunnerStrategy(
        parser=parser,
        registry=registry,
        supervisor=supervisor,
        command=["claude", "--output-format", "stream-json"],
        cwd="/tmp/workspace",
    )
    request = _make_request()
    result = await strategy.execute(request)

    parser.start_session.assert_awaited_once()
    assert result.success is True


@pytest.mark.asyncio
async def test_strategy_registers_session_in_registry() -> None:
    handle = _make_handle(mc_session_id="mc-002")
    parser = _make_parser(handle)
    registry = ProviderSessionRegistry()

    result_events = [ParsedCliEvent(kind="result", text="Done")]
    parser.parse_output.return_value = result_events

    async def fake_stream(h: ProviderProcessHandle):
        yield b""

    supervisor = MagicMock()
    supervisor.stream_output = fake_stream
    supervisor.wait_for_exit = AsyncMock(return_value=0)

    strategy = ProviderCliRunnerStrategy(
        parser=parser,
        registry=registry,
        supervisor=supervisor,
        command=["claude", "--output-format", "stream-json"],
        cwd="/tmp/workspace",
    )
    request = _make_request(task_id="task-002")
    await strategy.execute(request)

    record = registry.get(handle.mc_session_id)
    assert record is not None
    assert record.provider == "claude-code"


@pytest.mark.asyncio
async def test_strategy_returns_success_on_normal_exit() -> None:
    handle = _make_handle()
    parser = _make_parser(handle)
    registry = ProviderSessionRegistry()

    result_event = ParsedCliEvent(kind="result", text="Task completed successfully")
    parser.parse_output.return_value = [result_event]

    async def fake_stream(h: ProviderProcessHandle):
        yield b"some output"

    supervisor = MagicMock()
    supervisor.stream_output = fake_stream
    supervisor.wait_for_exit = AsyncMock(return_value=0)

    strategy = ProviderCliRunnerStrategy(
        parser=parser,
        registry=registry,
        supervisor=supervisor,
        command=["claude", "--output-format", "stream-json"],
        cwd="/tmp/workspace",
    )
    result = await strategy.execute(_make_request())
    assert result.success is True
    assert result.error_category is None


@pytest.mark.asyncio
async def test_strategy_returns_failure_on_error_event() -> None:
    handle = _make_handle()
    parser = _make_parser(handle)
    registry = ProviderSessionRegistry()

    error_event = ParsedCliEvent(kind="error", text="max_turns_exceeded")
    parser.parse_output.return_value = [error_event]

    async def fake_stream(h: ProviderProcessHandle):
        yield b"some error output"

    supervisor = MagicMock()
    supervisor.stream_output = fake_stream
    supervisor.wait_for_exit = AsyncMock(return_value=1)

    strategy = ProviderCliRunnerStrategy(
        parser=parser,
        registry=registry,
        supervisor=supervisor,
        command=["claude", "--output-format", "stream-json"],
        cwd="/tmp/workspace",
    )
    result = await strategy.execute(_make_request())
    assert result.success is False
    assert result.error_category == ErrorCategory.RUNNER


@pytest.mark.asyncio
async def test_strategy_returns_failure_on_nonzero_exit() -> None:
    handle = _make_handle()
    parser = _make_parser(handle)
    registry = ProviderSessionRegistry()

    parser.parse_output.return_value = []

    async def fake_stream(h: ProviderProcessHandle):
        yield b""

    supervisor = MagicMock()
    supervisor.stream_output = fake_stream
    supervisor.wait_for_exit = AsyncMock(return_value=2)

    strategy = ProviderCliRunnerStrategy(
        parser=parser,
        registry=registry,
        supervisor=supervisor,
        command=["claude", "--output-format", "stream-json"],
        cwd="/tmp/workspace",
    )
    result = await strategy.execute(_make_request())
    assert result.success is False
    assert result.error_category == ErrorCategory.RUNNER


@pytest.mark.asyncio
async def test_strategy_captures_output_text() -> None:
    handle = _make_handle()
    parser = _make_parser(handle)
    registry = ProviderSessionRegistry()

    result_event = ParsedCliEvent(kind="result", text="Final answer here")
    parser.parse_output.return_value = [result_event]

    async def fake_stream(h: ProviderProcessHandle):
        yield b"content"

    supervisor = MagicMock()
    supervisor.stream_output = fake_stream
    supervisor.wait_for_exit = AsyncMock(return_value=0)

    strategy = ProviderCliRunnerStrategy(
        parser=parser,
        registry=registry,
        supervisor=supervisor,
        command=["claude", "--output-format", "stream-json"],
        cwd="/tmp/workspace",
    )
    result = await strategy.execute(_make_request())
    assert result.success is True
    assert "Final answer here" in result.output


@pytest.mark.asyncio
async def test_strategy_returns_error_result_on_exception() -> None:
    parser = MagicMock()
    parser.provider_name = "claude-code"
    parser.start_session = AsyncMock(side_effect=RuntimeError("Process launch failed"))
    registry = ProviderSessionRegistry()

    supervisor = MagicMock()

    strategy = ProviderCliRunnerStrategy(
        parser=parser,
        registry=registry,
        supervisor=supervisor,
        command=["claude", "--output-format", "stream-json"],
        cwd="/tmp/workspace",
    )
    result = await strategy.execute(_make_request())
    assert result.success is False
    assert result.error_category == ErrorCategory.RUNNER


# ---------------------------------------------------------------------------
# Session ID discovery from parser output
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strategy_updates_registry_with_discovered_session_id() -> None:
    handle = _make_handle(mc_session_id="mc-disco-001")
    parser = MagicMock()
    parser.provider_name = "claude-code"
    parser.start_session = AsyncMock(return_value=handle)
    parser.stop = AsyncMock()

    session_id_event = ParsedCliEvent(
        kind="session_id",
        text="claude-sess-xyz",
        provider_session_id="claude-sess-xyz",
    )
    result_event = ParsedCliEvent(kind="result", text="Done")
    parser.parse_output = MagicMock(
        side_effect=[
            [session_id_event],
            [result_event],
        ]
    )

    registry = ProviderSessionRegistry()

    async def fake_stream(h: ProviderProcessHandle):
        yield b"chunk1"
        yield b"chunk2"

    supervisor = MagicMock()
    supervisor.stream_output = fake_stream
    supervisor.wait_for_exit = AsyncMock(return_value=0)

    strategy = ProviderCliRunnerStrategy(
        parser=parser,
        registry=registry,
        supervisor=supervisor,
        command=["claude", "--output-format", "stream-json"],
        cwd="/tmp/workspace",
    )
    result = await strategy.execute(_make_request())

    record = registry.get(handle.mc_session_id)
    assert record is not None
    assert record.provider_session_id == "claude-sess-xyz"
    assert result.session_id == "claude-sess-xyz"


# ---------------------------------------------------------------------------
# Prompt injection into command (Story 28-9)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strategy_appends_prompt_to_command_when_prompt_present() -> None:
    """The bootstrap prompt from ExecutionRequest must be forwarded to the CLI."""
    handle = _make_handle()
    parser = _make_parser(handle)
    registry = ProviderSessionRegistry()

    parser.parse_output.return_value = [ParsedCliEvent(kind="result", text="Done")]

    async def fake_stream(h: ProviderProcessHandle):
        yield b"output"

    supervisor = MagicMock()
    supervisor.stream_output = fake_stream
    supervisor.wait_for_exit = AsyncMock(return_value=0)

    base_command = ["claude", "--output-format", "stream-json", "--print"]
    strategy = ProviderCliRunnerStrategy(
        parser=parser,
        registry=registry,
        supervisor=supervisor,
        command=base_command,
        cwd="/tmp/workspace",
    )

    request = ExecutionRequest(
        entity_type=EntityType.STEP,
        entity_id="step-001",
        task_id="task-prompt-001",
        agent_name="dev",
        title="Do the work",
        runner_type=RunnerType.PROVIDER_CLI,
        prompt="Implement the feature per the spec.",
    )
    await strategy.execute(request)

    call_kwargs = parser.start_session.call_args
    assert call_kwargs is not None
    launched_command = call_kwargs.kwargs.get("command") or call_kwargs.args[1]
    assert "--prompt" in launched_command
    prompt_idx = launched_command.index("--prompt")
    assert launched_command[prompt_idx + 1] == "Implement the feature per the spec."


@pytest.mark.asyncio
async def test_strategy_does_not_append_prompt_when_prompt_is_empty() -> None:
    """When request.prompt is empty, no --prompt argument should be appended."""
    handle = _make_handle()
    parser = _make_parser(handle)
    registry = ProviderSessionRegistry()

    parser.parse_output.return_value = [ParsedCliEvent(kind="result", text="Done")]

    async def fake_stream(h: ProviderProcessHandle):
        yield b"output"

    supervisor = MagicMock()
    supervisor.stream_output = fake_stream
    supervisor.wait_for_exit = AsyncMock(return_value=0)

    base_command = ["claude", "--output-format", "stream-json", "--print"]
    strategy = ProviderCliRunnerStrategy(
        parser=parser,
        registry=registry,
        supervisor=supervisor,
        command=base_command,
        cwd="/tmp/workspace",
    )

    request = ExecutionRequest(
        entity_type=EntityType.STEP,
        entity_id="step-001",
        task_id="task-noprompt-001",
        agent_name="dev",
        title="Do the work",
        runner_type=RunnerType.PROVIDER_CLI,
        prompt="",
    )
    await strategy.execute(request)

    call_kwargs = parser.start_session.call_args
    assert call_kwargs is not None
    launched_command = call_kwargs.kwargs.get("command") or call_kwargs.args[1]
    assert "--prompt" not in launched_command


@pytest.mark.asyncio
async def test_strategy_does_not_mutate_base_command() -> None:
    """The base command list stored in the strategy must not be mutated between calls."""
    handle = _make_handle()
    parser = _make_parser(handle)
    registry = ProviderSessionRegistry()

    parser.parse_output.return_value = [ParsedCliEvent(kind="result", text="Done")]

    async def fake_stream(h: ProviderProcessHandle):
        yield b"output"

    supervisor = MagicMock()
    supervisor.stream_output = fake_stream
    supervisor.wait_for_exit = AsyncMock(return_value=0)

    base_command = ["claude", "--output-format", "stream-json", "--print"]
    original_command = list(base_command)
    strategy = ProviderCliRunnerStrategy(
        parser=parser,
        registry=registry,
        supervisor=supervisor,
        command=base_command,
        cwd="/tmp/workspace",
    )

    request = ExecutionRequest(
        entity_type=EntityType.STEP,
        entity_id="step-001",
        task_id="task-mutate-001",
        agent_name="dev",
        title="Do the work",
        runner_type=RunnerType.PROVIDER_CLI,
        prompt="First prompt",
    )
    await strategy.execute(request)

    # base_command must not have been mutated
    assert base_command == original_command


@pytest.mark.asyncio
async def test_strategy_end_to_end_with_prompt_result_and_session_id() -> None:
    """End-to-end: request with prompt → strategy → parser events → success result."""
    handle = _make_handle(mc_session_id="mc-e2e-001")
    parser = MagicMock()
    parser.provider_name = "claude-code"
    parser.start_session = AsyncMock(return_value=handle)

    session_id_event = ParsedCliEvent(
        kind="session_id",
        text="provider-sess-e2e",
        provider_session_id="provider-sess-e2e",
    )
    result_event = ParsedCliEvent(kind="result", text="E2E task complete")
    parser.parse_output = MagicMock(
        side_effect=[
            [session_id_event],
            [result_event],
        ]
    )

    registry = ProviderSessionRegistry()

    async def fake_stream(h: ProviderProcessHandle):
        yield b"init-chunk"
        yield b"result-chunk"

    supervisor = MagicMock()
    supervisor.stream_output = fake_stream
    supervisor.wait_for_exit = AsyncMock(return_value=0)

    strategy = ProviderCliRunnerStrategy(
        parser=parser,
        registry=registry,
        supervisor=supervisor,
        command=["claude", "--output-format", "stream-json", "--print"],
        cwd="/tmp/workspace",
    )

    request = ExecutionRequest(
        entity_type=EntityType.STEP,
        entity_id="step-e2e",
        task_id="task-e2e-001",
        agent_name="dev",
        title="E2E task",
        runner_type=RunnerType.PROVIDER_CLI,
        prompt="Execute the E2E test scenario.",
    )
    result = await strategy.execute(request)

    # Verify command was built with the prompt
    call_kwargs = parser.start_session.call_args
    launched_command = call_kwargs.kwargs.get("command") or call_kwargs.args[1]
    assert "--prompt" in launched_command
    assert "Execute the E2E test scenario." in launched_command

    # Verify result
    assert result.success is True
    assert result.output == "E2E task complete"
    assert result.session_id == "provider-sess-e2e"

    # Verify registry
    record = registry.get(handle.mc_session_id)
    assert record is not None
    assert record.provider_session_id == "provider-sess-e2e"
