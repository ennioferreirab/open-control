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
    """Default (no env var) now routes to PROVIDER_CLI (Story 28.7)."""
    import os

    os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
    runner_type = resolve_step_runner_type(_request(provider="codex"))

    assert runner_type == RunnerType.PROVIDER_CLI


def test_resolve_step_runner_type_supports_mc_interactive_provider() -> None:
    import os

    os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
    runner_type = resolve_step_runner_type(_request(provider="mc"))

    assert runner_type == RunnerType.PROVIDER_CLI


def test_resolve_step_runner_type_keeps_noninteractive_agents_on_provider_cli() -> None:
    runner_type = resolve_step_runner_type(_request(provider=None, backend="claude-code"))

    assert runner_type == RunnerType.PROVIDER_CLI


def test_resolve_step_runner_type_surfaces_disabled_interactive_execution() -> None:
    with patch.dict("os.environ", {"MC_INTERACTIVE_EXECUTION_MODE": "disabled"}):
        with pytest.raises(RuntimeError, match="Interactive execution is disabled"):
            resolve_step_runner_type(_request(provider="claude-code", backend="claude-code"))


def test_resolve_acp_backend_routes_to_acp() -> None:
    """An explicit ``<harness>-acp`` backend opts the agent into the ACP path."""
    runner_type = resolve_step_runner_type(_request(provider=None, backend="claude-code-acp"))

    assert runner_type == RunnerType.ACP


def test_resolve_acp_via_interactive_provider_after_roundtrip() -> None:
    """backend does not persist; the opt-in rides interactive_provider on read."""
    runner_type = resolve_step_runner_type(
        _request(provider="claude-code-acp", backend="claude-code")
    )

    assert runner_type == RunnerType.ACP


def test_resolve_acp_precedes_legacy_interactive_branches() -> None:
    """The ACP branch wins over is_cc / legacy interactive selection."""
    runner_type = resolve_step_runner_type(
        _request(provider="claude-code-acp", backend="claude-code", is_cc=True)
    )

    assert runner_type == RunnerType.ACP


def test_resolve_default_claude_code_stays_provider_cli() -> None:
    """Additive guard: the bare harness name keeps the legacy PROVIDER_CLI path."""
    runner_type = resolve_step_runner_type(_request(provider=None, backend="claude-code"))

    assert runner_type == RunnerType.PROVIDER_CLI


def test_resolve_unknown_acp_harness_raises() -> None:
    """An -acp opt-in naming an unregistered harness fails loudly, no silent default."""
    with pytest.raises(ValueError, match="Unknown harness"):
        resolve_step_runner_type(_request(provider=None, backend="hermes-acp"))
