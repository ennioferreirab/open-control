"""Runtime home compatibility helpers."""

from __future__ import annotations

import os
from pathlib import Path

OPEN_CONTROL_HOME_ENV = "OPEN_CONTROL_HOME"
NANOBOT_HOME_ENV = "NANOBOT_HOME"
LEGACY_RUNTIME_HOME = ".nanobot"


def get_runtime_home() -> Path:
    """Return the configured runtime home with Open Control compatibility."""
    for env_name in (OPEN_CONTROL_HOME_ENV, NANOBOT_HOME_ENV):
        configured = os.environ.get(env_name)
        if configured:
            return Path(configured).expanduser()
    return Path.home() / LEGACY_RUNTIME_HOME


def get_runtime_path(*parts: str) -> Path:
    """Return a path rooted at the configured runtime home."""
    return get_runtime_home().joinpath(*parts)


def get_agents_dir() -> Path:
    """Return the agents directory."""
    return get_runtime_path("agents")


def get_boards_dir() -> Path:
    """Return the boards directory."""
    return get_runtime_path("boards")


def get_tasks_dir() -> Path:
    """Return the tasks directory."""
    return get_runtime_path("tasks")


def get_workspace_dir() -> Path:
    """Return the shared workspace directory."""
    return get_runtime_path("workspace")


def get_config_path() -> Path:
    """Return the provider config path."""
    return get_runtime_path("config.json")


def get_secrets_path() -> Path:
    """Return the secrets file path."""
    return get_runtime_path("secrets.json")
