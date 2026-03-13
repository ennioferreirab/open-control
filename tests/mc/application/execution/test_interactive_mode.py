from __future__ import annotations

from unittest.mock import patch

import pytest

from mc.application.execution.interactive_mode import resolve_step_runner_type
from mc.application.execution.request import EntityType, ExecutionRequest, RunnerType
from mc.types import AgentData


def _request(
    *, provider: str | None, backend: str = "nanobot", is_cc: bool = False
) -> ExecutionRequest:
    return ExecutionRequest(
        entity_type=EntityType.STEP,
        entity_id="step-1",
        task_id="task-1",
        title="Run step",
        agent_name="agent-1",
        agent=AgentData(
            name="agent-1",
            display_name="Agent 1",
            role="Engineer",
            backend=backend,
            interactive_provider=provider,
        ),
        is_cc=is_cc,
    )


def test_resolve_step_runner_type_prefers_interactive_runtime_for_supported_agents() -> None:
    runner_type = resolve_step_runner_type(_request(provider="codex"))

    assert runner_type == RunnerType.INTERACTIVE_TUI


def test_resolve_step_runner_type_keeps_noninteractive_agents_on_nanobot() -> None:
    runner_type = resolve_step_runner_type(_request(provider=None, backend="nanobot"))

    assert runner_type == RunnerType.NANOBOT


def test_resolve_step_runner_type_surfaces_disabled_interactive_execution() -> None:
    with patch.dict("os.environ", {"MC_INTERACTIVE_EXECUTION_MODE": "disabled"}):
        with pytest.raises(RuntimeError, match="Interactive execution is disabled"):
            resolve_step_runner_type(_request(provider="claude-code", backend="claude-code"))
