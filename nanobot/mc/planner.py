"""LLM-based task planner for intelligent agent routing.

Decomposes tasks into structured execution plans using LLM reasoning
instead of keyword-matching heuristics. Falls back to heuristic planning
on LLM failure.

Created for Story 4.5 — extracted from orchestrator.py per NFR21
(500-line module limit).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from nanobot.mc.types import (
    AgentData,
    ExecutionPlan,
    ExecutionPlanStep,
    LEAD_AGENT_NAME,
)

logger = logging.getLogger(__name__)

LLM_TIMEOUT_SECONDS = 30

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "and", "or", "but", "not", "this", "that", "it", "my", "your",
}

SYSTEM_PROMPT = """\
You are a task planning assistant for a multi-agent system. Your job is to:
1. Decompose a task into one or more execution steps
2. Assign each step to the most appropriate agent based on their skills
3. Identify dependencies between steps (which steps must complete before others can start)

You MUST respond with valid JSON only, no markdown, no explanation.

Response format:
{
  "steps": [
    {
      "step_id": "step_1",
      "description": "Clear description of what this step does",
      "assigned_agent": "agent-name",
      "depends_on": []
    }
  ]
}

Rules:
- step_id must be "step_1", "step_2", etc.
- assigned_agent must be one of the agent names listed below, or "lead-agent" if no specialist fits
- depends_on is a list of step_ids that must complete before this step can start
- For simple tasks, a single step is fine
- Only create multiple steps if the task genuinely has distinct phases"""

USER_PROMPT_TEMPLATE = """\
Task: {title}
Description: {description}

Available agents:
{agent_roster}

Create an execution plan for this task."""


def extract_keywords(title: str, description: str | None = None) -> list[str]:
    """Extract meaningful keywords from task text.

    Tokenizes on non-alphanumeric characters, removes stopwords and
    tokens shorter than 3 characters.
    """
    text = title.lower()
    if description:
        text += " " + description.lower()
    tokens = re.split(r"[^a-z0-9]+", text)
    return [t for t in tokens if t and len(t) > 2 and t not in STOPWORDS]


def score_agent(agent: AgentData, keywords: list[str]) -> float:
    """Score an agent based on skill tag overlap with task keywords.

    Exact matches score 1.0 per keyword. Partial matches (keyword
    contained in skill or vice versa) score 0.5 each.
    """
    if not agent.skills or not keywords:
        return 0.0
    agent_skills_lower = {s.lower() for s in agent.skills}
    score = 0.0
    for kw in keywords:
        if kw in agent_skills_lower:
            score += 1.0
            continue
        for skill in agent_skills_lower:
            if kw in skill or skill in kw:
                score += 0.5
                break
    return score


def _build_file_summary(files: list[dict]) -> str:
    """Build a human-readable file summary for lead agent context."""
    if not files:
        return ""

    def _human_size(b: int) -> str:
        return f"{b // 1024} KB" if b < 1_048_576 else f"{b / 1_048_576:.1f} MB"

    total = sum(f.get("size", 0) for f in files)
    names = ", ".join(
        f"{f['name']} ({_human_size(f.get('size', 0))})" for f in files
    )
    return (
        f"Task has {len(files)} attached file(s) (total {_human_size(total)}): {names}. "
        f"Consider file types when selecting the best agent."
    )


def _build_agent_roster(agents: list[AgentData]) -> str:
    """Build the agent roster string for the LLM prompt."""
    lines = []
    for agent in agents:
        skills_str = ", ".join(agent.skills) if agent.skills else "general"
        lines.append(f"- {agent.name} (role: {agent.role}, skills: {skills_str})")
    if not lines:
        lines.append("- lead-agent (role: coordinator, skills: general)")
    return "\n".join(lines)


def _parse_plan_response(raw: str) -> ExecutionPlan:
    """Parse LLM response into ExecutionPlan, handling markdown fencing."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)

    data = json.loads(text)

    if "steps" not in data or not data["steps"]:
        raise ValueError("LLM response missing 'steps' key or empty steps")

    steps = []
    for s in data["steps"]:
        steps.append(ExecutionPlanStep(
            step_id=s.get("step_id", f"step_{len(steps) + 1}"),
            description=s.get("description", ""),
            assigned_agent=s.get("assigned_agent"),
            depends_on=s.get("depends_on", []),
        ))

    return ExecutionPlan(steps=steps)


class TaskPlanner:
    """Plans task execution using LLM reasoning."""

    async def plan_task(
        self,
        title: str,
        description: str | None,
        agents: list[AgentData],
        explicit_agent: str | None = None,
        files: list[dict] | None = None,
    ) -> ExecutionPlan:
        """Create an execution plan for a task.

        If explicit_agent is set, all steps are assigned to that agent.
        On LLM failure, falls back to heuristic planning.
        """
        try:
            plan = await self._llm_plan(title, description, agents, files=files)
            self._validate_agent_names(plan, agents)
            if explicit_agent:
                self._override_agents(plan, explicit_agent)
            return plan
        except Exception as exc:
            logger.warning(
                "[planner] LLM planning failed, using heuristic fallback: %s", exc
            )
            return self._fallback_heuristic_plan(
                title, description, agents, explicit_agent
            )

    async def _llm_plan(
        self,
        title: str,
        description: str | None,
        agents: list[AgentData],
        files: list[dict] | None = None,
    ) -> ExecutionPlan:
        """Call LLM to generate the plan."""
        from nanobot.mc.provider_factory import create_provider

        agent_roster = _build_agent_roster(agents)
        user_prompt = USER_PROMPT_TEMPLATE.format(
            title=title,
            description=description or "No description provided",
            agent_roster=agent_roster,
        )
        file_summary = _build_file_summary(files or [])
        if file_summary:
            user_prompt = user_prompt + "\n\n" + file_summary

        provider, model = create_provider()
        response = await asyncio.wait_for(
            asyncio.to_thread(
                provider.chat,
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )

        return _parse_plan_response(response)

    def _validate_agent_names(
        self, plan: ExecutionPlan, agents: list[AgentData]
    ) -> None:
        """Replace invalid agent names with lead-agent."""
        valid_names = {a.name for a in agents} | {LEAD_AGENT_NAME}
        for step in plan.steps:
            if not step.assigned_agent or step.assigned_agent not in valid_names:
                if step.assigned_agent:
                    logger.warning(
                        "[planner] Invalid agent '%s', replacing with lead-agent",
                        step.assigned_agent,
                    )
                step.assigned_agent = LEAD_AGENT_NAME

    def _override_agents(self, plan: ExecutionPlan, agent_name: str) -> None:
        """Override all step assignments with an explicit agent."""
        for step in plan.steps:
            step.assigned_agent = agent_name

    def _fallback_heuristic_plan(
        self,
        title: str,
        description: str | None,
        agents: list[AgentData],
        explicit_agent: str | None,
    ) -> ExecutionPlan:
        """Heuristic fallback using keyword-based score_agent logic."""
        if explicit_agent:
            return ExecutionPlan(steps=[
                ExecutionPlanStep(
                    step_id="step_1",
                    description=title,
                    assigned_agent=explicit_agent,
                )
            ])

        keywords = extract_keywords(title, description)
        scored = [(agent, score_agent(agent, keywords)) for agent in agents]
        scored.sort(key=lambda x: x[1], reverse=True)

        assigned = (
            scored[0][0].name
            if scored and scored[0][1] > 0
            else LEAD_AGENT_NAME
        )

        return ExecutionPlan(steps=[
            ExecutionPlanStep(
                step_id="step_1",
                description=title,
                assigned_agent=assigned,
            )
        ])
