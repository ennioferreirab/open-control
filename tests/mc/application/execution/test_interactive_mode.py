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


def test_resolve_codex_interactive_provider_routes_to_acp() -> None:
    """A codex agent now runs through ACP (codex-acp harness)."""
    import os

    os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
    runner_type = resolve_step_runner_type(_request(provider="codex", backend="codex"))

    assert runner_type == RunnerType.ACP


def test_resolve_codex_backend_routes_to_acp() -> None:
    """backend=codex alone (no interactive_provider) routes to ACP."""
    import os

    os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
    runner_type = resolve_step_runner_type(_request(provider=None, backend="codex"))

    assert runner_type == RunnerType.ACP


def test_resolve_hermes_interactive_provider_routes_to_acp() -> None:
    """A hermes agent runs through ACP via the provider shortcut, not by fallthrough."""
    import os

    os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
    runner_type = resolve_step_runner_type(_request(provider="hermes", backend="hermes"))

    assert runner_type == RunnerType.ACP


def test_resolve_hermes_provider_wins_when_backend_disagrees() -> None:
    """interactive_provider=hermes is authoritative even if backend was left stale."""
    import os

    os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
    runner_type = resolve_step_runner_type(_request(provider="hermes", backend="claude-code"))

    assert runner_type == RunnerType.ACP


def test_resolve_hermes_backend_routes_to_acp() -> None:
    """backend=hermes alone (no interactive_provider) routes to ACP."""
    import os

    os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
    runner_type = resolve_step_runner_type(_request(provider=None, backend="hermes"))

    assert runner_type == RunnerType.ACP


def test_resolve_codex_ignores_tui_escape_hatch() -> None:
    """The TUI hatch is claude-code-only; codex still resolves to ACP."""
    with patch.dict("os.environ", {"MC_INTERACTIVE_EXECUTION_MODE": "interactive-tui"}):
        runner_type = resolve_step_runner_type(_request(provider="codex", backend="codex"))

    assert runner_type == RunnerType.ACP


def test_resolve_unknown_backend_stays_provider_cli() -> None:
    """A backend that names no registered harness falls to PROVIDER_CLI."""
    import os

    os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
    runner_type = resolve_step_runner_type(_request(provider=None, backend="unknown-harness"))

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
