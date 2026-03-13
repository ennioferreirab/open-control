"""Execution-mode resolution for interactive-capable step providers."""

from __future__ import annotations

import os
from typing import Any

from mc.application.execution.request import RunnerType

INTERACTIVE_MODE_ENV = "MC_INTERACTIVE_EXECUTION_MODE"


def resolve_step_runner_type(request: Any) -> RunnerType:
    """Resolve step execution mode without silently falling back for interactive agents."""

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

    mode = os.environ.get(INTERACTIVE_MODE_ENV, "interactive-first").strip().lower()
    if mode in {"disabled", "off", "headless-only"}:
        raise RuntimeError(
            f"Interactive execution is disabled by {INTERACTIVE_MODE_ENV}={mode!r} for agent '{request.agent_name}'."
        )

    return RunnerType.INTERACTIVE_TUI
