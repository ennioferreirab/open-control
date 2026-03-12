"""Session key helpers for execution runners."""

from __future__ import annotations


def build_agent_session_key(
    agent_name: str,
    task_id: str | None = None,
    board_name: str | None = None,
) -> str:
    """Build the stable session key used by executor agent loops."""
    if board_name:
        prefix = f"mc:board:{board_name}:task:{agent_name}"
    else:
        prefix = f"mc:task:{agent_name}"
    if task_id:
        return f"{prefix}:{task_id}"
    return prefix
