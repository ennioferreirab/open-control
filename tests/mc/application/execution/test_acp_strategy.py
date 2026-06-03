"""Tests for AcpRunnerStrategy and the ACP update -> ParsedCliEvent mapper."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from acp.schema import (
    AgentMessageChunk,
    AvailableCommandsUpdate,
    TextContentBlock,
    ToolCallProgress,
    ToolCallStart,
    UsageUpdate,
)

from mc.application.execution.request import EntityType, ExecutionRequest, RunnerType
from mc.application.execution.strategies.acp import AcpRunnerStrategy, _acp_update_to_event
from mc.infrastructure.acp.types import AcpTurnResult


def test_agent_message_chunk_maps_to_text() -> None:
    update = AgentMessageChunk.model_construct(
        content=TextContentBlock.model_construct(text="hello")
    )
    event = _acp_update_to_event(update)
    assert event is not None
    assert event.kind == "text"
    assert event.text == "hello"


def test_empty_message_chunk_maps_to_none() -> None:
    update = AgentMessageChunk.model_construct(content=TextContentBlock.model_construct(text=""))
    assert _acp_update_to_event(update) is None


def test_tool_call_start_maps_to_tool_use() -> None:
    update = ToolCallStart.model_construct(title="Bash", tool_call_id="t-1")
    event = _acp_update_to_event(update)
    assert event is not None
    assert event.kind == "tool_use"
    assert event.metadata["tool_call_id"] == "t-1"


def test_tool_call_progress_maps_to_tool_result() -> None:
    update = ToolCallProgress.model_construct(title="Bash", tool_call_id="t-1")
    event = _acp_update_to_event(update)
    assert event is not None
    assert event.kind == "tool_result"


def test_usage_update_maps_to_system_event_with_cost() -> None:
    cost = MagicMock()
    cost.amount = 0.0207
    update = UsageUpdate.model_construct(used=120, size=2000, cost=cost)
    event = _acp_update_to_event(update)
    assert event is not None
    assert event.kind == "system_event"
    assert event.metadata["used_tokens"] == 120
    assert event.metadata["cost_usd"] == 0.0207


def test_usage_update_without_cost_omits_cost() -> None:
    update = UsageUpdate.model_construct(used=120, size=2000, cost=None)
    event = _acp_update_to_event(update)
    assert event is not None
    assert "cost_usd" not in event.metadata


def test_available_commands_update_maps_to_none() -> None:
    update = AvailableCommandsUpdate.model_construct(available_commands=[])
    assert _acp_update_to_event(update) is None


def _request() -> ExecutionRequest:
    return ExecutionRequest(
        entity_type=EntityType.TASK,
        entity_id="task_1",
        task_id="task_1",
        title="ACP task",
        agent_name="acp-agent",
        prompt="do the thing",
        model="haiku",
        runner_type=RunnerType.ACP,
    )


def _fake_acp_client(updates: list[Any], turn: AcpTurnResult, *, fail_enter: bool = False) -> type:
    """Build a fake AcpClient class capturing the updates/turn for one test."""

    class _FakeAcpClient:
        def __init__(self, *, command: list[str], cwd: str, model: str | None) -> None:
            self.command = command
            self.model = model

        @property
        def session_id(self) -> str:
            return "acp-sess-1"

        async def __aenter__(self) -> _FakeAcpClient:
            if fail_enter:
                raise RuntimeError("spawn failed")
            return self

        async def __aexit__(self, *exc: object) -> bool:
            return False

        async def prompt(self, text: str, on_update: Any = None) -> AcpTurnResult:
            for update in updates:
                if on_update is not None:
                    on_update(update)
            return turn

    return _FakeAcpClient


_OK_TURN = AcpTurnResult(
    text="final answer",
    stop_reason="end_turn",
    session_id="acp-sess-1",
    usage={},
    cost_usd=0.0207,
)


async def test_execute_returns_populated_result() -> None:
    registry = MagicMock()
    updates = [
        AgentMessageChunk.model_construct(
            content=TextContentBlock.model_construct(text="final answer")
        ),
        UsageUpdate.model_construct(used=120, size=2000, cost=None),
    ]
    fake = _fake_acp_client(updates, _OK_TURN)
    with (
        patch("mc.application.execution.strategies.acp.AcpClient", fake),
        patch("mc.application.execution.strategies.acp.SessionActivityService") as activity_cls,
    ):
        strategy = AcpRunnerStrategy(registry=registry, command=["x"], cwd=".")
        result = await strategy.execute(_request())

    assert result.success is True
    assert result.output == "final answer"
    assert result.cost_usd == 0.0207
    assert result.session_id == "acp-sess-1"
    registry.create.assert_called_once()
    registry.update_status.assert_called()
    registry.update_provider_session_id.assert_called_once_with("task_1-task_1", "acp-sess-1")
    activity_cls.return_value.append_parsed_cli_event.assert_called()


async def test_execute_maps_error_stop_reason_to_failure() -> None:
    registry = MagicMock()
    err_turn = AcpTurnResult(text="", stop_reason="error", session_id="s", usage={}, cost_usd=None)
    fake = _fake_acp_client([], err_turn)
    with (
        patch("mc.application.execution.strategies.acp.AcpClient", fake),
        patch("mc.application.execution.strategies.acp.SessionActivityService"),
    ):
        strategy = AcpRunnerStrategy(registry=registry, command=["x"], cwd=".")
        result = await strategy.execute(_request())

    assert result.success is False


async def test_execute_handles_client_exception() -> None:
    registry = MagicMock()
    fake = _fake_acp_client([], _OK_TURN, fail_enter=True)
    with (
        patch("mc.application.execution.strategies.acp.AcpClient", fake),
        patch("mc.application.execution.strategies.acp.SessionActivityService"),
    ):
        strategy = AcpRunnerStrategy(registry=registry, command=["x"], cwd=".")
        result = await strategy.execute(_request())

    assert result.success is False
    assert "spawn failed" in (result.error_message or "")
