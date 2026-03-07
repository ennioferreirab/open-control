"""
Init Wizard — business logic for `nanobot mc init`.

Pure functions and data structures for the guided agent setup wizard.
No CLI interaction, no I/O — all user-facing prompts live in ``mc.cli``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from mc.cli.agent_assist import (
    build_llm_provider,
    create_agent_workspace,
    extract_yaml_from_response,
    generate_agent_yaml,
    validate_yaml_content,
)
from mc.infrastructure.agents.yaml_validator import validate_agent_file

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENTS_DIR = Path.home() / ".nanobot" / "agents"

LEAD_AGENT_CONFIG: dict = {
    "name": "lead-agent",
    "role": "Lead Agent — Orchestrator",
    "prompt": (
        "You are the lead agent for Mission Control. "
        "You receive incoming tasks, match them to the best available agent "
        "based on skills and availability, create execution plans, and "
        "coordinate multi-agent workflows. You escalate to the human operator "
        "when confidence is low or approval is required."
    ),
    # Planning/orchestration-only skills (no execution capabilities).
    "skills": [
        "task-routing",
        "execution-planning",
        "agent-coordination",
        "escalation",
    ],
}


# ---------------------------------------------------------------------------
# Preset templates
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentPreset:
    """Immutable template for a preset agent."""

    name: str
    role: str
    prompt: str
    skills: list[str] = field(default_factory=list)


PRESETS: list[AgentPreset] = [
    AgentPreset(
        name="developer",
        role="Software Developer",
        prompt=(
            "You are a software developer agent. You write, review, and "
            "debug code across multiple languages and frameworks. You follow "
            "best practices, write tests, and document your work."
        ),
        skills=["coding", "debugging", "code-review", "testing"],
    ),
    AgentPreset(
        name="researcher",
        role="Research Analyst",
        prompt=(
            "You are a research analyst agent. You gather information from "
            "provided sources, synthesize findings into clear summaries, and "
            "identify key insights and action items."
        ),
        skills=["research", "summarization", "analysis"],
    ),
    AgentPreset(
        name="writer",
        role="Technical Writer",
        prompt=(
            "You are a technical writer agent. You create documentation, "
            "blog posts, README files, and user guides. You adapt tone and "
            "detail level to the target audience."
        ),
        skills=["writing", "documentation", "editing"],
    ),
    AgentPreset(
        name="data-analyst",
        role="Data Analyst",
        prompt=(
            "You are a data analyst agent. You explore datasets, run "
            "statistical analyses, build visualizations, and translate data "
            "findings into business recommendations."
        ),
        skills=["data-analysis", "visualization", "statistics"],
    ),
    AgentPreset(
        name="devops",
        role="DevOps Engineer",
        prompt=(
            "You are a DevOps engineer agent. You manage CI/CD pipelines, "
            "container orchestration, infrastructure-as-code, and monitoring. "
            "You prioritize reliability and security."
        ),
        skills=["ci-cd", "docker", "infrastructure", "monitoring"],
    ),
]


# ---------------------------------------------------------------------------
# Planning data structures
# ---------------------------------------------------------------------------

@dataclass
class AgentPlan:
    """One agent to be created (or skipped) during the wizard."""

    name: str
    role: str
    yaml_text: str
    source: str  # "lead", "preset", or "custom"
    skip: bool = False
    skip_reason: str = ""


@dataclass
class CreationResult:
    """Outcome of creating a single agent."""

    name: str
    success: bool
    path: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Existence checks
# ---------------------------------------------------------------------------

def agent_exists(name: str) -> bool:
    """Return True if ``~/.nanobot/agents/<name>/config.yaml`` exists."""
    return (AGENTS_DIR / name / "config.yaml").is_file()


def lead_agent_exists() -> bool:
    """Return True if the lead-agent is already configured."""
    return agent_exists("lead-agent")


# ---------------------------------------------------------------------------
# YAML builders
# ---------------------------------------------------------------------------

def build_lead_agent_yaml() -> str:
    """Return the YAML string for the lead-agent preset."""
    return yaml.dump(LEAD_AGENT_CONFIG, default_flow_style=False, sort_keys=False)


def build_preset_yaml(preset: AgentPreset) -> str:
    """Return a YAML string from an ``AgentPreset``."""
    data = {
        "name": preset.name,
        "role": preset.role,
        "prompt": preset.prompt,
        "skills": list(preset.skills),
    }
    return yaml.dump(data, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# Custom agent generation (async, uses LLM)
# ---------------------------------------------------------------------------

async def generate_custom_agent(description: str) -> tuple[str | None, list[str]]:
    """Generate agent YAML from a natural language description.

    Returns:
        ``(yaml_text, errors)`` — yaml_text is the validated YAML string on
        success, errors is a list of human-readable strings on failure.
    """
    provider = build_llm_provider()
    raw = await generate_agent_yaml(provider, description)
    if not raw.strip():
        return None, ["LLM returned an empty response."]

    yaml_text = extract_yaml_from_response(raw)
    parsed, errors = validate_yaml_content(yaml_text)
    if errors:
        return None, errors

    return yaml_text, []


# ---------------------------------------------------------------------------
# Batch creation
# ---------------------------------------------------------------------------

def create_agents(plans: list[AgentPlan]) -> list[CreationResult]:
    """Create agents from a list of plans, skipping those marked to skip.

    Each agent is independent — partial success is acceptable.
    """
    results: list[CreationResult] = []

    for plan in plans:
        if plan.skip:
            results.append(CreationResult(
                name=plan.name,
                success=True,
                error=f"skipped: {plan.skip_reason}",
            ))
            continue

        try:
            config_path = create_agent_workspace(plan.name, plan.yaml_text)

            # Post-write validation
            validation = validate_agent_file(config_path)
            if isinstance(validation, list):
                results.append(CreationResult(
                    name=plan.name,
                    success=False,
                    error="; ".join(validation),
                ))
                continue

            results.append(CreationResult(
                name=plan.name,
                success=True,
                path=str(config_path),
            ))
        except Exception as exc:
            results.append(CreationResult(
                name=plan.name,
                success=False,
                error=str(exc),
            ))

    return results
