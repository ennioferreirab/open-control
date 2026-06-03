"""Tests for provider-CLI runtime wiring defaults.

These tests verify that the default execution path routes claude-code agents
through ACP (Phase 6), codex through PROVIDER_CLI, and the legacy TUI path is
only reachable via an explicit escape hatch.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mc.application.execution.interactive_mode import (
    resolve_step_runner_type,
    resolve_task_runner_type,
)
from mc.application.execution.request import EntityType, ExecutionRequest, RunnerType
from mc.types import AgentData


def _make_request(
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


# ---------------------------------------------------------------------------
# Default (no env var)
# ---------------------------------------------------------------------------


def test_default_no_env_resolves_to_acp_for_claude_code() -> None:
    """With no env var set, claude-code agents route to ACP (Phase 6 default)."""
    with patch.dict("os.environ", {}, clear=False):
        import os

        os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
        runner = resolve_step_runner_type(_make_request(provider="claude-code"))

    assert runner == RunnerType.ACP


def test_direct_task_defaults_to_acp_for_claude_code() -> None:
    with patch.dict("os.environ", {}, clear=False):
        import os

        os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
        request = _make_request(provider="claude-code")
        request.entity_type = EntityType.TASK
        runner = resolve_task_runner_type(request)

    assert runner == RunnerType.ACP


def test_default_no_env_resolves_to_provider_cli_for_codex() -> None:
    with patch.dict("os.environ", {}, clear=False):
        import os

        os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
        runner = resolve_step_runner_type(_make_request(provider="codex"))

    assert runner == RunnerType.PROVIDER_CLI


def test_default_no_env_resolves_to_provider_cli_for_mc() -> None:
    with patch.dict("os.environ", {}, clear=False):
        import os

        os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
        runner = resolve_step_runner_type(_make_request(provider="mc"))

    assert runner == RunnerType.PROVIDER_CLI


# ---------------------------------------------------------------------------
# Explicit provider-cli value
# ---------------------------------------------------------------------------


def test_explicit_provider_cli_env_resolves_to_acp_for_claude_code() -> None:
    """For claude-code, 'provider-cli' env value still routes to ACP (Phase 6 default)."""
    with patch.dict("os.environ", {"MC_INTERACTIVE_EXECUTION_MODE": "provider-cli"}):
        runner = resolve_step_runner_type(_make_request(provider="claude-code"))

    assert runner == RunnerType.ACP


def test_interactive_first_resolves_to_acp_for_claude_code() -> None:
    """For claude-code, 'interactive-first' routes to ACP (Phase 6 default)."""
    with patch.dict("os.environ", {"MC_INTERACTIVE_EXECUTION_MODE": "interactive-first"}):
        runner = resolve_step_runner_type(_make_request(provider="claude-code"))

    assert runner == RunnerType.ACP


# ---------------------------------------------------------------------------
# Escape hatch — explicit interactive-tui
# ---------------------------------------------------------------------------


def test_interactive_tui_escape_hatch_resolves_to_interactive_tui() -> None:
    """Only the explicit 'interactive-tui' value routes to the legacy TUI."""
    with patch.dict("os.environ", {"MC_INTERACTIVE_EXECUTION_MODE": "interactive-tui"}):
        runner = resolve_step_runner_type(_make_request(provider="claude-code"))

    assert runner == RunnerType.INTERACTIVE_TUI


# ---------------------------------------------------------------------------
# Disabled mode
# ---------------------------------------------------------------------------


def test_disabled_mode_raises_runtime_error() -> None:
    with patch.dict("os.environ", {"MC_INTERACTIVE_EXECUTION_MODE": "disabled"}):
        with pytest.raises(RuntimeError, match="Interactive execution is disabled"):
            resolve_step_runner_type(_make_request(provider="claude-code", backend="claude-code"))


def test_off_mode_raises_runtime_error() -> None:
    with patch.dict("os.environ", {"MC_INTERACTIVE_EXECUTION_MODE": "off"}):
        with pytest.raises(RuntimeError, match="Interactive execution is disabled"):
            resolve_step_runner_type(_make_request(provider="claude-code"))


# ---------------------------------------------------------------------------
# Non-interactive agents
# ---------------------------------------------------------------------------


def test_claude_code_backend_no_provider_routes_to_acp() -> None:
    """backend=claude-code with no interactive_provider still identifies as claude-code → ACP."""
    runner = resolve_step_runner_type(_make_request(provider=None, backend="claude-code"))

    assert runner == RunnerType.ACP


# ---------------------------------------------------------------------------
# Engine strategy wiring (Story 28-8)
# ---------------------------------------------------------------------------


def test_engine_default_strategies_include_provider_cli() -> None:
    """ExecutionEngine creates a ProviderCliRunnerStrategy for PROVIDER_CLI by default."""
    from mc.application.execution.engine import ExecutionEngine
    from mc.application.execution.strategies.provider_cli import ProviderCliRunnerStrategy

    engine = ExecutionEngine()
    strategy = engine.get_strategy(RunnerType.PROVIDER_CLI)
    assert isinstance(strategy, ProviderCliRunnerStrategy)


def test_build_execution_engine_wires_provider_cli_strategy() -> None:
    """build_execution_engine() wires a ProviderCliRunnerStrategy for PROVIDER_CLI.

    The base command stored in the strategy must NOT include a trailing ``-p``.
    ``_build_command()`` is the sole authority that injects ``-p <prompt>``,
    so the base command only contains the binary and its stream-json flags.

    Correct base: ``["claude", "--verbose", "--output-format", "stream-json"]``
    Effective command with prompt: ``claude -p "<prompt>" --verbose --output-format stream-json``
    """
    from mc.application.execution.post_processing import build_execution_engine
    from mc.application.execution.strategies.provider_cli import ProviderCliRunnerStrategy

    engine = build_execution_engine()
    strategy = engine.get_strategy(RunnerType.PROVIDER_CLI)
    assert isinstance(strategy, ProviderCliRunnerStrategy)
    assert strategy._command == [
        "claude",
        "--verbose",
        "--output-format",
        "stream-json",
    ]
    assert "-p" not in strategy._command


def test_build_execution_engine_keeps_interactive_tui_separate() -> None:
    """INTERACTIVE_TUI must NOT be ProviderCliRunnerStrategy."""
    from mc.application.execution.post_processing import build_execution_engine
    from mc.application.execution.strategies.interactive import InteractiveTuiRunnerStrategy

    engine = build_execution_engine()
    strategy = engine.get_strategy(RunnerType.INTERACTIVE_TUI)
    assert isinstance(strategy, InteractiveTuiRunnerStrategy)


# ---------------------------------------------------------------------------
# Story 28-11: Cutover gate tests — document and enforce cutover criteria
# ---------------------------------------------------------------------------


class TestBackendCutoverGates:
    """Documents and enforces the Story 28-11 backend cutover criteria."""

    def test_gate_1_default_mode_resolves_to_acp_for_claude_code(self) -> None:
        import os

        env_backup = os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
        try:
            runner = resolve_step_runner_type(_make_request(provider="claude-code"))
            assert runner == RunnerType.ACP
        finally:
            if env_backup is not None:
                os.environ["MC_INTERACTIVE_EXECUTION_MODE"] = env_backup

    def test_gate_2_engine_strategy_is_provider_cli_runner(self) -> None:
        from mc.application.execution.engine import ExecutionEngine
        from mc.application.execution.strategies.provider_cli import ProviderCliRunnerStrategy

        engine = ExecutionEngine()
        strategy = engine.get_strategy(RunnerType.PROVIDER_CLI)
        assert isinstance(strategy, ProviderCliRunnerStrategy)

    def test_gate_3_strategy_no_interactive_session_coordinator(self) -> None:
        import pathlib

        strategy_path = (
            pathlib.Path(__file__).parents[3]
            / "mc"
            / "application"
            / "execution"
            / "strategies"
            / "provider_cli.py"
        )
        source = strategy_path.read_text(encoding="utf-8")
        assert "InteractiveSessionCoordinator" not in source

    def test_gate_4_supervisor_no_tmux_session_manager(self) -> None:
        import pathlib

        supervisor_path = (
            pathlib.Path(__file__).parents[3]
            / "mc"
            / "runtime"
            / "provider_cli"
            / "process_supervisor.py"
        )
        source = supervisor_path.read_text(encoding="utf-8")
        assert "TmuxSessionManager" not in source

    def test_gate_5_build_engine_uses_injected_provider_cli_services(self) -> None:
        from unittest.mock import MagicMock

        from mc.application.execution.post_processing import build_execution_engine
        from mc.application.execution.strategies.provider_cli import ProviderCliRunnerStrategy

        mock_registry = MagicMock()
        mock_supervisor = MagicMock()
        engine = build_execution_engine(
            provider_cli_registry=mock_registry,
            provider_cli_supervisor=mock_supervisor,
        )
        strategy = engine.get_strategy(RunnerType.PROVIDER_CLI)
        assert isinstance(strategy, ProviderCliRunnerStrategy)
        assert strategy._supervisor is mock_supervisor

    def test_gate_6_gateway_references_provider_cli_services(self) -> None:
        import pathlib

        gateway_path = pathlib.Path(__file__).parents[3] / "mc" / "runtime" / "gateway.py"
        source = gateway_path.read_text(encoding="utf-8")
        assert "provider_cli" in source or "ProviderCliRunnerStrategy" in source
