"""Agent roster and capability enrichment.

Extracts the duplicated agent config loading and Convex sync logic
from executor.py and step_dispatcher.py into a shared module.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mc.types import (
    AgentData,
    is_lead_agent,
    is_tier_reference,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def load_agent_config(
    agent_name: str,
) -> tuple[str | None, str | None, list[str] | None]:
    """Load prompt, model, and skills from the agent's YAML config file.

    Returns:
        Tuple of (prompt, model, skills). prompt/model may be None if not
        configured; skills is None when no config exists.
    """
    from mc.gateway import AGENTS_DIR
    from mc.yaml_validator import validate_agent_file

    config_file = AGENTS_DIR / agent_name / "config.yaml"
    if not config_file.exists():
        return None, None, None

    result = validate_agent_file(config_file)
    if isinstance(result, list):
        logger.warning(
            "[roster] Agent '%s' config invalid: %s", agent_name, result
        )
        return None, None, None

    return result.prompt, result.model, result.skills


def load_agent_data(agent_name: str) -> AgentData | None:
    """Load full AgentData from an agent's YAML config file.

    Returns the validated AgentData or None when the config file does
    not exist or fails validation.
    """
    from mc.gateway import AGENTS_DIR
    from mc.yaml_validator import validate_agent_file

    config_path = AGENTS_DIR / agent_name / "config.yaml"
    if not config_path.exists():
        return None
    result = validate_agent_file(config_path)
    return result if isinstance(result, AgentData) else None


def sync_agent_from_convex(
    agent_name: str,
    agent_prompt: str | None,
    agent_model: str | None,
    agent_skills: list[str] | None,
    convex_agent: dict[str, Any] | None,
) -> tuple[str | None, str | None, list[str] | None]:
    """Sync agent config from Convex (source of truth) over YAML values.

    Applies prompt, variables, model, and skills overrides from Convex
    agent data. Returns updated (prompt, model, skills).
    """
    if not convex_agent:
        return agent_prompt, agent_model, agent_skills

    # Sync prompt
    convex_prompt = convex_agent.get("prompt")
    if convex_prompt:
        agent_prompt = convex_prompt
        logger.info(
            "[roster] Convex prompt for '%s': len=%d",
            agent_name,
            len(convex_prompt),
        )

    # Interpolate {{var_name}} placeholders from Convex variables
    variables = convex_agent.get("variables") or []
    if variables and agent_prompt:
        for var in variables:
            placeholder = "{{" + var["name"] + "}}"
            agent_prompt = agent_prompt.replace(placeholder, var["value"])
        logger.info(
            "[roster] Interpolated %d variable(s) for '%s'",
            len(variables), agent_name,
        )

    # Sync model
    if convex_agent.get("model"):
        convex_model = convex_agent["model"]
        if convex_model != agent_model:
            logger.info(
                "[roster] Model synced from Convex for '%s': %s -> %s",
                agent_name, agent_model, convex_model,
            )
        agent_model = convex_model

    # Sync skills
    convex_skills = convex_agent.get("skills")
    if convex_skills is not None:
        if convex_skills != agent_skills:
            logger.info(
                "[roster] Skills synced from Convex for '%s': %s -> %s",
                agent_name, agent_skills, convex_skills,
            )
        agent_skills = convex_skills

    return agent_prompt, agent_model, agent_skills


def inject_orientation(
    agent_name: str, agent_prompt: str | None
) -> str | None:
    """Prepend global orientation for non-lead agents.

    Returns the prompt with orientation prepended, or None if
    the agent is a system agent (nanobot) which uses SOUL.md.
    """
    from mc.orientation import load_orientation

    orientation = load_orientation(agent_name)
    if not orientation:
        return agent_prompt

    if agent_prompt:
        return f"{orientation}\n\n---\n\n{agent_prompt}"
    return orientation


def resolve_tier(
    agent_model: str | None,
    tier_resolver: Any,
) -> tuple[str | None, str | None]:
    """Resolve tier references to concrete model + reasoning level.

    Args:
        agent_model: Model string, potentially a tier reference.
        tier_resolver: TierResolver instance.

    Returns:
        Tuple of (resolved_model, reasoning_level). reasoning_level is
        None if no tier reference or if reasoning is not configured.

    Raises:
        ValueError: If tier resolution fails.
    """
    reasoning_level: str | None = None
    if agent_model and is_tier_reference(agent_model):
        tier_ref = agent_model
        agent_model = tier_resolver.resolve_model(agent_model)
        logger.info("[roster] Resolved tier: %s -> %s", tier_ref, agent_model)
        reasoning_level = tier_resolver.resolve_reasoning_level(tier_ref)
        if reasoning_level:
            logger.info("[roster] Reasoning level: %s", reasoning_level)
    return agent_model, reasoning_level


def build_agent_roster() -> str:
    """Build a markdown roster of all available agents.

    Reads ~/.nanobot/agents/ config files. Excludes system agents
    and lead-agent.
    """
    from mc.gateway import AGENTS_DIR
    from mc.yaml_validator import validate_agent_file

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
        if getattr(result, "is_system", False) or is_lead_agent(result.name):
            continue
        skill_str = ", ".join(result.skills) if result.skills else "—"
        line = f"- `{result.name}` ({result.display_name}) — {result.role}"
        line += f"\n  Skills: {skill_str}"
        lines.append(line)
    return "\n".join(lines)
