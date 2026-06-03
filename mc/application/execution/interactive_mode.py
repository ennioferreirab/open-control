"""Execution-mode resolution for interactive-capable task/step providers."""

from __future__ import annotations

import logging
import os
from typing import Any

from mc.application.execution.request import RunnerType
from mc.infrastructure.acp.harness_registry import get_harness

logger = logging.getLogger(__name__)

INTERACTIVE_MODE_ENV = "MC_INTERACTIVE_EXECUTION_MODE"


def _acp_harness_for(selector: str | None) -> str | None:
    """Return the registered ACP harness a selector opts into, or None.

    Phase 4-5 opt-in convention: a ``<harness>-acp`` backend value routes to
    ACP while the bare harness name keeps the legacy path. Phase 6 deletes this
    helper and routes the harness name itself to ACP.

    Raises:
        ValueError: the selector opts into ACP but names a harness absent from
            the registry. Surfaced explicitly rather than silently degrading to
            PROVIDER_CLI.
    """
    if not selector or not selector.endswith("-acp"):
        return None
    harness = selector.removesuffix("-acp")
    get_harness(harness)
    return harness


def _resolve_interactive_runner_type(request: Any) -> RunnerType:
    """Resolve execution mode without silently falling back for interactive agents.

    Production default (no env var, or ``interactive-first``) is now
    ``PROVIDER_CLI`` (Story 28.7).  The legacy PTY/tmux path
    ``INTERACTIVE_TUI`` is only reachable via the explicit escape hatch
    ``MC_INTERACTIVE_EXECUTION_MODE=interactive-tui``.
    """

    agent = getattr(request, "agent", None)
    interactive_provider = getattr(agent, "interactive_provider", None) if agent else None
    backend = getattr(agent, "backend", None) if agent else None
    if _acp_harness_for(interactive_provider or backend) is not None:
        return RunnerType.ACP
    is_interactive = (
        interactive_provider in {"claude-code", "codex"}
        or request.is_cc
        or backend == "claude-code"
    )
    if not is_interactive:
        return RunnerType.PROVIDER_CLI

    mode = os.environ.get(INTERACTIVE_MODE_ENV, "provider-cli").strip().lower()
    if mode in {"disabled", "off", "headless-only"}:
        raise RuntimeError(
            f"Interactive execution is disabled by {INTERACTIVE_MODE_ENV}={mode!r} for agent '{request.agent_name}'."
        )

    # Explicit legacy escape hatch: interactive-tui routes to the PTY/tmux runtime.
    # TUI should only be used for authoring sessions (create squad, etc.).
    if mode == "interactive-tui":
        logger.warning(
            "[interactive-mode] Legacy TUI escape hatch active for '%s'. "
            "TUI should only be used for authoring sessions (create squad).",
            request.agent_name,
        )
        return RunnerType.INTERACTIVE_TUI

    # All other values (provider-cli, interactive-first, or unrecognised) default
    # to PROVIDER_CLI — the new production path.
    return RunnerType.PROVIDER_CLI


def resolve_step_runner_type(request: Any) -> RunnerType:
    """Resolve the execution mode for a materialized plan step."""
    return _resolve_interactive_runner_type(request)


def resolve_task_runner_type(request: Any) -> RunnerType:
    """Resolve the execution mode for a direct task execution request."""
    return _resolve_interactive_runner_type(request)
