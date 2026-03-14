"""Tests for provider-CLI runtime wiring defaults.

These tests verify that the default execution path routes interactive agents
through PROVIDER_CLI (not INTERACTIVE_TUI), and that the legacy TUI path is
only reachable via an explicit escape hatch.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mc.application.execution.interactive_mode import resolve_step_runner_type
from mc.application.execution.request import EntityType, ExecutionRequest, RunnerType
from mc.types import AgentData


def _make_request(
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


# ---------------------------------------------------------------------------
# Default (no env var)
# ---------------------------------------------------------------------------


def test_default_no_env_resolves_to_provider_cli_for_claude_code() -> None:
    """With no env var set, interactive agents default to PROVIDER_CLI."""
    with patch.dict("os.environ", {}, clear=False):
        # Ensure the env var is not present
        import os

        os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
        runner = resolve_step_runner_type(_make_request(provider="claude-code"))

    assert runner == RunnerType.PROVIDER_CLI


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


def test_explicit_provider_cli_env_resolves_to_provider_cli() -> None:
    """Explicit env var value 'provider-cli' resolves to PROVIDER_CLI."""
    with patch.dict("os.environ", {"MC_INTERACTIVE_EXECUTION_MODE": "provider-cli"}):
        runner = resolve_step_runner_type(_make_request(provider="claude-code"))

    assert runner == RunnerType.PROVIDER_CLI


def test_interactive_first_resolves_to_provider_cli() -> None:
    """Legacy 'interactive-first' mode now routes to PROVIDER_CLI."""
    with patch.dict("os.environ", {"MC_INTERACTIVE_EXECUTION_MODE": "interactive-first"}):
        runner = resolve_step_runner_type(_make_request(provider="claude-code"))

    assert runner == RunnerType.PROVIDER_CLI


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


def test_non_interactive_agents_still_route_to_nanobot() -> None:
    runner = resolve_step_runner_type(_make_request(provider=None, backend="nanobot"))

    assert runner == RunnerType.NANOBOT
