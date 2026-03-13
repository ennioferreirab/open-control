"""Helpers for loading interactive-capable agent metadata."""

from __future__ import annotations

from mc.application.execution.roster_builder import load_agent_data, sync_agent_from_convex
from mc.types import AgentData


def load_interactive_agent(
    agent_name: str,
    *,
    provider: str,
    bridge: object | None,
) -> AgentData | None:
    """Load agent data for interactive sessions, applying Convex overrides when available."""

    agent_data = load_agent_data(agent_name)
    convex_agent = bridge.get_agent_by_name(agent_name) if bridge else None  # type: ignore[attr-defined]

    if agent_data is None:
        if convex_agent is None:
            return None
        agent_data = AgentData(
            name=agent_name,
            display_name=convex_agent.get("display_name") or agent_name,
            role=convex_agent.get("role") or "agent",
            prompt=convex_agent.get("prompt"),
            model=convex_agent.get("model"),
            skills=convex_agent.get("skills") or [],
            backend=convex_agent.get("backend") or provider,
            interactive_provider=convex_agent.get("interactive_provider") or provider,
        )

    prompt, model, skills = sync_agent_from_convex(
        agent_name,
        agent_data.prompt,
        agent_data.model,
        agent_data.skills,
        convex_agent,
    )
    agent_data.prompt = prompt
    agent_data.model = model
    agent_data.skills = skills or []
    if convex_agent:
        agent_data.interactive_provider = convex_agent.get("interactive_provider") or provider
    else:
        agent_data.interactive_provider = provider
    return agent_data
