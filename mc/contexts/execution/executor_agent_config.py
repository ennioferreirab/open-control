"""Executor support helpers for agent config and orientation."""

from __future__ import annotations

import logging

from mc.types import AgentData

logger = logging.getLogger(__name__)


def get_iana_timezone() -> str | None:
    """Resolve IANA timezone name from system (e.g. 'America/Vancouver')."""
    from mc.infrastructure.orientation_helpers import get_iana_timezone as _get_iana_timezone

    return _get_iana_timezone()


def build_executor_agent_roster() -> str:
    """Build a roster of available agents for executor orientation."""
    from mc.infrastructure.orientation_helpers import build_agent_roster

    return build_agent_roster()


def load_agent_config(agent_name: str) -> tuple[str | None, str | None, list[str] | None]:
    """Load prompt, model, and skills from the agent's YAML config file."""
    from mc.infrastructure.agents.yaml_validator import validate_agent_file
    from mc.infrastructure.config import AGENTS_DIR

    config_file = AGENTS_DIR / agent_name / "config.yaml"
    if not config_file.exists():
        return None, None, None

    result = validate_agent_file(config_file)
    if isinstance(result, list):
        logger.warning("[executor] Agent '%s' config invalid: %s", agent_name, result)
        return None, None, None

    return result.prompt, result.model, result.skills


def load_agent_data(agent_name: str) -> AgentData | None:
    """Load validated AgentData from YAML config."""
    from mc.infrastructure.agents.yaml_validator import validate_agent_file
    from mc.infrastructure.config import AGENTS_DIR

    config_path = AGENTS_DIR / agent_name / "config.yaml"
    if not config_path.exists():
        return None
    result = validate_agent_file(config_path)
    return result if isinstance(result, AgentData) else None


def render_agent_roster() -> str:
    """Build a markdown roster of all available agents from AGENTS_DIR."""
    from mc.infrastructure.agents.yaml_validator import validate_agent_file
    from mc.infrastructure.config import AGENTS_DIR

    lines: list[str] = ["## Available Agents\n"]
    if not AGENTS_DIR.is_dir():
        return ""
    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir():
            continue
        config_path = agent_dir / "config.yaml"
        if not config_path.exists():
            continue
        result = validate_agent_file(config_path)
        if isinstance(result, list):
            continue
        skill_str = ", ".join(result.skills) if result.skills else "—"
        line = f"- `{result.name}` ({result.display_name}) — {result.role}"
        line += f"\n  Skills: {skill_str}"
        lines.append(line)
    return "\n".join(lines)


def maybe_inject_orientation(agent_name: str, agent_prompt: str | None) -> str | None:
    """Prepend global orientation for non-lead-agent MC agents."""
    from mc.infrastructure.orientation import load_orientation

    orientation = load_orientation(agent_name)
    if not orientation:
        return agent_prompt

    logger.info("[executor] Global orientation injected for agent '%s'", agent_name)
    if agent_prompt:
        return f"{orientation}\n\n---\n\n{agent_prompt}"
    return orientation
