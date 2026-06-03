from __future__ import annotations

from unittest.mock import patch

import pytest

from mc.application.execution.interactive_mode import resolve_step_runner_type
from mc.application.execution.request import EntityType, ExecutionRequest, RunnerType
from mc.types import AgentData


def _request(
    *, provider: str | None, backend: str = "claude-code", is_cc: bool = False
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


def test_resolve_step_runner_type_prefers_provider_cli_for_supported_agents() -> None:
    """Codex stays on PROVIDER_CLI regardless of env."""
    import os

    os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
    runner_type = resolve_step_runner_type(_request(provider="codex"))

    assert runner_type == RunnerType.PROVIDER_CLI


def test_resolve_step_runner_type_supports_mc_interactive_provider() -> None:
    import os

    os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
    runner_type = resolve_step_runner_type(_request(provider="mc"))

    assert runner_type == RunnerType.PROVIDER_CLI


def test_resolve_step_runner_type_surfaces_disabled_interactive_execution() -> None:
    with patch.dict("os.environ", {"MC_INTERACTIVE_EXECUTION_MODE": "disabled"}):
        with pytest.raises(RuntimeError, match="Interactive execution is disabled"):
            resolve_step_runner_type(_request(provider="claude-code", backend="claude-code"))


def test_resolve_claude_code_routes_to_acp_by_default() -> None:
    """Plain claude-code backend routes to ACP when no env var is set (Phase 6 default)."""
    with patch.dict("os.environ", {"MC_INTERACTIVE_EXECUTION_MODE": "provider-cli"}):
        runner_type = resolve_step_runner_type(_request(provider=None, backend="claude-code"))

    assert runner_type == RunnerType.ACP


def test_resolve_claude_code_is_cc_routes_to_acp() -> None:
    """is_cc=True identifies a claude-code agent and routes to ACP."""
    with patch.dict("os.environ", {"MC_INTERACTIVE_EXECUTION_MODE": "provider-cli"}):
        runner_type = resolve_step_runner_type(
            _request(provider=None, backend="claude-code", is_cc=True)
        )

    assert runner_type == RunnerType.ACP


def test_resolve_claude_code_tui_escape_hatch() -> None:
    """The interactive-tui env value routes claude-code to INTERACTIVE_TUI."""
    with patch.dict("os.environ", {"MC_INTERACTIVE_EXECUTION_MODE": "interactive-tui"}):
        runner_type = resolve_step_runner_type(
            _request(provider="claude-code", backend="claude-code")
        )

    assert runner_type == RunnerType.INTERACTIVE_TUI
