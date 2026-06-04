"""
Agent-assisted YAML generation for Mission Control.

Uses the LLM provider infrastructure to generate agent YAML
configurations from natural language descriptions. Validates output
with the Story 3.1 validator before presenting to the user.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from mc.infrastructure.agents.yaml_validator import AgentConfig, format_validation_errors
from mc.infrastructure.runtime_home import get_agents_dir

# ---------------------------------------------------------------------------
# LLM System Prompt
# ---------------------------------------------------------------------------

YAML_GENERATION_PROMPT = """\
You are helping create an agent configuration.
Based on the user's description, generate a valid YAML configuration file.

Required fields:
- name: lowercase, alphanumeric + hyphens (e.g., "finance-agent")
- role: brief role description (e.g., "Financial Analyst")
- prompt: detailed system prompt for the agent

Optional fields:
- skills: list of capability tags (e.g., ["financial-analysis", "boleto-tracking"])
- model: LLM model to use (omit to use system default)
- display_name: human-readable name (auto-generated from name if omitted)

Output ONLY the YAML content, no explanation. Example:

name: finance-agent
role: Financial Analyst
prompt: |
  You are a financial analyst agent specializing in personal finance management.
  You track payments, manage boletos, and provide financial summaries.
skills:
  - financial-analysis
  - boleto-tracking
  - payment-management
"""


# ---------------------------------------------------------------------------
# YAML extraction
# ---------------------------------------------------------------------------


def extract_yaml_from_response(response: str) -> str:
    """Extract YAML content from LLM response, handling code blocks."""
    match = re.search(r"```(?:yaml)?\s*\n(.*?)```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return response.strip()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_yaml_content(yaml_text: str) -> tuple[dict | None, list[str]]:
    """Parse and validate a YAML string as agent config.

    Returns:
        (parsed_dict, errors) — parsed_dict is the raw dict on success,
        errors is a list of human-readable strings on failure.
    """
    from pydantic import ValidationError

    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        return None, [f"YAML parse error: {exc}"]

    if not isinstance(data, dict):
        return None, [f"Invalid YAML structure: expected a mapping, got {type(data).__name__}."]

    try:
        AgentConfig(**data)
    except ValidationError as exc:
        return None, format_validation_errors(exc)

    return data, []


# ---------------------------------------------------------------------------
# LLM generation
# ---------------------------------------------------------------------------


async def generate_agent_yaml(
    description: str,
    feedback: str | None = None,
) -> str:
    """Generate agent YAML via the ACP utility harness.

    Args:
        description: Natural language description of the desired agent.
        feedback: Optional feedback from a previous rejected attempt.

    Returns:
        Raw LLM response text (may contain code fences).
    """
    from mc.infrastructure.acp.utility import run_utility_turn

    system = YAML_GENERATION_PROMPT
    if feedback:
        system += f"\n\nPrevious attempt was rejected. User feedback: {feedback}"

    prompt = f"{system}\n\nCreate an agent from this description: {description}"
    return await run_utility_turn(prompt, tier="medium")


# ---------------------------------------------------------------------------
# SOUL.md generation
# ---------------------------------------------------------------------------

DEFAULT_SOUL_TEMPLATE = """\
# Soul

I am {display_name}, an AI agent.

## Role
{role}

## Personality
- Helpful and focused on my area of expertise
- Concise and to the point
- Proactive in identifying relevant details

## Values
- Accuracy over speed
- Transparency in actions
- Collaboration with the team

## Communication Style
- Be clear and direct
- Explain reasoning when helpful
- Ask clarifying questions when needed
"""


def generate_soul_md(name: str, role: str, soul_override: str | None = None) -> str:
    """Generate SOUL.md content for an agent."""
    if soul_override:
        return soul_override
    display_name = name.replace("-", " ").replace("_", " ").title()
    return DEFAULT_SOUL_TEMPLATE.format(display_name=display_name, role=role)


def ensure_soul_md(agent_dir: Path, name: str, role: str, soul_override: str | None = None) -> None:
    """Write SOUL.md if it doesn't exist yet (never overwrites user edits)."""
    soul_path = agent_dir / "SOUL.md"
    if not soul_path.exists():
        soul_path.write_text(generate_soul_md(name, role, soul_override), encoding="utf-8")


# ---------------------------------------------------------------------------
# Workspace creation
# ---------------------------------------------------------------------------


def create_agent_workspace(name: str, yaml_text: str) -> Path:
    """Create the agent workspace directory and write config.yaml.

    Creates ``<agents_dir>/{name}/`` with:
      - config.yaml
      - memory/
      - skills/
      - SOUL.md

    Returns:
        Path to the written config.yaml file.
    """
    agent_dir = get_agents_dir() / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "memory").mkdir(exist_ok=True)
    (agent_dir / "skills").mkdir(exist_ok=True)

    config_path = agent_dir / "config.yaml"
    config_path.write_text(yaml_text, encoding="utf-8")

    # Generate SOUL.md from parsed YAML (role + optional soul override)
    try:
        parsed = yaml.safe_load(yaml_text)
        if isinstance(parsed, dict):
            role = parsed.get("role", "Agent")
            soul_override = parsed.get("soul")
            ensure_soul_md(agent_dir, name, role, soul_override)
    except yaml.YAMLError:
        pass  # YAML already validated upstream; skip soul on parse error

    return config_path
