"""Execution-mode resolution for interactive-capable task/step providers."""

from __future__ import annotations

import logging
import os
from typing import Any

from mc.application.execution.request import RunnerType

logger = logging.getLogger(__name__)

INTERACTIVE_MODE_ENV = "MC_INTERACTIVE_EXECUTION_MODE"


def _resolve_interactive_runner_type(request: Any) -> RunnerType:
    """Resolve execution mode without silently falling back for interactive agents.

    Claude Code now runs through ACP by default (Phase 6). Codex stays on
    PROVIDER_CLI until it too moves to ACP. The legacy PTY/tmux path
    INTERACTIVE_TUI is reachable only via the explicit escape hatch
    MC_INTERACTIVE_EXECUTION_MODE=interactive-tui, for authoring sessions.
    """
    agent = getattr(request, "agent", None)
    interactive_provider = getattr(agent, "interactive_provider", None) if agent else None
    backend = getattr(agent, "backend", None) if agent else None

    # interactive_provider names the provider authoritatively: codex and mc stay
    # on PROVIDER_CLI even when backend defaults to "claude-code".
    if interactive_provider in {"codex", "mc"}:
        return RunnerType.PROVIDER_CLI

    is_claude_code = (
        interactive_provider == "claude-code" or request.is_cc or backend == "claude-code"
    )
    if not is_claude_code:
        return RunnerType.PROVIDER_CLI

    mode = os.environ.get(INTERACTIVE_MODE_ENV, "provider-cli").strip().lower()
    if mode in {"disabled", "off", "headless-only"}:
        raise RuntimeError(
            f"Interactive execution is disabled by {INTERACTIVE_MODE_ENV}={mode!r} for agent '{request.agent_name}'."
        )
    if mode == "interactive-tui":
        logger.warning(
            "[interactive-mode] Legacy TUI escape hatch active for '%s'. "
            "TUI should only be used for authoring sessions (create squad).",
            request.agent_name,
        )
        return RunnerType.INTERACTIVE_TUI

    return RunnerType.ACP


def resolve_step_runner_type(request: Any) -> RunnerType:
    """Resolve the execution mode for a materialized plan step."""
    return _resolve_interactive_runner_type(request)


def resolve_task_runner_type(request: Any) -> RunnerType:
    """Resolve the execution mode for a direct task execution request."""
    return _resolve_interactive_runner_type(request)
