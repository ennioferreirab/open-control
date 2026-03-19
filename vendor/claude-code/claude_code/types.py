"""CC-specific types for the Claude Code backend."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CC_MODEL_PREFIX = "cc/"

CC_AVAILABLE_MODELS: list[str] = [
    "cc/claude-sonnet-4-6",
    "cc/claude-opus-4-6",
    "cc/claude-haiku-4-5",
]


def is_cc_model(model: str | None) -> bool:
    """Return True if model is a cc/ reference (routes to Claude Code backend)."""
    return model is not None and model.startswith(CC_MODEL_PREFIX)


def extract_cc_model_name(model: str) -> str:
    """Strip the cc/ prefix to get the bare model name."""
    return model[len(CC_MODEL_PREFIX):]


@dataclass
class ClaudeCodeOpts:
    """Options for agents using the claude-code backend."""
    max_budget_usd: float | None = None
    max_turns: int | None = None
    permission_mode: str = "acceptEdits"
    allowed_tools: list[str] | None = None
    disallowed_tools: list[str] | None = None
    effort_level: str | None = None


@dataclass
class WorkspaceContext:
    """Context for a Claude Code agent workspace, returned by CCWorkspaceManager.prepare()."""
    cwd: Path
    mcp_config: Path
    claude_md: Path
    socket_path: str


@dataclass
class CCTaskResult:
    """Result returned by ClaudeCodeProvider.execute_task()."""
    output: str       # final result text from the CLI
    session_id: str   # CC session ID for resume
    cost_usd: float   # total cost from result message
    usage: dict       # {input_tokens, output_tokens, ...}
    is_error: bool    # True if result.is_error or non-zero exit
    error_type: str = ""       # e.g. "invalid_request_error", "overloaded_error"
    error_message: str = ""    # detailed error message from API
