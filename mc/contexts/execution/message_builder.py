"""Helpers for building executor-facing task messages."""

from __future__ import annotations


def build_task_message(title: str, description: str | None) -> str:
    """Build the task message sent to the agent."""
    if description and description.strip():
        return f"<title>{title}</title>\n<description>{description}</description>"
    return title
