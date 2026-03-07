"""Shared helpers for agent orientation interpolation."""

from __future__ import annotations

import os
from pathlib import Path

from mc.types import is_lead_agent


def get_iana_timezone() -> str | None:
    """Resolve the host IANA timezone name (for example ``America/Sao_Paulo``)."""
    try:
        resolved = str(Path("/etc/localtime").resolve())
        if "zoneinfo/" in resolved:
            return resolved.split("zoneinfo/")[-1]
    except OSError:
        pass

    tz_env = os.environ.get("TZ")
    if tz_env and "/" in tz_env:
        return tz_env.lstrip(":")
    return None


def build_agent_roster() -> str:
    """Build the human-readable roster injected into orientation templates."""
    from mc.infrastructure.config import AGENTS_DIR
    from mc.infrastructure.agents.yaml_validator import validate_agent_file

    lines: list[str] = []
    if not AGENTS_DIR.is_dir():
        return "(no other agents available)"

    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir():
            continue
        config_path = agent_dir / "config.yaml"
        if not config_path.exists():
            continue

        result = validate_agent_file(config_path)
        if isinstance(result, list):
            continue
        if getattr(result, "is_system", False) or is_lead_agent(result.name):
            continue

        skill_str = ", ".join(result.skills) if result.skills else "general"
        lines.append(f"- **{result.name}** — {result.role} (skills: {skill_str})")

    if not lines:
        return "(no other agents available)"
    return "\n".join(lines)
