"""Execution-mode resolution for interactive-capable task/step providers."""

from __future__ import annotations

import os
from typing import Any

from mc.application.execution.request import RunnerType

INTERACTIVE_MODE_ENV = "MC_INTERACTIVE_EXECUTION_MODE"


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
    is_interactive = (
        interactive_provider in {"claude-code", "codex", "mc"}
        or request.is_cc
        or backend == "claude-code"
    )
    if not is_interactive:
        return RunnerType.NANOBOT

    mode = os.environ.get(INTERACTIVE_MODE_ENV, "provider-cli").strip().lower()
    if mode in {"disabled", "off", "headless-only"}:
        raise RuntimeError(
            f"Interactive execution is disabled by {INTERACTIVE_MODE_ENV}={mode!r} for agent '{request.agent_name}'."
        )

    # Explicit legacy escape hatch: interactive-tui routes to the PTY/tmux runtime.
    if mode == "interactive-tui":
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
