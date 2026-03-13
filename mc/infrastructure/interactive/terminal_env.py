"""Helpers for interactive terminal environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping


def build_interactive_terminal_env(
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return an environment suitable for full-screen interactive TUIs."""

    env = dict(base_env or os.environ)
    env["TERM"] = "xterm-256color"
    if not env.get("COLORTERM"):
        env["COLORTERM"] = "truecolor"
    return env
