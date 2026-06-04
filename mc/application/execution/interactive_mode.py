"""Execution-mode resolution for interactive-capable task/step providers."""

from __future__ import annotations

import logging
import os
from typing import Any

from mc.application.execution.request import RunnerType
from mc.infrastructure.acp.harness_registry import is_registered_harness

logger = logging.getLogger(__name__)

INTERACTIVE_MODE_ENV = "MC_INTERACTIVE_EXECUTION_MODE"


def _resolve_harness(request: Any) -> str | None:
    """Resolve the ACP harness backend for *request*, or None when it has none.

    interactive_provider names the harness authoritatively when set; is_cc is
    the legacy claude-code signal; otherwise agent.backend is the selector.
    """
    agent = getattr(request, "agent", None)
    interactive_provider = getattr(agent, "interactive_provider", None) if agent else None
    backend = getattr(agent, "backend", None) if agent else None

    if interactive_provider in {"claude-code", "codex"}:
        return interactive_provider
    if getattr(request, "is_cc", False):
        return "claude-code"
    return backend


def _resolve_interactive_runner_type(request: Any) -> RunnerType:
    """Resolve execution mode without silently falling back for interactive agents.

    Any agent whose backend names a registered ACP harness (claude-code, codex)
    runs through ACP. The homegrown "mc" provider and unknown backends stay on
    PROVIDER_CLI. The legacy PTY/tmux path INTERACTIVE_TUI is reachable only via
    the explicit escape hatch MC_INTERACTIVE_EXECUTION_MODE=interactive-tui, and
    only for claude-code authoring sessions.
    """
    agent = getattr(request, "agent", None)
    if getattr(agent, "interactive_provider", None) == "mc":
        return RunnerType.PROVIDER_CLI

    harness = _resolve_harness(request)
    if not is_registered_harness(harness):
        return RunnerType.PROVIDER_CLI

    mode = os.environ.get(INTERACTIVE_MODE_ENV, "provider-cli").strip().lower()
    if mode in {"disabled", "off", "headless-only"}:
        raise RuntimeError(
            f"Interactive execution is disabled by {INTERACTIVE_MODE_ENV}={mode!r} for agent '{request.agent_name}'."
        )
    if mode == "interactive-tui" and harness == "claude-code":
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
