"""
Shared orientation loader for Mission Control agents.

Extracts the orientation-loading logic that was duplicated in executor.py
and step_dispatcher.py into a single public function.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_orientation(agent_name: str) -> str | None:
    """Load and interpolate global orientation for non-lead agents.

    Reads ~/.nanobot/mc/agent-orientation.md, interpolates {agent_roster}
    and {host_timezone} placeholders, and returns the result.

    Returns None if:
    - agent is lead-agent
    - orientation file doesn't exist or is empty
    """
    from mc.types import is_lead_agent

    if is_lead_agent(agent_name):
        return None

    orientation_path = Path.home() / ".nanobot" / "mc" / "agent-orientation.md"
    if not orientation_path.exists():
        return None

    orientation = orientation_path.read_text(encoding="utf-8").strip()
    if not orientation:
        return None

    # Interpolate {agent_roster} placeholder if present
    if "{agent_roster}" in orientation:
        from mc.infrastructure.orientation_helpers import build_agent_roster

        orientation = orientation.replace("{agent_roster}", build_agent_roster())

    # Interpolate {host_timezone} placeholder if present
    if "{host_timezone}" in orientation:
        from mc.infrastructure.orientation_helpers import get_iana_timezone

        iana_tz = get_iana_timezone() or "UTC"
        orientation = orientation.replace("{host_timezone}", iana_tz)

    logger.info("[orientation] Global orientation loaded for agent '%s'", agent_name)
    return orientation
