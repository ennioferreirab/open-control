"""
Shared orientation loader for Mission Control agents.

Extracts the orientation-loading logic that was duplicated in executor.py
and step_dispatcher.py into a single public function.
"""

from __future__ import annotations

import logging
from typing import Any

from mc.infrastructure.runtime_home import get_runtime_path

logger = logging.getLogger(__name__)

FILE_ATTACHMENT_INSTRUCTION = (
    "\n\nIMPORTANT: When user messages include <UserAttached> tags, these are files "
    "the user explicitly attached for your analysis. Read these files FIRST before "
    "proceeding with your task — they contain critical context for the request."
)


def _read_saved_orientation(bridge: Any | None) -> str | None:
    """Read the saved global orientation prompt from Convex settings."""
    if bridge is None:
        return None

    try:
        saved = bridge.query("settings:get", {"key": "global_orientation_prompt"})
    except Exception:
        logger.warning("[orientation] Failed to fetch saved global orientation", exc_info=True)
        return None

    if not isinstance(saved, str):
        return None

    saved = saved.strip()
    return saved or None


def _interpolate_orientation(orientation: str) -> str:
    """Interpolate dynamic placeholders in the orientation text."""
    # Interpolate {agent_roster} placeholder if present
    if "{agent_roster}" in orientation:
        from mc.infrastructure.orientation_helpers import build_agent_roster

        orientation = orientation.replace("{agent_roster}", build_agent_roster())

    # Interpolate {host_timezone} placeholder if present
    if "{host_timezone}" in orientation:
        from mc.infrastructure.orientation_helpers import get_iana_timezone

        iana_tz = get_iana_timezone() or "UTC"
        orientation = orientation.replace("{host_timezone}", iana_tz)

    return orientation


def load_orientation(agent_name: str, bridge: Any | None = None) -> str | None:
    """Load and interpolate global orientation for eligible MC agents.

    Precedence:
    1. Saved ``global_orientation_prompt`` from Convex settings, if non-empty
    2. ``mc/agent-orientation.md`` in the configured runtime home (fallback file)

    Returns None if:
    - agent is orchestrator-agent or nanobot
    - orientation file doesn't exist or is empty
    """
    from mc.types import NANOBOT_AGENT_NAME, is_orchestrator_agent

    if is_orchestrator_agent(agent_name) or agent_name == NANOBOT_AGENT_NAME:
        return None

    orientation = _read_saved_orientation(bridge)
    if orientation is None:
        orientation_path = get_runtime_path("mc", "agent-orientation.md")
        if not orientation_path.exists():
            return None
        orientation = orientation_path.read_text(encoding="utf-8").strip()
        if not orientation:
            return None

    orientation = _interpolate_orientation(orientation)
    # Always append — orientation is loaded once at agent startup before any
    # messages arrive, so we cannot know whether attachments will appear later.
    orientation += FILE_ATTACHMENT_INSTRUCTION
    logger.info("[orientation] Global orientation loaded for agent '%s'", agent_name)
    return orientation
